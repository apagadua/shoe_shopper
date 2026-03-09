import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { getBestSize, getSizeRange } from '../utils/shoeSize';

function inToCm(inches) {
  return (inches * 2.54).toFixed(1);
}

function formatInches(val) {
  return `${val.toFixed(1)} in (${inToCm(val)} cm)`;
}

export default function MeasurementsScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding;
  const measurements = route.params?.measurements ?? null;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Your measurements</Text>
      <Text style={styles.subtitle}>
        {measurements
          ? 'Measurements computed from your scan.'
          : 'Scan a foot to see real measurements.'}
      </Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Foot profile</Text>
        <View style={styles.row}>
          <Text style={styles.label}>Foot length</Text>
          <Text style={styles.value}>
            {measurements ? formatInches(measurements.length_in) : '—'}
          </Text>
        </View>
        <View style={[styles.row, styles.rowLast]}>
          <Text style={styles.label}>Foot width</Text>
          <Text style={styles.value}>
            {measurements ? formatInches(measurements.width_in) : '—'}
          </Text>
        </View>
        {measurements ? (
          <View style={[styles.row, styles.rowLast]}>
            <Text style={styles.label}>Foot area</Text>
            <Text style={styles.value}>{measurements.area_sq_in.toFixed(1)} sq in</Text>
          </View>
        ) : null}
      </View>

      {measurements?.length_in ? (() => {
        const best = getBestSize(measurements.length_in);
        const range = getSizeRange(measurements.length_in);
        const rangeStr = range.length > 1
          ? `${range[0]}–${range[range.length - 1]}`
          : range[0] ?? best;
        return (
          <View style={styles.sizeCard}>
            <Text style={styles.sizeCardLabel}>Estimated US size (men's)</Text>
            <Text style={styles.sizeCardValue}>US {best}</Text>
            <Text style={styles.sizeCardRange}>Plausible range: {rangeStr}</Text>
            <Text style={styles.sizeCardNote}>
              Sizes vary by brand — use this as a starting point, not a guarantee.
            </Text>
          </View>
        );
      })() : null}

      {fromOnboarding ? (
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => navigation.replace('MainTabs')}
        >
          <Text style={styles.primaryButtonText}>Go to My Closet</Text>
        </TouchableOpacity>
      ) : (
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => navigation.navigate('Recommendations')}
        >
          <Text style={styles.primaryButtonText}>See Recommendations</Text>
        </TouchableOpacity>
      )}

      <TouchableOpacity
        style={styles.secondaryAction}
        onPress={() =>
          fromOnboarding
            ? navigation.navigate('Camera', { fromOnboarding: true })
            : navigation.navigate('ClosetHome')
        }
      >
        <Text style={styles.secondaryText}>
          {fromOnboarding ? 'Retake Photo' : 'Back to My Closet'}
        </Text>
      </TouchableOpacity>

      {!fromOnboarding && (
        <TouchableOpacity
          style={styles.tertiaryAction}
          onPress={() => navigation.navigate('Camera')}
        >
          <Text style={styles.tertiaryText}>Retake Photo</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5EFE6',
    paddingHorizontal: 24,
    paddingTop: 80,
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    color: '#6B5F52',
    marginBottom: 28,
    lineHeight: 21,
  },
  card: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    paddingVertical: 20,
    paddingHorizontal: 18,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2F2A25',
    marginBottom: 12,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F0E2D0',
  },
  rowLast: {
    borderBottomWidth: 0,
  },
  label: {
    fontSize: 14,
    color: '#4F453C',
  },
  value: {
    fontSize: 14,
    color: '#2F2A25',
    fontWeight: '600',
  },
  sizeCard: {
    marginTop: 16,
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    paddingVertical: 18,
    paddingHorizontal: 18,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  sizeCardLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6B5F52',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  sizeCardValue: {
    fontSize: 28,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 2,
  },
  sizeCardRange: {
    fontSize: 13,
    color: '#4F453C',
    marginBottom: 8,
  },
  sizeCardNote: {
    fontSize: 12,
    color: '#9B8E82',
    lineHeight: 17,
  },
  primaryButton: {
    marginTop: 28,
    backgroundColor: '#C28A5B',
    paddingVertical: 16,
    borderRadius: 999,
    alignItems: 'center',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryAction: {
    marginTop: 16,
    alignItems: 'center',
  },
  secondaryText: {
    fontSize: 14,
    color: '#6B5F52',
  },
  tertiaryAction: {
    marginTop: 10,
    alignItems: 'center',
  },
  tertiaryText: {
    fontSize: 13,
    color: '#9B8E82',
  },
});
