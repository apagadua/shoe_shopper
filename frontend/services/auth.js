import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { API_BASE_URL } from '../config/api';

GoogleSignin.configure({
  webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  scopes: ['profile', 'email'],
});

export async function googleSignIn() {
  await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
  const result = await GoogleSignin.signIn();
  if (result?.type === 'cancelled') {
    return null;
  }
  return result.data.idToken;
}

export async function signInWithGoogle(idToken) {
  const res = await fetch(`${API_BASE_URL}/api/auth/google/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: idToken }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error?.detail ?? 'Google sign-in failed');
  }

  const data = await res.json();
  return data.key;
}
