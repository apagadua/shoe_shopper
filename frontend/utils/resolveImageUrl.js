import { API_BASE_URL } from '../config/api';

/**
 * Resolve an image URL, routing Converse / Demandware CDN URLs through the
 * backend proxy so the server can attach the required browser-like headers.
 * React Native's Image component (Fresco on Android) does not reliably
 * forward custom headers set on the source prop.
 */
export function resolveImageUrl(uri) {
  if (!uri) return null;
  if (uri.includes('converse.com') || uri.includes('demandware.static')) {
    return `${API_BASE_URL}/api/proxy-image/?url=${encodeURIComponent(uri)}`;
  }
  return uri;
}
