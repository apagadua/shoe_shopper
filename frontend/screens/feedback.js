/**
 * Fit feedback sliders for owned shoes (length/width −5…+5).
 * UI-only today — submit does not POST to the backend; see FRONTEND_FEATURES.md §9.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const SCALE_VALUES = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5];

function ScaleNumbers() {
  return (
    <View style={styles.scaleNumberRow}>
      {SCALE_VALUES.map((value) => (
        <Text
          key={String(value)}
          style={[styles.scaleNumber, value === 0 && styles.scaleNumberCenter]}
        >
          {Math.abs(value)}
        </Text>
      ))}
    </View>
  );
}

function clamp(min, value, max) {
  return Math.max(min, Math.min(value, max));
}

function valueToOffset(value, trackWidth) {
  if (!trackWidth) return 0;
  return ((value + 5) / 10) * trackWidth;
}

function offsetToValue(offset, trackWidth) {
  if (!trackWidth) return 0;
  const normalized = clamp(0, offset, trackWidth) / trackWidth;
  return Math.round(normalized * 10 - 5);
}

function FitSlider({ title, leftLabel, rightLabel, value, onChange }) {
  const [trackWidth, setTrackWidth] = useState(0);

  const setByOffset = useCallback(
    (offsetX) => {
      onChange(offsetToValue(offsetX, trackWidth));
    },
    [onChange, trackWidth]
  );

  return (
    <View style={styles.sliderCard}>
      <Text style={styles.sliderTitle}>{title}</Text>
      <ScaleNumbers />

      <View
        style={styles.sliderTrackWrap}
        onLayout={(e) => setTrackWidth(e.nativeEvent.layout.width)}
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderGrant={(e) => setByOffset(e.nativeEvent.locationX)}
        onResponderMove={(e) => setByOffset(e.nativeEvent.locationX)}
      >
        <View style={styles.sliderTrackLine} />
        <View style={styles.sliderTickRow}>
          {SCALE_VALUES.map((step) => (
            <View key={String(step)} style={[styles.tickMark, step === 0 && styles.tickMarkCenter]} />
          ))}
        </View>
        <View
          pointerEvents="none"
          style={[
            styles.sliderThumb,
            {
              left: valueToOffset(value, trackWidth) - 11,
            },
          ]}
        >
          <View style={styles.sliderThumbInner} />
        </View>
      </View>

      <View style={styles.edgeLabelRow}>
        <Text style={styles.edgeLabel}>{leftLabel}</Text>
        <Text style={styles.edgeLabel}>{rightLabel}</Text>
      </View>
    </View>
  );
}

function getLengthLabel(value) {
  if (value === 0) return 'Perfect';
  return value < 0 ? 'Too short' : 'Too long';
}

function getWidthLabel(value) {
  if (value === 0) return 'Perfect';
  return value < 0 ? 'Too narrow' : 'Too wide';
}

export default function FeedbackScreen({ route, navigation }) {
  const shoe = route?.params?.shoe;
  const [lengthFeedback, setLengthFeedback] = useState(0);
  const [widthFeedback, setWidthFeedback] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submitTimeoutRef = useRef(null);

  const fitSummary = useMemo(() => {
    if (lengthFeedback === 0 && widthFeedback === 0) return 'Perfect fit';
    return 'Feedback captured';
  }, [lengthFeedback, widthFeedback]);

  useEffect(() => {
    return () => {
      if (submitTimeoutRef.current) clearTimeout(submitTimeoutRef.current);
    };
  }, []);

  // TODO: POST feedback to backend when /api/feedback/ exists — see FRONTEND_FEATURES.md §9.
  const handleSubmit = () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setSubmitted(true);
    submitTimeoutRef.current = setTimeout(() => {
      navigation.goBack();
    }, 900);
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.headerCard}>
        <View style={styles.headerIcon}>
          <Ionicons name="checkmark-circle-outline" size={24} color="#C28A5B" />
        </View>
        <Text style={styles.title}>Fit Feedback</Text>
        <Text style={styles.shoeName}>
          {shoe?.brand || ''} {shoe?.model || ''}
        </Text>
        <Text style={styles.subtitle}>
          Rate how this pair fits. Drag the slider knob to set your feedback.
        </Text>
      </View>

      <FitSlider
        title="Length Fit"
        leftLabel="Too short"
        rightLabel="Too long"
        value={lengthFeedback}
        onChange={setLengthFeedback}
      />

      <FitSlider
        title="Width Fit"
        leftLabel="Too narrow"
        rightLabel="Too wide"
        value={widthFeedback}
        onChange={setWidthFeedback}
      />

      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Current result</Text>
        <Text style={styles.summaryText}>{fitSummary}</Text>
        <Text style={styles.summaryTextSmall}>
          Length: {getLengthLabel(lengthFeedback)} | Width: {getWidthLabel(widthFeedback)}
        </Text>
      </View>

      <TouchableOpacity style={styles.submitButton} onPress={handleSubmit} activeOpacity={0.9}>
        <Text style={styles.submitButtonText}>{isSubmitting ? 'Submitting...' : 'Submit Feedback'}</Text>
      </TouchableOpacity>

      {submitted ? (
        <View style={styles.toastContainer} pointerEvents="none">
          <View style={styles.submittedCard}>
            <Ionicons name="checkmark-circle" size={18} color="#4D8C5C" />
            <Text style={styles.submittedText}>Thank you for submitting your fit feedback!</Text>
          </View>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FCFAF7',
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 36,
    gap: 16,
  },
  headerCard: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  headerIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F0E2D0',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 4,
  },
  shoeName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#4F453C',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#6B5F52',
    lineHeight: 20,
  },
  sliderCard: {
    backgroundColor: '#FFFBF5',
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  sliderTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#2F2A25',
    marginBottom: 12,
  },
  scaleNumberRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
    paddingHorizontal: 2,
  },
  scaleNumber: {
    fontSize: 11,
    color: '#9B8E82',
    width: 20,
    textAlign: 'center',
  },
  scaleNumberCenter: {
    color: '#C28A5B',
    fontWeight: '700',
  },
  sliderTrackWrap: {
    height: 44,
    justifyContent: 'center',
    position: 'relative',
  },
  sliderTrackLine: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#E2D4C0',
  },
  sliderTickRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  tickMark: {
    width: 2,
    height: 10,
    borderRadius: 1,
    backgroundColor: '#C9BBA8',
  },
  tickMarkCenter: {
    height: 14,
    backgroundColor: '#C28A5B',
  },
  sliderThumb: {
    position: 'absolute',
    top: 11,
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: '#C28A5B',
    backgroundColor: '#FFFBF5',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sliderThumbInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#C28A5B',
  },
  edgeLabelRow: {
    marginTop: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  edgeLabel: {
    fontSize: 12,
    color: '#6B5F52',
    fontWeight: '500',
  },
  summaryCard: {
    backgroundColor: '#FFF8F0',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2D4C0',
  },
  summaryTitle: {
    fontSize: 13,
    color: '#6B5F52',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    fontWeight: '600',
  },
  summaryText: {
    fontSize: 18,
    color: '#2F2A25',
    fontWeight: '700',
  },
  summaryTextSmall: {
    marginTop: 6,
    fontSize: 13,
    color: '#6B5F52',
  },
  toastContainer: {
    position: 'absolute',
    left: 34,
    right: 34,
    top: '42%',
    alignItems: 'center',
  },
  submittedCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#EEF8F0',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#CFE7D4',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 16,
    width: '100%',
  },
  submittedText: {
    flex: 1,
    fontSize: 13,
    color: '#2F6B3D',
    fontWeight: '600',
  },
  submitButton: {
    marginTop: 2,
    backgroundColor: '#C28A5B',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  submitButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
});
