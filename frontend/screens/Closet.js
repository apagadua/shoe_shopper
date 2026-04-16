import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSavedShoes } from '../SavedShoesContext';
import { useOwnedShoes } from '../ClosetContext';

const FIT_STATUS_COLOR = {
  PERFECT: '#2E7D32',
  GOOD: '#558B2F',
  ACCEPTABLE: '#F57F17',
  MARGINAL: '#E64A19',
  POOR: '#B71C1C',
  REJECTED: '#9E9E9E',
};

const OWNED_ICON_ACTIVE = '#5D8A7E';

export default function Closet() {
  const { toggleSaved, isSaved } = useSavedShoes();
  const { ownedMap, toggleOwned, isOwned } = useOwnedShoes();
  const items = Object.values(ownedMap).filter(Boolean);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {items.length === 0 ? (
        <View style={styles.emptyState}>
          <View style={styles.emptyIcon}>
            <Ionicons name="bag-handle-outline" size={48} color="#B0A499" />
          </View>
          <Text style={styles.emptyTitle}>No owned shoes yet</Text>
          <Text style={styles.emptySubtitle}>
            Mark shoes you own from Recommendations (bag icon) to track them here.
          </Text>
        </View>
      ) : (
        items.map((item) => {
          const saved = isSaved(item.id);
          const owned = isOwned(item.id);
          const statusColor = FIT_STATUS_COLOR[item.fit_status] || '#6B5F52';
          return (
            <View key={String(item.id)} style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.brand}>{item.brand}</Text>
                <View style={styles.cardActions}>
                  <TouchableOpacity
                    style={styles.iconButton}
                    onPress={() => toggleSaved(item)}
                    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                  >
                    <Ionicons
                      name={saved ? 'heart' : 'heart-outline'}
                      size={20}
                      color={saved ? '#C28A5B' : '#B0A499'}
                    />
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.iconButton}
                    onPress={() => toggleOwned(item)}
                    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                  >
                    <Ionicons
                      name={owned ? 'bag-handle' : 'bag-handle-outline'}
                      size={20}
                      color={owned ? OWNED_ICON_ACTIVE : '#B0A499'}
                    />
                  </TouchableOpacity>
                </View>
              </View>
              <Text style={styles.name}>{item.model}</Text>

              {item.fit_status && item.fit_status !== 'UNSCORED' && (
                <View style={styles.fitRow}>
                  <View style={[styles.fitBadge, { backgroundColor: statusColor + '20', borderColor: statusColor }]}>
                    <Text style={[styles.fitScore, { color: statusColor }]}>{item.fit_score}</Text>
                    <Text style={[styles.fitLabel, { color: statusColor }]}>{item.fit_status_label}</Text>
                  </View>
                  {item.fit_profile ? (
                    <Text style={styles.fitProfile}>{item.fit_profile.replace(/_/g, ' ')}</Text>
                  ) : null}
                </View>
              )}

              {item.shoe_image_url ? (
                <Image source={{ uri: item.shoe_image_url }} style={styles.shoeImage} resizeMode="contain" />
              ) : (
                <View style={styles.shoePhotoPlaceholder}>
                  <Ionicons name="image-outline" size={32} color="#B0A499" />
                  <Text style={styles.shoePhotoPlaceholderText}>Shoe photo</Text>
                </View>
              )}

              {item.product_url ? (
                <TouchableOpacity style={styles.primaryButton} onPress={() => Linking.openURL(item.product_url)}>
                  <Text style={styles.primaryButtonText}>View details</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          );
        })
      )}
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
    paddingTop: 24,
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
  cardActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  iconButton: { paddingHorizontal: 4, paddingVertical: 2 },
  brand: { fontSize: 13, color: '#4F453C', fontWeight: '600' },
  name: { fontSize: 17, fontWeight: '700', color: '#2F2A25', marginBottom: 10 },
  fitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  fitBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    borderWidth: 1,
  },
  fitScore: { fontSize: 16, fontWeight: '700' },
  fitLabel: { fontSize: 12, fontWeight: '600' },
  fitProfile: { fontSize: 11, color: '#9B8E82', textTransform: 'uppercase', letterSpacing: 0.4 },
  shoeImage: {
    width: '100%',
    height: 160,
    borderRadius: 12,
    marginBottom: 12,
    backgroundColor: '#F0E2D0',
  },
  shoePhotoPlaceholder: {
    height: 120,
    backgroundColor: '#F0E2D0',
    borderRadius: 12,
    marginBottom: 12,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E2D4C0',
    borderStyle: 'dashed',
  },
  shoePhotoPlaceholderText: { fontSize: 12, color: '#6B5F52', marginTop: 6 },
  primaryButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
  },
  primaryButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '600' },
});
