import { useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  NativeModules,
  requireNativeComponent,
} from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { Accelerometer } from 'expo-sensors';
import { API_BASE_URL } from '../config/api';

const { ARCoreModule } = NativeModules;
const ARCorePreview = requireNativeComponent('ARCorePreview');

const TILT_OK_DEGREES = 15; // slightly more lenient than paper method
const MIN_PLANE_EXTENT = 0.3; // metres — minimum floor extent to feel confident

export default function ARCameraScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding ?? false;

  // Phases: 'initializing' → 'scanning' → 'preview' → 'processing' | 'unavailable' | 'error'
  const [phase, setPhase] = useState('initializing');
  const [initError, setInitError] = useState(null);

  const [capturedUri, setCapturedUri] = useState(null);
  const [arSnapshot, setArSnapshot] = useState(null);
  const [captureError, setCaptureError] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  const [tiltDegrees, setTiltDegrees] = useState(null);
  const [isAligned, setIsAligned] = useState(false);
  const [floorDetected, setFloorDetected] = useState(false);

  // Track whether session is running so cleanup is safe
  const sessionActive = useRef(false);

  // -------------------------------------------------------------------------
  // Initialization: check ARCore availability, then start session
  // -------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      try {
        if (!ARCoreModule) {
          setInitError('ARCore is not available on this device or platform.');
          setPhase('unavailable');
          return;
        }

        const availability = await ARCoreModule.checkAvailability();

        if (cancelled) return;

        if (availability === 'unsupported') {
          setInitError('ARCore is not supported on this device.');
          setPhase('unavailable');
          return;
        }

        if (availability === 'supported_not_installed') {
          try {
            await ARCoreModule.requestInstall();
          } catch {
            if (!cancelled) {
              setInitError('ARCore (Google Play Services for AR) is required. Please install it from the Play Store.');
              setPhase('unavailable');
            }
            return;
          }
        }

        // Start the AR session
        await ARCoreModule.startSession();

        if (!cancelled) {
          sessionActive.current = true;
          setPhase('scanning');
        }
      } catch (e) {
        if (!cancelled) {
          setInitError(e.message || 'Failed to start AR session.');
          setPhase('error');
        }
      }
    };

    init();

    return () => {
      cancelled = true;
      if (sessionActive.current) {
        ARCoreModule?.stopSession?.();
        sessionActive.current = false;
      }
    };
  }, []);

  // -------------------------------------------------------------------------
  // Accelerometer tilt detection while scanning
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (phase !== 'scanning') return;

    Accelerometer.setUpdateInterval(200);
    const sub = Accelerometer.addListener(({ x, y, z }) => {
      const mag = Math.sqrt(x * x + y * y + z * z) || 1;
      const nz = z / mag;
      const clamped = Math.max(-1, Math.min(1, nz));
      const angleDeg = Math.round((Math.acos(Math.abs(clamped)) * 180) / Math.PI);
      setTiltDegrees(angleDeg);
      setIsAligned(angleDeg <= TILT_OK_DEGREES);
    });

    return () => sub.remove();
  }, [phase]);

  // -------------------------------------------------------------------------
  // Poll native for floor-plane detection while scanning
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (phase !== 'scanning') return;

    const poll = async () => {
      try {
        const state = await ARCoreModule.queryTrackingState();
        setFloorDetected(state.floorPlaneCount > 0);
      } catch {
        // ignore transient errors
      }
    };

    poll();
    const id = setInterval(poll, 500);
    return () => clearInterval(id);
  }, [phase]);

  // -------------------------------------------------------------------------
  // Capture: request AR snapshot from native module
  // -------------------------------------------------------------------------
  const handleCapture = async () => {
    setCaptureError(null);
    try {
      const snapshot = await ARCoreModule.captureSnapshot();

      // Guard: ARCore must be actively tracking
      if (snapshot.trackingState !== 'TRACKING') {
        setCaptureError('Floor tracking lost. Keep the camera pointed at the floor and try again.');
        return;
      }

      // Guard: plane must exist and be large enough to be reliable
      const extentX = snapshot.planeExtentX ?? 0;
      const extentZ = snapshot.planeExtentZ ?? 0;
      if (!snapshot.planeCenter || (extentX < MIN_PLANE_EXTENT && extentZ < MIN_PLANE_EXTENT)) {
        setCaptureError('Floor not fully detected yet. Move the phone slowly over the floor and try again.');
        return;
      }

      setCapturedUri(snapshot.imageUri);
      setArSnapshot(snapshot);
      setPhase('preview');
    } catch (e) {
      setCaptureError(e.message || 'Could not capture AR snapshot. Try again.');
    }
  };

  // -------------------------------------------------------------------------
  // Upload: POST image + ar_snapshot to /api/foot/measure/
  // -------------------------------------------------------------------------
  const handleUsePhoto = async () => {
    setPhase('processing');
    setUploadError(null);
    try {
      const token = await SecureStore.getItemAsync('authToken');

      const formData = new FormData();
      const filename = capturedUri.split('/').pop();
      formData.append('image', { uri: capturedUri, name: filename, type: 'image/jpeg' });
      formData.append('measurement_method', 'arcore');
      formData.append('ar_snapshot', JSON.stringify({
        camera_intrinsics: arSnapshot.cameraIntrinsics,
        camera_pose: arSnapshot.cameraPose,
        plane_center: arSnapshot.planeCenter,
        plane_normal: arSnapshot.planeNormal,
        plane_extent_x: arSnapshot.planeExtentX,
        plane_extent_z: arSnapshot.planeExtentZ,
        image_dimensions: arSnapshot.imageDimensions,
        tracking_state: arSnapshot.trackingState,
      }));

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
      setUploadError(e.message || 'Could not process photo. Please try again.');
      setPhase('preview');
    }
  };

  const handleRetake = () => {
    setCapturedUri(null);
    setArSnapshot(null);
    setCaptureError(null);
    setUploadError(null);
    setPhase('scanning');
  };

  // -------------------------------------------------------------------------
  // Render: unavailable
  // -------------------------------------------------------------------------
  if (phase === 'unavailable' || phase === 'error') {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.unavailableTitle}>
          {phase === 'unavailable' ? 'AR Not Available' : 'Something went wrong'}
        </Text>
        <Text style={styles.unavailableText}>
          {initError || 'ARCore could not start.'}
        </Text>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => navigation.navigate('FootCapture')}
        >
          <Text style={styles.primaryButtonText}>Use paper method instead</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryButton} onPress={() => navigation.goBack()}>
          <Text style={styles.secondaryButtonText}>Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // -------------------------------------------------------------------------
  // Render: initializing spinner
  // -------------------------------------------------------------------------
  if (phase === 'initializing') {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
        <Text style={styles.loadingText}>Starting AR session…</Text>
      </View>
    );
  }

  // -------------------------------------------------------------------------
  // Render: processing spinner
  // -------------------------------------------------------------------------
  if (phase === 'processing') {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
        <Text style={styles.loadingText}>Processing…</Text>
      </View>
    );
  }

  // -------------------------------------------------------------------------
  // Render: preview (photo confirmation)
  // -------------------------------------------------------------------------
  if (phase === 'preview' && capturedUri) {
    return (
      <View style={styles.previewContainer}>
        <Text style={styles.previewTitle}>Check your photo</Text>
        <Text style={styles.previewSubtitle}>
          Make sure your full foot is visible and the floor is clear.
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
        {uploadError ? <Text style={styles.errorText}>{uploadError}</Text> : null}
      </View>
    );
  }

  // -------------------------------------------------------------------------
  // Render: scanning (AR camera active)
  // -------------------------------------------------------------------------
  const tiltLabel = tiltDegrees == null ? 'Tilt: —' : `Tilt: ${tiltDegrees}°`;
  const tiltStatus = isAligned ? 'Aligned' : 'Hold phone flatter';
  const tiltStatusColor = isAligned ? '#2E7D32' : '#C0392B';
  const floorColor = floorDetected ? '#2E7D32' : '#B8860B';
  const floorLabel = floorDetected ? 'Floor detected' : 'Scanning for floor…';

  const canCapture = isAligned && floorDetected;
  const captureLabel = !isAligned
    ? 'Align phone to capture'
    : !floorDetected
    ? 'Waiting for floor detection…'
    : 'Capture';

  return (
    <View style={styles.cameraScreen}>
      {/* Native AR camera preview fills the screen */}
      <ARCorePreview style={StyleSheet.absoluteFill} />

      <View style={styles.overlay}>
        {/* Top guidance bar */}
        <View style={styles.guidanceBar}>
          <Text style={styles.guidanceTitle}>Point at the floor</Text>
          <Text style={styles.guidanceBody}>
            Move the phone slowly in a small arc over the floor until it is detected.
          </Text>
          <View style={styles.divider} />
          <View style={styles.statusRow}>
            <Text style={[styles.tiltStatus, { color: tiltStatusColor }]}>
              {tiltLabel} · {tiltStatus}
            </Text>
            <Text style={[styles.tiltStatus, { color: floorColor }]}>
              {floorLabel}
            </Text>
          </View>
        </View>

        {/* Capture error */}
        {captureError ? (
          <View style={styles.captureErrorBanner}>
            <Text style={styles.captureErrorText}>{captureError}</Text>
          </View>
        ) : null}

        {/* Capture button */}
        <TouchableOpacity
          style={[styles.captureButton, !canCapture && styles.captureButtonDisabled]}
          onPress={handleCapture}
          disabled={!canCapture}
        >
          <Text style={styles.captureButtonText}>{captureLabel}</Text>
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
  overlay: {
    flex: 1,
    paddingBottom: 112,
    justifyContent: 'space-between',
  },
  guidanceBar: {
    width: '100%',
    backgroundColor: '#FFFBF5',
    paddingHorizontal: 24,
    paddingVertical: 14,
  },
  guidanceTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 3,
  },
  guidanceBody: {
    fontSize: 13,
    color: '#6B5F52',
    lineHeight: 19,
    marginBottom: 8,
  },
  divider: {
    height: 1,
    backgroundColor: '#E2D4C0',
    marginBottom: 8,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  tiltStatus: {
    fontSize: 12,
    fontWeight: '500',
  },
  captureErrorBanner: {
    marginHorizontal: 24,
    backgroundColor: 'rgba(0,0,0,0.6)',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  captureErrorText: {
    fontSize: 13,
    color: '#FFCDD2',
    textAlign: 'center',
    lineHeight: 18,
  },
  captureButton: {
    marginHorizontal: 24,
    backgroundColor: '#C28A5B',
    paddingVertical: 16,
    borderRadius: 999,
    alignItems: 'center',
  },
  captureButtonDisabled: {
    opacity: 0.5,
  },
  captureButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  centerContainer: {
    flex: 1,
    backgroundColor: '#F5EFE6',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 28,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B5F52',
    fontWeight: '500',
  },
  unavailableTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 10,
    textAlign: 'center',
  },
  unavailableText: {
    fontSize: 14,
    color: '#6B5F52',
    marginBottom: 28,
    lineHeight: 20,
    textAlign: 'center',
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
});
