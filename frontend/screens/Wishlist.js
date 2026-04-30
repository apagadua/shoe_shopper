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
import { useOwnedShoes } from '../OwnedShoesContext';

const FIT_STATUS_COLOR = {
  PERFECT: '#2E7D32',
  GOOD: '#558B2F',
  ACCEPTABLE: '#F57F17',
  MARGINAL: '#E64A19',
  POOR: '#B71C1C',
  REJECTED: '#9E9E9E',
};

const OWNED_ICON_ACTIVE = '#5D8A7E';

/** Matches Recommendations — readable emerald on warm panels, distinct from PERFECT fit green. */
const PRICE_DISPLAY_COLOR = '#047857';

const COLOR_SWATCH_MAP = {
  black: '#212121',
  white: '#F4F4F4',
  red: '#D94A4A',
  blue: '#4E7EDB',
  navy: '#213A73',
  green: '#4D8A4E',
  yellow: '#F1C40F',
  orange: '#E67E22',
  pink: '#D673B3',
  purple: '#8E5BBF',
  brown: '#7A5A42',
  tan: '#B78B5A',
  gray: '#9AA1AA',
  grey: '#9AA1AA',
  silver: '#BFC6CF',
  gold: '#C8A74E',
  beige: '#D6C3A1',
  cream: '#E8DEC5',
  khaki: '#B9AA79',
  olive: '#7A8450',
  moss: '#6A7B4E',
  charcoal: '#4A4A4A',
  teal: '#3D8E8B',
};

function getColorSwatch(colorName = '') {
  const normalized = colorName.toLowerCase();
  const match = Object.keys(COLOR_SWATCH_MAP).find((key) => normalized.includes(key));
  return match ? COLOR_SWATCH_MAP[match] : '#C9B8A7';
}

function formatUsd(price) {
  if (price == null || price === '') return '—';
  const n = typeof price === 'string' ? parseFloat(price) : Number(price);
  if (Number.isNaN(n)) return '—';
  return `$${n.toFixed(2)}`;
}

function tagsForItem(item) {
  const a = item.function_tags || [];
  const b = item.style_tags || [];
  const out = [];
  for (const t of [...a, ...b]) {
    if (t && !out.includes(t)) out.push(t);
  }
  return out;
}

export default function Wishlist() {
  const { savedMap, toggleSaved, isSaved } = useSavedShoes();
  const { ownedMap, toggleOwned, isOwned } = useOwnedShoes();
  const items = Object.values(savedMap).filter((item) => item && !ownedMap[item.id]);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {items.length === 0 ? (
        <View style={styles.emptyState}>
          <View style={styles.emptyIcon}>
            <Ionicons name="heart-outline" size={48} color="#B0A499" />
          </View>
          <Text style={styles.emptyTitle}>Your wishlist is empty</Text>
          <Text style={styles.emptySubtitle}>
            Save shoes from Recommendations to see them here.
          </Text>
        </View>
      ) : (
        items.map((item) => {
          const saved = isSaved(item.id);
          const owned = isOwned(item.id);
          const statusColor = FIT_STATUS_COLOR[item.fit_status] || '#6B5F52';
          const sizeValue = item.recommended_size ?? item.us_size ?? item.size;
          const priceText = formatUsd(item.price_usd);
          const cardTags = tagsForItem(item);
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
                    onPress={() => {
                      const ownedNow = isOwned(item.id);
                      if (ownedNow) {
                        toggleOwned(item);
                        return;
                      }
                      // Move Wishlist -> Closet and remember to restore when unowned.
                      toggleOwned({ ...item, returnToWishlistOnRemove: true });
                      if (isSaved(item.id)) {
                        toggleSaved(item);
                      }
                    }}
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
              {item.colorway ? (
                <View style={styles.colorRow}>
                  <Text style={styles.colorLabel}>Color</Text>
                  <View style={[styles.colorSwatch, { backgroundColor: getColorSwatch(item.colorway) }]} />
                </View>
              ) : null}

              {item.fit_status && item.fit_status !== 'UNSCORED' && (
                <View style={styles.fitRow}>
                  <View style={[styles.fitBadge, { backgroundColor: statusColor + '20', borderColor: statusColor }]}>
                    <Text style={[styles.fitScore, { color: statusColor }]}>{item.fit_score}</Text>
                    <Text style={[styles.fitLabel, { color: statusColor }]}>{item.fit_status_label}</Text>
                  </View>
                  <Text style={styles.fitProfile}>{item.fit_profile?.replace(/_/g, ' ')}</Text>
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

              <View style={styles.keyFacts}>
                <View style={styles.keyFactCol}>
                  <View style={styles.keyFactLabelRow}>
                    <Ionicons name="pricetag" size={11} color={PRICE_DISPLAY_COLOR} />
                    <Text style={[styles.keyFactLabel, styles.keyFactLabelPrice]}>Price</Text>
                  </View>
                  <Text
                    style={[styles.keyFactValuePrice, priceText === '—' && styles.keyFactValuePriceUnavailable]}
                    numberOfLines={1}
                  >
                    {priceText}
                  </Text>
                </View>
                <View style={styles.keyFactDivider} />
                <View style={styles.keyFactCol}>
                  <View style={styles.keyFactLabelRow}>
                    <Ionicons name="footsteps" size={11} color="#9A6645" />
                    <Text style={styles.keyFactLabel}>Size</Text>
                  </View>
                  <Text style={styles.keyFactValue} numberOfLines={1}>
                    {sizeValue != null && sizeValue !== '' ? `US ${sizeValue}` : '—'}
                  </Text>
                </View>
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
  name: { fontSize: 17, fontWeight: '700', color: '#2F2A25', marginBottom: 2 },
  colorRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  colorLabel: { fontSize: 12, color: '#8C7B6E' },
  colorSwatch: {
    width: 14,
    height: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#D8C9B8',
  },
  keyFacts: {
    flexDirection: 'row',
    alignItems: 'stretch',
    backgroundColor: 'rgba(194, 138, 91, 0.12)',
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: 'rgba(194, 138, 91, 0.45)',
    paddingVertical: 7,
    paddingHorizontal: 8,
    marginBottom: 10,
  },
  keyFactCol: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  keyFactLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginBottom: 3,
  },
  keyFactLabel: {
    fontSize: 8,
    fontWeight: '800',
    color: '#7A6A5C',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  keyFactLabelPrice: {
    color: PRICE_DISPLAY_COLOR,
  },
  keyFactValue: {
    fontSize: 17,
    fontWeight: '800',
    color: '#2F2A25',
    letterSpacing: -0.25,
  },
  keyFactValuePrice: {
    fontSize: 18,
    fontWeight: '800',
    color: PRICE_DISPLAY_COLOR,
    letterSpacing: -0.35,
  },
  keyFactValuePriceUnavailable: {
    color: '#8C7B6E',
    fontWeight: '700',
  },
  keyFactDivider: {
    width: 1,
    backgroundColor: 'rgba(194, 138, 91, 0.35)',
    marginVertical: 0,
  },
  attrTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 },
  attrTag: { backgroundColor: '#F0E2D0', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  attrTagText: { fontSize: 11, color: '#6B5F52' },
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
