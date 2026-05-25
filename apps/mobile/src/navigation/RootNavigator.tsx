import AsyncStorage from "@react-native-async-storage/async-storage";
import { NavigationContainer, DarkTheme, DefaultTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { useAuth } from "../auth/AuthContext";
import { AuthScreen } from "../screens/AuthScreen";
import { ConfirmedScreen } from "../screens/ConfirmedScreen";
import { DraftDetailScreen } from "../screens/DraftDetailScreen";
import { DraftEditScreen } from "../screens/DraftEditScreen";
import { EventDetailScreen } from "../screens/EventDetailScreen";
import { CarouselSlidePickScreen } from "../screens/CarouselSlidePickScreen";
import { ImportLinkScreen } from "../screens/ImportLinkScreen";
import { ManualVenueScreen } from "../screens/ManualVenueScreen";
import { CommunityListingDetailScreen } from "../screens/CommunityListingDetailScreen";
import { BusinessProfileViewScreen } from "../screens/BusinessProfileViewScreen";
import { OnboardingScreen } from "../screens/OnboardingScreen";
import { PosterImportScreen } from "../screens/PosterImportScreen";
import { SharedMediaImportScreen } from "../screens/SharedMediaImportScreen";
import { ProcessingScreen } from "../screens/ProcessingScreen";
import { SocialHubScreen } from "../screens/SocialHubScreen";
import { STORAGE_ONBOARDING_DONE } from "../lib/constants";
import { useTheme } from "../design/theme";
import { navigationRef } from "./navigationRef";
import { ShareBootstrap } from "./ShareBootstrap";
import type { RootStackParamList } from "./types";
import { MainTabsNavigator } from "./MainTabsNavigator";

function SessionGuard({
  navReady,
  onboardingDone,
}: {
  navReady: boolean;
  onboardingDone: boolean;
}) {
  const { session, loading } = useAuth();

  useEffect(() => {
    if (loading || !onboardingDone || !navReady || !navigationRef.isReady()) return;
    if (session) return;
    const name = navigationRef.getCurrentRoute()?.name;
    if (name && name !== "Onboarding" && name !== "Auth") {
      navigationRef.reset({ index: 0, routes: [{ name: "Auth" }] });
    }
  }, [session, loading, onboardingDone, navReady]);

  return null;
}

const Stack = createNativeStackNavigator<RootStackParamList>();

function Splash() {
  const { colors } = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center", alignItems: "center" }}>
      <ActivityIndicator size="large" color={colors.textPrimary} />
    </View>
  );
}

export function RootNavigator() {
  const { loading: authLoading, session } = useAuth();
  const { mode, colors, hydrated } = useTheme();
  const [onboardingDone, setOnboardingDone] = useState<boolean | null>(null);
  const [navReady, setNavReady] = useState(false);

  useEffect(() => {
    void AsyncStorage.getItem(STORAGE_ONBOARDING_DONE)
      .then((v) => setOnboardingDone(v === "1"))
      .catch((e) => {
        console.error("Failed to read onboarding storage", e);
        setOnboardingDone(false);
      });
  }, []);

  const markOnboardingStored = useCallback(() => setOnboardingDone(true), []);

  if (!hydrated || authLoading || onboardingDone === null) {
    return <Splash />;
  }

  const initialRouteName: keyof RootStackParamList = !onboardingDone
    ? "Onboarding"
    : !session
      ? "Auth"
      : "Main";

  const baseTheme = mode === "dark" ? DarkTheme : DefaultTheme;
  const navTheme = {
    ...baseTheme,
    colors: {
      ...baseTheme.colors,
      background: colors.bg,
      card: colors.surface1,
      primary: colors.textPrimary,
      text: colors.textPrimary,
      border: colors.border,
    },
  };

  return (
    <NavigationContainer
      ref={navigationRef}
      theme={navTheme}
      onReady={() => setNavReady(true)}
    >
      <ShareBootstrap navReady={navReady} />
      <SessionGuard navReady={navReady} onboardingDone={onboardingDone} />
      <Stack.Navigator
        key={String(onboardingDone)}
        initialRouteName={initialRouteName}
        screenOptions={{
          headerStyle: { backgroundColor: colors.surface1 },
          headerTintColor: colors.textPrimary,
          headerTitleStyle: { color: colors.textPrimary },
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="Onboarding" options={{ headerShown: false }}>
          {(props) => (
            <OnboardingScreen {...props} onOnboardingStored={markOnboardingStored} />
          )}
        </Stack.Screen>
        <Stack.Screen name="Auth" component={AuthScreen} options={{ title: "Sign in" }} />
        <Stack.Screen name="Main" component={MainTabsNavigator} options={{ headerShown: false }} />
        <Stack.Screen name="ImportLink" component={ImportLinkScreen} options={{ title: "Import link" }} />
        <Stack.Screen name="CarouselSlidePick" component={CarouselSlidePickScreen} options={{ title: "Choose slides" }} />
        <Stack.Screen name="SharedMediaImport" component={SharedMediaImportScreen} options={{ title: "Import media" }} />
        <Stack.Screen name="PosterImport" component={PosterImportScreen} options={{ title: "Upload poster" }} />
        <Stack.Screen name="Processing" component={ProcessingScreen} options={{ headerShown: false }} />
        <Stack.Screen name="DraftDetail" component={DraftDetailScreen} options={{ title: "Review event" }} />
        <Stack.Screen name="DraftEdit" component={DraftEditScreen} options={{ title: "Edit draft" }} />
        <Stack.Screen name="Confirmed" component={ConfirmedScreen} options={{ title: "Scheduled" }} />
        <Stack.Screen name="EventDetail" component={EventDetailScreen} options={{ title: "Review event" }} />
        <Stack.Screen name="ManualVenue" component={ManualVenueScreen} options={{ title: "Add venue" }} />
        <Stack.Screen
          name="CommunityListingDetail"
          component={CommunityListingDetailScreen}
          options={{ title: "Listing" }}
        />
        <Stack.Screen
          name="BusinessProfileView"
          component={BusinessProfileViewScreen}
          options={{ title: "Business" }}
        />
        <Stack.Screen
          name="SocialHub"
          component={SocialHubScreen}
          options={{
            headerShown: false,
            presentation: "modal",
          }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
