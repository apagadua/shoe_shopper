import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { API_BASE_URL } from '../config/api';

const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;

GoogleSignin.configure({
  webClientId,
  scopes: ['profile', 'email'],
});

export async function googleSignIn() {
  if (!webClientId) {
    throw new Error('Missing EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID (check frontend/.env)');
  }
  await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
  const result = await GoogleSignin.signIn();
  if (result?.type === 'cancelled') {
    return null;
  }
  let idToken = result.data?.idToken;
  if (!idToken) {
    const tokens = await GoogleSignin.getTokens();
    idToken = tokens?.idToken;
  }
  if (!idToken) {
    throw new Error('No ID token from Google (check Web client ID in Google Cloud matches backend GOOGLE_CLIENT_ID)');
  }
  return idToken;
}

export async function signInWithGoogle(idToken) {
  const res = await fetch(`${API_BASE_URL}/api/auth/google/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: idToken }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    const msg = error?.detail ?? 'Google sign-in failed';
    const extra = error?.debug ? ` — ${error.debug}` : '';
    throw new Error(`${msg}${extra}`);
  }

  const data = await res.json();
  return data.key;
}
