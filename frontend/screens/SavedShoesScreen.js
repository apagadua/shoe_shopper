import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSavedShoes } from '../SavedShoesContext';
import { ATTRIBUTE_FILTERS } from '../constants/attributes';
import { emptyStateStyles } from '../styles/emptyState';

export default function SavedShoesScreen() {
  const { savedShoes, toggleSaved, isSaved } = useSavedShoes();
  const hasSaved = savedShoes && savedShoes.length > 0;

  if (!hasSaved) {
    return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.emptyState}>
          <View style={styles.emptyIcon}>
            <Ionicons name="heart-outline" size={48} color="#B0A499" />
          </View>
          <Text style={styles.emptyTitle}>Your wishlist is empty</Text>
          <Text style={styles.emptySubtitle}>
            Save shoes from Recommendations to see them here.
          </Text>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* ——— Shoe cards (Saved Shoes): same layout as Recommendations — brand, heart, name, size rows, tags, View details ——— */}
      {savedShoes.map((shoe) => {
        const functionTags = shoe.functionPath || [];
        const cardTags = [];

        // Match Recommendations screen behavior: show attribute tags
        // plus the function path tags, without extra silhouette tags.
        ATTRIBUTE_FILTERS.forEach(({ key, label }) => {
          if (shoe.attributes && shoe.attributes[key] && !cardTags.includes(label)) {
            cardTags.push(label);
          }
        });

        functionTags.forEach((t) => {
          if (!cardTags.includes(t)) cardTags.push(t);
        });

        const saved = isSaved(shoe.id);

        return (
          <View key={shoe.id} style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.brand}>{shoe.brand}</Text>
              <TouchableOpacity
                style={styles.heartButton}
                onPress={() => toggleSaved(shoe)}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <Ionicons
                  name={saved ? 'heart' : 'heart-outline'}
                  size={20}
                  color={saved ? '#C28A5B' : '#B0A499'}
                />
              </TouchableOpacity>
            </View>
            <Text style={styles.name}>{shoe.name}</Text>
            <View style={styles.sizeRow}>
              <Text style={styles.sizeLabel}>Typical size</Text>
              <Text style={styles.sizeValue}>{shoe.typicalSize}</Text>
            </View>
            <View style={styles.sizeRow}>
              <Text style={styles.sizeLabel}>Length</Text>
              <Text style={styles.sizeValue}>{shoe.lengthCm} cm</Text>
            </View>
            <View style={[styles.sizeRow, styles.sizeRowLast]}>
              <Text style={styles.sizeLabel}>Width</Text>
              <Text style={styles.sizeValue}>{shoe.widthCm} cm</Text>
            </View>
            {cardTags.length > 0 && (
              <View style={styles.attrTags}>
                {cardTags.map((t) => (
                  <View key={t} style={styles.attrTag}>
                    <Text style={styles.attrTagText}>{t}</Text>
                  </View>
                ))}
              </View>
            )}
            <TouchableOpacity style={styles.primaryButton} onPress={() => {}}>
              <Text style={styles.primaryButtonText}>View details</Text>
            </TouchableOpacity>
          </View>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  ...emptyStateStyles,
  container: {
    flex: 1,
    backgroundColor: '#F5EFE6',
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 40,
  },
  /* ——— Shoe card styles (same layout as RecommendationsScreen) ——— */
  card: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: '#E2D4C0',
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  brand: {
    fontSize: 13,
    fontWeight: '600',
    color: '#4F453C',
  },
  name: {
    fontSize: 17,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 10,
  },
  sizeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: '#F0E2D0',
  },
  sizeRowLast: {
    borderBottomWidth: 0,
    marginBottom: 12,
  },
  sizeLabel: {
    fontSize: 13,
    color: '#6B5F52',
  },
  sizeValue: {
    fontSize: 13,
    color: '#2F2A25',
    fontWeight: '600',
  },
  heartButton: {
    paddingHorizontal: 4,
    paddingVertical: 2,
  },
  attrTags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 12,
  },
  attrTag: {
    backgroundColor: '#F0E2D0',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  attrTagText: {
    fontSize: 11,
    color: '#6B5F52',
  },
  primaryButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
});
