import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const FRAME_PADDING = 32;
const FRAME_SCALE = 0.72;
const FRAME_BASE_WIDTH = SCREEN_WIDTH - FRAME_PADDING * 2;
const FRAME_ASPECT = 3 / 4;
const FRAME_WIDTH = FRAME_BASE_WIDTH * FRAME_SCALE;
const FRAME_HEIGHT = (FRAME_BASE_WIDTH / FRAME_ASPECT) * FRAME_SCALE;

export default function CameraScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding ?? false;
  const [phase, setPhase] = useState('guide'); // 'guide' | 'loading' | 'preview' | 'processing'
  const [capturedUri, setCapturedUri] = useState(null);
  const [error, setError] = useState(null);

  const openCamera = async () => {
    setError(null);
    setPhase('loading');
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        setError('Camera permission is required to capture your foot.');
        setPhase('guide');
        return;
      }
      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ['images'],
        allowsEditing: false,
        quality: 0.9,
      });
      if (result.canceled) {
        setPhase('guide');
        return;
      }
      const uri = result.assets[0].uri;
      setCapturedUri(uri);
      setPhase('preview');
    } catch (err) {
      setError(err.message || 'Could not open camera.');
      setPhase('guide');
    }
  };

  const handleUsePhoto = () => {
    setPhase('processing');
    // Simulate processing; later replace with real upload/API call
    setTimeout(() => {
      navigation.navigate('Measurements', {
        fromOnboarding,
        imageUri: capturedUri,
      });
    }, 1500);
  };

  const handleRetake = () => {
    setCapturedUri(null);
    setPhase('guide');
  };

  // Loading overlay: opening camera or processing
  if (phase === 'loading' || phase === 'processing') {
    return (
      <View style={styles.container}>
        <View style={styles.loadingCard}>
          <ActivityIndicator size="large" color="#C28A5B" />
          <Text style={styles.loadingText}>
            {phase === 'loading' ? 'Opening camera…' : 'Processing…'}
          </Text>
        </View>
      </View>
    );
  }

  // Confirmation: preview + Use photo / Retake
  if (phase === 'preview' && capturedUri) {
    return (
      <View style={styles.container}>
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
      </View>
    );
  }

  // Guide: alignment frame + distance text + Take photo
  return (
    <View style={styles.container}>
      <Text style={styles.guideTitle}>Frame your foot</Text>
      <Text style={styles.guideSubtitle}>
        Place the paper vertically (portrait). Put your foot in the middle of the paper. Frame both inside the guide below, then tap "Take photo".
      </Text>

      <View style={styles.viewfinder}>
        <View style={styles.alignmentFrame}>
          <View style={[styles.corner, styles.cornerTL]} />
          <View style={[styles.corner, styles.cornerTR]} />
          <View style={[styles.corner, styles.cornerBL]} />
          <View style={[styles.corner, styles.cornerBR]} />
          <Text style={styles.frameLabel}>Paper (vertical)</Text>
          <Text style={styles.frameLabelFoot}>Foot in center</Text>
        </View>
      </View>

      <View style={styles.distanceCard}>
        <Text style={styles.distanceTitle}>Distance</Text>
        <Text style={styles.distanceText}>
          Hold your phone at knee height, about 30 cm (12 in) above the paper. The full sheet (vertical) with your foot centered should fit inside the frame.
        </Text>
      </View>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <TouchableOpacity style={styles.captureButton} onPress={openCamera}>
        <Text style={styles.captureButtonText}>Take photo</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5EFE6',
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 24,
  },
  guideTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 6,
  },
  guideSubtitle: {
    fontSize: 14,
    color: '#6B5F52',
    marginBottom: 20,
    lineHeight: 20,
  },
  viewfinder: {
    width: FRAME_WIDTH,
    height: FRAME_HEIGHT,
    alignSelf: 'center',
    marginBottom: 20,
    backgroundColor: '#E8DDD0',
    borderRadius: 16,
    overflow: 'hidden',
    justifyContent: 'center',
    alignItems: 'center',
  },
  alignmentFrame: {
    width: FRAME_WIDTH - 24,
    height: FRAME_HEIGHT - 24,
    borderWidth: 3,
    borderColor: 'rgba(194, 138, 91, 0.9)',
    borderRadius: 12,
    borderStyle: 'dashed',
    justifyContent: 'center',
    alignItems: 'center',
  },
  corner: {
    position: 'absolute',
    width: 24,
    height: 24,
    borderColor: '#C28A5B',
    borderWidth: 3,
  },
  cornerTL: { top: -2, left: -2, borderRightWidth: 0, borderBottomWidth: 0, borderTopLeftRadius: 12 },
  cornerTR: { top: -2, right: -2, borderLeftWidth: 0, borderBottomWidth: 0, borderTopRightRadius: 12 },
  cornerBL: { bottom: -2, left: -2, borderRightWidth: 0, borderTopWidth: 0, borderBottomLeftRadius: 12 },
  cornerBR: { bottom: -2, right: -2, borderLeftWidth: 0, borderTopWidth: 0, borderBottomRightRadius: 12 },
  frameLabel: {
    fontSize: 13,
    color: '#6B5F52',
    fontWeight: '600',
  },
  frameLabelFoot: {
    fontSize: 12,
    color: '#8B7D6F',
    marginTop: 2,
    fontWeight: '500',
  },
  distanceCard: {
    backgroundColor: '#FFFBF5',
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  distanceTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#2F2A25',
    marginBottom: 4,
  },
  distanceText: {
    fontSize: 13,
    color: '#6B5F52',
    lineHeight: 18,
  },
  errorText: {
    fontSize: 13,
    color: '#B33',
    marginBottom: 12,
    textAlign: 'center',
  },
  captureButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 16,
    borderRadius: 999,
    alignItems: 'center',
  },
  captureButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  loadingCard: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B5F52',
    fontWeight: '500',
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
});
