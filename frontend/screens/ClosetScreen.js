import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useFocusEffect } from '@react-navigation/native';
import { getBestSize } from '../utils/shoeSize';

export default function ClosetScreen({ navigation }) {
  const [measurements, setMeasurements] = useState(null);

  useFocusEffect(
    React.useCallback(() => {
      AsyncStorage.getItem('footMeasurements')
        .then(raw => { if (raw) setMeasurements(JSON.parse(raw)); })
        .catch(() => {});
    }, [])
  );

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* Measurements card - top of dashboard */}
      <View style={styles.measurementsCard}>
        <View style={styles.measurementsHeader}>
          <Ionicons name="footsteps" size={28} color="#C28A5B" />
          <Text style={styles.measurementsTitle}>Your Foot Profile</Text>
        </View>
        <View style={styles.measurementsGrid}>
          <View style={styles.measurementItem}>
            <Text style={styles.measurementLabel}>Length</Text>
            <Text style={styles.measurementValue}>
              {measurements ? (measurements.length_in * 2.54).toFixed(1) + ' cm' : '—'}
            </Text>
          </View>
          <View style={styles.measurementItem}>
            <Text style={styles.measurementLabel}>Width</Text>
            <Text style={styles.measurementValue}>
              {measurements ? (measurements.width_in * 2.54).toFixed(1) + ' cm' : '—'}
            </Text>
          </View>
          <View style={styles.measurementItem}>
            <Text style={styles.measurementLabel}>Arch</Text>
            <Text style={styles.measurementValue}>—</Text>
          </View>
          <View style={styles.measurementItem}>
            <Text style={styles.measurementLabel}>Typical size</Text>
            <Text style={styles.measurementValue}>
              {measurements?.length_in ? `US ${getBestSize(measurements.length_in)}` : '—'}
            </Text>
          </View>
        </View>
      </View>

      {/* Big action buttons */}
      <TouchableOpacity
        style={styles.actionButton}
        onPress={() => navigation.navigate('SavedShoes')}
      >
        <View style={styles.actionButtonIcon}>
          <Ionicons name="heart" size={34} color="#C28A5B" />
        </View>
        <Text style={styles.actionButtonTitle}>Saved Shoes</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionButton}
        onPress={() => navigation.navigate('OwnedShoes')}
      >
        <View style={styles.actionButtonIcon}>
          <Ionicons name="archive" size={34} color="#C28A5B" />
        </View>
        <Text style={styles.actionButtonTitle}>Owned Shoes</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionButtonPrimary}
        onPress={() => navigation.navigate('FootCapture')}
      >
        <View style={styles.actionButtonIconLight}>
          <Ionicons name="camera" size={32} color="#FFFFFF" />
        </View>
        <Text style={styles.actionButtonPrimaryTitle}>Update Foot Profile</Text>
      </TouchableOpacity>
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
    paddingTop: 28,
    paddingBottom: 48,
  },
  measurementsCard: {
    backgroundColor: '#FFFBF5',
    borderRadius: 24,
    padding: 26,
    borderWidth: 1,
    borderColor: '#E2D4C0',
    marginBottom: 28,
  },
  measurementsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 20,
  },
  measurementsTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#2F2A25',
  },
  measurementsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 20,
  },
  measurementItem: {
    minWidth: '42%',
  },
  measurementLabel: {
    fontSize: 14,
    color: '#6B5F52',
    marginBottom: 4,
  },
  measurementValue: {
    fontSize: 19,
    fontWeight: '600',
    color: '#2F2A25',
  },
  actionButton: {
    backgroundColor: '#FFFBF5',
    borderRadius: 24,
    padding: 26,
    borderWidth: 1,
    borderColor: '#E2D4C0',
    marginBottom: 20,
    flexDirection: 'row',
    alignItems: 'center',
  },
  actionButtonIcon: {
    width: 64,
    height: 64,
    borderRadius: 20,
    backgroundColor: '#FFF8F0',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 20,
  },
  actionButtonTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#2F2A25',
  },
  actionButtonPrimary: {
    backgroundColor: '#C28A5B',
    borderRadius: 24,
    padding: 26,
    marginBottom: 20,
    flexDirection: 'row',
    alignItems: 'center',
  },
  actionButtonIconLight: {
    width: 64,
    height: 64,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 20,
  },
  actionButtonPrimaryTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
