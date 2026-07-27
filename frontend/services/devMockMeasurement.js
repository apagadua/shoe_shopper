import { Platform } from 'react-native';
import { authorizedFetch, getAuthToken } from './http';

/**
 * Dev-only: POST a mock foot measurement so Recommendations works without a camera.
 * Set EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1 in frontend/.env, then restart Metro
 * (no native rebuild). Remove or set to 0 when testing on a real device with real scans.
 */
export async function ensureDevMockMeasurementIfNeeded() {
  if (!__DEV__) return;
  if (Platform.OS === 'web') return;
  if (process.env.EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT !== '1') return;

  const token = await getAuthToken();
  if (!token) return;

  try {
    const res = await authorizedFetch('/api/dev/mock-measurement/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (res.status === 404) return;
    if (!res.ok) {
      console.warn('[dev] mock measurement HTTP', res.status);
    }
  } catch (e) {
    console.warn('[dev] mock measurement', e?.message ?? e);
  }
}
