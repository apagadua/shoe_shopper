import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image } from 'react-native';
import { CommonActions } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';

export default function ProfileScreen({ navigation }) {
  // Placeholder: no profile image yet; will wire to auth/picker later
  const profileImageUri = null;

  const handleChangePhoto = () => {
    // TODO: open image picker / camera for profile photo
  };

  const handleManageEmailPassword = () => {
    // TODO: navigate to manage email & password screen
  };

  const handleDeleteAccount = () => {
    // TODO: show confirm dialog, then delete account and sign out
  };

  const handleSignOut = () => {
    // TODO: clear auth state; for now go to Welcome (root stack is 3 levels up: Profile > ProfileStack > Tab > Root)
    const root = navigation.getParent()?.getParent()?.getParent();
    if (root) {
      root.dispatch(CommonActions.reset({ index: 0, routes: [{ name: 'Welcome' }] }));
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
        <TouchableOpacity style={styles.rowButton} onPress={handleManageEmailPassword}>
          <Text style={styles.rowButtonText}>Manage email & password</Text>
          <Ionicons name="chevron-forward" size={20} color="#A39380" />
        </TouchableOpacity>
        <TouchableOpacity style={styles.rowButton} onPress={handleDeleteAccount}>
          <Text style={styles.rowButtonTextDanger}>Delete account</Text>
          <Ionicons name="chevron-forward" size={20} color="#A39380" />
        </TouchableOpacity>
        <TouchableOpacity style={[styles.rowButton, styles.rowButtonLast]} onPress={handleSignOut}>
          <Text style={styles.rowButtonTextDanger}>Sign out</Text>
          <Ionicons name="log-out-outline" size={20} color="#B3513D" />
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
});
