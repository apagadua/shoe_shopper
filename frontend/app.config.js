/**
 * Expo reads static config from app.json. This file runs first so we can load
 * env files that Metro does not merge by default:
 * - Repo root `.env` (e.g. `shoe_shopper/.env`) — common for Django + one shared file
 * - `frontend/.env` — wins for duplicate keys (where `app.json` lives)
 *
 * EXPO_PUBLIC_* vars must exist in one of these before `npx expo start` (restart Metro after edits).
 */
const path = require('path');
const fs = require('fs');

function loadEnvFile(filePath, override) {
  try {
    if (fs.existsSync(filePath)) {
      require('dotenv').config({ path: filePath, override: Boolean(override) });
    }
  } catch (_) {
    /* ignore missing dotenv or read errors */
  }
}

loadEnvFile(path.join(__dirname, '..', '.env'), false);
loadEnvFile(path.join(__dirname, '.env'), true);

const appJson = require('./app.json');

/**
 * Metro often only inlines EXPO_PUBLIC_* from env files it scans; `extra` is always embedded
 * from this config so root `.env` + dotenv above still reach the runtime bundle.
 */
module.exports = {
  expo: {
    ...appJson.expo,
    extra: {
      ...(appJson.expo.extra || {}),
      supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL || '',
      supabaseAnonKey: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || '',
    },
  },
};
