import React, { useState, useEffect } from 'react';
import { StyleSheet, View, Text, ActivityIndicator } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import SetupScanner from './SetupScanner';
import TaskRunner from './TaskRunner';
import Dashboard from './Dashboard';

const API_BASE_URL = 'http://192.168.1.110:8000/api/v1';

export default function App() {
  const [isBound, setIsBound] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showTaskRunner, setShowTaskRunner] = useState(false);
  const [deviceToken, setDeviceToken] = useState(null);
  
  const [patientName, setPatientName] = useState('');
  const [todayTasks, setTodayTasks] = useState([]);
  const [appointments, setAppointments] = useState([]);

  useEffect(() => {
    checkBinding();
  }, []);

  const checkBinding = async () => {
    try {
      const token = await SecureStore.getItemAsync('device_token');
      if (token) {
        setDeviceToken(token);
        await fetchTasks(token);
        setIsBound(true);
      } else {
        setIsBound(false);
      }
    } catch (e) {
      console.error('Failed to load token', e);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTasks = async (token) => {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/today`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setPatientName(data.patient_name);
        setTodayTasks(data.tasks);
        setAppointments(data.upcoming_appointments);
      } else if (response.status === 401) {
        await SecureStore.deleteItemAsync('device_token');
        setIsBound(false);
      }
    } catch (e) {
      console.error('Failed to fetch tasks', e);
    }
  };

  const handleBindingComplete = async (token) => {
    setDeviceToken(token);
    await fetchTasks(token);
    setIsBound(true);
  };

  const handleTasksComplete = async () => {
    setShowTaskRunner(false);
    await fetchTasks(deviceToken); // Refresh to show completed state
  };

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#4a3728" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (!isBound) {
    return (
      <View style={styles.container}>
        <SetupScanner onBindingComplete={handleBindingComplete} apiBaseUrl={API_BASE_URL} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {showTaskRunner ? (
        <TaskRunner 
          tasks={todayTasks} 
          deviceToken={deviceToken} 
          apiBaseUrl={API_BASE_URL} 
          onComplete={handleTasksComplete} 
        />
      ) : (
        <Dashboard 
          patientName={patientName} 
          tasks={todayTasks} 
          appointments={appointments} 
          onStartTasks={() => setShowTaskRunner(true)} 
          onRefresh={() => fetchTasks(deviceToken)}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f7f5f0',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f7f5f0',
  },
  loadingText: {
    marginTop: 20,
    fontSize: 24,
    fontWeight: 'bold',
    color: '#4a3728',
  }
});
