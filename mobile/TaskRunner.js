import React, { useState } from 'react';
import { StyleSheet, View, Text, TouchableOpacity, ActivityIndicator, Alert, TextInput } from 'react-native';

export default function TaskRunner({ tasks, deviceToken, apiBaseUrl, onComplete }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFinished, setIsFinished] = useState(false);
  const [inputValue, setInputValues] = useState({}); // Stores { task_id: value }

  const currentTask = tasks[currentIndex];

  const validateInput = (id, val) => {
    const num = parseFloat(val);
    if (isNaN(num)) return false;

    const ranges = {
      'weight_reading': { min: 30, max: 250, label: 'Weight' },
      'bp_reading_sys': { min: 70, max: 250, label: 'Systolic BP' },
      'bp_reading_dia': { min: 40, max: 150, label: 'Diastolic BP' },
      'hr_reading': { min: 30, max: 220, label: 'Heart Rate' },
      'spo2_reading': { min: 70, max: 100, label: 'Oxygen' }
    };

    const range = ranges[id];
    if (range && (num < range.min || num > range.max)) {
      Alert.alert('Unusual Value', `The entered ${range.label} (${val}) seems incorrect. Please check the number.`);
      return false;
    }
    return true;
  };

  const handleNext = () => {
    // For BP we need two inputs, handle specially
    if (currentTask.id === 'bp_reading') {
      const sys = inputValue['bp_sys'];
      const dia = inputValue['bp_dia'];
      if (!validateInput('bp_reading_sys', sys) || !validateInput('bp_reading_dia', dia)) return;
      
      const newAnswers = [...answers, 
        { question_id: 'bp_reading_sys', answer_value: sys },
        { question_id: 'bp_reading_dia', answer_value: dia }
      ];
      finalizeStep(newAnswers);
    } else {
      const val = inputValue[currentTask.id];
      if (!validateInput(currentTask.id, val)) return;
      
      const newAnswers = [...answers, { question_id: currentTask.id, answer_value: val }];
      finalizeStep(newAnswers);
    }
  };

  const finalizeStep = (newAnswers) => {
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
      const submission = {
        vitals: {
          weight: parseFloat(finalAnswers.find(a => a.question_id === 'weight_reading')?.answer_value),
          systolic: parseInt(finalAnswers.find(a => a.question_id === 'bp_reading_sys')?.answer_value),
          diastolic: parseInt(finalAnswers.find(a => a.question_id === 'bp_reading_dia')?.answer_value),
          heart_rate: parseInt(finalAnswers.find(a => a.question_id === 'hr_reading')?.answer_value),
          spo2: parseInt(finalAnswers.find(a => a.question_id === 'spo2_reading')?.answer_value),
        },
        questionnaire: finalAnswers.filter(a => !['weight_reading', 'bp_reading_sys', 'bp_reading_dia', 'hr_reading', 'spo2_reading'].includes(a.question_id))
      };

      const response = await fetch(`${apiBaseUrl}/tasks/submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${deviceToken}`
        },
        body: JSON.stringify(submission),
      });

      if (response.ok) setIsFinished(true);
      else Alert.alert('Error', 'Failed to save readings.');
    } catch (e) {
      Alert.alert('Network Error', 'Check your connection.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isFinished) {
    return (
      <View style={styles.centered}>
        <Text style={styles.successIcon}>✅</Text>
        <Text style={styles.mainLabel}>Readings Saved!</Text>
        <TouchableOpacity style={styles.backButton} onPress={onComplete}><Text style={styles.backButtonText}>Finish</Text></TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.progressText}>Item {currentIndex + 1} of {tasks.length}</Text>
      
      <View style={styles.content}>
        <Text style={styles.instructionText}>{currentTask.label}</Text>
        
        {currentTask.type === 'vital' ? (
          <View style={styles.inputArea}>
            {currentTask.id === 'bp_reading' ? (
              <View style={styles.bpContainer}>
                <TextInput 
                  style={styles.hugeInput} 
                  keyboardType="numeric" 
                  placeholder="SYS"
                  onChangeText={(v) => setInputValues({...inputValue, 'bp_sys': v})}
                />
                <Text style={styles.slash}>/</Text>
                <TextInput 
                  style={styles.hugeInput} 
                  keyboardType="numeric" 
                  placeholder="DIA"
                  onChangeText={(v) => setInputValues({...inputValue, 'bp_dia': v})}
                />
              </View>
            ) : (
              <TextInput 
                style={styles.hugeInput} 
                keyboardType="numeric" 
                placeholder="00.0"
                onChangeText={(v) => setInputValues({...inputValue, [currentTask.id]: v})}
              />
            )}
            <TouchableOpacity style={styles.nextButton} onPress={handleNext}>
              <Text style={styles.nextButtonText}>NEXT →</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.buttonGrid}>
            <TouchableOpacity style={[styles.choiceButton, styles.yesButton]} onPress={() => finalizeStep([...answers, { question_id: currentTask.id, answer_value: 'Yes' }])}>
              <Text style={styles.choiceText}>YES</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.choiceButton, styles.noButton]} onPress={() => finalizeStep([...answers, { question_id: currentTask.id, answer_value: 'No' }])}>
              <Text style={styles.choiceText}>NO</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f7f5f0', padding: 20, paddingTop: 60 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f7f5f0' },
  progressText: { fontSize: 16, fontWeight: '900', color: '#b47b59', textAlign: 'center', letterSpacing: 2 },
  content: { flex: 1, justifyContent: 'center' },
  instructionText: { fontSize: 44, fontWeight: '900', textAlign: 'center', color: '#4a3728', marginBottom: 40 },
  inputArea: { alignItems: 'center' },
  hugeInput: { fontSize: 80, fontWeight: '900', color: '#4a3728', textAlign: 'center', borderBottomWidth: 5, borderBottomColor: '#e6e2da', width: 200, marginBottom: 40 },
  bpContainer: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  slash: { fontSize: 60, color: '#e6e2da', fontWeight: 'bold' },
  nextButton: { backgroundColor: '#4a3728', paddingVertical: 25, paddingHorizontal: 60, borderRadius: 25, width: '100%' },
  nextButtonText: { color: '#fff', fontSize: 32, fontWeight: '900', textAlign: 'center' },
  buttonGrid: { gap: 20 },
  choiceButton: { height: 160, justifyContent: 'center', alignItems: 'center', borderRadius: 30 },
  yesButton: { backgroundColor: '#16a34a' },
  noButton: { backgroundColor: '#dc2626' },
  choiceText: { fontSize: 70, fontWeight: '900', color: '#fff' },
  successIcon: { fontSize: 100, marginBottom: 20 },
  mainLabel: { fontSize: 32, fontWeight: '900', color: '#4a3728' },
  backButton: { marginTop: 40, backgroundColor: '#b47b59', padding: 20, borderRadius: 20 },
  backButtonText: { color: '#fff', fontSize: 20, fontWeight: 'bold' }
});
