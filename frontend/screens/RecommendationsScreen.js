import React, { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, ScrollView, TouchableOpacity,
  Dimensions, Animated, Pressable, ActivityIndicator,
  Image, Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Path, Circle } from 'react-native-svg';
import * as SecureStore from 'expo-secure-store';
import { useFocusEffect } from '@react-navigation/native';
import { useSavedShoes } from '../SavedShoesContext';
import { useOwnedShoes } from '../OwnedShoesContext';
import { ATTRIBUTE_FILTERS } from '../constants/attributes';
import { API_BASE_URL } from '../config/api';
import { resolveImageUrl } from '../utils/resolveImageUrl';
import { animateListChange } from '../utils/listAnimations';
import ShoeCardKeyFacts from '../components/ShoeCardKeyFacts';
import {
  readRecommendationsCache,
  writeRecommendationsCache,
  isCacheStale,
} from '../services/recommendationsCache';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const DRAWER_WIDTH = Math.min(172, SCREEN_WIDTH * 0.5);
const CAROUSEL_WIDTH = SCREEN_WIDTH - 48;

const FUNCTION_CATEGORIES = {
  Athletic: ['Running', 'Training', 'Basketball', 'Soccer', 'Tennis', 'Skate', 'Hiking'],
  Casual: ['Sneakers', 'Boots', 'Slip-ons'],
  Work: ['Indoor', 'Outdoor'],
  Formal: [],
};

const SILHOUETTE_CATEGORIES = {
  Boot: ['Chelsea', 'Chukka', 'Moc Toe', 'Hiking', 'Work', 'Combat', 'Dress'],
  Sneaker: ['Low-top', 'High-top', 'Slip-on Sneaker'],
  'Slip-on': ['Loafer', 'Clog'],
  'Dress Shoe': [],
};

function getCategoriesAndSubcategories(path, selectedCategory) {
  const categories = path === 'function' ? Object.keys(FUNCTION_CATEGORIES) : Object.keys(SILHOUETTE_CATEGORIES);
  const subcategories = selectedCategory
    ? (path === 'function' ? FUNCTION_CATEGORIES[selectedCategory] : SILHOUETTE_CATEGORIES[selectedCategory]) || []
    : [];
  return { categories, subcategories };
}

