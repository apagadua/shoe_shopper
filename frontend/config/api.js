/** Resolves Django API base URL — emulator defaults or EXPO_PUBLIC_API_URL override. */
import { Platform } from 'react-native';

const defaultBaseUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://127.0.0.1:8000';

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || defaultBaseUrl;
