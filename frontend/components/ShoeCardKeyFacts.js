import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

/** Price accent: deep emerald on warm cream cards (shared across Recommendations / Wishlist / Closet). */
export const SHOE_CARD_PRICE_COLOR = '#157D5C';
const SIZE_ICON_COLOR = '#9A6645';

export function formatShoeCardUsd(price) {
  if (price == null || price === '') return '—';
  const n = typeof price === 'string' ? parseFloat(price) : Number(price);
  if (Number.isNaN(n)) return '—';
  return `$${n.toFixed(2)}`;
}

/**
 * Price (left) then Size (right) — keep in sync across all shoe list cards.
 * @param {{ priceUsd: unknown, sizeValue: unknown }} props
 */
export default function ShoeCardKeyFacts({ priceUsd, sizeValue }) {
  const priceStr = formatShoeCardUsd(priceUsd);
  const sizeStr = sizeValue != null && sizeValue !== '' ? `US ${sizeValue}` : '—';

  return (
    <View style={styles.keyFacts}>
      <View style={styles.keyFactCol}>
        <View style={styles.keyFactLabelRow}>
          <Ionicons name="pricetag" size={11} color={SHOE_CARD_PRICE_COLOR} />
          <Text style={[styles.keyFactLabel, styles.keyFactLabelPrice]}>Price</Text>
        </View>
        <Text
          style={[styles.keyFactValuePrice, priceStr === '—' && styles.keyFactValuePriceMuted]}
          numberOfLines={1}
        >
          {priceStr}
        </Text>
      </View>
      <View style={styles.keyFactDivider} />
      <View style={styles.keyFactCol}>
        <View style={styles.keyFactLabelRow}>
          <Ionicons name="footsteps" size={11} color={SIZE_ICON_COLOR} />
          <Text style={styles.keyFactLabel}>Size</Text>
        </View>
        <Text style={styles.keyFactValue} numberOfLines={1}>
          {sizeStr}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
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
    color: SHOE_CARD_PRICE_COLOR,
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
    color: SHOE_CARD_PRICE_COLOR,
    letterSpacing: -0.35,
  },
  keyFactValuePriceMuted: {
    color: '#8C7B6E',
    fontWeight: '700',
  },
  keyFactDivider: {
    width: 1,
    backgroundColor: 'rgba(194, 138, 91, 0.35)',
    marginVertical: 0,
  },
});
