// Shared fetch helpers: timeout wrapper + authorized requests.
//
// React Native's fetch has no built-in timeout: on a dropped connection the
// promise hangs forever and the calling screen's spinner never stops. Every
// API call should go through fetchWithTimeout so a dead network surfaces as
// a catchable error instead of a hung UI.
//
// Authenticated calls should go through authorizedFetch, which reads the
// stored token, sets the DRF `Token` header, and centrally handles session
// expiry: any 401 clears the stored token and notifies onSessionExpired
// listeners (App.js resets navigation to Welcome). Screens never need their
// own 401 branches.

import * as SecureStore from 'expo-secure-store';
import { API_BASE_URL } from '../config/api';

export const DEFAULT_TIMEOUT_MS = 30000;
export const UPLOAD_TIMEOUT_MS = 60000; // image uploads on slow cellular need longer

const AUTH_TOKEN_KEY = 'authToken';

export async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (e) {
    if (e?.name === 'AbortError') {
      throw new Error('Request timed out. Check your connection and try again.');
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function getAuthToken() {
  try {
    return await SecureStore.getItemAsync(AUTH_TOKEN_KEY);
  } catch {
    return null; // SecureStore unavailable — treat as signed out
  }
}

export async function clearAuthToken() {
  await SecureStore.deleteItemAsync(AUTH_TOKEN_KEY).catch(() => {});
}

// Session-expiry listeners. App.js registers one that finishes the sign-out
// (Google session) and resets navigation to Welcome.
const sessionExpiredListeners = new Set();

export function onSessionExpired(listener) {
  sessionExpiredListeners.add(listener);
  return () => sessionExpiredListeners.delete(listener);
}

function notifySessionExpired() {
  sessionExpiredListeners.forEach((listener) => {
    try {
      listener();
    } catch {}
  });
}

/**
 * Fetch an API path with the stored auth token.
 *
 * @param {string} path - repo-relative API path, e.g. '/api/profile/'
 * @throws when no token is stored (message doubles as user-facing copy)
 *
 * Backend tokens expire (AUTH_TOKEN_MAX_AGE_DAYS): a 401 from any endpoint
 * means the session is over, so the token is cleared and listeners fire
 * before the response is returned to the caller.
 */
export async function authorizedFetch(path, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Session expired. Please sign in again.');
  }
  const res = await fetchWithTimeout(
    `${API_BASE_URL}${path}`,
    {
      ...options,
      headers: { ...(options.headers || {}), Authorization: `Token ${token}` },
    },
    timeoutMs,
  );
  if (res.status === 401) {
    await clearAuthToken();
    notifySessionExpired();
  }
  return res;
}
