import type { NativeStackNavigationOptions } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React, { useMemo } from "react";
import { Ionicons } from "@expo/vector-icons";
import { HomeScreen } from "../screens/HomeScreen";
import { CalendarScreen } from "../screens/CalendarScreen";
import { CaptureScreen } from "../screens/CaptureScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { useTheme } from "../design/theme";
import type {
  CalendarStackParamList,
  CaptureStackParamList,
  InboxStackParamList,
  MainTabParamList,
  ProfileStackParamList,
} from "./types";

const InboxStack = createNativeStackNavigator<InboxStackParamList>();
const CalendarStack = createNativeStackNavigator<CalendarStackParamList>();
const CaptureStack = createNativeStackNavigator<CaptureStackParamList>();
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

function CalendarStackNavigator() {
  const stackScreenOptions = useStackScreenOptions();
  return (
    <CalendarStack.Navigator screenOptions={stackScreenOptions}>
      <CalendarStack.Screen name="CalendarHome" component={CalendarScreen} options={{ title: "Calendar" }} />
    </CalendarStack.Navigator>
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

function ProfileStackNavigator() {
  const stackScreenOptions = useStackScreenOptions();
  return (
    <ProfileStack.Navigator screenOptions={stackScreenOptions}>
      <ProfileStack.Screen name="ProfileHome" component={ProfileScreen} options={{ title: "Profile" }} />
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
        name="Calendar"
        component={CalendarStackNavigator}
        options={{
          title: "Calendar",
          tabBarIcon: ({ color, size }) => <Ionicons name="calendar-outline" color={color} size={size} />,
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
