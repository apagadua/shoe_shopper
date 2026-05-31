import { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  NativeModules,
  requireNativeComponent,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { useCameraPermissions } from 'expo-camera';
import { openPermissionSettings } from '../utils/openPermissionSettings';
import { Accelerometer } from 'expo-sensors';

const { ARCoreModule } = NativeModules;
const ARCorePreview = requireNativeComponent('ARCorePreview');

const TILT_OK_DEGREES  = 15;   // slightly more lenient than paper method
const MIN_PLANE_EXTENT = 0.3;  // metres — minimum floor extent to feel confident
const CAM_H_MIN_M      = 0.30; // 12 in — too close, plane data unstable
const CAM_H_MAX_M      = 0.89; // 35 in — too far, projection error amplifies

export default function ARCameraScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding ?? false;

  const [permission] = useCameraPermissions();

  // Phases: 'initializing' → 'scanning' | 'unavailable' | 'error'
  // Preview is now a separate screen (PhotoPreviewScreen).
  const [phase, setPhase] = useState('initializing');
  const [initError, setInitError] = useState(null);

  const [captureError, setCaptureError] = useState(null);

  const [tiltDegrees, setTiltDegrees] = useState(null);
  const [isAligned, setIsAligned] = useState(false);
  const [floorDetected, setFloorDetected] = useState(false);
  const [cameraHeightM, setCameraHeightM] = useState(null); // null = not yet known

  // Track whether session is running so cleanup is safe
  const sessionActive = useRef(false);

  // When the user taps Capture and we navigate to PhotoPreview, the screen
  // loses focus which normally triggers the useFocusEffect cleanup and stops
  // the AR session. That would make the captured image file inaccessible and
  // crash the upload. Set this ref to true just before navigating to
  // PhotoPreview so the cleanup skips stopSession; PhotoPreview will stop
  // the session itself after a successful upload.
  const keepSessionForPreview = useRef(false);

  // -------------------------------------------------------------------------
  // Initialization: reset all state and (re)start the AR session every time
  // this screen comes into focus. This ensures the user always gets a fresh
  // scanning phase — whether it's their first visit or they returned from
  // Measurements after a completed capture.
  // Cleanup on blur stops the native session so it doesn't run in background.
  // -------------------------------------------------------------------------
  useFocusEffect(
    useCallback(() => {
      if (!permission?.granted) return;

      let cancelled = false;

      // Always reset the scanning sub-state so the UI is fresh.
      setCaptureError(null);
      setFloorDetected(false);
      setCameraHeightM(null);
      setTiltDegrees(null);
      setIsAligned(false);

      if (sessionActive.current) {
        // ---------------------------------------------------------------
        // RETAKE PATH: the session was kept alive intentionally when we
        // navigated to PhotoPreview (keepSessionForPreview). Don't stop
        // and restart — captureSnapshot() leaves the native session in a
        // post-capture state where startSession() reliably fails.
        // Just reset the UI and let the already-running session resume.
        // ---------------------------------------------------------------
        setPhase('scanning');
        // Return the normal cleanup; if the user now navigates away for
        // real (not to PhotoPreview), the session will be stopped then.
        return () => {
          cancelled = true;
          if (sessionActive.current && !keepSessionForPreview.current) {
            ARCoreModule?.stopSession?.();
            sessionActive.current = false;
          }
          keepSessionForPreview.current = false;
        };
      }

      // -------------------------------------------------------------------
      // FRESH START PATH: no session running — first visit, or returning
      // after a completed measurement where the session was properly stopped.
      // -------------------------------------------------------------------
      setPhase('initializing');
      setInitError(null);

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

          // Defensive stop in case something left a session open unexpectedly.
          try { await ARCoreModule?.stopSession?.(); } catch { /* ignore */ }

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

      // Cleanup: runs when the screen loses focus (navigating away) or unmounts.
      return () => {
        cancelled = true;
        if (sessionActive.current && !keepSessionForPreview.current) {
          // Normal blur (back button, tab switch, navigate to Measurements, etc.)
          // — stop the session immediately.
          ARCoreModule?.stopSession?.();
          sessionActive.current = false;
        }
        // Always reset the flag so the NEXT blur uses normal cleanup.
        keepSessionForPreview.current = false;
      };
    }, [permission?.granted])
  );

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
  // Poll native for floor-plane detection + camera height while scanning
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (phase !== 'scanning') return;

    const poll = async () => {
      try {
        const state = await ARCoreModule.queryTrackingState();
        setFloorDetected(state.floorPlaneCount > 0);
        // cameraHeightM is -1 when no floor plane is tracked yet
        setCameraHeightM(state.cameraHeightM >= 0 ? state.cameraHeightM : null);
      } catch {
        // ignore transient errors
      }
    };

    poll();
    const id = setInterval(poll, 500);
    return () => clearInterval(id);
  }, [phase]);

  // -------------------------------------------------------------------------
  // Capture: validate AR snapshot then hand off to the shared preview screen.
  // Navigating away triggers useFocusEffect cleanup → session stops.
  // If the user presses Retake in PhotoPreviewScreen, goBack() returns here
  // and useFocusEffect fires again → fresh session starts automatically.
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

      // Tell the blur cleanup not to stop the session — the image file
      // is still needed for the upload that happens in PhotoPreviewScreen.
      keepSessionForPreview.current = true;
      navigation.navigate('PhotoPreview', {
        capturedUri: snapshot.imageUri,
        method: 'arcore',
        arSnapshot: {
          camera_intrinsics: snapshot.cameraIntrinsics,
          camera_pose: snapshot.cameraPose,
          plane_center: snapshot.planeCenter,
          plane_normal: snapshot.planeNormal,
          plane_extent_x: snapshot.planeExtentX,
          plane_extent_z: snapshot.planeExtentZ,
          image_dimensions: snapshot.imageDimensions,
          tracking_state: snapshot.trackingState,
        },
        fromOnboarding,
      });
    } catch (e) {
      setCaptureError(e.message || 'Could not capture AR snapshot. Try again.');
    }
  };

  // -------------------------------------------------------------------------
  // Render: permission not yet loaded
  // -------------------------------------------------------------------------
  if (!permission) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
      </View>
    );
  }

  // -------------------------------------------------------------------------
  // Render: camera permission denied
  // -------------------------------------------------------------------------
  if (!permission.granted) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.unavailableTitle}>Camera access needed</Text>
        <Text style={styles.unavailableText}>
          Enable camera permission in Settings to use AR measurement.
        </Text>
        <TouchableOpacity style={styles.primaryButton} onPress={openPermissionSettings}>
          <Text style={styles.primaryButtonText}>Open Settings</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => navigation.navigate('FootCapture')}
        >
          <Text style={styles.secondaryButtonText}>Use paper method</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // -------------------------------------------------------------------------
  // Render: unavailable / error
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
          <Text style={styles.primaryButtonText}>Use paper method</Text>
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
  // Render: scanning (AR camera active)
  // -------------------------------------------------------------------------

  // --- Tilt status ---
  const tiltLabel = tiltDegrees == null ? 'Tilt: —' : `Tilt: ${tiltDegrees}°`;
  const tiltStatus = isAligned ? 'Aligned' : 'Hold phone flatter';
  const tiltStatusColor = isAligned ? '#2E7D32' : '#C0392B';

  // --- Height / floor status (right column) ---
  // Before floor is known: show scanning state.
  // Once floor is detected: pivot to live height guidance.
  let rightLabel, rightColor;
  if (!floorDetected) {
    rightLabel = 'Scanning for floor…';
    rightColor = '#B8860B'; // amber
  } else if (cameraHeightM === null) {
    rightLabel = 'Reading height…';
    rightColor = '#B8860B';
  } else if (cameraHeightM > CAM_H_MAX_M) {
    rightLabel = 'Lower the phone';
    rightColor = '#C0392B'; // red
  } else if (cameraHeightM < CAM_H_MIN_M) {
    rightLabel = 'Raise the phone';
    rightColor = '#B8860B';
  } else {
    rightLabel = 'Height: Good';
    rightColor = '#2E7D32'; // green
  }

  // --- Guidance bar text ---
  // Adapts as the user progresses through scanning → height → ready.
  const heightInRange =
    floorDetected &&
    cameraHeightM !== null &&
    cameraHeightM >= CAM_H_MIN_M &&
    cameraHeightM <= CAM_H_MAX_M;

  let guidanceTitle, guidanceBody;
  if (!floorDetected) {
    guidanceTitle = 'Point at the floor';
    guidanceBody  = 'Move the phone slowly in a small arc over the floor until it is detected.';
  } else if (!heightInRange) {
    guidanceTitle = 'Adjust height';
    guidanceBody  =
      cameraHeightM !== null && cameraHeightM > CAM_H_MAX_M
        ? 'Lower your phone — hold it 20–30" above your foot.'
        : 'Raise your phone a little — hold it 20–30" above your foot.';
  } else if (!isAligned) {
    guidanceTitle = 'Almost ready';
    guidanceBody  = 'Hold the phone a little flatter to reduce tilt.';
  } else {
    guidanceTitle = 'All set';
    guidanceBody  = 'Keep still, then tap Capture.';
  }

  // --- Capture gate ---
  const canCapture = isAligned && floorDetected && heightInRange;
  const captureLabel = !isAligned
    ? 'Align phone to capture'
    : !floorDetected
    ? 'Waiting for floor detection…'
    : !heightInRange
    ? (cameraHeightM !== null && cameraHeightM > CAM_H_MAX_M ? 'Lower the phone to capture' : 'Adjust height to capture')
    : 'Capture';

  return (
    <View style={styles.cameraScreen}>
      {/* Native AR camera preview fills the screen */}
      <ARCorePreview style={StyleSheet.absoluteFill} />

      <View style={styles.overlay}>
        {/* Top guidance bar */}
        <View style={styles.guidanceBar}>
          <Text style={styles.guidanceTitle}>{guidanceTitle}</Text>
          {guidanceBody ? (
            <Text style={styles.guidanceBody}>{guidanceBody}</Text>
          ) : null}
          <View style={[styles.divider, guidanceBody ? null : styles.dividerCompact]} />
          <View style={styles.statusRow}>
            {/* Left: tilt */}
            <Text style={[styles.statusItem, { color: tiltStatusColor }]}>
              {tiltLabel} · {tiltStatus}
            </Text>
            {/* Right: height (once floor known) or floor scanning */}
            <Text style={[styles.statusItem, { color: rightColor }]}>
              {rightLabel}
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
  dividerCompact: {
    marginTop: 8,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  statusItem: {
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
});
