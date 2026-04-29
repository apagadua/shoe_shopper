import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';

export default function FootCaptureScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding;

  const handleCapture = () => {
    navigation.navigate('Camera', { fromOnboarding });
  };

  const handlePickFromGallery = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.9,
    });
    if (!result.canceled && result.assets?.length > 0) {
      navigation.navigate('Camera', {
        fromOnboarding,
        galleryUri: result.assets[0].uri,
      });
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Measure your foot</Text>
      <Text style={styles.subtitle}>
        Choose a method. AR is faster and requires no paper — just a flat floor and good lighting.
      </Text>

      {/* ── AR method (primary) ── */}
      <View style={styles.methodCard}>
        <View style={styles.methodHeader}>
          <Ionicons name="scan" size={22} color="#C28A5B" />
          <Text style={styles.methodTitle}>Augmented Reality</Text>
          <View style={styles.betaBadge}>
            <Text style={styles.betaLabel}>BETA</Text>
          </View>
        </View>
        <Text style={styles.methodDesc}>
          No paper needed. Your phone detects the floor and measures your foot directly.
        </Text>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => navigation.navigate('ARFootCapture', { fromOnboarding })}
        >
          <Text style={styles.primaryButtonText}>Measure with AR</Text>
        </TouchableOpacity>
      </View>

      {/* ── Divider ── */}
      <View style={styles.dividerRow}>
        <View style={styles.dividerLine} />
        <Text style={styles.dividerText}>or</Text>
        <View style={styles.dividerLine} />
      </View>

      {/* ── Paper method (secondary) ── */}
      <View style={styles.methodCard}>
        <View style={styles.methodHeader}>
          <Ionicons name="document-outline" size={22} color="#6B5F52" />
          <Text style={styles.methodTitleSecondary}>Paper method</Text>
        </View>
        <View style={styles.mockPhoto}>
          <View style={styles.paper} />
          <Image
            source={require('../assets/Asset_1-8.png')}
            style={styles.footprintImage}
            resizeMode="contain"
          />
        </View>
        <Text style={styles.methodDesc}>
          Place a sheet of printer paper on the floor, stand on it, and take a photo from above.
        </Text>
        <TouchableOpacity style={styles.outlineButton} onPress={handleCapture}>
          <Text style={styles.outlineButtonText}>Open camera</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.galleryAction} onPress={handlePickFromGallery}>
          <Text style={styles.galleryText}>Pick from gallery</Text>
        </TouchableOpacity>
      </View>

      {fromOnboarding && (
        <TouchableOpacity
          style={styles.skipAction}
          onPress={() => navigation.replace('MainTabs')}
        >
          <Text style={styles.skipText}>Skip for now</Text>
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
    paddingTop: 60,
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
    lineHeight: 21,
  },

  // ── Method cards ──
  methodCard: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  methodHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  methodTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#2F2A25',
    flex: 1,
  },
  methodTitleSecondary: {
    fontSize: 16,
    fontWeight: '700',
    color: '#4F453C',
    flex: 1,
  },
  betaBadge: {
    backgroundColor: '#F5E6D0',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: '#DFC4A8',
  },
  betaLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#7B4F2E',
    letterSpacing: 0.5,
  },
  methodDesc: {
    fontSize: 13,
    color: '#6B5F52',
    lineHeight: 19,
    marginBottom: 16,
  },

  // ── Paper card visuals ──
  mockPhoto: {
    height: 140,
    borderRadius: 14,
    backgroundColor: '#F0E2D0',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 14,
  },
  paper: {
    width: '38%',
    height: '84%',
    borderRadius: 6,
    backgroundColor: '#FFF',
    position: 'absolute',
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  footprintImage: {
    width: 80,
    height: 80,
  },

  // ── Buttons ──
  primaryButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 15,
    borderRadius: 999,
    alignItems: 'center',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  outlineButton: {
    borderWidth: 1.5,
    borderColor: '#C28A5B',
    paddingVertical: 14,
    borderRadius: 999,
    alignItems: 'center',
  },
  outlineButtonText: {
    color: '#C28A5B',
    fontSize: 16,
    fontWeight: '600',
  },
  galleryAction: {
    marginTop: 14,
    alignItems: 'center',
  },
  galleryText: {
    fontSize: 14,
    color: '#6B5F52',
    fontWeight: '500',
    textDecorationLine: 'underline',
  },

  // ── Divider ──
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 16,
    gap: 10,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#E2D4C0',
  },
  dividerText: {
    fontSize: 13,
    color: '#A89880',
    fontWeight: '500',
  },

  // ── Skip ──
  skipAction: {
    marginTop: 20,
    alignItems: 'center',
  },
  skipText: {
    fontSize: 14,
    color: '#6B5F52',
    textAlign: 'center',
  },
});
