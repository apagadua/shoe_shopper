import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function ManualMeasurementScreen({ navigation, route }) {
    const fromOnboarding = route.params?.fromOnboarding;
    const [length, setLength] = useState('');
    const [width, setWidth] = useState('');
    const [toeboxLength, setToeboxLength] = useState('');
    const [toeboxWidth, setToeboxWidth] = useState('');

    const [errors, setErrors] = useState({
        length: false,
        width: false,
        toeboxLength: false,
        toeboxWidth: false,
    });
    const [errorMessage, setErrorMessage] = useState('');

    const handleSubmit = () => {
        const newErrors = {
            length: !length,
            width: !width,
            toeboxLength: !toeboxLength,
            toeboxWidth: !toeboxWidth,
        };
        setErrors(newErrors);

        if (Object.values(newErrors).some((e) => e)) {
            setErrorMessage("Please fill in all fields before submitting.");
            return;
        }

        const area = Number(length) * Number(width) * 0.70;

        const measurements = {
            length_in: Number(length),
            width_in: Number(width),
            toebox_length_in: Number(toeboxLength),
            toebox_width_in: Number(toeboxWidth),
            area_sq_in: area,
            measurement_method: 'manual',
        };

        navigation.navigate('Measurements', { fromOnboarding, measurements: measurements });
    };

    return (
        <ScrollView contentContainerStyle={styles.container}>
            <Text style={styles.title}>Manual Measurement</Text>
            <Text style={styles.subtitle}>
                Enter your foot measurements using a ruler or tape measure.
            </Text>

            <View style={styles.card}>
                <View style={styles.filedRow}>
                    <Ionicons name="swap-vertical-outline" size={20} color="#6b5F52" style={{ marginBottom: 10 }} />
                    <Text style={styles.fieldLabel}>Foot length (in)</Text>
                </View>
            </View>
            <TextInput
                style={[styles.input, errors.length && styles.inputError]}
                keyboardType="numeric"
                value={length}
                onChangeText={setLength}
                placeholder="e.g. 10.5"
                placeholderTextColor="#A89880"
            />

            <View style={styles.card}>
                <View style={styles.filedRow}>
                    <Ionicons name="swap-horizontal-outline" size={20} color="#6b5F52" style={{ marginBottom: 10 }} />
                    <Text style={styles.fieldLabel}>Foot width (in)</Text>
                </View>
            </View>
            <TextInput
                style={[styles.input, errors.width && styles.inputError]}
                keyboardType="numeric"
                value={width}
                onChangeText={setWidth}
                placeholder="e.g. 4.0"
                placeholderTextColor="#A89880"
            />

            <View style={styles.card}>
                <View style={styles.filedRow}>
                    <Ionicons name="swap-vertical-outline" size={20} color="#6b5F52" style={{ marginBottom: 10 }} />
                    <Text style={styles.fieldLabel}>Toebox length (in)</Text>
                </View>
            </View>
            <TextInput
                style={[styles.input, errors.toeboxLength && styles.inputError]}
                keyboardType="numeric"
                value={toeboxLength}
                onChangeText={setToeboxLength}
                placeholder="e.g. 3.5"
                placeholderTextColor="#A89880"
            />

            <View style={styles.card}>
                <View style={styles.filedRow}>
                    <Ionicons name="swap-horizontal-outline" size={20} color="#6b5F52" style={{ marginBottom: 10 }} />
                    <Text style={styles.fieldLabel}>Toebox width (in)</Text>
                </View>
            </View>
            <TextInput
                style={[styles.input, errors.toeboxWidth && styles.inputError]}
                keyboardType="numeric"
                value={toeboxWidth}
                onChangeText={setToeboxWidth}
                placeholder="e.g. 3.5"
                placeholderTextColor="#A89880"
            />

            {errorMessage ? (
                <Text style={styles.errorMessage}>{errorMessage}</Text>
            ) : null}

            <TouchableOpacity style={styles.primaryButton} onPress={handleSubmit}>
                <Text style={styles.primaryButtonText}>Save Measurements</Text>
            </TouchableOpacity>
        </ScrollView>
    )
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#F5EFE6',
        paddingHorizontal: 24,
        paddingTop: 60,
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
        marginBottom: 24,
        lineHeight: 21,
    },
    card: {
        backgroundColor: '#FFFBF5',
        borderRadius: 20,
        padding: 6,
        borderWidth: 1,
        borderColor: '#E2D4C0',
        marginBottom: 4,
    },
    filedRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
        marginTop: 12,
    },
    fieldLabel: {
        fontSize: 14,
        fontWeight: '600',
        color: '#4F453C',
        marginBottom: 8,
    },
    input: {
        backgroundColor: '#FFF',
        borderWidth: 1,
        borderColor: '#E2D4C0',
        borderRadius: 12,
        paddingHorizontal: 14,
        paddingVertical: 12,
        fontSize: 15,
        color: '#2F2A25',
        marginBottom: 16,
    },
    inputError: {
        borderColor: "#D9534F",
    },
    errorMessage: {
        color: '#D9534F',
        fontSize: 15,
        marginBottom: 12,
        textAlign: 'center',
    },
    primaryButton: {
        backgroundColor: '#C28A5B',
        paddingVertical: 15,
        borderRadius: 999,
        alignItems: 'center',
    },
    primaryButtonText: {
        color: '#FFFFF',
        fontSize: 16,
        fontWeight: '600',
    },
});