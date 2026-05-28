/**
 * withARCore.js — Expo config plugin for ARCore integration.
 *
 * Applied during `expo prebuild` to:
 *   1. Add `com.google.ar:core` to app/build.gradle dependencies
 *   2. Add android.hardware.camera.ar uses-feature (required=false) to AndroidManifest
 *   3. Add com.google.ar.core meta-data (value="optional") to AndroidManifest
 *
 * NOTE: In bare workflow the android/ directory is committed and these changes
 * are already applied directly. This plugin ensures they survive a future
 * `expo prebuild --clean` run.
 */

const {
  withAndroidManifest,
  withAppBuildGradle,
  createRunOncePlugin,
} = require('@expo/config-plugins');

const ARCORE_DEPENDENCY = "implementation('com.google.ar:core:1.44.0')";
const AR_FEATURE_NAME   = 'android.hardware.camera.ar';
const AR_META_NAME      = 'com.google.ar.core';

// ---------------------------------------------------------------------------
// 1. Gradle: add ARCore dependency
// ---------------------------------------------------------------------------
function withARCoreGradle(config) {
  return withAppBuildGradle(config, (config) => {
    const { contents } = config.modResults;

    if (contents.includes('com.google.ar:core')) {
      // Already present — idempotent
      return config;
    }

    // Insert after the opening `dependencies {` brace
    config.modResults.contents = contents.replace(
      /dependencies\s*\{/,
      `dependencies {\n    ${ARCORE_DEPENDENCY}`,
    );

    return config;
  });
}

// ---------------------------------------------------------------------------
// 2. Manifest: uses-feature + meta-data
// ---------------------------------------------------------------------------
function withARCoreManifest(config) {
  return withAndroidManifest(config, (config) => {
    const manifest     = config.modResults.manifest;
    const application  = manifest.application[0];

    // --- uses-permission: CAMERA (required by ARCore at runtime) ---
    if (!manifest['uses-permission']) {
      manifest['uses-permission'] = [];
    }
    const hasCameraPerm = manifest['uses-permission'].some(
      (p) => p.$?.['android:name'] === 'android.permission.CAMERA',
    );
    if (!hasCameraPerm) {
      manifest['uses-permission'].push({
        $: { 'android:name': 'android.permission.CAMERA' },
      });
    }

    // --- uses-feature (required=false so app installs on non-AR devices) ---
    if (!manifest['uses-feature']) {
      manifest['uses-feature'] = [];
    }
    const hasArFeature = manifest['uses-feature'].some(
      (f) => f.$?.['android:name'] === AR_FEATURE_NAME,
    );
    if (!hasArFeature) {
      manifest['uses-feature'].push({
        $: {
          'android:name':     AR_FEATURE_NAME,
          'android:required': 'false',
        },
      });
    }

    // --- meta-data (value="optional" → ARCore not required by Google Play) ---
    if (!application['meta-data']) {
      application['meta-data'] = [];
    }
    const hasArMeta = application['meta-data'].some(
      (m) => m.$?.['android:name'] === AR_META_NAME,
    );
    if (!hasArMeta) {
      application['meta-data'].push({
        $: {
          'android:name':  AR_META_NAME,
          'android:value': 'optional',
        },
      });
    }

    return config;
  });
}

// ---------------------------------------------------------------------------
// Combined plugin
// ---------------------------------------------------------------------------
const withARCore = (config) => {
  config = withARCoreGradle(config);
  config = withARCoreManifest(config);
  return config;
};

module.exports = createRunOncePlugin(withARCore, 'withARCore', '1.0.0');
