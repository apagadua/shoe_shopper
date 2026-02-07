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

export default function LoginScreen({ navigation }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = () => {
    // Placeholder: plug in real auth later
    console.log('Logging in with:', { email, password });
    navigation.replace('MainTabs');
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
        <View style={styles.container}>
          <Text style={styles.title}>Log In</Text>
          <Text style={styles.subtitle}>
            Use your email to access your Shoe Shopper account.
          </Text>

          <View style={styles.form}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={styles.input}
              placeholder="you@example.com"
              placeholderTextColor="#B0A499"
              keyboardType="email-address"
              autoCapitalize="none"
              value={email}
              onChangeText={setEmail}
            />

            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              placeholder="********"
              placeholderTextColor="#B0A499"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />

            <TouchableOpacity style={styles.button} onPress={handleLogin}>
              <Text style={styles.buttonText}>Continue</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryAction}
              onPress={() => navigation.navigate('CreateAccount')}
            >
              <Text style={styles.secondaryText}>
                Don't have an account?{' '}
                <Text style={styles.secondaryTextBold}>Create account</Text>
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
  button: {
    marginTop: 16,
    backgroundColor: '#C28A5B',
    paddingVertical: 14,
    borderRadius: 999,
    alignItems: 'center',
  },
  buttonText: {
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
