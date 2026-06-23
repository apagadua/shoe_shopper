import { LayoutAnimation, Platform, UIManager } from 'react-native';

// LayoutAnimation needs an explicit opt-in on Android's legacy architecture
// only. On the New Architecture (Fabric) it is enabled by default and the
// setter is a no-op that logs a warning, so skip it there.
const isFabric = global?.nativeFabricUIManager != null;
if (Platform.OS === 'android' && !isFabric && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

/**
 * Call right before a state change that adds/removes cards from a list so
 * the surrounding items slide into place instead of snapping.
 */
export function animateListChange() {
  LayoutAnimation.configureNext(
    LayoutAnimation.create(
      220,
      LayoutAnimation.Types.easeInEaseOut,
      LayoutAnimation.Properties.opacity,
    ),
  );
}
