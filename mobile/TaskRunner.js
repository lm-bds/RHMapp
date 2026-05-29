import React, { useState } from 'react';
import { StyleSheet, View, Text, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';

export default function TaskRunner({ tasks, deviceToken, apiBaseUrl, onComplete }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFinished, setIsFinished] = useState(false);

  const currentTask = tasks[currentIndex];

  const handleAnswer = (value) => {
    const newAnswers = [...answers, { question_id: currentTask.id, answer_value: value }];
    setAnswers(newAnswers);
    
    if (currentIndex < tasks.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      submitAll(newAnswers);
    }
  };

  const submitAll = async (finalAnswers) => {
    setIsSubmitting(true);
    try {
      // Logic for MVP: Separate vitals and questionnaire answers
      // This is a simplified mapper
      const submission = {
        vitals: {
          weight: finalAnswers.find(a => a.question_id === 'weight_reading')?.answer_value === 'DONE' ? 85.5 : null, // Simulated
          systolic: finalAnswers.find(a => a.question_id === 'bp_reading')?.answer_value === 'DONE' ? 120 : null,
          diastolic: finalAnswers.find(a => a.question_id === 'bp_reading')?.answer_value === 'DONE' ? 80 : null,
        },
        questionnaire: finalAnswers.filter(a => !['weight_reading', 'bp_reading'].includes(a.question_id))
      };

      const response = await fetch(`${apiBaseUrl}/tasks/submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${deviceToken}`
        },
        body: JSON.stringify(submission),
      });

      if (response.ok) {
        setIsFinished(true);
      } else {
        Alert.alert('Error', 'Failed to submit tasks. Please try again.');
      }
    } catch (e) {
      console.error(e);
      Alert.alert('Network Error', 'Check your connection.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (tasks.length === 0 || isFinished) {
    return (
      <View style={styles.centered}>
        <Text style={styles.successText}>✅</Text>
        <Text style={styles.mainLabel}>You are all caught up for today.</Text>
        <Text style={styles.subLabel}>See you tomorrow!</Text>
      </View>
    );
  }

  if (isSubmitting) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.mainLabel}>Sending to your doctor...</Text>
      </View>
    );
  }

  // Task Rendering Logic
  if (currentTask.type === 'vital') {
    return (
      <View style={styles.container}>
        <Text style={styles.instructionText}>{currentTask.label}</Text>
        <View style={styles.devicePlaceholder}>
          <ActivityIndicator size="large" color="#007AFF" style={{ transform: [{ scale: 2 }] }} />
          <Text style={styles.placeholderText}>Waiting for device...</Text>
          {/* TODO: Add react-native-ble-plx hardware hooks here */}
        </View>
        <TouchableOpacity style={styles.manualButton} onPress={() => handleAnswer('DONE')}>
          <Text style={styles.manualButtonText}>I'm Done</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (currentTask.type === 'questionnaire') {
    const options = currentTask.metadata?.options || ["Yes", "No"];
    return (
      <View style={styles.container}>
        <Text style={styles.instructionText}>{currentTask.label}</Text>
        <View style={styles.buttonGrid}>
          {options.map((opt) => (
            <TouchableOpacity 
              key={opt}
              style={[styles.choiceButton, opt === 'Yes' ? styles.yesButton : styles.noButton]} 
              onPress={() => handleAnswer(opt)}
            >
              <Text style={styles.choiceText}>{opt}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
    );
  }

  return null;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#fff',
    justifyContent: 'space-between',
    paddingVertical: 80,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
    backgroundColor: '#fff',
  },
  instructionText: {
    fontSize: 48,
    fontWeight: '900',
    textAlign: 'center',
    color: '#000',
  },
  devicePlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
    height: 300,
  },
  placeholderText: {
    fontSize: 24,
    color: '#666',
    marginTop: 40,
  },
  manualButton: {
    backgroundColor: '#eee',
    padding: 30,
    borderRadius: 20,
  },
  manualButtonText: {
    fontSize: 24,
    textAlign: 'center',
    color: '#333',
  },
  buttonGrid: {
    flex: 1,
    justifyContent: 'center',
    gap: 30,
  },
  choiceButton: {
    height: 180,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 30,
  },
  yesButton: {
    backgroundColor: '#34C759',
  },
  noButton: {
    backgroundColor: '#FF3B30',
  },
  choiceText: {
    fontSize: 72,
    fontWeight: 'bold',
    color: '#fff',
  },
  successText: {
    fontSize: 120,
    marginBottom: 20,
  },
  mainLabel: {
    fontSize: 42,
    fontWeight: 'bold',
    textAlign: 'center',
    color: '#000',
  },
  subLabel: {
    fontSize: 28,
    color: '#666',
    marginTop: 20,
    textAlign: 'center',
  }
});
