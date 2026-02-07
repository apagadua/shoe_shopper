import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Dimensions,
} from 'react-native';
import { Feather, FontAwesome5 } from '@expo/vector-icons';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
// Section has scroll padding 24*2 + section padding 18*2
const CARD_WIDTH = SCREEN_WIDTH - 24 * 2 - 18 * 2;

const FEATURES = [
  {
    key: '1',
    icon: 'camera',
    iconSet: 'feather',
    iconBg: '#D3E2F2',
    title: '1. Upload Photo',
    text: 'Snap your foot on a sheet of paper. We use it as a scale to keep every measurement accurate.',
  },
  {
    key: '2',
    icon: 'magic',
    iconSet: 'fontawesome5',
    iconBg: '#D4E3C4',
    title: '2. AI Measurement',
    text: 'Our model detects your foot outline and calculates length, width, and key pressure areas.',
  },
  {
    key: '3',
    icon: 'shopping-bag',
    iconSet: 'feather',
    iconBg: '#E5D4FF',
    title: '3. Smart Recommendations',
    text: 'Get shoes matched to your measurements and style so each pair feels like it was made for you.',
  },
];

export default function WelcomeScreen({ navigation }) {
  const [activeIndex, setActiveIndex] = useState(0);

  const onScroll = useCallback((e) => {
    const offset = e.nativeEvent.contentOffset.x;
    const index = Math.round(offset / CARD_WIDTH);
    setActiveIndex(index);
  }, []);

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.heroSection}>
          <Text style={styles.title}>Find Your Perfect Fit</Text>
          <Text style={styles.subtitle}>
            Upload a photo of your foot and let our AI-powered measurements recommend
            the right shoes for comfort and confidence.
          </Text>

          <TouchableOpacity
            style={styles.button}
            onPress={() => navigation.navigate('CreateAccount')}
          >
            <Text style={styles.buttonText}>Get Started Free</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.secondaryAction}
            onPress={() => navigation.navigate('Login')}
          >
            <Text style={styles.secondaryText}>
              Already have an account?{' '}
              <Text style={styles.secondaryTextBold}>Log in</Text>
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.infoSection}>
          <Text style={styles.sectionTitle}>How Shoe Shopper Works</Text>
          <Text style={styles.sectionSubtitle}>
            Our computer vision pipeline turns a simple foot photo into precise
            measurements and personalized shoe recommendations.
          </Text>

          <View style={styles.carouselWrapper}>
            <ScrollView
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              onScroll={onScroll}
              scrollEventThrottle={16}
              decelerationRate="fast"
              snapToInterval={CARD_WIDTH}
              snapToAlignment="start"
              contentContainerStyle={styles.carouselContent}
            >
              {FEATURES.map((feature) => (
                <View key={feature.key} style={[styles.stepCard, { width: CARD_WIDTH }]}>
                  <View style={[styles.stepIcon, { backgroundColor: feature.iconBg }]}>
                    {feature.iconSet === 'feather' ? (
                      <Feather name={feature.icon} size={22} color="#2F2A25" />
                    ) : (
                      <FontAwesome5 name={feature.icon} size={20} color="#2F2A25" />
                    )}
                  </View>
                  <Text style={styles.stepTitle}>{feature.title}</Text>
                  <Text style={styles.stepText}>{feature.text}</Text>
                </View>
              ))}
            </ScrollView>
            <View style={styles.pagination}>
              {FEATURES.map((_, index) => (
                <View
                  key={index}
                  style={[
                    styles.dot,
                    index === activeIndex && styles.dotActive,
                  ]}
                />
              ))}
            </View>
          </View>
        </View>
      </ScrollView>
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
    paddingTop: 64,
    paddingBottom: 40,
  },
  heroSection: {
    alignItems: 'center',
    marginBottom: 40,
  },
  title: {
    fontSize: 30,
    fontWeight: '700',
    marginBottom: 16,
    textAlign: 'center',
    color: '#2F2A25',
    paddingHorizontal: 8,
  },
  subtitle: {
    fontSize: 15,
    textAlign: 'center',
    color: '#6B5F52',
    marginBottom: 32,
    lineHeight: 22,
    paddingHorizontal: 8,
  },
  button: {
    backgroundColor: '#C28A5B',
    paddingHorizontal: 40,
    paddingVertical: 16,
    borderRadius: 999,
    marginBottom: 16,
    minWidth: 220,
    alignItems: 'center',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryAction: {
    paddingVertical: 8,
    alignItems: 'center',
  },
  secondaryText: {
    fontSize: 14,
    color: '#7A6B5A',
  },
  secondaryTextBold: {
    fontWeight: '600',
    color: '#2F2A25',
  },
  infoSection: {
    backgroundColor: '#FFF',
    borderRadius: 24,
    paddingVertical: 24,
    paddingHorizontal: 18,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
    color: '#2F2A25',
    marginBottom: 6,
  },
  sectionSubtitle: {
    fontSize: 14,
    textAlign: 'center',
    color: '#6B5F52',
    marginBottom: 20,
    lineHeight: 20,
  },
  carouselWrapper: {
    marginBottom: 8,
  },
  carouselContent: {
    alignItems: 'stretch',
  },
  stepCard: {
    paddingVertical: 20,
    paddingHorizontal: 16,
    borderRadius: 16,
    backgroundColor: '#F9F2E6',
    alignItems: 'center',
    marginRight: 0,
  },
  stepIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    marginBottom: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pagination: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    marginTop: 16,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#D4C9B8',
  },
  dotActive: {
    backgroundColor: '#C28A5B',
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  stepTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#2F2A25',
    textAlign: 'center',
    marginBottom: 4,
  },
  stepText: {
    fontSize: 12,
    color: '#6B5F52',
    textAlign: 'center',
    lineHeight: 18,
  },
});
