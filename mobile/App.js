import React, { useState, useEffect } from 'react';
import { StyleSheet, View, Text, ActivityIndicator } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import SetupScanner from './SetupScanner';
import TaskRunner from './TaskRunner';

const API_BASE_URL = 'http://YOUR_BACKEND_IP:8000/api/v1'; // Update with actual backend IP

export default function App() {
  const [isBound, setIsBound] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [deviceToken, setDeviceToken] = useState(null);
  const [todayTasks, setTodayTasks] = useState([]);

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
        setTodayTasks(data.tasks);
      } else {
        // If token is invalid or revoked, reset binding
        if (response.status === 401) {
          await SecureStore.deleteItemAsync('device_token');
          setIsBound(false);
        }
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

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#0000ff" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {!isBound ? (
        <SetupScanner onBindingComplete={handleBindingComplete} apiBaseUrl={API_BASE_URL} />
      ) : (
        <TaskRunner tasks={todayTasks} deviceToken={deviceToken} apiBaseUrl={API_BASE_URL} onComplete={() => fetchTasks(deviceToken)} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
  },
  loadingText: {
    marginTop: 20,
    fontSize: 32,
    fontWeight: 'bold',
  }
});
