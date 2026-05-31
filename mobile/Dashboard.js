import React, { useState } from 'react';
import { StyleSheet, View, Text, TouchableOpacity, ScrollView, RefreshControl } from 'react-native';

export default function Dashboard({ patientName, tasks, appointments, onStartTasks, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await onRefresh();
    setRefreshing(false);
  };

  const hasTasks = tasks && tasks.length > 0;

  return (
    <View style={styles.container}>
      <ScrollView 
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor="#b47b59" />
        }
      >
        <Text style={styles.greeting}>Hello,</Text>
        <Text style={styles.name}>{patientName}</Text>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Today's Health Tasks</Text>
          {hasTasks ? (
            <TouchableOpacity style={styles.startButton} onPress={onStartTasks}>
              <Text style={styles.startButtonText}>START NOW</Text>
              <Text style={styles.taskCount}>{tasks.length} items to check</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.completedCard}>
              <Text style={styles.completedText}>✅ You are all caught up for today!</Text>
            </View>
          )}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Upcoming Appointments</Text>
          {appointments && appointments.length > 0 ? (
            appointments.map((apt, index) => (
              <View key={index} style={styles.appointmentCard}>
                <Text style={styles.aptDate}>{apt.date}</Text>
                <Text style={styles.aptDesc}>{apt.description}</Text>
              </View>
            ))
          ) : (
            <Text style={styles.noApts}>No upcoming appointments scheduled.</Text>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f7f5f0', // Matching "Warm Earth" canvas
  },
  scrollContent: {
    padding: 30,
    paddingTop: 80,
  },
  greeting: {
    fontSize: 32,
    color: '#4a3728',
    fontWeight: '400',
  },
  name: {
    fontSize: 56,
    color: '#4a3728',
    fontWeight: '900',
    marginBottom: 40,
  },
  section: {
    marginBottom: 40,
  },
  sectionTitle: {
    fontSize: 18,
    fontBlack: '900',
    color: '#b47b59',
    textTransform: 'uppercase',
    letterSpacing: 2,
    marginBottom: 20,
  },
  startButton: {
    backgroundColor: '#4a3728',
    padding: 40,
    borderRadius: 30,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 5,
  },
  startButtonText: {
    color: '#fff',
    fontSize: 48,
    fontWeight: '900',
  },
  taskCount: {
    color: '#b47b59',
    fontSize: 18,
    fontWeight: '700',
    marginTop: 10,
  },
  completedCard: {
    backgroundColor: '#fff',
    padding: 30,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: '#16a34a',
  },
  completedText: {
    fontSize: 24,
    color: '#16a34a',
    fontWeight: 'bold',
    textAlign: 'center',
  },
  appointmentCard: {
    backgroundColor: '#fff',
    padding: 25,
    borderRadius: 20,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: '#e6e2da',
  },
  aptDate: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#4a3728',
  },
  aptDesc: {
    fontSize: 16,
    color: '#78716c',
    marginTop: 5,
  },
  noApts: {
    fontSize: 18,
    color: '#a8a29e',
    italic: 'italic',
  }
});
