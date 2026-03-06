import * as SecureStore from 'expo-secure-store';
import React, { useState } from 'react';
import { Alert, View, Text, StyleSheet, TouchableOpacity, ScrollView, Image } from 'react-native';
import { CommonActions } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { API_BASE_URL } from '../config/api';

export default function ProfileScreen({ navigation }) {
  // Placeholder: no profile image yet; will wire to auth/picker later
  const profileImageUri = null;
  const [apiStatus, setApiStatus] = useState('Not tested yet');
  const [shoePreview, setShoePreview] = useState([]);

  const handleChangePhoto = () => {
    // TODO: open image picker / camera for profile photo
  };

  const signOutAndReset = async () => {
    await SecureStore.deleteItemAsync('authToken');
    await GoogleSignin.signOut();
    const root = navigation.getParent()?.getParent();
    root?.dispatch(CommonActions.reset({ index: 0, routes: [{ name: 'Welcome' }] }));
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

  const handleTestBackend = async () => {
    setApiStatus('Checking backend...');
    try {
      const [healthRes, shoesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/health/`),
        fetch(`${API_BASE_URL}/api/shoes/`),
      ]);

      if (!healthRes.ok || !shoesRes.ok) {
        setApiStatus(`API error: health ${healthRes.status}, shoes ${shoesRes.status}`);
        return;
      }

      const healthJson = await healthRes.json();
      const shoesJson = await shoesRes.json();
      const preview = shoesJson.slice(0, 3).map((shoe) => `${shoe.brand} ${shoe.model}`);
      setShoePreview(preview);
      setApiStatus(`Connected: ${healthJson.shoe_count} shoes in DB`);
    } catch (error) {
      setApiStatus(`Connection failed: ${error.message}`);
      setShoePreview([]);
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.title}>Profile</Text>
      <Text style={styles.subtitle}>
        Your account and preferences.
      </Text>

      {/* Profile picture + change option */}
      <View style={styles.photoSection}>
        <TouchableOpacity
          style={styles.avatarWrapper}
          onPress={handleChangePhoto}
          activeOpacity={0.85}
        >
          {profileImageUri ? (
            <Image source={{ uri: profileImageUri }} style={styles.avatar} />
          ) : (
            <View style={styles.avatarPlaceholder}>
              <Ionicons name="person" size={48} color="#A39380" />
            </View>
          )}
          <View style={styles.changePhotoBadge}>
            <Ionicons name="camera" size={16} color="#FFFFFF" />
            <Text style={styles.changePhotoText}>Change photo</Text>
          </View>
        </TouchableOpacity>
      </View>

      {/* Account */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Account</Text>
        <TouchableOpacity style={styles.rowButton} onPress={handleDeleteAccount}>
          <Text style={styles.rowButtonTextDanger}>Delete account</Text>
          <Ionicons name="chevron-forward" size={20} color="#A39380" />
        </TouchableOpacity>
        <TouchableOpacity style={[styles.rowButton, styles.rowButtonLast]} onPress={handleSignOut}>
          <Text style={styles.rowButtonTextDanger}>Sign out</Text>
          <Ionicons name="log-out-outline" size={20} color="#B3513D" />
        </TouchableOpacity>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Backend Smoke Test</Text>
        <Text style={styles.helpText}>Base URL: {API_BASE_URL}</Text>
        <Text style={styles.helpText}>{apiStatus}</Text>
        {shoePreview.map((line) => (
          <Text key={line} style={styles.helpText}>- {line}</Text>
        ))}
        <TouchableOpacity style={[styles.rowButton, styles.rowButtonLast]} onPress={handleTestBackend}>
          <Text style={styles.rowButtonText}>Test /api/health and /api/shoes</Text>
          <Ionicons name="cloud-done-outline" size={20} color="#A39380" />
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5EFE6',
  },
  content: {
    paddingTop: 24,
    paddingHorizontal: 24,
    paddingBottom: 40,
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    color: '#6B5F52',
    marginBottom: 28,
    lineHeight: 21,
  },
  photoSection: {
    alignItems: 'center',
    marginBottom: 28,
  },
  avatarWrapper: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatar: {
    width: 100,
    height: 100,
    borderRadius: 50,
  },
  avatarPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#F0E2D0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  changePhotoBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 12,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 999,
    backgroundColor: '#C28A5B',
  },
  changePhotoText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  card: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2F2A25',
    marginBottom: 4,
    paddingHorizontal: 14,
    paddingTop: 4,
  },
  rowButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#F0E2D0',
  },
  rowButtonLast: {
    borderBottomWidth: 0,
  },
  rowButtonText: {
    fontSize: 15,
    color: '#2F2A25',
  },
  rowButtonTextDanger: {
    fontSize: 15,
    color: '#B3513D',
    fontWeight: '500',
  },
  helpText: {
    fontSize: 14,
    color: '#6B5F52',
    paddingHorizontal: 14,
    paddingBottom: 8,
  },
});