const FIT_STATUS_COLOR = {
  PERFECT:    '#2E7D32',
  GOOD:       '#558B2F',
  ACCEPTABLE: '#F57F17',
  MARGINAL:   '#E64A19',
  POOR:       '#B71C1C',
  REJECTED:   '#9E9E9E',
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

function getColorSwatch(colorName = '') {
  const normalized = String(colorName).toLowerCase();
  const match = Object.keys(COLOR_SWATCH_MAP).find((key) => normalized.includes(key));
  return match ? COLOR_SWATCH_MAP[match] : '#C9B8A7';
}

function getColorwaySwatch(cw = {}) {
  return cw.dominant_color_hex || getColorSwatch(cw.name) || '#C9B8A7';
}

/**
 * Return a palette array for a colorway object.
 * Falls back to a single-element array so callers always get at least one color.
 */
function getColorwayPalette(cw = {}) {
  if (Array.isArray(cw.color_palette_hex) && cw.color_palette_hex.length > 0) {
    return cw.color_palette_hex.slice(0, 3);
  }
  const single = cw.dominant_color_hex || getColorSwatch(cw.name) || '#C9B8A7';
  return [single];
}

// SVG viewBox is "0 0 18 18" with center (9, 9).
// Radius 9 fills the full circle; leave 0.5px margin so the outer
// stroke on the View border isn't overlapped.
const SWATCH_R = 8.5;
const SWATCH_C = 9;

function swatchPointOnCircle(angleDegrees) {
  const rad = (angleDegrees * Math.PI) / 180;
  return {
    x: SWATCH_C + SWATCH_R * Math.cos(rad),
    y: SWATCH_C + SWATCH_R * Math.sin(rad),
  };
}

function describeSwatchSlice(index, count) {
  const startAngle = -90 + (index * 360) / count;
  const endAngle   = -90 + ((index + 1) * 360) / count;
  const start = swatchPointOnCircle(startAngle);
  const end   = swatchPointOnCircle(endAngle);
  // Large-arc flag: 1 when the slice spans more than 180° (only possible
  // with a single 2-color swatch where each half is exactly 180°).
  const largeArc = (360 / count) > 180 ? 1 : 0;

  return [
    `M ${SWATCH_C} ${SWATCH_C}`,
    `L ${start.x.toFixed(4)} ${start.y.toFixed(4)}`,
    `A ${SWATCH_R} ${SWATCH_R} 0 ${largeArc} 1 ${end.x.toFixed(4)} ${end.y.toFixed(4)}`,
    'Z',
  ].join(' ');
}

/**
 * Renders a small circular swatch showing 1, 2, or 3 color segments.
 *
 * Single color: plain View with backgroundColor + View border (no SVG overhead).
 * Multi-color:  borderless View so the SVG starts at (0,0) with no offset,
 *               then the SVG draws the pie slices and its own border Circle.
 *               This avoids the 1px shift caused by positioning an absolute SVG
 *               inside a View that has borderWidth.
 */
function ColorwaySwatch({ colors, active }) {
  const palette = Array.isArray(colors) && colors.length > 0
    ? colors.slice(0, 3)
    : ['#C9B8A7'];

  if (palette.length === 1) {
    return (
      <View
        style={[
          styles.swatchCircle,
          active && styles.swatchCircleActive,
          { backgroundColor: palette[0] },
        ]}
      />
    );
  }

  // Border drawn by SVG so no View borderWidth offset shifts the SVG.
  const borderColor = active ? '#9A6645' : '#D9CCBD';
  const borderWidth = active ? 2 : 1;

  return (
    <View
      style={[
        styles.swatchPieContainer,
        active && { transform: [{ scale: 1.1 }] },
      ]}
    >
      <Svg width={18} height={18} viewBox="0 0 18 18">
        {palette.map((color, index) => (
          <Path
            key={`${color}-${index}`}
            d={describeSwatchSlice(index, palette.length)}
            fill={color}
          />
        ))}
        {/* Border circle drawn on top so it frames the slices cleanly */}
        <Circle
          cx={SWATCH_C}
          cy={SWATCH_C}
          r={SWATCH_R}
          fill="none"
          stroke={borderColor}
          strokeWidth={borderWidth}
        />
      </Svg>
    </View>
  );
}

/**
 * One recommendation card (horizontal colorway carousel).
 *
 * Memoized so that per-card state changes elsewhere in the list (another
 * card's carousel swipe, a failed image, a toast) don't re-render every
 * mounted card — each card is a multi-slide carousel, so blanket re-renders
 * were the main source of scroll jank on this screen.
 *
 * Carousel images are only mounted for the active slide ± 1; farther slides
 * render an identically-sized placeholder so card height never shifts.
 */
const ShoeCard = React.memo(function ShoeCard({
  item, activeIndex, saved, owned,
  path, selectedCategory, selectedSubcategory,
  catalog, failedImageByColorway, carouselRefs,
  onColorwayChange, onImageFailed, onSave, onOwn,
}) {
  const statusColor = FIT_STATUS_COLOR[item.fit_status] || '#6B5F52';
  const tags = (path === 'function' ? item.function_tags : item.style_tags) || [];
  const baseSize = item.recommended_size ?? item.us_size ?? item.size;
  const colorways = catalog?.colorways ?? [];
  const hasColorways = colorways.length > 0;
  const cardVariants = hasColorways ? colorways : [null];

  const cardTags = [];
  if (selectedCategory && tags.includes(selectedCategory)) cardTags.push(selectedCategory);
  if (selectedSubcategory && tags.includes(selectedSubcategory) && !cardTags.includes(selectedSubcategory)) {
    cardTags.push(selectedSubcategory);
  }
  ATTRIBUTE_FILTERS.forEach(({ key, label }) => {
    const attrs = item.attributes_json || {};
    if (attrs[key] && !cardTags.includes(label)) cardTags.push(label);
  });
  tags.forEach(t => { if (!cardTags.includes(t)) cardTags.push(t); });

  return (
    <ScrollView
      ref={(ref) => { carouselRefs.current[item.id] = ref; }}
      horizontal
      pagingEnabled
      nestedScrollEnabled
      directionalLockEnabled
      showsHorizontalScrollIndicator={false}
      style={styles.colorwayCarousel}
      decelerationRate="fast"
      snapToInterval={CAROUSEL_WIDTH}
      snapToAlignment="start"
      onMomentumScrollEnd={(event) => {
        const nextIndex = Math.round(event.nativeEvent.contentOffset.x / CAROUSEL_WIDTH);
        onColorwayChange(item.id, nextIndex);
      }}
    >
      {cardVariants.map((variant, variantIndex) => {
        const variantKey = `${item.id}-${variant?.goat_id ?? 'base'}`;
        const variantImageOk = variant?.image_url && !failedImageByColorway[variantKey];
        const catalogImg = catalog?.catalog_shoe_image_url ?? null;
        const apiImg = item.shoe_image_url && String(item.shoe_image_url).trim()
          ? String(item.shoe_image_url).trim()
          : null;
        const imageUrl = variantImageOk ? variant.image_url : (catalogImg || apiImg || null);
        const isNearActive = Math.abs(variantIndex - activeIndex) <= 1;
        const priceUsd = hasColorways
          ? (variant?.sizes?.[0]?.price_usd ?? item.price_usd)
          : item.price_usd;
        const sizeForFacts = hasColorways
          ? (variant?.sizes?.[0]?.us_size ?? baseSize)
          : baseSize;
        const detailsUrl = hasColorways
          ? (variant?.product_url ?? catalog?.catalog_shoe_product_url ?? item.product_url)
          : item.product_url;
        const colorwayLabel = hasColorways ? (variant?.name ?? null) : item.colorway;
        const selectedCardItem = {
          ...item,
          colorway: colorwayLabel ?? null,
          product_url: detailsUrl || item.product_url,
          shoe_image_url: imageUrl || item.shoe_image_url,
          price_usd: priceUsd ?? item.price_usd,
          recommended_size: sizeForFacts ?? item.recommended_size,
        };

        return (
          <View key={`${variantKey}-${variantIndex}`} style={[styles.card, styles.colorwaySlide]}>
            <View style={styles.cardHeader}>
              <Text style={styles.brand}>{item.brand}</Text>
              <View style={styles.cardActions}>
                <TouchableOpacity
                  style={styles.heartButton}
                  onPress={() => onSave(selectedCardItem, saved)}
                  hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                >
                  <Ionicons
                    name={saved ? 'heart' : 'heart-outline'}
                    size={20}
                    color={saved ? '#C28A5B' : '#B0A499'}
                  />
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.heartButton}
                  onPress={() => onOwn(selectedCardItem, owned, saved)}
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
            {(variant?.name || (!hasColorways && item.colorway)) ? (
              <Text style={styles.colorway}>{variant?.name || item.colorway}</Text>
            ) : null}

            {hasColorways && (
              <View style={styles.colorwayPills}>
                {colorways.map((cw, index) => (
                  <TouchableOpacity
                    key={`${item.id}-${cw.goat_id ?? ''}-${cw.sku ?? index}`}
                    activeOpacity={0.7}
                    onPress={() => {
                      carouselRefs.current[item.id]?.scrollTo({
                        x: index * CAROUSEL_WIDTH,
                        animated: true,
                      });
                      onColorwayChange(item.id, index);
                    }}
                  >
                    <ColorwaySwatch
                      colors={getColorwayPalette(cw)}
                      active={index === activeIndex}
                    />
                  </TouchableOpacity>
                ))}
              </View>
            )}

            {item.fit_status !== 'UNSCORED' && (
              <View style={styles.fitRow}>
                <View style={[styles.fitBadge, { backgroundColor: statusColor + '20', borderColor: statusColor }]}>
                  <Text style={[styles.fitScore, { color: statusColor }]}>{item.fit_score}</Text>
                  <Text style={[styles.fitLabel, { color: statusColor }]}>{item.fit_status_label}</Text>
                </View>
                <Text style={styles.fitProfile}>{item.fit_profile?.replace(/_/g, ' ')}</Text>
              </View>
            )}

            {imageUrl ? (
              isNearActive ? (
                <Image
                  key={`${variantKey}|${imageUrl}`}
                  source={{ uri: resolveImageUrl(imageUrl) }}
                  style={styles.shoeImage}
                  resizeMode="contain"
                  onError={() => {
                    if (variant?.image_url) onImageFailed(variantKey);
                  }}
                />
              ) : (
                <View style={styles.shoeImage} />
              )
            ) : (
              <View style={styles.shoePhotoPlaceholder}>
                <Ionicons name="image-outline" size={32} color="#B0A499" />
                <Text style={styles.shoePhotoPlaceholderText}>Shoe photo</Text>
              </View>
            )}

            <ShoeCardKeyFacts priceUsd={priceUsd} sizeValue={sizeForFacts} />

            {cardTags.length > 0 && (
              <View style={styles.attrTags}>
                {cardTags.map(t => (
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
          </View>
        );
      })}
    </ScrollView>
  );
});

export default function RecommendationsScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding;

  const [allResults, setAllResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [noMeasurement, setNoMeasurement] = useState(false);
  const [hasToebox, setHasToebox] = useState(false);

  // Applied filters
  const [path, setPath] = useState('function');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedSubcategory, setSelectedSubcategory] = useState(null);
  const [attributeFilters, setAttributeFilters] = useState({});

  // Draft filters
  const [pathDraft, setPathDraft] = useState('function');
  const [selectedCategoryDraft, setSelectedCategoryDraft] = useState(null);
  const [selectedSubcategoryDraft, setSelectedSubcategoryDraft] = useState(null);
  const [attributeFiltersDraft, setAttributeFiltersDraft] = useState({});

  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerAnim = useRef(new Animated.Value(0)).current;
  const isAnimatingRef = useRef(false);

  const { toggleSaved, isSaved } = useSavedShoes();
  const { toggleOwned, isOwned } = useOwnedShoes();
  const [toastMessage, setToastMessage] = useState(null);
  const toastTimeoutRef = useRef(null);
  const toastAnim = useRef(new Animated.Value(0)).current;
  const [activeColorwayByShoe, setActiveColorwayByShoe] = useState({});
  const [failedImageByColorway, setFailedImageByColorway] = useState({});
  const [catalogByShoeId, setCatalogByShoeId] = useState(() => new Map());
  const carouselRefs = useRef({});
  const flatListRef = useRef(null);
  const scrollToShoeId = route.params?.scrollToShoeId ?? null;

  // Fade/slide the toast in, hold, then fade out before unmounting it.
  const showToast = useCallback((message) => {
    setToastMessage(message);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    Animated.timing(toastAnim, { toValue: 1, duration: 180, useNativeDriver: true }).start();
    toastTimeoutRef.current = setTimeout(() => {
      Animated.timing(toastAnim, { toValue: 0, duration: 220, useNativeDriver: true }).start(({ finished }) => {
        if (finished) setToastMessage(null);
      });
    }, 1600);
  }, [toastAnim]);

  // Fetch recommendations — show cache immediately, then revalidate in background.
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      setFetchError(null);
      setNoMeasurement(false);

      (async () => {
        // 1. Show cached data instantly.
        const cache = await readRecommendationsCache();
        if (cancelled) return;
        if (cache?.results?.length) {
          setAllResults(cache.results);
          setHasToebox(cache.has_toebox_data ?? false);
          setLoading(false);
        } else {
          setLoading(true);
        }

        const token = await SecureStore.getItemAsync('authToken');
        if (!token || cancelled) { setLoading(false); return; }

        // 2. Fetch shoe count and latest measurement ID in parallel.
        //    Both are needed to correctly detect stale cache — a remeasure
        //    changes measurement_id but not shoe_count, so checking only one
        //    would miss the other invalidation case.
        let currentShoeCount = null;
        let latestMeasurementId = null;
        const [healthResult, measurementResult] = await Promise.allSettled([
          fetch(`${API_BASE_URL}/api/health/`),
          fetch(`${API_BASE_URL}/api/measurements/latest/`, {
            headers: { Authorization: `Token ${token}` },
          }),
        ]);
        try {
          const hRes = healthResult.value;
          if (hRes.ok) {
            const hData = await hRes.json();
            currentShoeCount = hData.shoe_count ?? null;
          }
        } catch {}
        try {
          const mRes = measurementResult.value;
          if (mRes.ok) {
            const mData = await mRes.json();
            latestMeasurementId = mData.id ?? null;
          }
        } catch {}
        if (cancelled) return;

        // 3. Skip the full recs fetch if neither measurement nor shoe count changed.
        if (!isCacheStale(cache, latestMeasurementId, currentShoeCount)) {
          setLoading(false);
          return;
        }

        // 4. Fetch fresh recommendations.
        try {
          const res = await fetch(`${API_BASE_URL}/api/recommendations/`, {
            headers: { Authorization: `Token ${token}` },
          });
          if (cancelled) return;
          if (res.status === 404) {
            setNoMeasurement(true);
            setLoading(false);
            return;
          }
          if (!res.ok) throw new Error('fetch failed');
          const data = await res.json();
          if (cancelled) return;

          setAllResults(data.results || []);
          setHasToebox(data.has_toebox_data ?? false);

          // Persist so Dashboard and next visit are instant.
          await writeRecommendationsCache({
            results:           data.results || [],
            measurement_id:    latestMeasurementId,
            shoe_count:        currentShoeCount,
            has_toebox_data:   data.has_toebox_data ?? false,
            algorithm_version: data.algorithm_version ?? null,
          });
        } catch {
          if (!cancelled && !cache?.results?.length) setFetchError(true);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();

      return () => { cancelled = true; };
    }, [])
  );

  // Build the catalog map directly from API results — no Supabase needed.
  // colorway_options from /api/recommendations/ already includes goat_id, sku,
  // image_url, product_url, and sizes for the recommended size.
  useEffect(() => {
    const map = new Map();
    for (const item of allResults) {
      if (item.id == null) continue;
      map.set(item.id, {
        shoe_id:                  item.id,
        catalog_shoe_image_url:   item.shoe_image_url ?? null,
        catalog_shoe_product_url: item.product_url ?? null,
        colorways:                item.colorway_options ?? [],
      });
    }
    setCatalogByShoeId(map);
  }, [allResults]);

  const onScrollToIndexFailed = useCallback((info) => {
    flatListRef.current?.scrollToOffset({ offset: info.averageItemLength * info.index, animated: true });
    setTimeout(() => {
      flatListRef.current?.scrollToIndex({ index: info.index, animated: true, viewPosition: 0 });
    }, 300);
  }, []);

  const { subcategories: subcategoriesDraft } =
    getCategoriesAndSubcategories(pathDraft, selectedCategoryDraft);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <TouchableOpacity
          onPress={() => {
            if (isAnimatingRef.current) return;
            isAnimatingRef.current = true;
            if (drawerOpen) {
              setDrawerOpen(false);
              Animated.timing(drawerAnim, { toValue: 0, duration: 250, useNativeDriver: true }).start(() => {
                isAnimatingRef.current = false;
              });
            } else {
              setPathDraft(path);
              setSelectedCategoryDraft(selectedCategory);
              setSelectedSubcategoryDraft(selectedSubcategory);
              setAttributeFiltersDraft({ ...attributeFilters });
              setDrawerOpen(true);
              Animated.timing(drawerAnim, { toValue: 1, duration: 280, useNativeDriver: true }).start(() => {
                isAnimatingRef.current = false;
              });
            }
          }}
          style={styles.headerFilterButton}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        >
          <Ionicons name="options-outline" size={24} color="#2F2A25" />
          {(selectedCategory || selectedSubcategory || Object.values(attributeFilters).some(Boolean)) && (
            <View style={styles.headerFilterBadge} />
          )}
        </TouchableOpacity>
      ),
    });
  }, [navigation, drawerOpen, path, selectedCategory, selectedSubcategory, attributeFilters]);

  const filteredResults = useMemo(() => {
    const pathKey = path === 'function' ? 'function_tags' : 'style_tags';
    return allResults.filter(item => {
      if (item.fit_status === 'REJECTED') return false;
      // Once moved to Wishlist/Closet, hide from Recommendations.
      if (isSaved(item.id) || isOwned(item.id)) return false;

      const tags = (item[pathKey] || []).map(t => t.toLowerCase());
      const matchCat = !selectedCategory || tags.includes(selectedCategory.toLowerCase());
      const matchSub = !selectedSubcategory || tags.includes(selectedSubcategory.toLowerCase());
      if (!matchCat || !matchSub) return false;

      const activeAttrs = Object.entries(attributeFilters).filter(([, v]) => v);
      for (const [key] of activeAttrs) {
        const attrs = item.attributes_json || {};
        if (!attrs[key]) return false;
      }
      return true;
    });
  }, [allResults, path, selectedCategory, selectedSubcategory, attributeFilters, isSaved, isOwned]);

  const applyFilters = () => {
    setPath(pathDraft);
    setSelectedCategory(selectedCategoryDraft);
    setSelectedSubcategory(selectedSubcategoryDraft);
    setAttributeFilters({ ...attributeFiltersDraft });
    setDrawerOpen(false);
    isAnimatingRef.current = true;
    Animated.timing(drawerAnim, { toValue: 0, duration: 250, useNativeDriver: true }).start(() => {
      isAnimatingRef.current = false;
    });
  };

  const clearDraft = () => {
    setSelectedCategoryDraft(null);
    setSelectedSubcategoryDraft(null);
    setAttributeFiltersDraft({});
  };

  const hasActiveFilters = selectedCategory || selectedSubcategory || Object.values(attributeFilters).some(Boolean);
  const hasDraftFilters  = selectedCategoryDraft || selectedSubcategoryDraft || Object.values(attributeFiltersDraft).some(Boolean);

  const drawerTranslateX = drawerAnim.interpolate({ inputRange: [0, 1], outputRange: [DRAWER_WIDTH, 0] });
  const overlayOpacity   = drawerAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 0.4] });

  // Memoised so it doesn't recompute on unrelated re-renders (e.g. toast state change).
  const displayedResults = useMemo(() => {
    if (hasActiveFilters) return filteredResults;
    return allResults.filter(
      (r) => r.fit_status !== 'REJECTED' && !isSaved(r.id) && !isOwned(r.id)
    );
  }, [hasActiveFilters, filteredResults, allResults, isSaved, isOwned]);

  // Must come after the displayedResults declaration — referencing it earlier
  // in the component body would hit the const temporal dead zone.
  useEffect(() => {
    if (scrollToShoeId == null || loading || displayedResults.length === 0) return;
    const idx = displayedResults.findIndex((r) => r.id === scrollToShoeId);
    if (idx <= 0) return;
    const timer = setTimeout(() => {
      flatListRef.current?.scrollToIndex({ index: idx, animated: true, viewPosition: 0 });
    }, 350);
    return () => clearTimeout(timer);
  }, [scrollToShoeId, loading, displayedResults]);

  // FlatList render helpers ────────────────────────────────────────────────────

  // Stable callbacks passed into the memoized ShoeCard. Functional updates
  // bail out (return the same object) when nothing changed so untouched
  // cards keep their props and skip re-rendering.
  const handleColorwayChange = useCallback((shoeId, index) => {
    setActiveColorwayByShoe((prev) => (
      (prev[shoeId] ?? 0) === index ? prev : { ...prev, [shoeId]: index }
    ));
  }, []);

  const handleImageFailed = useCallback((variantKey) => {
    setFailedImageByColorway((prev) => (
      prev[variantKey] ? prev : { ...prev, [variantKey]: true }
    ));
  }, []);

  const handleSaveFromCard = useCallback((cardItem, wasSaved) => {
    animateListChange();
    toggleSaved(cardItem);
    showToast(wasSaved ? 'Removed from Wishlist' : 'Added to Wishlist');
  }, [toggleSaved, showToast]);

  const handleOwnFromCard = useCallback((cardItem, wasOwned, wasSaved) => {
    animateListChange();
    if (!wasOwned && wasSaved) {
      toggleSaved(cardItem);
    }
    toggleOwned({ ...cardItem, returnToWishlistOnRemove: false });
    showToast(wasOwned ? 'Removed from Closet' : 'Added to Closet');
  }, [toggleSaved, toggleOwned, showToast]);

  const renderItem = useCallback(({ item }) => (
    <ShoeCard
      item={item}
      activeIndex={activeColorwayByShoe[item.id] ?? 0}
      saved={isSaved(item.id)}
      owned={isOwned(item.id)}
      path={path}
      selectedCategory={selectedCategory}
      selectedSubcategory={selectedSubcategory}
      catalog={catalogByShoeId.get(item.id)}
      failedImageByColorway={failedImageByColorway}
      carouselRefs={carouselRefs}
      onColorwayChange={handleColorwayChange}
      onImageFailed={handleImageFailed}
      onSave={handleSaveFromCard}
      onOwn={handleOwnFromCard}
    />
  ), [
    isSaved, isOwned, catalogByShoeId, activeColorwayByShoe, failedImageByColorway,
    path, selectedCategory, selectedSubcategory,
    handleColorwayChange, handleImageFailed, handleSaveFromCard, handleOwnFromCard,
  ]);

  const listHeader = useMemo(() => (
    <>
      {!hasToebox && allResults.length > 0 && (
        <View style={styles.noToebox}>
          <Ionicons name="information-circle-outline" size={16} color="#6B5F52" />
          <Text style={styles.noToeboxText}>
            Toebox not detected — scored on overall length and width only. Rescan for more precise results.
          </Text>
        </View>
      )}
      {hasActiveFilters && (
        <View style={styles.resultsHeader}>
          <Text style={styles.resultsTitle}>
            {displayedResults.length} {displayedResults.length === 1 ? 'shoe' : 'shoes'}
          </Text>
        </View>
      )}
    </>
  ), [hasToebox, allResults.length, hasActiveFilters, displayedResults.length]);

  const renderEmpty = useCallback(() => (
    <View style={styles.emptyState}>
      {allResults.length === 0 ? (
        <>
          <Ionicons name="archive-outline" size={40} color="#B0A499" />
          <Text style={styles.emptyText}>No shoes in our catalog yet.</Text>
          <Text style={styles.emptySubText}>Check back soon as we add inventory.</Text>
        </>
      ) : (
        <>
          <Ionicons name="search-outline" size={40} color="#B0A499" />
          <Text style={styles.emptyText}>No shoes match your filters.</Text>
          <TouchableOpacity
            style={styles.clearButton}
            onPress={() => { setSelectedCategory(null); setSelectedSubcategory(null); setAttributeFilters({}); }}
          >
            <Text style={styles.clearButtonText}>Clear filters</Text>
          </TouchableOpacity>
        </>
      )}
    </View>
  ), [allResults.length, setSelectedCategory, setSelectedSubcategory, setAttributeFilters]);

  const renderFooter = useCallback(() => fromOnboarding ? (
    <View style={styles.doneSection}>
      <View style={styles.doneCard}>
        <Ionicons name="checkmark-circle" size={32} color="#C28A5B" style={styles.doneIcon} />
        <Text style={styles.doneTitle}>You're all set</Text>
        <Text style={styles.doneSubtitle}>Head to your closet to see your foot profile and saved shoes.</Text>
        <TouchableOpacity
          style={styles.doneButton}
          onPress={() => navigation.replace('MainTabs')}
          activeOpacity={0.85}
        >
          <Text style={styles.doneButtonText}>Go to My Closet</Text>
          <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />
        </TouchableOpacity>
      </View>
    </View>
  ) : null, [fromOnboarding, navigation]);

  // --- Render states ---
  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
        <Text style={styles.loadingText}>Finding your best fits…</Text>
      </View>
    );
  }

  if (fetchError) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="cloud-offline-outline" size={48} color="#B0A499" />
        <Text style={styles.emptyTitle}>Couldn't load recommendations</Text>
        <Text style={styles.emptySubtitle}>Check your connection and try again.</Text>
      </View>
    );
  }

  if (noMeasurement) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="footsteps-outline" size={48} color="#B0A499" />
        <Text style={styles.emptyTitle}>No foot scan yet</Text>
        <Text style={styles.emptySubtitle}>
          Go to My Closet, scan your foot, and come back here for shoe recommendations tailored to your measurements.
        </Text>
        <TouchableOpacity
          style={styles.ctaButton}
          onPress={() => navigation.navigate('Closet')}
        >
          <Text style={styles.ctaButtonText}>Go to My Closet</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        ref={flatListRef}
        data={displayedResults}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderItem}
        ListHeaderComponent={listHeader}
        ListEmptyComponent={renderEmpty}
        ListFooterComponent={renderFooter}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        removeClippedSubviews
        maxToRenderPerBatch={3}
        initialNumToRender={4}
        windowSize={5}
        onScrollToIndexFailed={onScrollToIndexFailed}
      />

      {toastMessage && (
        <Animated.View
          pointerEvents="none"
          style={[
            styles.toastContainer,
            {
              opacity: toastAnim,
              transform: [{
                translateY: toastAnim.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }),
              }],
            },
          ]}
        >
          <View style={styles.toastInner}>
            <Ionicons name="heart" size={18} color="#C28A5B" style={styles.toastIcon} />
            <Text style={styles.toastText}>{toastMessage}</Text>
          </View>
        </Animated.View>
      )}

      <Pressable
        style={[StyleSheet.absoluteFill, { pointerEvents: drawerOpen ? 'auto' : 'none' }]}
        onPress={() => {
          setDrawerOpen(false);
          isAnimatingRef.current = true;
          Animated.timing(drawerAnim, { toValue: 0, duration: 250, useNativeDriver: true }).start(() => {
            isAnimatingRef.current = false;
          });
        }}
      >
        <Animated.View style={[styles.drawerOverlay, { opacity: overlayOpacity }]} />
      </Pressable>

      <Animated.View
        style={[styles.drawerPanel, { width: DRAWER_WIDTH, transform: [{ translateX: drawerTranslateX }] }]}
        pointerEvents={drawerOpen ? 'auto' : 'none'}
      >
        <ScrollView style={styles.drawerScroll} contentContainerStyle={styles.drawerContent}>
          <Text style={styles.drawerTitle}>Refine results</Text>

          <View style={styles.drawerSection}>
            <Text style={styles.drawerSectionLabel}>Browse by</Text>
            <View style={styles.drawerList}>
              {[['function', 'By use'], ['silhouette', 'By style']].map(([val, label]) => (
                <TouchableOpacity
                  key={val}
                  style={[styles.drawerRow, pathDraft === val && styles.drawerRowActive]}
                  onPress={() => { setPathDraft(val); setSelectedCategoryDraft(null); setSelectedSubcategoryDraft(null); }}
                >
                  <Text style={[styles.drawerRowText, pathDraft === val && styles.drawerRowTextActive]}>{label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          <View style={styles.drawerSection}>
            <Text style={styles.drawerSectionLabel}>{pathDraft === 'function' ? 'Function' : 'Silhouette'}</Text>
            <View style={styles.drawerList}>
              {(pathDraft === 'function' ? Object.keys(FUNCTION_CATEGORIES) : Object.keys(SILHOUETTE_CATEGORIES)).map(cat => (
                <TouchableOpacity
                  key={cat}
                  style={[styles.drawerRow, selectedCategoryDraft === cat && styles.drawerRowActive]}
                  onPress={() => { setSelectedCategoryDraft(selectedCategoryDraft === cat ? null : cat); setSelectedSubcategoryDraft(null); }}
                >
                  <Text style={[styles.drawerRowText, selectedCategoryDraft === cat && styles.drawerRowTextActive]}>{cat}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {selectedCategoryDraft && subcategoriesDraft.length > 0 && (
            <View style={styles.drawerSection}>
              <Text style={styles.drawerSectionLabel}>Type</Text>
              <View style={styles.drawerList}>
                {subcategoriesDraft.map(sub => (
                  <TouchableOpacity
                    key={sub}
                    style={[styles.drawerRow, selectedSubcategoryDraft === sub && styles.drawerRowActive]}
                    onPress={() => setSelectedSubcategoryDraft(selectedSubcategoryDraft === sub ? null : sub)}
                  >
                    <Text style={[styles.drawerRowText, selectedSubcategoryDraft === sub && styles.drawerRowTextActive]}>{sub}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}

          <View style={styles.drawerSection}>
            <Text style={styles.drawerSectionLabel}>Filters</Text>
            <View style={styles.drawerList}>
              {ATTRIBUTE_FILTERS.map(({ key, label }) => (
                <TouchableOpacity
                  key={key}
                  style={[styles.drawerRow, attributeFiltersDraft[key] && styles.drawerRowActive]}
                  onPress={() => setAttributeFiltersDraft(prev => ({ ...prev, [key]: !prev[key] }))}
                >
                  <Text style={[styles.drawerRowText, attributeFiltersDraft[key] && styles.drawerRowTextActive]}>{label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {hasDraftFilters && (
            <TouchableOpacity style={styles.drawerClearButton} onPress={clearDraft}>
              <Ionicons name="close-circle-outline" size={16} color="#C28A5B" />
              <Text style={styles.clearButtonText}>Clear selections</Text>
            </TouchableOpacity>
          )}
        </ScrollView>

        <View style={styles.drawerFooter}>
          <TouchableOpacity style={styles.applyFilterButton} onPress={applyFilters} activeOpacity={0.85}>
            <Text style={styles.applyFilterButtonText}>Apply filters</Text>
          </TouchableOpacity>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FCFAF7' },
  scrollContent: { paddingHorizontal: 24, paddingTop: 24, paddingBottom: 40 },
  centerContainer: {
    flex: 1, backgroundColor: '#FCFAF7',
    alignItems: 'center', justifyContent: 'center',
    paddingHorizontal: 32,
  },
  loadingText: { marginTop: 16, fontSize: 15, color: '#6B5F52' },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: '#2F2A25', marginTop: 16, textAlign: 'center' },
  emptySubtitle: { fontSize: 14, color: '#6B5F52', marginTop: 8, textAlign: 'center', lineHeight: 20 },
  ctaButton: {
    marginTop: 24, backgroundColor: '#C28A5B',
    paddingVertical: 14, paddingHorizontal: 32, borderRadius: 999,
  },
  ctaButtonText: { color: '#FFFFFF', fontSize: 16, fontWeight: '600' },
  noToebox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    backgroundColor: '#FFF8F0', borderRadius: 12, padding: 12,
    borderWidth: 1, borderColor: '#E2D4C0', marginBottom: 16,
  },
  noToeboxText: { flex: 1, fontSize: 12, color: '#6B5F52', lineHeight: 17 },
  headerFilterButton: {
    width: 40, height: 40, marginRight: 4,
    justifyContent: 'center', alignItems: 'center', position: 'relative',
  },
  headerFilterBadge: {
    position: 'absolute', top: 8, right: 8,
    width: 8, height: 8, borderRadius: 4, backgroundColor: '#C28A5B',
  },
  resultsHeader: { marginBottom: 16 },
  resultsTitle: { fontSize: 18, fontWeight: '700', color: '#2F2A25' },
  card: {
    backgroundColor: '#FFFBF5', borderRadius: 20,
    padding: 18, borderWidth: 1, borderColor: '#E2D4C0', marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 4,
  },
  heartButton: { paddingHorizontal: 4, paddingVertical: 2 },
  cardActions: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  brand: { fontSize: 13, color: '#4F453C', fontWeight: '600' },
  name: { fontSize: 17, fontWeight: '700', color: '#2F2A25', marginBottom: 2 },
  colorway: { fontSize: 12, color: '#8C7B6E', marginBottom: 10 },
  colorwayCarousel: { marginBottom: 12 },
  colorwaySlide: { width: CAROUSEL_WIDTH, justifyContent: 'center' },
  colorwayPills: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 },
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
  // Multi-color pie: no borderWidth so the SVG fills from (0,0) with no offset.
  // The SVG draws its own border Circle on top of the slices.
  swatchPieContainer: {
    width: 18,
    height: 18,
    borderRadius: 9,
    overflow: 'hidden',
  },
  fitRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12,
  },
  fitBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 8, borderWidth: 1,
  },
  fitScore: { fontSize: 16, fontWeight: '700' },
  fitLabel: { fontSize: 12, fontWeight: '600' },
  fitProfile: { fontSize: 11, color: '#9B8E82', textTransform: 'uppercase', letterSpacing: 0.4 },
  shoeImage: {
    width: '100%', height: 160, borderRadius: 12, marginBottom: 12,
    backgroundColor: '#F0E2D0',
  },
  shoePhotoPlaceholder: {
    height: 120, backgroundColor: '#F0E2D0', borderRadius: 12,
    marginBottom: 12, justifyContent: 'center', alignItems: 'center',
    borderWidth: 1, borderColor: '#E2D4C0', borderStyle: 'dashed',
  },
  shoePhotoPlaceholderText: { fontSize: 12, color: '#6B5F52', marginTop: 6 },
  attrTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 },
  attrTag: { backgroundColor: '#F0E2D0', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  attrTagText: { fontSize: 11, color: '#6B5F52' },
  primaryButton: { backgroundColor: '#C28A5B', paddingVertical: 12, borderRadius: 12, alignItems: 'center' },
  primaryButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '600' },
  emptyState: { alignItems: 'center', paddingVertical: 40 },
  emptyText: { fontSize: 15, color: '#6B5F52', marginTop: 12, marginBottom: 8 },
  emptySubText: { fontSize: 13, color: '#9B8E82', textAlign: 'center' },
  clearButton: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', marginBottom: 20 },
  clearButtonText: { fontSize: 14, fontWeight: '600', color: '#C28A5B' },
  drawerOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: '#000' },
  drawerPanel: {
    position: 'absolute', top: 0, right: 0, bottom: 0,
    backgroundColor: '#EDE6DC', borderLeftWidth: 1, borderLeftColor: '#DED4C4',
    shadowColor: '#000', shadowOffset: { width: -2, height: 0 },
    shadowOpacity: 0.1, shadowRadius: 8, elevation: 8,
  },
  drawerScroll: { flex: 1 },
  drawerContent: { paddingVertical: 16, paddingLeft: 8, paddingRight: 14, paddingBottom: 24, alignItems: 'flex-end' },
  drawerTitle: { fontSize: 16, fontWeight: '700', color: '#2F2A25', marginBottom: 16, alignSelf: 'flex-end' },
  drawerSection: { marginBottom: 18, alignSelf: 'stretch', alignItems: 'flex-end' },
  drawerSectionLabel: {
    fontSize: 11, fontWeight: '600', color: '#6B5F52', marginBottom: 6,
    textTransform: 'uppercase', letterSpacing: 0.5, alignSelf: 'flex-end',
  },
  drawerList: { paddingRight: 0, alignSelf: 'flex-end', alignItems: 'flex-end' },
  drawerRow: {
    paddingVertical: 10, paddingHorizontal: 14, marginBottom: 2, borderRadius: 10,
    backgroundColor: '#F8F4EE', borderWidth: 1, borderColor: '#E2D4C0',
    alignSelf: 'flex-end', minWidth: 132, alignItems: 'center',
  },
  drawerRowActive: { backgroundColor: '#C28A5B', borderColor: '#C28A5B' },
  drawerRowText: { fontSize: 14, fontWeight: '500', color: '#2F2A25' },
  drawerRowTextActive: { color: '#FFFFFF', fontWeight: '600' },
  drawerClearButton: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginTop: 8, marginBottom: 8, paddingVertical: 8, alignSelf: 'flex-end',
  },
  drawerFooter: {
    padding: 14, paddingTop: 12, paddingBottom: 28,
    borderTopWidth: 1, borderTopColor: '#DED4C4',
    backgroundColor: '#EDE6DC', alignItems: 'flex-end',
  },
  applyFilterButton: {
    backgroundColor: '#C28A5B', paddingVertical: 12, paddingHorizontal: 20,
    borderRadius: 12, alignItems: 'center', justifyContent: 'center', alignSelf: 'flex-end',
  },
  applyFilterButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '600' },
  doneSection: { marginTop: 28, marginBottom: 32 },
  doneCard: {
    backgroundColor: '#FFFBF5', borderRadius: 20, padding: 24,
    borderWidth: 1, borderColor: '#E2D4C0', alignItems: 'center',
  },
  doneIcon: { marginBottom: 12 },
  doneTitle: { fontSize: 20, fontWeight: '700', color: '#2F2A25', marginBottom: 6 },
  doneSubtitle: { fontSize: 14, color: '#6B5F52', textAlign: 'center', lineHeight: 20, marginBottom: 20 },
  doneButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, backgroundColor: '#C28A5B', paddingVertical: 14, paddingHorizontal: 24,
    borderRadius: 12, width: '100%',
  },
  doneButtonText: { color: '#FFFFFF', fontSize: 16, fontWeight: '600' },
  toastContainer: { position: 'absolute', left: 40, right: 40, top: '40%', alignItems: 'center' },
  toastInner: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 14, paddingHorizontal: 18,
    borderRadius: 18, backgroundColor: 'rgba(47, 42, 37, 0.9)',
  },
  toastIcon: { marginRight: 8 },
  toastText: { color: '#FFFBF5', fontSize: 15, fontWeight: '600', textAlign: 'center' },
});
