import AsyncStorage from '@react-native-async-storage/async-storage';

const CACHE_KEY = 'rec_cache_v3';

/**
 * Read recommendations from AsyncStorage.
 * Returns null if missing or corrupt.
 *
 * @returns {Promise<{
 *   results: object[],
 *   measurement_id: number|null,
 *   shoe_count: number|null,
 *   has_toebox_data: boolean,
 *   algorithm_version: string,
 *   cached_at: number,
 * }|null>}
 */
export async function readRecommendationsCache() {
  try {
    const raw = await AsyncStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Persist recommendations to AsyncStorage.
 *
 * @param {{
 *   results: object[],
 *   measurement_id: number|null,
 *   shoe_count: number|null,
 *   has_toebox_data: boolean,
 *   algorithm_version: string,
 * }} data
 */
export async function writeRecommendationsCache(data) {
  try {
    await AsyncStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ ...data, cached_at: Date.now() }),
    );
  } catch {}
}

/**
 * Delete the cache entirely.
 */
export async function clearRecommendationsCache() {
  try {
    await AsyncStorage.removeItem(CACHE_KEY);
  } catch {}
}

/**
 * Return true if a fresh API fetch is needed.
 *
 * Stale when:
 *  - No cache exists
 *  - latestMeasurementId differs from what was cached (user remeasured)
 *  - currentShoeCount differs from what was cached (new shoes added to catalog)
 *
 * @param {object|null} cache               Result from readRecommendationsCache()
 * @param {number|null} latestMeasurementId id from /api/measurements/latest/
 * @param {number|null} currentShoeCount    shoe_count from /api/health/
 */
export function isCacheStale(cache, latestMeasurementId, currentShoeCount) {
  if (!cache) return true;
  if (latestMeasurementId != null && cache.measurement_id !== latestMeasurementId) return true;
  if (currentShoeCount != null && cache.shoe_count !== currentShoeCount) return true;
  return false;
}
