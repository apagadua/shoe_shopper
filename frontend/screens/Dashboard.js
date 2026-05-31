import React, { useState, useCallback, useMemo, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Image,
  Dimensions,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as SecureStore from 'expo-secure-store';
import { useFocusEffect } from '@react-navigation/native';
import { API_BASE_URL } from '../config/api';
import { ensureDevMockMeasurementIfNeeded } from '../services/devMockMeasurement';
import { getBestSize } from '../utils/shoeSize';
import { useSavedShoes } from '../SavedShoesContext';
import { useOwnedShoes } from '../OwnedShoesContext';
import {
  readRecommendationsCache,
  writeRecommendationsCache,
  isCacheStale,
} from '../services/recommendationsCache';
import ShoeDetailModal from '../components/ShoeDetailModal';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const H_PAD = 24;
/** Max shoes shown per dashboard row; use View All for the full list. */
const PREVIEW_LIMIT = 5;
const REC_CARD_WIDTH = Math.min(200, SCREEN_WIDTH * 0.52);
const REC_GAP = 12;
const THUMB_SIZE = Math.min(104, (SCREEN_WIDTH - H_PAD * 2 - 36) / 3);

function formatUsd(price) {
  if (price == null || price === '') return '—';
  const n = typeof price === 'string' ? parseFloat(price) : Number(price);
  if (Number.isNaN(n)) return '—';
  return `$${n.toFixed(2)}`;
}

/**
 * API returns one row per Shoe DB record. Duplicate brand+model rows (e.g. re-imported
 * catalog) would repeat in the UI — keep first occurrence (best rank after API sort).
 */
function dedupeRecommendationsByBrandModel(results) {
  const seen = new Set();
  const out = [];
  for (const item of results) {
    const key = `${String(item.brand ?? '').trim()}|${String(item.model ?? '').trim()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function SectionHeader({ title, onViewAll }) {
  return (
    <View style={styles.sectionHeaderRow}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <TouchableOpacity
        style={styles.viewAllTouchable}
        onPress={onViewAll}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Text style={styles.viewAllText}>View All</Text>
        <Ionicons name="chevron-forward" size={14} color="#C28A5B" />
      </TouchableOpacity>
    </View>
  );
}

function firstNameFromDisplayName(displayName) {
  const t = (displayName || '').trim();
  if (!t) return '';
  return t.split(/\s+/)[0];
}

/**
 * Resolve an image URL, routing Converse / Demandware CDN URLs through the
 * backend proxy so the server can attach the required browser headers.
 * The React Native Image component (Fresco on Android) does not reliably
 * forward custom headers set on the source prop.
 */
function resolveImageUrl(uri) {
  if (!uri) return null;
  if (uri.includes('converse.com') || uri.includes('demandware.static')) {
    return `${API_BASE_URL}/api/proxy-image/?url=${encodeURIComponent(uri)}`;
  }
  return uri;
}

export default function Dashboard({ navigation }) {
  const [measurements, setMeasurements] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [recResults, setRecResults] = useState([]);
  const [recLoading, setRecLoading] = useState(true);
  const [recFetchError, setRecFetchError] = useState(false);
  /** null = not loaded yet; string (maybe empty) = first name for greeting */
  const [greetingFirstName, setGreetingFirstName] = useState(null);

  const { savedMap, toggleSaved, isSaved } = useSavedShoes();
  const { ownedMap, toggleOwned, isOwned } = useOwnedShoes();
  const [detailShoe, setDetailShoe] = useState(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const shoeModalRef = useRef(null);

  const savedItems = useMemo(
    () => Object.values(savedMap).filter((item) => item && !ownedMap[item.id]),
    [savedMap, ownedMap]
  );
  const ownedItems = useMemo(
    () => Object.values(ownedMap).filter(Boolean),
    [ownedMap]
  );
  const recPreview = useMemo(
    () => dedupeRecommendationsByBrandModel(recResults)
      .filter((item) => !savedMap[item.id] && !ownedMap[item.id])
      .slice(0, PREVIEW_LIMIT),
    [recResults, savedMap, ownedMap]
  );
  const savedPreview = useMemo(() => savedItems.slice(0, PREVIEW_LIMIT), [savedItems]);
  const ownedPreview = useMemo(() => ownedItems.slice(0, PREVIEW_LIMIT), [ownedItems]);
  const recSlotWidth = REC_CARD_WIDTH + REC_GAP;

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      setLoadError(false);
      setRecFetchError(false);

      (async () => {
        // Show cached recommendations immediately — no spinner if we have data.
        const cache = await readRecommendationsCache();
        if (cancelled) return;
        if (cache?.results?.length) {
          setRecResults(cache.results);
          setRecLoading(false);
        } else {
          setRecLoading(true);
        }

        await ensureDevMockMeasurementIfNeeded();
        if (cancelled) return;

        const token = await SecureStore.getItemAsync('authToken');
        if (!token || cancelled) {
          setRecLoading(false);
          setGreetingFirstName(null);
          return;
        }

        // Fetch profile, latest measurement, and shoe count in parallel.
        const [profileResult, measurementResult, healthResult] = await Promise.allSettled([
          fetch(`${API_BASE_URL}/api/profile/`, { headers: { Authorization: `Token ${token}` } }),
          fetch(`${API_BASE_URL}/api/measurements/latest/`, { headers: { Authorization: `Token ${token}` } }),
          fetch(`${API_BASE_URL}/api/health/`),
        ]);
        if (cancelled) return;

        // Profile → greeting
        try {
          if (profileResult.status === 'fulfilled' && profileResult.value.ok) {
            const pData = await profileResult.value.json();
            const raw = typeof pData.display_name === 'string' ? pData.display_name : '';
            if (!cancelled) setGreetingFirstName(firstNameFromDisplayName(raw));
          }
        } catch {}

        // Measurement
        let latestMeasurementId = null;
        try {
          const mRes = measurementResult.value;
          if (mRes.status === 404) {
            if (!cancelled) setMeasurements(null);
          } else if (mRes.ok) {
            const mData = await mRes.json();
            if (!cancelled) {
              setMeasurements(mData);
              latestMeasurementId = mData.id ?? null;
            }
          } else {
            if (!cancelled) setLoadError(true);
          }
        } catch {
          if (!cancelled) setLoadError(true);
        }

        // Shoe count from health endpoint
        let currentShoeCount = null;
        try {
          const hRes = healthResult.value;
          if (hRes.ok) {
            const hData = await hRes.json();
            currentShoeCount = hData.shoe_count ?? null;
          }
        } catch {}

        if (cancelled) return;

        // Only hit the recommendations API if something has changed.
        if (!isCacheStale(cache, latestMeasurementId, currentShoeCount)) {
          setRecLoading(false);
          return;
        }

        try {
          const rRes = await fetch(`${API_BASE_URL}/api/recommendations/`, {
            headers: { Authorization: `Token ${token}` },
          });
          if (cancelled) return;
          if (rRes.status === 404) {
            setRecResults([]);
          } else if (!rRes.ok) {
            throw new Error('rec failed');
          } else {
            const rData = await rRes.json();
            if (!cancelled) {
              setRecResults(rData.results || []);
              await writeRecommendationsCache({
                results:           rData.results || [],
                measurement_id:    latestMeasurementId,
                shoe_count:        currentShoeCount,
                has_toebox_data:   rData.has_toebox_data ?? false,
                algorithm_version: rData.algorithm_version ?? null,
              });
            }
          }
        } catch {
          if (!cancelled && !cache?.results?.length) setRecFetchError(true);
        } finally {
          if (!cancelled) setRecLoading(false);
        }
      })();

      return () => { cancelled = true; };
    }, [])
  );

  const goTabRecommendations = () => {
    navigation.getParent()?.navigate('Recommendations', {
      screen: 'RecommendationsHome',
    });
  };

  const openShoeDetail = (item) => {
    setDetailShoe(item);
    setDetailVisible(true);
  };

  const closeShoeDetail = () => {
    shoeModalRef.current?.dismiss();
  };

  const onShoeDetailClosed = () => {
    setDetailVisible(false);
    setDetailShoe(null);
  };

  const handleToggleSaved = (cardItem) => {
    const wasSaved = isSaved(cardItem.id);
    toggleSaved(cardItem);
    if (!wasSaved) closeShoeDetail();
  };

  const handleToggleOwned = (cardItem) => {
    const wasOwned = isOwned(cardItem.id);
    if (!wasOwned && isSaved(cardItem.id)) {
      toggleSaved(cardItem);
    }
    toggleOwned({ ...cardItem, returnToWishlistOnRemove: false });
    if (!wasOwned) {
      closeShoeDetail();
    }
  };

  return (
    <>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      nestedScrollEnabled
    >
      {greetingFirstName !== null ? (
        <View style={styles.greetingBlock}>
          <Text style={styles.greetingText}>
            {greetingFirstName ? `Hi, ${greetingFirstName}!` : 'Hi there'}
          </Text>
        </View>
      ) : null}

      {/* Foot profile */}
      <View style={styles.profileCard}>
        <View style={styles.profileHeader}>
          <Ionicons name="footsteps" size={26} color="#C28A5B" />
          <Text style={styles.profileTitle}>Your Foot Profile</Text>
        </View>
        {loadError ? (
          <Text style={styles.loadErrorText}>Could not load measurements. Check your connection.</Text>
        ) : null}

        <View style={styles.profileMetrics}>
          <View style={styles.metricCol}>
            <Text style={styles.metricLabel}>Length</Text>
            <Text style={styles.metricValue}>
              {measurements ? `${(measurements.length_in * 2.54).toFixed(1)} cm` : '—'}
            </Text>
          </View>
          <View style={styles.metricCol}>
            <Text style={styles.metricLabel}>Width</Text>
            <Text style={styles.metricValue}>
              {measurements ? `${(measurements.width_in * 2.54).toFixed(1)} cm` : '—'}
            </Text>
          </View>
          <View style={styles.metricCol}>
            <Text style={styles.metricLabel}>Typical size</Text>
            <Text style={styles.metricValue}>
              {measurements?.length_in ? `US ${getBestSize(measurements.length_in)}` : '—'}
            </Text>
          </View>
        </View>

        <TouchableOpacity
          style={styles.updateMeasurementsBtn}
          onPress={() => navigation.navigate('FootCapture')}
          activeOpacity={0.9}
        >
          <Ionicons name="camera" size={20} color="#FFFFFF" />
          <Text style={styles.updateMeasurementsText}>Update Measurements</Text>
        </TouchableOpacity>
      </View>

      {/* Recommended for you */}
      <SectionHeader title="Recommended For You" onViewAll={() => goTabRecommendations()} />
      {recLoading ? (
        <View style={styles.recLoading}>
          <ActivityIndicator color="#C28A5B" />
        </View>
      ) : recFetchError ? (
        <Text style={styles.sectionError}>Could not load recommendations.</Text>
      ) : recPreview.length === 0 ? (
        <Text style={styles.sectionEmpty}>Complete a foot scan to see personalized picks.</Text>
      ) : (
        <>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            decelerationRate="fast"
            snapToInterval={recSlotWidth}
            snapToAlignment="start"
            contentContainerStyle={styles.recCarouselContent}
          >
            {recPreview.map((item, index) => (
              <TouchableOpacity
                key={item.id}
                style={[
                  styles.recCard,
                  { width: REC_CARD_WIDTH, marginRight: index === recPreview.length - 1 ? 0 : REC_GAP },
                ]}
                onPress={() => openShoeDetail(item)}
                activeOpacity={0.9}
              >
                {item.shoe_image_url ? (
                  <Image source={{ uri: resolveImageUrl(item.shoe_image_url) }} style={styles.recImage} resizeMode="contain" />
                ) : (
                  <View style={styles.recImagePlaceholder}>
                    <Ionicons name="image-outline" size={28} color="#B0A499" />
                  </View>
                )}
                <Text style={styles.recShoeName} numberOfLines={2}>
                  {item.brand} {item.model}
                </Text>
                <Text style={styles.recMeta}>
                  {item.recommended_size != null ? `US ${item.recommended_size}` : '—'}
                </Text>
                <Text style={styles.recPrice}>{formatUsd(item.price_usd)}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </>
      )}

      {/* Wishlist */}
      <View style={styles.sectionSpacer} />
      <SectionHeader title="Wishlist" onViewAll={() => navigation.navigate('SavedShoes')} />
      {savedItems.length === 0 ? (
        <Text style={styles.sectionEmpty}>
          Tap the heart icon on the Recommended page to add your favorite shoes here.
        </Text>
      ) : (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.thumbRow}
        >
          {savedPreview.map((item, index) => (
            <TouchableOpacity
              key={String(item.id)}
              style={[
                styles.thumbBox,
                {
                  width: THUMB_SIZE,
                  height: THUMB_SIZE,
                  marginRight: index === savedPreview.length - 1 ? 0 : 10,
                },
              ]}
              onPress={() => navigation.navigate('SavedShoes')}
            >
              {item.shoe_image_url ? (
                <Image source={{ uri: resolveImageUrl(item.shoe_image_url) }} style={styles.thumbImage} resizeMode="cover" />
              ) : (
                <View style={styles.thumbPlaceholder}>
                  <Ionicons name="image-outline" size={24} color="#B0A499" />
                </View>
              )}
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {/* My Closet (owned) */}
      <View style={styles.sectionSpacer} />
      <SectionHeader title="My Closet" onViewAll={() => navigation.navigate('OwnedShoes')} />
      {ownedItems.length === 0 ? (
        <Text style={styles.sectionEmpty}>
          Tap the bag icon on the Recommended page to add the shoes you own here.
        </Text>
      ) : (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.thumbRow}
        >
          {ownedPreview.map((item, index) => (
            <TouchableOpacity
              key={String(item.id)}
              style={[
                styles.thumbBox,
                {
                  width: THUMB_SIZE,
                  height: THUMB_SIZE,
                  marginRight: index === ownedPreview.length - 1 ? 0 : 10,
                },
              ]}
              onPress={() => navigation.navigate('OwnedShoes')}
            >
              {item.shoe_image_url ? (
                <Image source={{ uri: resolveImageUrl(item.shoe_image_url) }} style={styles.thumbImage} resizeMode="cover" />
              ) : (
                <View style={styles.thumbPlaceholder}>
                  <Ionicons name="image-outline" size={24} color="#B0A499" />
                </View>
              )}
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
    </ScrollView>

    <ShoeDetailModal
      ref={shoeModalRef}
      visible={detailVisible}
      item={detailShoe}
      onClose={onShoeDetailClosed}
      isSaved={isSaved}
      isOwned={isOwned}
      onToggleSaved={handleToggleSaved}
      onToggleOwned={handleToggleOwned}
    />
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FAF9F6',
  },
  content: {
    paddingHorizontal: H_PAD,
    paddingTop: 20,
    paddingBottom: 40,
  },
  greetingBlock: {
    marginBottom: 20,
  },
  greetingText: {
    fontFamily: 'Outfit_600SemiBold',
    fontSize: 24,
    color: '#2F2A25',
    letterSpacing: -0.3,
  },
  profileCard: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    padding: 22,
    borderWidth: 1,
    borderColor: '#E2D4C0',
    marginBottom: 28,
  },
  profileHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 20,
  },
  profileTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#2F2A25',
  },
  loadErrorText: {
    fontSize: 13,
    color: '#B3513D',
    marginBottom: 10,
  },
  profileMetrics: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 22,
  },
  metricCol: {
    flex: 1,
    alignItems: 'flex-start',
  },
  metricLabel: {
    fontSize: 13,
    color: '#6B5F52',
    marginBottom: 6,
  },
  metricValue: {
    fontSize: 17,
    fontWeight: '600',
    color: '#2F2A25',
  },
  updateMeasurementsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#C28A5B',
    paddingVertical: 14,
    borderRadius: 999,
  },
  updateMeasurementsText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#2F2A25',
  },
  viewAllTouchable: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  viewAllText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#C28A5B',
  },
  sectionSpacer: {
    height: 8,
  },
  sectionEmpty: {
    fontSize: 14,
    color: '#6B5F52',
    marginBottom: 16,
  },
  sectionError: {
    fontSize: 14,
    color: '#B3513D',
    marginBottom: 16,
  },
  recLoading: {
    paddingVertical: 32,
    alignItems: 'center',
  },
  recCarouselContent: {
    paddingRight: H_PAD,
  },
  recCard: {
    backgroundColor: '#FFFBF5',
    borderRadius: 16,
    padding: 12,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  recImage: {
    width: '100%',
    height: 120,
    borderRadius: 12,
    backgroundColor: '#F0E2D0',
    marginBottom: 10,
  },
  recImagePlaceholder: {
    width: '100%',
    height: 120,
    borderRadius: 12,
    backgroundColor: '#F0E2D0',
    marginBottom: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recShoeName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 4,
    minHeight: 40,
  },
  recMeta: {
    fontSize: 13,
    color: '#6B5F52',
    marginBottom: 2,
  },
  recPrice: {
    fontSize: 16,
    fontWeight: '700',
    color: '#2F2A25',
  },
  thumbRow: {
    paddingBottom: 4,
  },
  thumbBox: {
    borderRadius: 14,
    overflow: 'hidden',
    backgroundColor: '#FFFBF5',
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  thumbImage: {
    width: '100%',
    height: '100%',
  },
  thumbPlaceholder: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F0E2D0',
  },
});
