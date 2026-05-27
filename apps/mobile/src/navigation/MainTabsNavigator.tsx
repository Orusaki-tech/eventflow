import type { NativeStackNavigationOptions } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React, { useMemo } from "react";
import { Ionicons } from "@expo/vector-icons";
import { BusinessProfileScreen } from "../screens/BusinessProfileScreen";
import { CaptureScreen } from "../screens/CaptureScreen";
import { DiscoverHomeScreen } from "../screens/DiscoverHomeScreen";
import { HomeScreen } from "../screens/HomeScreen";
import { MyTicketsScreen } from "../screens/MyTicketsScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { useTheme } from "../design/theme";
import type {
  DiscoverStackParamList,
  CaptureStackParamList,
  InboxStackParamList,
  MainTabParamList,
  ProfileStackParamList,
  TicketsStackParamList,
} from "./types";

const InboxStack = createNativeStackNavigator<InboxStackParamList>();
const CaptureStack = createNativeStackNavigator<CaptureStackParamList>();
const DiscoverStack = createNativeStackNavigator<DiscoverStackParamList>();
const TicketsStack = createNativeStackNavigator<TicketsStackParamList>();
const ProfileStack = createNativeStackNavigator<ProfileStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();

function useStackScreenOptions(): NativeStackNavigationOptions {
  const { colors } = useTheme();
  return useMemo(
    () => ({
      headerStyle: { backgroundColor: colors.surface1 },
      headerTintColor: colors.textPrimary,
      headerTitleStyle: { color: colors.textPrimary },
      headerTitleAlign: "center" as const,
      contentStyle: { backgroundColor: colors.bg },
    }),
    [colors],
  );
}

function InboxStackNavigator() {
  const stackScreenOptions = useStackScreenOptions();
  return (
    <InboxStack.Navigator screenOptions={stackScreenOptions}>
      <InboxStack.Screen name="InboxHome" component={HomeScreen} options={{ title: "Inbox" }} />
    </InboxStack.Navigator>
  );
}

function CaptureStackNavigator() {
  const stackScreenOptions = useStackScreenOptions();
  return (
    <CaptureStack.Navigator screenOptions={stackScreenOptions}>
      <CaptureStack.Screen name="CaptureHome" component={CaptureScreen} options={{ title: "Capture" }} />
    </CaptureStack.Navigator>
  );
}

function DiscoverStackNavigator() {
  const stackScreenOptions = useStackScreenOptions();
  return (
    <DiscoverStack.Navigator screenOptions={stackScreenOptions}>
      <DiscoverStack.Screen name="DiscoverHome" component={DiscoverHomeScreen} options={{ title: "Discover" }} />
    </DiscoverStack.Navigator>
  );
}

function TicketsStackNavigator() {
  const stackScreenOptions = useStackScreenOptions();
  return (
    <TicketsStack.Navigator screenOptions={stackScreenOptions}>
      <TicketsStack.Screen name="TicketsHome" component={MyTicketsScreen} options={{ title: "My Tickets" }} />
    </TicketsStack.Navigator>
  );
}

function ProfileStackNavigator() {
  const stackScreenOptions = useStackScreenOptions();
  return (
    <ProfileStack.Navigator screenOptions={stackScreenOptions}>
      <ProfileStack.Screen name="ProfileHome" component={ProfileScreen} options={{ title: "Profile" }} />
      <ProfileStack.Screen name="BusinessProfile" component={BusinessProfileScreen} options={{ title: "Business" }} />
    </ProfileStack.Navigator>
  );
}

export function MainTabsNavigator() {
  const { colors } = useTheme();
  const tabScreenOptions = useMemo(
    () => ({
      headerShown: false,
      tabBarStyle: {
        backgroundColor: colors.surface1,
        borderTopColor: colors.border,
      },
      tabBarActiveTintColor: colors.textPrimary,
      tabBarInactiveTintColor: colors.textTertiary,
      tabBarIconStyle: { marginTop: 2 },
    }),
    [colors],
  );

  return (
    <Tab.Navigator screenOptions={tabScreenOptions}>
      <Tab.Screen
        name="Inbox"
        component={InboxStackNavigator}
        options={{
          title: "Inbox",
          tabBarIcon: ({ color, size }) => <Ionicons name="mail-outline" color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Tickets"
        component={TicketsStackNavigator}
        options={{
          title: "Tickets",
          tabBarIcon: ({ color, size }) => <Ionicons name="ticket-outline" color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Capture"
        component={CaptureStackNavigator}
        options={{
          title: "Capture",
          tabBarIcon: ({ color, size }) => <Ionicons name="add-circle-outline" color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Discover"
        component={DiscoverStackNavigator}
        options={{
          title: "Discover",
          tabBarIcon: ({ color, size }) => <Ionicons name="compass-outline" color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileStackNavigator}
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size }) => <Ionicons name="person-outline" color={color} size={size} />,
        }}
      />
    </Tab.Navigator>
  );
}
