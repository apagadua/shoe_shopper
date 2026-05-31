import React, { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  Pressable,
  TouchableOpacity,
  ScrollView,
  Image,
  Animated,
  Dimensions,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Path, Circle } from 'react-native-svg';
import { API_BASE_URL } from '../config/api';
import ShoeCardKeyFacts from './ShoeCardKeyFacts';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const CARD_MAX_WIDTH = Math.min(400, SCREEN_WIDTH - 40);
const CARD_MAX_HEIGHT = SCREEN_HEIGHT * 0.82;

const FIT_STATUS_COLOR = {
  PERFECT: '#2E7D32',
  GOOD: '#558B2F',
  ACCEPTABLE: '#F57F17',
  MARGINAL: '#E64A19',
  POOR: '#B71C1C',
  REJECTED: '#9E9E9E',
};

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

function resolveImageUrl(uri) {
  if (!uri) return null;
  if (uri.includes('converse.com') || uri.includes('demandware.static')) {
    return `${API_BASE_URL}/api/proxy-image/?url=${encodeURIComponent(uri)}`;
  }
  return uri;
}

function getColorSwatch(colorName = '') {
  const normalized = String(colorName).toLowerCase();
  const match = Object.keys(COLOR_SWATCH_MAP).find((key) => normalized.includes(key));
  return match ? COLOR_SWATCH_MAP[match] : '#C9B8A7';
}

function getColorwayPalette(cw = {}) {
  if (Array.isArray(cw.color_palette_hex) && cw.color_palette_hex.length > 0) {
    return cw.color_palette_hex.slice(0, 3);
  }
  const single = cw.dominant_color_hex || getColorSwatch(cw.name) || '#C9B8A7';
  return [single];
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

// SVG viewBox "0 0 18 18", center (9, 9), radius 8.5
const SWATCH_R = 8.5;
const SWATCH_C = 9;

function swatchPointOnCircle(angleDeg) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: SWATCH_C + SWATCH_R * Math.cos(rad), y: SWATCH_C + SWATCH_R * Math.sin(rad) };
}

function describeSwatchSlice(index, count) {
  const startAngle = -90 + (index * 360) / count;
  const endAngle   = -90 + ((index + 1) * 360) / count;
  const start = swatchPointOnCircle(startAngle);
  const end   = swatchPointOnCircle(endAngle);
  const largeArc = (360 / count) > 180 ? 1 : 0;
  return [
    `M ${SWATCH_C} ${SWATCH_C}`,
    `L ${start.x.toFixed(4)} ${start.y.toFixed(4)}`,
    `A ${SWATCH_R} ${SWATCH_R} 0 ${largeArc} 1 ${end.x.toFixed(4)} ${end.y.toFixed(4)}`,
    'Z',
  ].join(' ');
}

function ColorwaySwatch({ colors, active, onPress }) {
  const palette = Array.isArray(colors) && colors.length > 0 ? colors.slice(0, 3) : ['#C9B8A7'];

  if (palette.length === 1) {
    return (
      <TouchableOpacity activeOpacity={0.75} onPress={onPress}>
        <View
          style={[
            styles.swatchCircle,
            active && styles.swatchCircleActive,
            { backgroundColor: palette[0] },
          ]}
        />
      </TouchableOpacity>
    );
  }

  const borderColor = active ? '#9A6645' : '#D9CCBD';
  const borderWidth = active ? 2 : 1;

  return (
    <TouchableOpacity activeOpacity={0.75} onPress={onPress}>
      <View style={[styles.swatchPieContainer, active && { transform: [{ scale: 1.1 }] }]}>
        <Svg width={18} height={18} viewBox="0 0 18 18">
          {palette.map((color, index) => (
            <Path
              key={`${color}-${index}`}
              d={describeSwatchSlice(index, palette.length)}
              fill={color}
            />
          ))}
          <Circle cx={SWATCH_C} cy={SWATCH_C} r={SWATCH_R} fill="none" stroke={borderColor} strokeWidth={borderWidth} />
        </Svg>
      </View>
    </TouchableOpacity>
  );
}

/**
 * Centered shoe detail overlay with dimmed backdrop.
 * Dismiss via backdrop tap or close button.
 */
