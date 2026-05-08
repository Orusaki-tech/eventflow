import * as Location from "expo-location";
import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { ActivityIndicator, Platform, StyleSheet, View } from "react-native";
import MapView, { Marker, type Region } from "react-native-maps";
import { AppText } from "../design/components";
import { tokens } from "../design/tokens";

export type VenuePinMapRef = {
  animateTo: (lat: number, lng: number) => void;
};

type Props = {
  active: boolean;
  pinLat: number | null;
  pinLng: number | null;
  onPinChange: (lat: number, lng: number) => void;
};

const FALLBACK_REGION: Region = {
  latitude: 40.7128,
  longitude: -74.006,
  latitudeDelta: 0.08,
  longitudeDelta: 0.08,
};

export const VenuePinMap = forwardRef<VenuePinMapRef, Props>(function VenuePinMap(
  { active, pinLat, pinLng, onPinChange },
  ref
) {
  const mapRef = useRef<MapView>(null);
  const [initialRegion, setInitialRegion] = useState<Region | null>(null);

  useImperativeHandle(ref, () => ({
    animateTo(lat: number, lng: number) {
      mapRef.current?.animateToRegion(
        {
          latitude: lat,
          longitude: lng,
          latitudeDelta: 0.025,
          longitudeDelta: 0.025,
        },
        320
      );
    },
  }));

  useEffect(() => {
    if (!active) {
      setInitialRegion(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const last = await Location.getLastKnownPositionAsync({});
        if (cancelled) return;
        if (last?.coords) {
          setInitialRegion({
            latitude: last.coords.latitude,
            longitude: last.coords.longitude,
            latitudeDelta: 0.06,
            longitudeDelta: 0.06,
          });
          return;
        }
      } catch {
        /* use fallback */
      }
      if (!cancelled) setInitialRegion(FALLBACK_REGION);
    })();
    return () => {
      cancelled = true;
    };
  }, [active]);

  if (!active) return null;

  if (Platform.OS === "web") {
    return (
      <View style={styles.webFallback}>
        <AppText tone="secondary" style={styles.webFallbackText}>
          Map pinning runs on the iOS and Android apps. Use “Use current location” here, or open EventFlow on your phone.
        </AppText>
      </View>
    );
  }

  if (!initialRegion) {
    return (
      <View style={styles.loadingBox}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.mapShell}>
        <MapView
          ref={mapRef}
          style={styles.map}
          initialRegion={initialRegion}
          onPress={(e) => {
            const { latitude, longitude } = e.nativeEvent.coordinate;
            onPinChange(latitude, longitude);
          }}
          rotateEnabled={false}
          pitchEnabled={false}
          toolbarEnabled={false}
        >
          {pinLat != null && pinLng != null ? (
            <Marker
              coordinate={{ latitude: pinLat, longitude: pinLng }}
              draggable
              onDragEnd={(e) => {
                const { latitude, longitude } = e.nativeEvent.coordinate;
                onPinChange(latitude, longitude);
              }}
            />
          ) : null}
        </MapView>
      </View>
      <AppText variant="labelSmall" tone="tertiary" style={styles.hint}>
        Tap to place the pin, drag to fine-tune, or use your current location below.
      </AppText>
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: {
    gap: tokens.spacing[8],
  },
  mapShell: {
    height: 208,
    width: "100%",
    borderRadius: tokens.radii.sm,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(128,128,128,0.35)",
  },
  map: {
    ...StyleSheet.absoluteFillObject,
  },
  loadingBox: {
    height: 208,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: tokens.radii.sm,
    backgroundColor: "rgba(128,128,128,0.15)",
  },
  hint: {
    textAlign: "center",
    lineHeight: 18,
  },
  webFallback: {
    minHeight: 120,
    padding: tokens.spacing[12],
    borderRadius: tokens.radii.sm,
    backgroundColor: "rgba(128,128,128,0.12)",
    justifyContent: "center",
  },
  webFallbackText: {
    textAlign: "center",
    lineHeight: 20,
  },
});
