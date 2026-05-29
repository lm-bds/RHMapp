import React, { useState, useEffect } from 'react';
import { Text, View, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as SecureStore from 'expo-secure-store';

export default function SetupScanner({ onBindingComplete, apiBaseUrl }) {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);

  if (!permission) {
    return <View />;
  }

  if (!permission.granted) {
    return (
      <View style={styles.container}>
        <Text style={styles.mainText}>We need camera access to set up your device.</Text>
        <TouchableOpacity style={styles.button} onPress={requestPermission}>
          <Text style={styles.buttonText}>Allow Camera</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const handleBarCodeScanned = async ({ data }) => {
    setScanned(true);
    try {
      const response = await fetch(`${apiBaseUrl}/auth/bind-device`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ setup_token: data }),
      });

      if (response.ok) {
        const result = await response.json();
        await SecureStore.setItemAsync('device_token', result.access_token);
        onBindingComplete(result.access_token);
      } else {
        Alert.alert('Error', 'Invalid QR Code. Please contact your clinician.');
        setScanned(false);
      }
    } catch (e) {
      console.error(e);
      Alert.alert('Connection Error', 'Please check your internet connection.');
      setScanned(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.headerText}>Point camera at QR code</Text>
      <CameraView
        style={StyleSheet.absoluteFillObject}
        onBarcodeScanned={scanned ? undefined : handleBarCodeScanned}
        barcodeScannerSettings={{
          barcodeTypes: ['qr'],
        }}
      />
      {scanned && (
        <View style={styles.overlay}>
          <Text style={styles.loadingText}>Binding Device...</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    flexDirection: 'column',
    justifyContent: 'center',
    backgroundColor: '#000',
  },
  mainText: {
    fontSize: 28,
    color: '#fff',
    textAlign: 'center',
    marginBottom: 40,
    paddingHorizontal: 20,
  },
  headerText: {
    position: 'absolute',
    top: 60,
    width: '100%',
    textAlign: 'center',
    color: '#fff',
    fontSize: 24,
    zIndex: 1,
    fontWeight: 'bold',
    backgroundColor: 'rgba(0,0,0,0.5)',
    paddingVertical: 10,
  },
  button: {
    backgroundColor: '#007AFF',
    padding: 25,
    borderRadius: 15,
    marginHorizontal: 30,
  },
  buttonText: {
    color: '#fff',
    fontSize: 28,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#fff',
    fontSize: 32,
    fontWeight: 'bold',
  }
});
