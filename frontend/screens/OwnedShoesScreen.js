import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function OwnedShoesScreen() {
  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.emptyState}>
        <View style={styles.emptyIcon}>
          <Ionicons name="archive-outline" size={48} color="#B0A499" />
        </View>
        <Text style={styles.emptyTitle}>No owned shoes yet</Text>
        <Text style={styles.emptySubtitle}>
          Add shoes you own to get better recommendations and track your closet.
        </Text>
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
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 40,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 48,
  },
  emptyIcon: {
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#2F2A25',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#6B5F52',
    textAlign: 'center',
    lineHeight: 20,
  },
});
