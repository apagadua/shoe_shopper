import * as SecureStore from 'expo-secure-store';
import React, { useState } from 'react';
import { Alert, View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { googleSignIn, signInWithGoogle } from '../services/auth';

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
    <View style={styles.container}>
      <Text style={styles.title}>Log In</Text>
      <Text style={styles.subtitle}>
        Sign in with your Google account to continue.
      </Text>

      <TouchableOpacity
        style={[styles.googleButton, loading && styles.buttonDisabled]}
        disabled={loading}
        onPress={handleGooglePress}
      >
        <Text style={styles.googleButtonText}>
          {loading ? 'Signing in...' : 'Continue with Google'}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 80,
    backgroundColor: '#F5EFE6',
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 15,
    color: '#6B5F52',
    marginBottom: 32,
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
