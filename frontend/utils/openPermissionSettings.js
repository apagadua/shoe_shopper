import { Linking, Platform } from 'react-native';
import * as IntentLauncher from 'expo-intent-launcher';

const ANDROID_PACKAGE = 'com.alyssapagaduan.shoe_shopper';

/**
 * Opens the app's permissions page directly.
 * - Android: jumps straight to the app info / permissions screen via IntentLauncher
 * - iOS: opens the app's entry in the Settings app
 */
export function openPermissionSettings() {
  if (Platform.OS === 'android') {
    IntentLauncher.startActivityAsync(
      IntentLauncher.ActivityAction.APPLICATION_DETAILS_SETTINGS,
      { data: `package:${ANDROID_PACKAGE}` }
    );
  } else {
    Linking.openURL('app-settings:');
  }
}
