import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { Alert, ScrollView, TextInput, View } from "react-native";
import { useAuth } from "../auth/AuthContext";
import { supabaseConfigured } from "../lib/supabase";
import type { RootStackParamList } from "../navigation/types";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<RootStackParamList, "Auth">;

export function AuthScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[8], flexGrow: 1 },
    center: { flex: 1, backgroundColor: c.bg, padding: tokens.spacing[24], justifyContent: "center" as const },
    title: { marginBottom: tokens.spacing[12] },
    body: { lineHeight: 22 },
    label: { marginTop: tokens.spacing[8] },
    input: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 10,
      padding: 14,
      color: c.textPrimary,
      backgroundColor: c.surface1,
    },
  }));
  const { signIn, signUp } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  if (!supabaseConfigured) {
    return (
      <View style={styles.center}>
        <AppText variant="headline" style={styles.title}>
          Sign-in unavailable
        </AppText>
        <AppText tone="secondary" style={styles.body}>
          This build is missing account sign-in configuration. If you are developing EventFlow, add the required public keys
          to your environment and rebuild. Otherwise, contact support for a configured build.
        </AppText>
      </View>
    );
  }

  const onSignIn = async () => {
    setBusy(true);
    try {
      await signIn(email.trim(), password);
      navigation.reset({ index: 0, routes: [{ name: "Main" }] });
    } catch (e: unknown) {
      Alert.alert("Sign in failed", e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSignUp = async () => {
    setBusy(true);
    try {
      await signUp(email.trim(), password);
      Alert.alert("Check your email", "Confirm your account if your project requires it, then sign in.");
    } catch (e: unknown) {
      Alert.alert("Sign up failed", e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <AppText variant="headline" style={styles.title}>
        EventFlow
      </AppText>
      <AppText tone="secondary" style={[styles.body, { marginBottom: tokens.spacing[16] }]}>
        Sign in or create an account to sync your events across devices.
      </AppText>
      <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
        Email
      </AppText>
      <TextInput
        style={styles.input}
        autoCapitalize="none"
        keyboardType="email-address"
        placeholder="you@example.com"
        placeholderTextColor={colors.textTertiary}
        value={email}
        onChangeText={setEmail}
      />
      <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
        Password
      </AppText>
      <TextInput
        style={styles.input}
        secureTextEntry
        placeholder="••••••••"
        placeholderTextColor={colors.textTertiary}
        value={password}
        onChangeText={setPassword}
      />
      <Button label="Sign in" loading={busy} onPress={() => void onSignIn()} fullWidth />
      <Button label="Create account" variant="text" disabled={busy} onPress={() => void onSignUp()} fullWidth />
    </ScrollView>
  );
}
