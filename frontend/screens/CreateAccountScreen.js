import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  TouchableWithoutFeedback,
  Keyboard,
} from 'react-native';

export default function CreateAccountScreen({ navigation }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const handleCreateAccount = () => {
    // TODO: wire up to real backend later
    console.log('Creating account with:', { email, password, confirmPassword });
    navigation.navigate('FootCapture', { fromOnboarding: true });
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
        <View style={styles.container}>
          <Text style={styles.title}>Create Account</Text>
          <Text style={styles.subtitle}>
            Use your existing Gmail and a secure password to get started.
          </Text>

          <View style={styles.form}>
            <Text style={styles.label}>Gmail address</Text>
            <TextInput
              style={styles.input}
              placeholder="you@gmail.com"
              placeholderTextColor="#B0A499"
              keyboardType="email-address"
              autoCapitalize="none"
              value={email}
              onChangeText={setEmail}
            />

            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              placeholder="Create a password"
              placeholderTextColor="#B0A499"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />

            <Text style={styles.label}>Confirm password</Text>
            <TextInput
              style={styles.input}
              placeholder="Re-enter password"
              placeholderTextColor="#B0A499"
              secureTextEntry
              value={confirmPassword}
              onChangeText={setConfirmPassword}
            />

            <TouchableOpacity
              style={styles.buttonPrimary}
              onPress={handleCreateAccount}
            >
              <Text style={styles.buttonPrimaryText}>Create account</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryAction}
              onPress={() => navigation.navigate('Login')}
            >
              <Text style={styles.secondaryText}>
                Already have an account?{' '}
                <Text style={styles.secondaryTextBold}>Log in</Text>
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </TouchableWithoutFeedback>
    </KeyboardAvoidingView>
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
  form: {
    gap: 16,
  },
  label: {
    fontSize: 14,
    color: '#4F453C',
    marginBottom: 4,
  },
  input: {
    borderWidth: 1,
    borderColor: '#E2D4C0',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: '#FFFBF5',
    fontSize: 15,
    marginBottom: 4,
  },
  buttonPrimary: {
    marginTop: 20,
    backgroundColor: '#C28A5B',
    paddingVertical: 14,
    borderRadius: 999,
    alignItems: 'center',
  },
  buttonPrimaryText: {
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
  },
  secondaryTextBold: {
    fontWeight: '600',
    color: '#2F2A25',
  },
});
