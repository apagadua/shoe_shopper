/**
 * Paper foot capture: live camera with accelerometer tilt gating and Android light hints.
 * Navigates to PhotoPreviewScreen for upload to POST /api/foot/measure/.
 * See FRONTEND_FEATURES.md §3.2 and §5.1.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { openPermissionSettings } from '../utils/openPermissionSettings';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { Accelerometer, LightSensor } from 'expo-sensors';

const TILT_OK_DEGREES = 10;
const LIGHT_MIN_LUX = 50; // simple threshold for "too dark" on Android

export default function CameraScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding ?? false;

  const cameraRef = useRef(null);
  const [permission, requestPermission] = useCameraPermissions();

  const [error, setError] = useState(null);

  const [paperSize, setPaperSize] = useState('letter'); // 'letter' | 'a4'

  const [tiltDegrees, setTiltDegrees] = useState(null);
  const [isAligned, setIsAligned] = useState(false);

  const [lightOk, setLightOk] = useState(true);
  const [lightAvailable, setLightAvailable] = useState(false);

  // Tilt guidance while camera is open
  useEffect(() => {
    Accelerometer.setUpdateInterval(200);
    const sub = Accelerometer.addListener(({ x, y, z }) => {
      const mag = Math.sqrt(x * x + y * y + z * z) || 1;
      const nz = z / mag;
      const clamped = Math.max(-1, Math.min(1, nz));
      const angleRad = Math.acos(Math.abs(clamped));
      const angleDeg = (angleRad * 180) / Math.PI;
      const rounded = Math.round(angleDeg);
      setTiltDegrees(rounded);
      setIsAligned(rounded <= TILT_OK_DEGREES);
    });
    return () => sub.remove();
  }, []);

  // Light guidance (Android only) while camera is open
  useEffect(() => {
    let sub;
    let mounted = true;

    if (Platform.OS === 'android') {
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
  }, []);

  const handleTakePhoto = async () => {
    if (!cameraRef.current) return;
    setError(null);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.9 });
      navigation.navigate('PhotoPreview', {
        capturedUri: photo.uri,
        method: 'paper',
        paperSize,
        fromOnboarding,
      });
    } catch (e) {
      setError(e.message || 'Could not take photo.');
    }
  };

  const handlePickFromGallery = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.9,
    });
    if (!result.canceled && result.assets?.length > 0) {
      navigation.navigate('PhotoPreview', {
        capturedUri: result.assets[0].uri,
        method: 'paper',
        paperSize,
        fromOnboarding,
      });
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
          Enable camera permission in Settings so you can capture your foot.
        </Text>
        <TouchableOpacity style={styles.primaryButton} onPress={openPermissionSettings}>
          <Text style={styles.primaryButtonText}>Open Settings</Text>
        </TouchableOpacity>
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

        <View style={styles.bottomActions}>
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
  bottomActions: {
    width: '100%',
    alignItems: 'center',
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
    width: '90%',
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