function ShoeDetailModal({
  visible,
  item,
  onClose,
  isSaved,
  isOwned,
  onToggleSaved,
  onToggleOwned,
}, ref) {
  const backdropAnim = useRef(new Animated.Value(0)).current;
  const cardAnim = useRef(new Animated.Value(0)).current;
  const [activeColorwayIndex, setActiveColorwayIndex] = useState(0);
  const [imageFailed, setImageFailed] = useState(false);
  const closingRef = useRef(false);

  const colorways = item?.colorway_options?.length ? item.colorway_options : [];
  const hasColorways = colorways.length > 0;
  const activeVariant = hasColorways ? colorways[activeColorwayIndex] : null;

  const baseSize = item?.recommended_size ?? item?.us_size ?? item?.size;
  const imageUrlRaw = activeVariant?.image_url
    ? activeVariant.image_url
    : (item?.shoe_image_url && String(item.shoe_image_url).trim()) || null;
  const imageUrl = imageUrlRaw && !imageFailed ? resolveImageUrl(imageUrlRaw) : null;
  const priceUsd = hasColorways
    ? (activeVariant?.sizes?.[0]?.price_usd ?? item?.price_usd)
    : item?.price_usd;
  const sizeForFacts = hasColorways
    ? (activeVariant?.sizes?.[0]?.us_size ?? baseSize)
    : baseSize;
  const detailsUrl = hasColorways
    ? (activeVariant?.product_url ?? item?.product_url)
    : item?.product_url;
  const colorwayLabel = hasColorways ? (activeVariant?.name ?? null) : item?.colorway;

  const animateIn = useCallback(() => {
    backdropAnim.setValue(0);
    cardAnim.setValue(0);
    Animated.parallel([
      Animated.timing(backdropAnim, {
        toValue: 1,
        duration: 260,
        useNativeDriver: true,
      }),
      Animated.spring(cardAnim, {
        toValue: 1,
        friction: 9,
        tension: 68,
        useNativeDriver: true,
      }),
    ]).start();
  }, [backdropAnim, cardAnim]);

  const animateOut = useCallback(
    (thenClose) => {
      if (closingRef.current) return;
      closingRef.current = true;
      Animated.parallel([
        Animated.timing(backdropAnim, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(cardAnim, {
          toValue: 0,
          duration: 180,
          useNativeDriver: true,
        }),
      ]).start(() => {
        closingRef.current = false;
        thenClose?.();
      });
    },
    [backdropAnim, cardAnim]
  );

  const handleClose = useCallback(() => {
    animateOut(onClose);
  }, [animateOut, onClose]);

  useImperativeHandle(ref, () => ({ dismiss: handleClose }), [handleClose]);

  useEffect(() => {
    if (visible && item) {
      setActiveColorwayIndex(0);
      setImageFailed(false);
      closingRef.current = false;
      animateIn();
    }
  }, [visible, item?.id, animateIn]);

  useEffect(() => {
    setImageFailed(false);
  }, [activeColorwayIndex, item?.id]);

  if (!item) return null;

  const saved = isSaved(item.id);
  const owned = isOwned(item.id);
  const statusColor = FIT_STATUS_COLOR[item.fit_status] || '#6B5F52';
  const cardTags = tagsForItem(item);

  const selectedCardItem = {
    ...item,
    colorway: colorwayLabel ?? null,
    product_url: detailsUrl || item.product_url,
    shoe_image_url: imageUrlRaw || item.shoe_image_url,
    price_usd: priceUsd ?? item.price_usd,
    recommended_size: sizeForFacts ?? item.recommended_size,
  };

  const backdropOpacity = backdropAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0.48],
  });
  const cardScale = cardAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0.92, 1],
  });
  const cardOpacity = cardAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 1],
  });
  const cardTranslateY = cardAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [24, 0],
  });

  return (
    <Modal
      visible={visible}
      transparent
      animationType="none"
      statusBarTranslucent
      onRequestClose={handleClose}
    >
      <View style={styles.root}>
        <Pressable style={StyleSheet.absoluteFill} onPress={handleClose} accessibilityRole="button" accessibilityLabel="Close shoe details">
          <Animated.View style={[styles.backdrop, { opacity: backdropOpacity }]} />
        </Pressable>

        <View style={styles.centerStage} pointerEvents="box-none">
          <Animated.View
            style={[
              styles.cardShell,
              {
                opacity: cardOpacity,
                transform: [{ scale: cardScale }, { translateY: cardTranslateY }],
              },
            ]}
          >
            <TouchableOpacity
              style={styles.closeButton}
              onPress={handleClose}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
              accessibilityRole="button"
              accessibilityLabel="Close"
            >
              <Ionicons name="close" size={22} color="#6B5F52" />
            </TouchableOpacity>

            <ScrollView
              style={styles.cardScroll}
              contentContainerStyle={styles.cardScrollContent}
              showsVerticalScrollIndicator={false}
              bounces={false}
            >
              <View style={styles.cardHeader}>
                <Text style={styles.brand}>{item.brand}</Text>
                <View style={styles.cardActions}>
                  <TouchableOpacity
                    style={styles.iconButton}
                    onPress={() => onToggleSaved?.(selectedCardItem)}
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
                    onPress={() => onToggleOwned?.(selectedCardItem)}
                    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                  >
                    <Ionicons
                      name={owned ? 'bag-handle' : 'bag-handle-outline'}
                      size={20}
                      color={owned ? '#C28A5B' : '#B0A499'}
                    />
                  </TouchableOpacity>
                </View>
              </View>

              <Text style={styles.name}>{item.model}</Text>
              {colorwayLabel ? <Text style={styles.colorway}>{colorwayLabel}</Text> : null}

              {hasColorways && (
                <View style={styles.colorwayPills}>
                  {colorways.map((cw, index) => (
                    <ColorwaySwatch
                      key={`${item.id}-${cw.goat_id ?? ''}-${cw.sku ?? index}`}
                      colors={getColorwayPalette(cw)}
                      active={index === activeColorwayIndex}
                      onPress={() => setActiveColorwayIndex(index)}
                    />
                  ))}
                </View>
              )}

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

              {imageUrl ? (
                <Image
                  source={{ uri: imageUrl }}
                  style={styles.shoeImage}
                  resizeMode="contain"
                  onError={() => setImageFailed(true)}
                />
              ) : (
                <View style={styles.shoePhotoPlaceholder}>
                  <Ionicons name="image-outline" size={32} color="#B0A499" />
                  <Text style={styles.shoePhotoPlaceholderText}>Shoe photo</Text>
                </View>
              )}

              <ShoeCardKeyFacts priceUsd={priceUsd} sizeValue={sizeForFacts} />

              {cardTags.length > 0 && (
                <View style={styles.attrTags}>
                  {cardTags.map((t) => (
                    <View key={t} style={styles.attrTag}>
                      <Text style={styles.attrTagText}>{t}</Text>
                    </View>
                  ))}
                </View>
              )}

              {detailsUrl ? (
                <TouchableOpacity style={styles.primaryButton} onPress={() => Linking.openURL(detailsUrl)}>
                  <Text style={styles.primaryButtonText}>View details</Text>
                </TouchableOpacity>
              ) : null}
            </ScrollView>
          </Animated.View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#1A1612',
  },
  centerStage: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 32,
  },
  cardShell: {
    width: CARD_MAX_WIDTH,
    maxHeight: CARD_MAX_HEIGHT,
    backgroundColor: '#FFFBF5',
    borderRadius: 22,
    borderWidth: 1,
    borderColor: '#E2D4C0',
    shadowColor: '#2F2A25',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 12,
    overflow: 'hidden',
  },
  closeButton: {
    position: 'absolute',
    top: 10,
    right: 10,
    zIndex: 2,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: 'rgba(255, 251, 245, 0.95)',
    borderWidth: 1,
    borderColor: '#E2D4C0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardScroll: {
    maxHeight: CARD_MAX_HEIGHT,
  },
  cardScrollContent: {
    padding: 18,
    paddingTop: 20,
    paddingBottom: 22,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
    paddingRight: 36,
  },
  cardActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  iconButton: { paddingHorizontal: 4, paddingVertical: 2 },
  brand: { fontSize: 13, color: '#4F453C', fontWeight: '600' },
  name: { fontSize: 17, fontWeight: '700', color: '#2F2A25', marginBottom: 2 },
  colorway: { fontSize: 12, color: '#8C7B6E', marginBottom: 10 },
  colorwayPills: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 10 },
  swatchCircle: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1,
    borderColor: '#D9CCBD',
    overflow: 'hidden',
  },
  swatchCircleActive: {
    borderWidth: 2,
    borderColor: '#9A6645',
    transform: [{ scale: 1.1 }],
  },
  swatchPieContainer: {
    width: 18,
    height: 18,
    borderRadius: 9,
    overflow: 'hidden',
  },
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
    height: 168,
    borderRadius: 12,
    marginBottom: 12,
    backgroundColor: '#F0E2D0',
  },
  shoePhotoPlaceholder: {
    height: 128,
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
  attrTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 },
  attrTag: { backgroundColor: '#F0E2D0', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  attrTagText: { fontSize: 11, color: '#6B5F52' },
  primaryButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
  },
  primaryButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '600' },
});

export default forwardRef(ShoeDetailModal);
