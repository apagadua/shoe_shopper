import React, { useState, useMemo, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Dimensions, Animated, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSavedShoes } from '../SavedShoesContext';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const HORIZONTAL_PADDING = 24;
const CHIP_ROW_VIEWPORT = SCREEN_WIDTH - HORIZONTAL_PADDING * 2;
// Drawer sized to content: row minWidth 132 + padding ~36; keep minimal left space
const DRAWER_WIDTH = Math.min(172, SCREEN_WIDTH * 0.5);

// Navigation paths: Function (use) and Silhouette (style)
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

const ATTRIBUTE_FILTERS = [
  { key: 'waterproof', label: 'Waterproof' },
  { key: 'vegan', label: 'Vegan' },
  { key: 'leather', label: 'Leather' },
  { key: 'resoleable', label: 'Resoleable' },
  { key: 'insulated', label: 'Insulated' },
  { key: 'slipResistant', label: 'Slip-resistant' },
];

// Minimal hardcoded shoes for recommended page (filtering already tested). Replace with API when wiring DB.
const ALL_SHOES = [
  {
    id: '1',
    name: 'CloudWalk Runner',
    brand: 'StrideLab',
    description: 'Soft midsole, neutral support, roomy toe box.',
    functionPath: ['Athletic', 'Running'],
    silhouettePath: ['Sneaker', 'Low-top'],
    attributes: { vegan: true },
    availableSizes: ['8', '8.5', '9', '9.5'],
    typicalSize: '9',
    lengthCm: '26.2',
    widthCm: '9.8',
  },
  {
    id: '2',
    name: 'CityStep Sneaker',
    brand: 'Urban Form',
    description: 'Low profile, flexible forefoot, breathable upper.',
    functionPath: ['Casual', 'Sneakers'],
    silhouettePath: ['Sneaker', 'Low-top'],
    attributes: {},
    availableSizes: ['7', '7.5', '8', '8.5', '9'],
    typicalSize: '8',
    lengthCm: '25.1',
    widthCm: '9.2',
  },
];

