import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
} from 'react-native';

export default function FootCaptureScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding;

  const handleCapture = () => {
    navigation.navigate('Camera', { fromOnboarding });
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Capture your foot</Text>
      <Text style={styles.subtitle}>
        Place a sheet of printer paper vertically on a smooth floor. Put your bare foot in the middle of the paper. Keep the camera directly above for the most accurate scan.
      </Text>

      <View style={styles.card}>
        <View style={styles.mockPhoto}>
          {/* Vertical paper with foot centered */}
          <View style={styles.paper} />
          <View style={styles.foot} />
        </View>
        <View style={styles.tipsList}>
          <Text style={styles.tipBullet}>* Paper vertical (portrait), foot in the center.</Text>
          <Text style={styles.tipBullet}>* Use a well-lit room (no harsh shadows).</Text>
          <Text style={styles.tipBullet}>* Keep your phone about knee-height.</Text>
        </View>
      </View>

      <TouchableOpacity style={styles.captureButton} onPress={handleCapture}>
        <Text style={styles.captureButtonText}>Open camera</Text>
      </TouchableOpacity>

      {fromOnboarding && (
        <TouchableOpacity
          style={styles.secondaryAction}
          onPress={() => navigation.replace('MainTabs')}
        >
          <Text style={styles.secondaryText}>Skip for now</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5EFE6',
    paddingHorizontal: 24,
    paddingTop: 80,
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    color: '#6B5F52',
    marginBottom: 28,
    lineHeight: 21,
  },
  card: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  mockPhoto: {
    height: 200,
    borderRadius: 16,
    backgroundColor: '#F0E2D0',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  paper: {
    width: '42%',
    height: '88%',
    borderRadius: 8,
    backgroundColor: '#FFF',
    position: 'absolute',
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  foot: {
    width: 56,
    height: 88,
    borderRadius: 28,
    backgroundColor: '#E0B68A',
    position: 'absolute',
    transform: [{ rotate: '-8deg' }],
  },
  tipsList: {
    gap: 6,
  },
  tipBullet: {
    fontSize: 13,
    color: '#4F453C',
    lineHeight: 18,
  },
  captureButton: {
    marginTop: 28,
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
  secondaryAction: {
    marginTop: 16,
    alignItems: 'center',
  },
  secondaryText: {
    fontSize: 14,
    color: '#6B5F52',
    textAlign: 'center',
  },
});
