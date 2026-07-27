import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  NativeModules,
} from 'react-native';
import { authorizedFetch, UPLOAD_TIMEOUT_MS } from '../services/http';

// Needed only to clean up native AR temp files after the user is done.
const { ARCoreModule } = NativeModules;

/**
 * Shared photo-preview screen used by both camera methods.
 *
 * Route params:
 *   capturedUri   string   — local URI of the captured image
 *   method        string   — 'paper' | 'arcore'
 *   paperSize     string   — 'letter' | 'a4'  (paper only)
 *   arSnapshot    object   — AR geometry data  (arcore only)
 *   fromOnboarding bool
 *
 * "Use this photo" → uploads to /api/foot/measure/ → Measurements screen
 * "Retake"         → navigation.goBack() → the camera that pushed here
 */
export default function PhotoPreviewScreen({ navigation, route }) {
  const {
    capturedUri,
    method,
    paperSize,
    arSnapshot,
    fromOnboarding,
  } = route.params;

  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  // ------------------------------------------------------------------
  // Upload & navigate to results
  // ------------------------------------------------------------------
  const handleUsePhoto = async () => {
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      const filename = capturedUri.split('/').pop();
      const ext = filename?.split('.').pop()?.toLowerCase() ?? 'jpg';
      const mimeType = ext === 'png' ? 'image/png' : 'image/jpeg';
      formData.append('image', { uri: capturedUri, name: filename, type: mimeType });

      if (method === 'paper') {
        formData.append('paper_size', paperSize);
      } else if (method === 'arcore') {
        formData.append('measurement_method', 'arcore');
        formData.append('ar_snapshot', JSON.stringify(arSnapshot));
      }

      const response = await authorizedFetch('/api/foot/measure/', {
        method: 'POST',
        body: formData,
      }, UPLOAD_TIMEOUT_MS);

      // Parse defensively: proxies/deploys can return HTML error pages, and
      // .json() throwing before the ok-check would mask the real HTTP error.
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || 'Measurement failed');
      if (!data) throw new Error('Measurement failed');

      // Clean up the native AR temp file — it has been uploaded and is
      // no longer needed. Session teardown is ARCameraScreen's responsibility
      // (its useFocusEffect cleanup fires when it eventually loses focus).
      if (method === 'arcore') {
        ARCoreModule?.cleanupCaptureFile?.(capturedUri);
      }

      navigation.navigate('Measurements', { fromOnboarding, measurementMethod: method, measurements: data });
    } catch (e) {
      setError(e.message || 'Could not process photo. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  // ------------------------------------------------------------------
  // Retake — go back to whatever camera pushed this screen.
  // For AR: the session is still running (ARCamera intentionally kept it
  //         alive). Cleanup the temp file here; ARCamera's useFocusEffect
  //         will stop the old session and start a fresh one on re-focus.
  // For paper: CameraScreen was never unmounted; camera is still live.
  // ------------------------------------------------------------------
  const handleRetake = () => {
    if (method === 'arcore') {
      ARCoreModule?.cleanupCaptureFile?.(capturedUri);
    }
    navigation.goBack();
  };

  // ------------------------------------------------------------------
  // Render: uploading
  // ------------------------------------------------------------------
  if (uploading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
        <Text style={styles.loadingText}>Processing…</Text>
      </View>
    );
  }

  // ------------------------------------------------------------------
  // Render: preview
  // ------------------------------------------------------------------
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Check your photo</Text>
      <Text style={styles.subtitle}>
        {method === 'paper'
          ? 'Make sure the paper is vertical, your foot is in the center, and both are clearly visible.'
          : 'Make sure your full foot is visible and the floor is clear.'}
      </Text>

      <View style={styles.imageFrame}>
        <Image source={{ uri: capturedUri }} style={styles.image} resizeMode="contain" />
      </View>

      <TouchableOpacity style={styles.primaryButton} onPress={handleUsePhoto}>
        <Text style={styles.primaryButtonText}>Use this photo</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.secondaryButton} onPress={handleRetake}>
        <Text style={styles.secondaryButtonText}>Retake</Text>
      </TouchableOpacity>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}
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
  centerContainer: {
    flex: 1,
    backgroundColor: '#F5EFE6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 14,
    color: '#6B5F52',
    marginBottom: 16,
    lineHeight: 20,
  },
  imageFrame: {
    width: '100%',
    aspectRatio: 3 / 4,
    backgroundColor: '#E8DDD0',
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 24,
    flex: 1,
  },
  image: {
    width: '100%',
    height: '100%',
  },
  primaryButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 16,
    borderRadius: 999,
    alignItems: 'center',
    marginBottom: 12,
    marginTop: 16,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButton: {
    paddingVertical: 12,
    alignItems: 'center',
  },
  secondaryButtonText: {
    fontSize: 15,
    color: '#6B5F52',
    fontWeight: '500',
  },
  errorText: {
    marginTop: 12,
    fontSize: 13,
    color: '#B33',
    textAlign: 'center',
    lineHeight: 18,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B5F52',
    fontWeight: '500',
  },
});