export default function RecommendationsScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding;
  const skippedScan = route.params?.skippedScan ?? false;
  const userTypicalSize = route.params?.userTypicalSize ?? '9';

  // Applied filters (used for the list)
  const [path, setPath] = useState('function');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedSubcategory, setSelectedSubcategory] = useState(null);
  const [attributeFilters, setAttributeFilters] = useState({});

  // Draft filters (only in drawer until user taps "Filter")
  const [pathDraft, setPathDraft] = useState('function');
  const [selectedCategoryDraft, setSelectedCategoryDraft] = useState(null);
  const [selectedSubcategoryDraft, setSelectedSubcategoryDraft] = useState(null);
  const [attributeFiltersDraft, setAttributeFiltersDraft] = useState({});

  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerAnim = useRef(new Animated.Value(0)).current;

  const { savedShoes, toggleSaved, isSaved } = useSavedShoes();
  const [toastMessage, setToastMessage] = useState(null);
  const toastTimeoutRef = useRef(null);

  const showToast = (message) => {
    setToastMessage(message);
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    toastTimeoutRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 1800);
  };

  const categories = path === 'function' ? Object.keys(FUNCTION_CATEGORIES) : Object.keys(SILHOUETTE_CATEGORIES);
  const subcategories = selectedCategory
    ? (path === 'function' ? FUNCTION_CATEGORIES[selectedCategory] : SILHOUETTE_CATEGORIES[selectedCategory]) || []
    : [];

  const categoriesDraft = pathDraft === 'function' ? Object.keys(FUNCTION_CATEGORIES) : Object.keys(SILHOUETTE_CATEGORIES);
  const subcategoriesDraft = selectedCategoryDraft
    ? (pathDraft === 'function' ? FUNCTION_CATEGORIES[selectedCategoryDraft] : SILHOUETTE_CATEGORIES[selectedCategoryDraft]) || []
    : [];

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <TouchableOpacity
          onPress={() => {
            if (drawerOpen) {
              setDrawerOpen(false);
              Animated.timing(drawerAnim, { toValue: 0, duration: 250, useNativeDriver: true }).start();
            } else {
              setPathDraft(path);
              setSelectedCategoryDraft(selectedCategory);
              setSelectedSubcategoryDraft(selectedSubcategory);
              setAttributeFiltersDraft({ ...attributeFilters });
              setDrawerOpen(true);
              Animated.timing(drawerAnim, { toValue: 1, duration: 280, useNativeDriver: true }).start();
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

  const toggleAttributeDraft = (key) => {
    setAttributeFiltersDraft((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const filteredShoes = useMemo(() => {
    const pathTags = path === 'function' ? 'functionPath' : 'silhouettePath';
    return ALL_SHOES.filter((shoe) => {
      if (!skippedScan && userTypicalSize) {
        const sizes = shoe.availableSizes;
        if (!sizes || !Array.isArray(sizes) || !sizes.includes(String(userTypicalSize))) return false;
      }
      const tags = shoe[pathTags];
      if (!tags || !Array.isArray(tags)) return false;
      const matchCategory = !selectedCategory || tags.includes(selectedCategory);
      const matchSub = !selectedSubcategory || tags.includes(selectedSubcategory);
      if (!matchCategory || !matchSub) return false;
      const activeAttrs = Object.entries(attributeFilters).filter(([, v]) => v);
      for (const [key] of activeAttrs) {
        if (!shoe.attributes || !shoe.attributes[key]) return false;
      }
      return true;
    });
  }, [skippedScan, userTypicalSize, path, selectedCategory, selectedSubcategory, attributeFilters]);

  const applyFilters = () => {
    setPath(pathDraft);
    setSelectedCategory(selectedCategoryDraft);
    setSelectedSubcategory(selectedSubcategoryDraft);
    setAttributeFilters({ ...attributeFiltersDraft });
    setDrawerOpen(false);
    Animated.timing(drawerAnim, { toValue: 0, duration: 250, useNativeDriver: true }).start();
  };

  const clearDraft = () => {
    setSelectedCategoryDraft(null);
    setSelectedSubcategoryDraft(null);
    setAttributeFiltersDraft({});
  };

  const hasActiveFilters = selectedCategory || selectedSubcategory || Object.values(attributeFilters).some(Boolean);
  const hasDraftFilters = selectedCategoryDraft || selectedSubcategoryDraft || Object.values(attributeFiltersDraft).some(Boolean);

  const drawerTranslateX = drawerAnim.interpolate({ inputRange: [0, 1], outputRange: [DRAWER_WIDTH, 0] });
  const overlayOpacity = drawerAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 0.4] });

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Shoe count and list — only after filters are applied */}
        {hasActiveFilters && (
          <View style={styles.resultsHeader}>
            <Text style={styles.resultsTitle}>
              {filteredShoes.length} {filteredShoes.length === 1 ? 'shoe' : 'shoes'}
            </Text>
          </View>
        )}

        {/* ——— Shoe cards (Recommendations): each card = brand, heart, name, size rows, tags, View details ——— */}
        {filteredShoes.map((shoe) => {
          const pathTags = path === 'function' ? (shoe.functionPath || []) : (shoe.silhouettePath || []);

          // Build tags for this shoe, always including any matching filters plus attributes.
          const cardTags = [];

          if (selectedCategory && pathTags.includes(selectedCategory)) {
            cardTags.push(selectedCategory);
          }
          if (selectedSubcategory && pathTags.includes(selectedSubcategory) && !cardTags.includes(selectedSubcategory)) {
            cardTags.push(selectedSubcategory);
          }

          ATTRIBUTE_FILTERS.forEach(({ key, label }) => {
            if (shoe.attributes && shoe.attributes[key] && !cardTags.includes(label)) {
              cardTags.push(label);
            }
          });

          pathTags.forEach((t) => {
            if (!cardTags.includes(t)) {
              cardTags.push(t);
            }
          });

          const saved = isSaved(shoe.id);

          return (
            <View key={shoe.id} style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.brand}>{shoe.brand}</Text>
                <TouchableOpacity
                  style={styles.heartButton}
                  onPress={() => {
                    const wasSaved = isSaved(shoe.id);
                    toggleSaved(shoe);
                    showToast(wasSaved ? 'Removed from Saved Shoes' : 'Added to Saved Shoes');
                  }}
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
              <View style={styles.shoePhotoPlaceholder}>
                <Ionicons name="image-outline" size={32} color="#B0A499" />
                <Text style={styles.shoePhotoPlaceholderText}>Shoe photo</Text>
              </View>
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

        {filteredShoes.length === 0 && hasActiveFilters && (
          <View style={styles.emptyState}>
            <Ionicons name="search-outline" size={40} color="#B0A499" />
            <Text style={styles.emptyText}>No shoes match your filters.</Text>
            <TouchableOpacity style={styles.clearButton} onPress={() => { setSelectedCategory(null); setSelectedSubcategory(null); setAttributeFilters({}); }}>
              <Text style={styles.clearButtonText}>Clear filters</Text>
            </TouchableOpacity>
          </View>
        )}

        {fromOnboarding && (
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
        )}
      </ScrollView>

      {toastMessage && (
        <View style={styles.toastContainer}>
          <View style={styles.toastInner}>
            <Ionicons name="heart" size={18} color="#C28A5B" style={styles.toastIcon} />
            <Text style={styles.toastText}>{toastMessage}</Text>
          </View>
        </View>
      )}

      {/* Overlay when drawer is open — always mounted for animation */}
      <Pressable
        style={[StyleSheet.absoluteFill, { pointerEvents: drawerOpen ? 'auto' : 'none' }]}
        onPress={() => {
          setDrawerOpen(false);
          Animated.timing(drawerAnim, { toValue: 0, duration: 250, useNativeDriver: true }).start();
        }}
      >
        <Animated.View style={[styles.drawerOverlay, { opacity: overlayOpacity }]} />
      </Pressable>

      {/* Sliding filter panel from the right */}
      <Animated.View
        style={[
          styles.drawerPanel,
          { width: DRAWER_WIDTH, transform: [{ translateX: drawerTranslateX }] },
        ]}
        pointerEvents={drawerOpen ? 'auto' : 'none'}
      >
        <ScrollView
          style={styles.drawerScroll}
          contentContainerStyle={styles.drawerContent}
          showsVerticalScrollIndicator={true}
        >
          <Text style={styles.drawerTitle}>Refine results</Text>

          <View style={styles.drawerSection}>
            <Text style={styles.drawerSectionLabel}>Browse by</Text>
            <View style={styles.drawerList}>
              <TouchableOpacity
                style={[styles.drawerRow, pathDraft === 'function' && styles.drawerRowActive]}
                onPress={() => { setPathDraft('function'); setSelectedCategoryDraft(null); setSelectedSubcategoryDraft(null); }}
              >
                <Text style={[styles.drawerRowText, pathDraft === 'function' && styles.drawerRowTextActive]}>By use</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.drawerRow, pathDraft === 'silhouette' && styles.drawerRowActive]}
                onPress={() => { setPathDraft('silhouette'); setSelectedCategoryDraft(null); setSelectedSubcategoryDraft(null); }}
              >
                <Text style={[styles.drawerRowText, pathDraft === 'silhouette' && styles.drawerRowTextActive]}>By style</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.drawerSection}>
            <Text style={styles.drawerSectionLabel}>{pathDraft === 'function' ? 'Function' : 'Silhouette'}</Text>
            <View style={styles.drawerList}>
              {categoriesDraft.map((cat) => (
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
                {subcategoriesDraft.map((sub) => (
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
                  onPress={() => toggleAttributeDraft(key)}
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
  container: {
    flex: 1,
    backgroundColor: '#F5EFE6',
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 40,
  },
  headerFilterButton: {
    width: 40,
    height: 40,
    marginRight: 4,
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  headerFilterBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#C28A5B',
  },
  drawerOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000',
  },
  drawerPanel: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#EDE6DC',
    borderLeftWidth: 1,
    borderLeftColor: '#DED4C4',
    shadowColor: '#000',
    shadowOffset: { width: -2, height: 0 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 8,
  },
  drawerScroll: {
    flex: 1,
  },
  drawerContent: {
    paddingVertical: 16,
    paddingLeft: 8,
    paddingRight: 14,
    paddingBottom: 24,
    alignItems: 'flex-end',
  },
  drawerTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 16,
    paddingRight: 0,
    alignSelf: 'flex-end',
  },
  drawerSection: {
    marginBottom: 18,
    alignSelf: 'stretch',
    alignItems: 'flex-end',
  },
  drawerSectionLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#6B5F52',
    marginBottom: 6,
    paddingRight: 0,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    alignSelf: 'flex-end',
  },
  drawerList: {
    paddingRight: 0,
    alignSelf: 'flex-end',
    alignItems: 'flex-end',
  },
  drawerRow: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 2,
    borderRadius: 10,
    backgroundColor: '#F8F4EE',
    borderWidth: 1,
    borderColor: '#E2D4C0',
    alignSelf: 'flex-end',
    minWidth: 132,
    alignItems: 'center',
  },
  drawerRowActive: {
    backgroundColor: '#C28A5B',
    borderColor: '#C28A5B',
  },
  drawerRowText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#2F2A25',
  },
  drawerRowTextActive: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  drawerClearButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
    marginBottom: 8,
    paddingRight: 0,
    paddingVertical: 8,
    alignSelf: 'flex-end',
  },
  drawerFooter: {
    padding: 14,
    paddingTop: 12,
    paddingBottom: 28,
    borderTopWidth: 1,
    borderTopColor: '#DED4C4',
    backgroundColor: '#EDE6DC',
    alignItems: 'flex-end',
  },
  applyFilterButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'flex-end',
  },
  applyFilterButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  section: {
    marginBottom: 20,
    alignItems: 'center',
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6B5F52',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    textAlign: 'center',
    width: '100%',
  },
  pathRow: {
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'center',
  },
  pathPill: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 12,
    backgroundColor: '#FFFBF5',
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  pathPillActive: {
    backgroundColor: '#C28A5B',
    borderColor: '#C28A5B',
  },
  pathPillText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#2F2A25',
  },
  pathPillTextActive: {
    color: '#FFFFFF',
  },
  chipRowWrap: {
    width: '100%',
  },
  chipRow: {
    flexDirection: 'row',
    gap: 10,
    paddingLeft: 0,
    paddingRight: HORIZONTAL_PADDING,
    justifyContent: 'flex-start',
    flexGrow: 1,
    minHeight: 44,
  },
  attrRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    justifyContent: 'center',
  },
  chip: {
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 10,
    backgroundColor: '#FFFBF5',
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  chipSmall: {
    paddingHorizontal: 16,
    paddingVertical: 9,
  },
  chipActive: {
    backgroundColor: '#C28A5B',
    borderColor: '#C28A5B',
  },
  chipText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#2F2A25',
  },
  chipTextSmall: {
    fontSize: 12,
  },
  chipTextActive: {
    color: '#FFFFFF',
  },
  clearButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    marginBottom: 20,
  },
  clearButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#C28A5B',
  },
  resultsHeader: {
    marginBottom: 16,
  },
  resultsTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#2F2A25',
  },
  /* ——— Shoe card styles (card, cardHeader, heartButton, brand, tags, attrTags, primaryButton) ——— */
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
  heartButton: {
    paddingHorizontal: 4,
    paddingVertical: 2,
  },
  brand: {
    fontSize: 13,
    color: '#4F453C',
    fontWeight: '600',
  },
  tagsRow: {
    flexDirection: 'row',
    gap: 6,
    flexWrap: 'wrap',
  },
  tag: {
    backgroundColor: '#F0E2D0',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  tagText: {
    fontSize: 11,
    color: '#6B5F52',
    fontWeight: '500',
  },
  name: {
    fontSize: 17,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 10,
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
  shoePhotoPlaceholderText: {
    fontSize: 12,
    color: '#6B5F52',
    marginTop: 6,
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
  description: {
    fontSize: 14,
    color: '#6B5F52',
    marginBottom: 8,
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
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 15,
    color: '#6B5F52',
    marginTop: 12,
    marginBottom: 16,
  },
  doneSection: {
    marginTop: 28,
    marginBottom: 32,
  },
  doneCard: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    padding: 24,
    borderWidth: 1,
    borderColor: '#E2D4C0',
    alignItems: 'center',
  },
  doneIcon: { marginBottom: 12 },
  doneTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 6,
  },
  doneSubtitle: {
    fontSize: 14,
    color: '#6B5F52',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
  },
  doneButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#C28A5B',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    width: '100%',
  },
  doneButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  toastContainer: {
    position: 'absolute',
    left: 40,
    right: 40,
    top: '40%',
    alignItems: 'center',
  },
  toastInner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: 18,
    backgroundColor: 'rgba(47, 42, 37, 0.9)',
  },
  toastIcon: {
    marginRight: 8,
  },
  toastText: {
    color: '#FFFBF5',
    fontSize: 15,
    fontWeight: '600',
    textAlign: 'center',
  },
});
