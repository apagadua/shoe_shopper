import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { API_BASE_URL } from '../config/api';
import { clearAuthToken, fetchWithTimeout } from './http';

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
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/auth/google/`, {
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

/**
 * Clear all local sign-in state: the stored backend token AND the native
 * Google session. Skipping the Google half leaves the previous account
 * attached to the device — the next sign-in silently reuses it.
 * Navigation reset is the caller's job.
 */
export async function signOutLocal() {
  await clearAuthToken();
  try {
    await GoogleSignin.signOut();
  } catch {
    // Native module unavailable (Expo Go) or already signed out — the
    // backend token is gone either way.
  }
}
