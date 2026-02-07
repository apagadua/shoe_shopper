import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';

export default function MeasurementsScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding;

  // Placeholder "sample" measurements - later we can pass real data in params.
  const sample = {
    length: "25.3 cm",
    width: "9.4 cm",
    arch: "Neutral",
    pressure: "Slightly higher on forefoot",
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Your measurements</Text>
      <Text style={styles.subtitle}>
        These are example values so you can see how your fit report will look.
        We'll replace them with real measurements after your first scan.
      </Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Foot profile</Text>
        <View style={styles.row}>
          <Text style={styles.label}>Length</Text>
          <Text style={styles.value}>{sample.length}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Width</Text>
          <Text style={styles.value}>{sample.width}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Arch type</Text>
          <Text style={styles.value}>{sample.arch}</Text>
        </View>
        <View style={[styles.row, styles.rowLast]}>
          <Text style={styles.label}>Pressure areas</Text>
          <Text style={[styles.value, styles.valueMultiline]}>
            {sample.pressure}
          </Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.primaryButton}
        onPress={() =>
          fromOnboarding
            ? navigation.replace('MainTabs')
            : navigation.navigate('ClosetHome')
        }
      >
        <Text style={styles.primaryButtonText}>
          {fromOnboarding ? 'Go to My Closet' : 'Back to My Closet'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.secondaryAction}
        onPress={() => navigation.navigate('Camera', fromOnboarding ? { fromOnboarding: true } : {})}
      >
        <Text style={styles.secondaryText}>Retake Photo</Text>
      </TouchableOpacity>
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
    alignItems: 'flex-start',
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
  valueMultiline: {
    maxWidth: '60%',
    textAlign: 'right',
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
});
