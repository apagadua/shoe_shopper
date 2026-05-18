import * as SecureStore from 'expo-secure-store';
import React, { useState } from 'react';
import { Alert, View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { StackActions } from '@react-navigation/native';
import { googleSignIn, signInWithGoogle } from '../services/auth';
import AppLogo from '../components/AppLogo';

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
      Alert.alert('Sign-in failed', err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'left', 'right']}>
      <View style={styles.topBar}>
        <TouchableOpacity
          onPress={() => navigation.dispatch(StackActions.popToTop())}
          style={styles.backButton}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons name="chevron-back" size={24} color="#2F2A25" />
        </TouchableOpacity>
        <Text style={styles.topBarTitle}>Log In</Text>
        <View style={styles.topBarSpacer} />
      </View>

      <View style={styles.body}>
        <View style={styles.logoWrap}>
          <AppLogo size="xl" />
        </View>
        <Text style={styles.subtitle}>
          Sign in with your Google account to continue.
        </Text>

        <TouchableOpacity
          style={[styles.googleButton, loading && styles.buttonDisabled]}
          disabled={loading}
          onPress={handleGooglePress}
          activeOpacity={0.9}
        >
          <Text style={styles.googleButtonText}>
            {loading ? 'Signing in...' : 'Continue with Google'}
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#F5EFE6',
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingBottom: 8,
  },
  backButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  topBarTitle: {
    flex: 1,
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 24,
    color: '#2F2A25',
    textAlign: 'center',
    marginRight: 40,
    letterSpacing: -0.3,
  },
  topBarSpacer: {
    width: 0,
  },
  body: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 20,
  },
  logoWrap: {
    alignItems: 'center',
    marginBottom: 24,
  },
  subtitle: {
    fontSize: 15,
    color: '#6B5F52',
    lineHeight: 22,
    marginBottom: 28,
    textAlign: 'center',
    paddingHorizontal: 8,
  },
  googleButton: {
    backgroundColor: '#FFFBF5',
    borderWidth: 1,
    borderColor: '#E2D4C0',
    paddingVertical: 14,
    borderRadius: 999,
    alignItems: 'center',
  },
  googleButtonText: {
    color: '#2F2A25',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
});
