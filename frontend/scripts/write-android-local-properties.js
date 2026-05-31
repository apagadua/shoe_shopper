/**
 * Writes android/local.properties with sdk.dir so Gradle can find the Android SDK.
 * Safe to run after `expo prebuild --clean` (which deletes local.properties).
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const SDK_CANDIDATES = [
  process.env.ANDROID_HOME,
  process.env.ANDROID_SDK_ROOT,
  path.join(os.homedir(), 'AppData', 'Local', 'Android', 'Sdk'),
  path.join(os.homedir(), 'Library', 'Android', 'sdk'),
  path.join(os.homedir(), 'Android', 'Sdk'),
].filter(Boolean);

function findSdk() {
  for (const candidate of SDK_CANDIDATES) {
    const normalized = path.resolve(candidate);
    if (fs.existsSync(path.join(normalized, 'platform-tools'))) {
      return normalized;
    }
  }
  return null;
}

const sdk = findSdk();
const androidDir = path.join(__dirname, '..', 'android');
const outFile = path.join(androidDir, 'local.properties');

if (!fs.existsSync(androidDir)) {
  console.warn('[write-android-local-properties] android/ not found — run expo prebuild first.');
  process.exit(0);
}

if (!sdk) {
  console.error(
    '[write-android-local-properties] Android SDK not found.\n'
      + 'Install Android Studio, then set ANDROID_HOME to your Sdk folder\n'
      + '(e.g. C:\\Users\\<you>\\AppData\\Local\\Android\\Sdk).'
  );
  process.exit(1);
}

const sdkDirLine = `sdk.dir=${sdk.replace(/\\/g, '\\\\')}\n`;
fs.writeFileSync(outFile, sdkDirLine, 'utf8');
console.log(`[write-android-local-properties] Wrote ${outFile}`);
console.log(`  sdk.dir=${sdk}`);
