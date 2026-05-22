import * as SecureStore from 'expo-secure-store';
import { LinearGradient } from 'expo-linear-gradient';
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { StackActions } from '@react-navigation/native';
import { googleSignIn, signInWithGoogle } from '../services/auth';
import AppLogo from '../components/AppLogo';

const ACCENT = '#C28A5B';
const ACCENT_DEEP = '#9A6645';
const CREAM = '#F5EFE6';
const CARD = '#FFFBF5';
const FG = '#2F2A25';
const MUTED = '#6B5F52';

const PERKS = [
  {
    key: 'sync',
    icon: 'cloud-done-outline',
    text: 'Measurements and recommendations stay with your account',
  },
  {
    key: 'closet',
    icon: 'heart-outline',
    text: 'Wishlist and owned shoes sync when you log in',
  },
  {
    key: 'secure',
    icon: 'shield-checkmark-outline',
    text: 'Private log-in — we only use Google to verify you',
  },
];

export default function LoginScreen({ navigation }) {
  const [loading, setLoading] = useState(false);

  async function handleGooglePress() {
    setLoading(true);
    try {
      const idToken = await googleSignIn();
      if (!idToken) return;
      const token = await signInWithGoogle(idToken);
      await SecureStore.setItemAsync('authToken', token);
      navigation.replace('MainTabs');
    } catch (err) {
      Alert.alert('Log-in failed', err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'left', 'right', 'bottom']}>
      <LinearGradient
        colors={[ACCENT, ACCENT_DEEP]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.hero}
      >
        <TouchableOpacity
          onPress={() => navigation.dispatch(StackActions.popToTop())}
          style={styles.backButton}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          accessibilityRole="button"
          accessibilityLabel="Back to welcome"
        >
          <Ionicons name="chevron-back" size={22} color={FG} />
        </TouchableOpacity>

        <View style={styles.heroBrand}>
          <View style={styles.logoPad}>
            <AppLogo size="lg" />
          </View>
        </View>

        <Text style={styles.heroTitle}>Log in to your fit</Text>
        <Text style={styles.heroSubtitle}>
          One tap with Google — then pick up measuring and shopping where you left off.
        </Text>
      </LinearGradient>

      <View style={styles.sheet}>
        <View style={styles.card}>
          <Text style={styles.cardEyebrow}>Account</Text>
          <Text style={styles.cardHeading}>Continue with Google</Text>

          <TouchableOpacity
            style={[styles.googleButton, loading && styles.buttonDisabled]}
            disabled={loading}
            onPress={handleGooglePress}
            activeOpacity={0.9}
            accessibilityRole="button"
            accessibilityLabel="Continue with Google"
          >
            {loading ? (
              <ActivityIndicator color={FG} size="small" />
            ) : (
              <>
                <View style={styles.googleIconWrap}>
                  <Ionicons name="logo-google" size={20} color="#4285F4" />
                </View>
                <Text style={styles.googleButtonText}>Continue with Google</Text>
              </>
            )}
          </TouchableOpacity>

          <View style={styles.perks}>
            {PERKS.map((perk, index) => (
              <View
                key={perk.key}
                style={[styles.perkRow, index === PERKS.length - 1 && styles.perkRowLast]}
              >
                <View style={styles.perkIcon}>
                  <Ionicons name={perk.icon} size={18} color={ACCENT} />
                </View>
                <Text style={styles.perkText}>{perk.text}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: CREAM,
  },
  hero: {
    paddingHorizontal: 24,
    paddingBottom: 36,
    borderBottomLeftRadius: 28,
    borderBottomRightRadius: 28,
    alignItems: 'center',
  },
  backButton: {
    alignSelf: 'flex-start',
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: CARD,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: -8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#E8DDD0',
    shadowColor: '#2F2A25',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  heroBrand: {
    alignItems: 'center',
    marginBottom: 20,
  },
  logoPad: {
    backgroundColor: CARD,
    paddingHorizontal: 20,
    paddingVertical: 18,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E8DDD0',
    shadowColor: '#2F2A25',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 10,
    elevation: 4,
  },
  heroTitle: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 26,
    color: '#FFFFFF',
    letterSpacing: -0.3,
    marginBottom: 8,
    textAlign: 'center',
  },
  heroSubtitle: {
    fontFamily: 'Outfit_400Regular',
    fontSize: 15,
    color: 'rgba(255,255,255,0.92)',
    lineHeight: 22,
    maxWidth: 320,
    textAlign: 'center',
  },
  sheet: {
    flex: 1,
    marginTop: -14,
    paddingHorizontal: 20,
    paddingTop: 4,
  },
  card: {
    backgroundColor: CARD,
    borderRadius: 20,
    padding: 22,
    borderWidth: 1,
    borderColor: '#E8DDD0',
    shadowColor: '#2F2A25',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.06,
    shadowRadius: 12,
    elevation: 3,
  },
  cardEyebrow: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 12,
    color: ACCENT,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  cardHeading: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 18,
    color: FG,
    marginBottom: 18,
  },
  googleButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D4C9B8',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 14,
    gap: 10,
    marginBottom: 22,
  },
  googleIconWrap: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#F5EFE6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  googleButtonText: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 16,
    color: FG,
  },
  buttonDisabled: {
    opacity: 0.65,
  },
  perks: {
    borderTopWidth: 1,
    borderTopColor: '#EDE4D6',
    paddingTop: 4,
  },
  perkRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F0E8DC',
  },
  perkRowLast: {
    borderBottomWidth: 0,
    paddingBottom: 0,
  },
  perkIcon: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: '#F5EFE6',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  perkText: {
    flex: 1,
    fontFamily: 'Outfit_400Regular',
    fontSize: 13,
    color: MUTED,
    lineHeight: 19,
  },
});
