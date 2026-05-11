import { createClient } from '@supabase/supabase-js';
import Constants from 'expo-constants';

/**
 * Supabase reads catalog colorways (`shoe`, `shoe_colorway`, `shoe_colorway_size`).
 * Credentials: `EXPO_PUBLIC_SUPABASE_*` in `frontend/.env` or repo-root `.env`, OR `extra.supabaseUrl` / `extra.supabaseAnonKey`
 * from `app.config.js` (so Metro inlining is not the only path). Restart Metro after env changes.
 */
function firstNonEmpty(...candidates) {
  for (const c of candidates) {
    if (c != null && String(c).trim() !== '') return String(c).trim();
  }
  return null;
}

const extra = Constants.expoConfig?.extra ?? {};

const url = firstNonEmpty(
  process.env.EXPO_PUBLIC_SUPABASE_URL,
  extra.supabaseUrl,
);
const anonKey = firstNonEmpty(
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY,
  extra.supabaseAnonKey,
);

export const isSupabaseConfigured = Boolean(url && anonKey);

export const supabase = isSupabaseConfigured
  ? createClient(url, anonKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    })
  : null;
