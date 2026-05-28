import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function ARFootCaptureScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding ?? false;
  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.title}>Measure with AR</Text>
      <Text style={styles.subtitle}>
        No paper needed. Your phone uses augmented reality to detect the floor and measure your foot directly.
      </Text>

      <View style={styles.card}>
        {/* Visual: floor scan illustration */}
        <View style={styles.mockScan}>
          <Ionicons name="scan" size={64} color="#C28A5B" style={styles.scanIcon} />
          <View style={styles.scanLine} />
          <Text style={styles.scanLabel}>Floor detected</Text>
        </View>

        <View style={styles.tipsList}>
          <View style={styles.tip}>
            <Ionicons name="checkmark-circle" size={18} color="#C28A5B" style={styles.tipIcon} />
            <Text style={styles.tipText}>Stand on a flat, hard floor (wood, tile, or smooth concrete works best).</Text>
          </View>
          <View style={styles.tip}>
            <Ionicons name="checkmark-circle" size={18} color="#C28A5B" style={styles.tipIcon} />
            <Text style={styles.tipText}>Good lighting helps — avoid very dark rooms or direct sunlight glare.</Text>
          </View>
          <View style={styles.tip}>
            <Ionicons name="checkmark-circle" size={18} color="#C28A5B" style={styles.tipIcon} />
            <Text style={styles.tipText}>Wear a light, fitted sock so your foot shape is clear.</Text>
          </View>
          <View style={styles.tip}>
            <Ionicons name="checkmark-circle" size={18} color="#C28A5B" style={styles.tipIcon} />
            <Text style={styles.tipText}>When the camera opens, slowly move your phone over the floor until the surface is detected, then place your foot in the frame.</Text>
          </View>
        </View>
      </View>

      <View style={styles.betaBadge}>
        <Ionicons name="flask" size={14} color="#7B4F2E" />
        <Text style={styles.betaText}>Experimental — AR accuracy may vary by device and environment.</Text>
      </View>

      <TouchableOpacity
        style={styles.captureButton}
        onPress={() => navigation.navigate('ARCamera', { fromOnboarding })}
      >
        <Text style={styles.captureButtonText}>Open AR Camera</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.fallbackAction}
        onPress={() => navigation.navigate('FootCapture')}
      >
        <Text style={styles.fallbackText}>Use paper method</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5EFE6',
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 48,
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
    marginBottom: 24,
    lineHeight: 22,
  },
  card: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: '#E2D4C0',
    marginBottom: 16,
  },
  mockScan: {
    height: 160,
    borderRadius: 16,
    backgroundColor: '#F0E2D0',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
    overflow: 'hidden',
  },
  scanIcon: {
    opacity: 0.85,
  },
  scanLine: {
    position: 'absolute',
    left: 24,
    right: 24,
    height: 2,
    backgroundColor: '#C28A5B',
    opacity: 0.5,
    borderRadius: 1,
  },
  scanLabel: {
    position: 'absolute',
    bottom: 12,
    fontSize: 12,
    fontWeight: '600',
    color: '#C28A5B',
    letterSpacing: 0.4,
  },
  tipsList: {
    gap: 12,
  },
  tip: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  tipIcon: {
    marginRight: 10,
    marginTop: 1,
  },
  tipText: {
    flex: 1,
    fontSize: 13,
    color: '#4F453C',
    lineHeight: 19,
  },
  betaBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#F5E6D0',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#DFC4A8',
  },
  betaText: {
    flex: 1,
    fontSize: 12,
    color: '#7B4F2E',
    lineHeight: 17,
  },
  captureButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 16,
    borderRadius: 999,
    alignItems: 'center',
    marginBottom: 14,
  },
  captureButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  fallbackAction: {
    alignItems: 'center',
    paddingVertical: 4,
  },
  fallbackText: {
    fontSize: 14,
    color: '#6B5F52',
    textDecorationLine: 'underline',
  },
});
