import React from 'react';
import { Image, StyleSheet, View } from 'react-native';

/** @type {const} */
export const LOGO_SOURCE = require('../assets/ShoeShopper Logo.png');

const PRESETS = {
  sm: { width: 120, height: 44 },
  md: { width: 168, height: 60 },
  lg: { width: 252, height: 90 },
  xl: { width: 320, height: 114 },
  header: { width: 148, height: 40 },
  corner: { width: 156, height: 46 },
  watermark: { width: 260, height: 90 },
};

/**
 * Shoe Shopper wordmark / logo from assets.
 * @param {'sm'|'md'|'lg'|'header'|'watermark'} size
 */
export default function AppLogo({ size = 'md', style }) {
  const dims = PRESETS[size] || PRESETS.md;
  return (
    <Image
      source={LOGO_SOURCE}
      style={[dims, style]}
      resizeMode="contain"
      accessibilityRole="image"
      accessibilityLabel="Shoe Shopper"
    />
  );
}

/** Centered logo for stack navigator headers. */
export function HeaderLogo() {
  return (
    <View style={styles.headerWrap}>
      <AppLogo size="header" />
    </View>
  );
}

/** Compact logo for the top-right of a navigation header. */
export function HeaderLogoCorner({ style }) {
  return (
    <View style={[styles.cornerWrap, style]}>
      <AppLogo size="corner" />
    </View>
  );
}

const styles = StyleSheet.create({
  headerWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 40,
  },
  cornerWrap: {
    justifyContent: 'center',
    alignItems: 'flex-end',
    marginRight: -26,
    minHeight: 48,
  },
});
