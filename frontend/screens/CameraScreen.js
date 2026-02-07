import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';

export default function CameraScreen({ navigation, route }) {
  const fromOnboarding = route.params?.fromOnboarding;

  const handleContinue = () => {
    navigation.navigate('Measurements', { fromOnboarding });
  };

  return (
    <View style={styles.container}>
      {/* Placeholder - camera UI will go here later */}
      <View style={styles.placeholder} />
      <TouchableOpacity style={styles.continueButton} onPress={handleContinue}>
        <Text style={styles.continueButtonText}>Continue</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5EFE6',
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 24,
  },
  placeholder: {
    height: 280,
    backgroundColor: '#F0E2D0',
    borderRadius: 16,
    marginBottom: 24,
  },
  continueButton: {
    backgroundColor: '#C28A5B',
    paddingVertical: 16,
    borderRadius: 999,
    alignItems: 'center',
  },
  continueButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
