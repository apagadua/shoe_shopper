import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  Dimensions,
  Platform,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import * as SecureStore from 'expo-secure-store';
import { Accelerometer, LightSensor } from 'expo-sensors';
import { API_BASE_URL } from '../config/api';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const FRAME_PADDING = 32;
const FRAME_SCALE = 0.72;
const FRAME_BASE_WIDTH = SCREEN_WIDTH - FRAME_PADDING * 2;
// Portrait frame: paper vertical, foot in center
const FRAME_ASPECT = 3 / 4; // width / height
const FRAME_WIDTH = FRAME_BASE_WIDTH * FRAME_SCALE;
const FRAME_HEIGHT = (FRAME_BASE_WIDTH / FRAME_ASPECT) * FRAME_SCALE;

const TILT_OK_DEGREES = 10;
const LIGHT_MIN_LUX = 50; // simple threshold for "too dark" on Android

export default function CameraScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding ?? false;

  const cameraRef = useRef(null);
  const [permission, requestPermission] = useCameraPermissions();

  const [phase, setPhase] = useState('camera'); // 'camera' | 'preview' | 'processing'
  const [capturedUri, setCapturedUri] = useState(null);
  const [error, setError] = useState(null);

  const [paperSize, setPaperSize] = useState('letter'); // 'letter' | 'a4'

  const [tiltDegrees, setTiltDegrees] = useState(null);
  const [isAligned, setIsAligned] = useState(false);

  const [lightLevel, setLightLevel] = useState(null);
  const [lightOk, setLightOk] = useState(true);
  const [lightAvailable, setLightAvailable] = useState(false);

  // Tilt guidance while camera is open
  useEffect(() => {
    let sub;
    if (phase === 'camera') {
      Accelerometer.setUpdateInterval(200);
      sub = Accelerometer.addListener(({ x, y, z }) => {
        const mag = Math.sqrt(x * x + y * y + z * z) || 1;
        const nz = z / mag;
        const clamped = Math.max(-1, Math.min(1, nz));
        const angleRad = Math.acos(Math.abs(clamped));
        const angleDeg = (angleRad * 180) / Math.PI;
        const rounded = Math.round(angleDeg);
        setTiltDegrees(rounded);
        setIsAligned(rounded <= TILT_OK_DEGREES);
      });
    }
    return () => {
      sub?.remove();
    };
  }, [phase]);

  // Light guidance (Android only) while camera is open
  useEffect(() => {
    let sub;
    let mounted = true;

    if (phase === 'camera' && Platform.OS === 'android') {
      (async () => {
        try {
          const available = await LightSensor.isAvailableAsync();
          if (!mounted) return;
          if (!available) {
            setLightAvailable(false);
            return;
          }
          setLightAvailable(true);
          sub = LightSensor.addListener(({ illuminance }) => {
            setLightLevel(illuminance);
            setLightOk(illuminance == null || illuminance >= LIGHT_MIN_LUX);
          });
        } catch {
          setLightAvailable(false);
        }
      })();
    }

    return () => {
      mounted = false;
      sub?.remove();
    };
  }, [phase]);

  const handleTakePhoto = async () => {
    if (!cameraRef.current) return;
    setError(null);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.9 });
      setCapturedUri(photo.uri);
      setPhase('preview');
    } catch (e) {
      setError(e.message || 'Could not take photo.');
    }
  };

  const handleUsePhoto = async () => {
    setPhase('processing');
    setError(null);
    try {
      const formData = new FormData();
      const filename = capturedUri.split('/').pop();
      const ext = filename?.split('.').pop()?.toLowerCase() ?? 'jpg';
      const mimeType = ext === 'png' ? 'image/png' : 'image/jpeg';
      formData.append('image', { uri: capturedUri, name: filename, type: mimeType });
      formData.append('paper_size', paperSize);

      const token = await SecureStore.getItemAsync('authToken');
      const response = await fetch(`${API_BASE_URL}/api/foot/measure/`, {
        method: 'POST',
        headers: { Authorization: `Token ${token}` },
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Measurement failed');
      }

      navigation.navigate('Measurements', { fromOnboarding, measurements: data });
    } catch (e) {
      setError(e.message || 'Could not process photo. Please try again.');
      setPhase('preview');
    }
  };

  const handleRetake = () => {
    setCapturedUri(null);
    setError(null);
    setPhase('camera');
  };

  const handlePickFromGallery = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.9,
    });
    if (!result.canceled && result.assets?.length > 0) {
      setCapturedUri(result.assets[0].uri);
      setPhase('preview');
    }
  };

  if (!permission) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.permissionTitle}>Allow camera access</Text>
        <Text style={styles.permissionText}>
          We need access to your camera so you can capture your foot on the paper.
        </Text>
        <TouchableOpacity style={styles.primaryButton} onPress={requestPermission}>
          <Text style={styles.primaryButtonText}>Enable camera</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (phase === 'processing') {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
        <Text style={styles.loadingText}>Processing…</Text>
      </View>
    );
  }

  const tiltLabel = tiltDegrees == null ? 'Tilt: —' : `Tilt: ${tiltDegrees}°`;
  const tiltStatus = isAligned ? 'Aligned' : 'Hold phone flatter';
  const tiltStatusColor = isAligned ? '#2E7D32' : '#B33';

  const canUseLight = Platform.OS === 'android' && lightAvailable;
  let lightStatus = 'Check that foot and paper are clear';
  let lightStatusColor = '#F5EFE6';
  if (canUseLight) {
    if (!lightOk) {
      lightStatus = 'Too dark – move to brighter light';
      lightStatusColor = '#FFCDD2';
    } else {
      lightStatus = 'Lighting OK';
      lightStatusColor = '#C8E6C9';
    }
  }

  const canCapture = isAligned; // always gate on tilt; lighting is guidance only

  // Preview / confirmation
  if (phase === 'preview' && capturedUri) {
    return (
      <View style={styles.previewContainer}>
        <Text style={styles.previewTitle}>Check your photo</Text>
        <Text style={styles.previewSubtitle}>
          Make sure the paper is vertical, your foot is in the center, and both are clearly visible.
        </Text>
        <View style={styles.previewFrame}>
          <Image source={{ uri: capturedUri }} style={styles.previewImage} resizeMode="contain" />
        </View>
        <TouchableOpacity style={styles.primaryButton} onPress={handleUsePhoto}>
          <Text style={styles.primaryButtonText}>Use this photo</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryButton} onPress={handleRetake}>
          <Text style={styles.secondaryButtonText}>Retake</Text>
        </TouchableOpacity>
        {error ? <Text style={styles.previewErrorText}>{error}</Text> : null}
      </View>
    );
  }

  // Main camera with overlays
  return (
    <View style={styles.cameraScreen}>
      <CameraView
        ref={cameraRef}
        style={styles.camera}
        facing="back"
      />
      <View style={styles.overlay}>
        <View style={styles.topGuidance}>
          <View style={styles.whiteHeader}>
            <View style={styles.whiteHeaderRow}>
              <View style={styles.whiteHeaderColumnLeft}>
                <Text style={styles.whiteHeaderLabel}>Distance</Text>
                <Text style={styles.whiteHeaderValue}>
                Knee height above the paper.
                </Text>
              </View>
              <View style={styles.whiteHeaderVerticalDivider} />
              <View style={styles.whiteHeaderColumnRight}>
                <Text style={styles.whiteHeaderLabel}>Lighting</Text>
              <Text style={styles.whiteHeaderValue}>{lightStatus}</Text>
              </View>
            </View>
            <View style={styles.whiteHeaderDivider} />
            <View style={styles.whiteHeaderTiltRow}>
              <Text
                style={[
                  styles.whiteHeaderValue,
                  styles.whiteHeaderTiltText,
                  { color: tiltStatusColor },
                ]}
              >
                {tiltLabel} · {tiltStatus}
              </Text>
            </View>
            <View style={styles.whiteHeaderDivider} />
            <View style={styles.whiteHeaderPaperRow}>
              <Text style={styles.whiteHeaderLabel}>Paper</Text>
              {[['letter', 'Letter'], ['a4', 'A4']].map(([val, label]) => (
                <TouchableOpacity
                  key={val}
                  style={[styles.paperHeaderOption, paperSize === val && styles.paperHeaderOptionActive]}
                  onPress={() => setPaperSize(val)}
                >
                  <Text style={[styles.paperHeaderOptionText, paperSize === val && styles.paperHeaderOptionTextActive]}>
                    {label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.captureButton, !canCapture && styles.captureButtonDisabled]}
          onPress={handleTakePhoto}
          disabled={!canCapture}
        >
          <Text style={styles.captureButtonText}>
            {canCapture ? 'Capture photo' : 'Align phone and lighting to capture'}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.galleryButton} onPress={handlePickFromGallery}>
          <Text style={styles.galleryButtonText}>Pick from gallery</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  cameraScreen: {
    flex: 1,
    backgroundColor: '#000',
  },
  camera: {
    ...StyleSheet.absoluteFillObject,
  },
  overlay: {
    flex: 1,
    paddingHorizontal: 0,
    paddingTop: 0,
    paddingBottom: 112,
    justifyContent: 'space-between',
  },
  topGuidance: {
    width: '100%',
    paddingHorizontal: 0,
  },
  whiteHeader: {
    width: '100%',
    backgroundColor: '#FFFBF5',
    borderRadius: 0,
    paddingLeft: 24,
    paddingRight: 16,
    paddingVertical: 12,
  },
  whiteHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  whiteHeaderColumn: {
    flex: 1,
  },
  whiteHeaderColumnLeft: {
    flex: 1,
    paddingRight: 0,
  },
  whiteHeaderColumnRight: {
    flex: 1,
    paddingLeft: 36,
  },
  whiteHeaderVerticalDivider: {
    width: 1,
    backgroundColor: '#E2D4C0',
    marginLeft: 16,
  },
  whiteHeaderDivider: {
    height: 1,
    backgroundColor: '#E2D4C0',
    marginBottom: 6,
  },
  whiteHeaderTiltRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  whiteHeaderLabel: {
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.2,
    color: '#4A3B2D',
  },
  whiteHeaderValue: {
    fontSize: 13,
    lineHeight: 20,
    color: '#6B5F52',
  },
  whiteHeaderTiltText: {
    textAlign: 'center',
    fontSize: 12,
    fontWeight: '500',
  },
  whiteHeaderPaperRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 6,
  },
  paperHeaderOption: {
    paddingHorizontal: 14,
    paddingVertical: 5,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#C28A5B',
  },
  paperHeaderOptionActive: {
    backgroundColor: '#C28A5B',
  },
  paperHeaderOptionText: {
    fontSize: 12,
    color: '#C28A5B',
    fontWeight: '600',
  },
  paperHeaderOptionTextActive: {
    color: '#FFFFFF',
  },
  centerContainer: {
    flex: 1,
    backgroundColor: '#F5EFE6',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  errorText: {
    fontSize: 13,
    color: '#FFCDD2',
    marginBottom: 8,
    textAlign: 'center',
  },
  captureButton: {
    marginTop: 4,
    backgroundColor: '#C28A5B',
    paddingVertical: 14,
    borderRadius: 999,
    alignItems: 'center',
  },
  captureButtonDisabled: {
    opacity: 0.5,
  },
  galleryButton: {
    marginTop: 10,
    alignItems: 'center',
    paddingVertical: 10,
  },
  galleryButtonText: {
    color: '#FFFBF5',
    fontSize: 14,
    fontWeight: '500',
    textDecorationLine: 'underline',
  },
  captureButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    textAlign: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B5F52',
    fontWeight: '500',
  },
  previewContainer: {
    flex: 1,
    backgroundColor: '#F5EFE6',
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 24,
  },
  previewTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 6,
  },
  previewSubtitle: {
    fontSize: 14,
    color: '#6B5F52',
    marginBottom: 16,
    lineHeight: 20,
  },
  previewFrame: {
    width: '100%',
    aspectRatio: 3 / 4,
    backgroundColor: '#E8DDD0',
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 24,
  },
  previewImage: {
    width: '100%',
    height: '100%',
  },
  primaryButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 16,
    borderRadius: 999,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButton: {
    paddingVertical: 14,
    alignItems: 'center',
  },
  secondaryButtonText: {
    fontSize: 15,
    color: '#6B5F52',
    fontWeight: '500',
  },
  previewErrorText: {
    marginTop: 12,
    fontSize: 13,
    color: '#B33',
    textAlign: 'center',
    lineHeight: 18,
  },
  permissionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 8,
    textAlign: 'center',
  },
  permissionText: {
    fontSize: 14,
    color: '#6B5F52',
    marginBottom: 20,
    lineHeight: 20,
    textAlign: 'center',
  },
});
