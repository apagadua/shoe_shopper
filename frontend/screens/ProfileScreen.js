import * as SecureStore from 'expo-secure-store';
import { LinearGradient } from 'expo-linear-gradient';
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { CommonActions, useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { API_BASE_URL } from '../config/api';
import AppLogo from '../components/AppLogo';

const ACCENT = '#C28A5B';
const ACCENT_DEEP = '#9A6645';
const MUTED = '#6B5F52';
const FG = '#2F2A25';
const CREAM = '#F5EFE6';
const CARD = '#FFFBF5';

function firstNameOrThere(displayName) {
  const t = (displayName || '').trim();
  if (!t) return { greeting: 'Welcome', useThere: true };
  const first = t.split(/\s+/)[0];
  return { greeting: first, useThere: false };
}

export default function ProfileScreen({ navigation }) {
  const profileImageUri = null;

  const [savedName, setSavedName] = useState('');
  const [nameInput, setNameInput] = useState('');
  const [loadState, setLoadState] = useState('loading');
  const [saving, setSaving] = useState(false);

  const loadProfile = useCallback(async () => {
    setLoadState('loading');
    try {
      const token = await SecureStore.getItemAsync('authToken');
      if (!token) {
        setLoadState('error');
        return;
      }
      const res = await fetch(`${API_BASE_URL}/api/profile/`, {
        headers: { Authorization: `Token ${token}` },
      });
      if (!res.ok) {
        setLoadState('error');
        return;
      }
      const data = await res.json();
      const n = typeof data.display_name === 'string' ? data.display_name : '';
      setSavedName(n);
      setNameInput(n);
      setLoadState('ok');
    } catch {
      setLoadState('error');
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadProfile();
    }, [loadProfile])
  );

  const dirty = (nameInput || '').trim() !== (savedName || '').trim();
  const canSave = dirty && !saving && loadState === 'ok';

  const saveName = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      const token = await SecureStore.getItemAsync('authToken');
      if (!token) throw new Error('Session expired. Please sign in again.');
      const res = await fetch(`${API_BASE_URL}/api/profile/`, {
        method: 'PATCH',
        headers: {
          Authorization: `Token ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ display_name: nameInput }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        const detail = errBody.detail || 'Could not save your name';
        throw new Error(typeof detail === 'string' ? detail : 'Could not save your name');
      }
      const data = await res.json();
      const n = typeof data.display_name === 'string' ? data.display_name : '';
      setSavedName(n);
      setNameInput(n);
    } catch (e) {
      Alert.alert('Could not save', e.message);
    } finally {
      setSaving(false);
    }
  };

  const signOutAndReset = async () => {
    await SecureStore.deleteItemAsync('authToken');
    await GoogleSignin.signOut();
    const root = navigation.getParent()?.getParent();
    root?.dispatch(CommonActions.reset({ index: 0, routes: [{ name: 'Welcome' }] }));
  };

  const handleChangePhoto = () => {
    // TODO: open image picker / camera for profile photo
  };

  const handleDeleteAccount = () => {
    Alert.alert(
      'Delete Account',
      'Are you sure you want to delete your account? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              const token = await SecureStore.getItemAsync('authToken');
              if (!token) throw new Error('Session expired. Please sign in again.');
              const res = await fetch(`${API_BASE_URL}/api/auth/delete/`, {
                method: 'DELETE',
                headers: { Authorization: `Token ${token}` },
              });
              if (!res.ok) throw new Error('Failed to delete account');
              await signOutAndReset();
            } catch (err) {
              Alert.alert('Error', err.message);
            }
          },
        },
      ]
    );
  };

  const handleSignOut = async () => {
    try {
      await signOutAndReset();
    } catch (err) {
      Alert.alert('Sign-out failed', err.message);
    }
  };

  const { greeting, useThere } = firstNameOrThere(savedName);
  const heroSubtitleText =
    loadState === 'error'
      ? 'Could not load profile.'
      : loadState === 'ok' && useThere
        ? 'Add your name for a more personal experience.'
        : null;

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 88 : 0}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <LinearGradient
          colors={[ACCENT, ACCENT_DEEP]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.hero}
        >
          {loadState === 'loading' ? (
            <View style={styles.heroLoading}>
              <ActivityIndicator color="#FFFFFF" />
            </View>
          ) : (
            <>
              <TouchableOpacity
                style={styles.avatarOuter}
                onPress={handleChangePhoto}
                activeOpacity={0.9}
                accessibilityRole="button"
                accessibilityLabel="Change profile photo"
              >
                {profileImageUri ? (
                  <Image source={{ uri: profileImageUri }} style={styles.avatarImg} />
                ) : (
                  <View style={styles.avatarPlaceholder}>
                    <Ionicons name="person" size={40} color="#6B5F52" />
                  </View>
                )}
                <View style={styles.cameraBadge}>
                  <Ionicons name="camera" size={14} color="#FFFFFF" />
                </View>
              </TouchableOpacity>
              <Text style={styles.heroGreeting} numberOfLines={1}>
                {useThere ? 'Your profile' : greeting}
              </Text>
              {heroSubtitleText != null ? (
                <Text style={styles.heroSub}>{heroSubtitleText}</Text>
              ) : null}
            </>
          )}
        </LinearGradient>

        <View style={styles.sheet}>
          {loadState === 'error' ? (
            <TouchableOpacity style={styles.retryBanner} onPress={loadProfile} activeOpacity={0.85}>
              <Ionicons name="refresh" size={20} color={ACCENT} />
              <Text style={styles.retryText}>Tap to retry</Text>
            </TouchableOpacity>
          ) : null}

          <View style={styles.card}>
            <View style={styles.cardHead}>
              <Ionicons name="person-circle-outline" size={22} color={ACCENT} />
              <Text style={styles.cardTitle}>Your name</Text>
            </View>
            <Text style={styles.fieldHint}>How you’d like to be addressed in the app.</Text>
            <TextInput
              style={styles.input}
              value={nameInput}
              onChangeText={setNameInput}
              placeholder="e.g. Alex Morgan"
              placeholderTextColor="#A39380"
              autoCapitalize="words"
              autoCorrect
              returnKeyType="done"
              editable={loadState === 'ok' && !saving}
              onSubmitEditing={saveName}
            />
            <TouchableOpacity
              style={[styles.saveBtn, !canSave && styles.saveBtnDisabled]}
              onPress={saveName}
              disabled={!canSave}
              activeOpacity={0.9}
            >
              {saving ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <Text style={styles.saveBtnText}>Save</Text>
              )}
            </TouchableOpacity>
          </View>

          <View style={styles.card}>
            <View style={styles.cardHead}>
              <Ionicons name="settings-outline" size={22} color={MUTED} />
              <Text style={styles.cardTitle}>Account</Text>
            </View>
            <TouchableOpacity style={styles.row} onPress={handleDeleteAccount} activeOpacity={0.7}>
              <Text style={styles.rowDanger}>Delete account</Text>
              <Ionicons name="chevron-forward" size={20} color="#A39380" />
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.row, styles.rowLast]}
              onPress={handleSignOut}
              activeOpacity={0.7}
            >
              <Text style={styles.rowDanger}>Sign out</Text>
              <Ionicons name="log-out-outline" size={20} color="#B3513D" />
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.brandFooter}>
          <AppLogo size="watermark" style={styles.brandLogo} />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: CREAM,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 32,
  },
  hero: {
    paddingTop: 8,
    paddingBottom: 28,
    paddingHorizontal: 24,
    alignItems: 'center',
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  heroLoading: {
    paddingVertical: 48,
  },
  avatarOuter: {
    marginBottom: 16,
  },
  avatarImg: {
    width: 92,
    height: 92,
    borderRadius: 46,
    borderWidth: 3,
    borderColor: 'rgba(255,255,255,0.85)',
  },
  avatarPlaceholder: {
    width: 92,
    height: 92,
    borderRadius: 46,
    backgroundColor: 'rgba(255,255,255,0.95)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: 'rgba(255,255,255,0.85)',
  },
  cameraBadge: {
    position: 'absolute',
    right: 0,
    bottom: 0,
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: ACCENT_DEEP,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.9)',
  },
  heroGreeting: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 24,
    color: '#FFFFFF',
    marginBottom: 6,
    textAlign: 'center',
  },
  heroSub: {
    fontFamily: 'Outfit_400Regular',
    fontSize: 15,
    color: 'rgba(255,255,255,0.9)',
    textAlign: 'center',
    lineHeight: 22,
    maxWidth: 300,
  },
  sheet: {
    marginTop: -12,
    paddingHorizontal: 20,
  },
  retryBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#FCEEE8',
    borderRadius: 12,
    paddingVertical: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E8C4B8',
  },
  retryText: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 15,
    color: ACCENT_DEEP,
  },
  card: {
    backgroundColor: CARD,
    borderRadius: 20,
    padding: 18,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#E2D4C0',
    shadowColor: '#2F2A25',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.06,
    shadowRadius: 10,
    elevation: 2,
  },
  cardHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  cardTitle: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 17,
    color: FG,
  },
  fieldHint: {
    fontFamily: 'Outfit_400Regular',
    fontSize: 14,
    color: MUTED,
    marginBottom: 12,
    lineHeight: 20,
  },
  input: {
    fontFamily: 'Outfit_400Regular',
    fontSize: 16,
    color: FG,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2D4C0',
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 14,
  },
  saveBtn: {
    backgroundColor: ACCENT,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
  },
  saveBtnDisabled: {
    opacity: 0.45,
  },
  saveBtnText: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 16,
    color: '#FFFFFF',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#F0E2D0',
  },
  rowLast: {
    borderBottomWidth: 0,
  },
  rowDanger: {
    fontFamily: 'Outfit_400Regular',
    fontSize: 15,
    color: '#B3513D',
  },
  brandFooter: {
    alignItems: 'center',
    paddingTop: 28,
    paddingBottom: 8,
    opacity: 0.72,
  },
  brandLogo: {
    opacity: 0.9,
  },
});
