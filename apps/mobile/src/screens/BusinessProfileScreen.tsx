import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Linking from "expo-linking";
import React, { useCallback, useState } from "react";
import { Alert, ScrollView, TextInput, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import {
  BusinessResponse,
  EventflowApiError,
  getBusiness,
  patchBusiness,
  postBillingCheckoutStub,
  postBusiness,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button, Card } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { STORAGE_MY_BUSINESS_ID } from "../lib/constants";

export function BusinessProfileScreen() {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[16], flexGrow: 1 },
    card: { padding: tokens.spacing[16], gap: tokens.spacing[12] },
    input: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      padding: tokens.spacing[12],
      color: c.textPrimary,
      backgroundColor: c.surface1,
    },
    demoNote: {
      padding: tokens.spacing[12],
      borderRadius: tokens.radii.sm,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surface1,
    },
  }));

  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [name, setName] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [business, setBusiness] = useState<BusinessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [billingBusy, setBillingBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const stored = await AsyncStorage.getItem(STORAGE_MY_BUSINESS_ID);
      if (stored && accessToken) {
        const b = await getBusiness(apiBaseUrl, accessToken, stored);
        setBusiness(b);
        setName(b.name);
        setWhatsapp(b.whatsapp_e164 ?? "");
      } else {
        setBusiness(null);
      }
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) await refreshSession().catch(() => undefined);
      setBusiness(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, apiBaseUrl, refreshSession]);

  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload])
  );

  const createOrReplace = () => {
    if (!accessToken) {
      Alert.alert("Sign in required", "Create a business while signed in.");
      return;
    }
    const n = name.trim();
    if (n.length < 1) {
      Alert.alert("Name required", "Enter a business name.");
      return;
    }
    setSaving(true);
    void (async () => {
      try {
        const wa = whatsapp.trim();
        const waVal = wa.length ? wa : null;
        if (business) {
          const res = await patchBusiness(apiBaseUrl, accessToken, business.business_id, {
            name: n,
            whatsapp_e164: waVal,
          });
          setBusiness(res);
        } else {
          const res = await postBusiness(apiBaseUrl, accessToken, {
            name: n,
            whatsapp_e164: waVal,
          });
          await AsyncStorage.setItem(STORAGE_MY_BUSINESS_ID, res.business_id);
          setBusiness(res);
        }
      } catch (e: unknown) {
        if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
        Alert.alert("Save failed", e instanceof Error ? e.message : String(e));
      } finally {
        setSaving(false);
      }
    })();
  };

  const openBizBillingDemo = () => {
    if (!accessToken) {
      Alert.alert("Sign in required", "Billing demo requires an authenticated session.");
      return;
    }
    setBillingBusy(true);
    void (async () => {
      try {
        const res = await postBillingCheckoutStub(apiBaseUrl, accessToken, "stripe");
        const ok = await Linking.canOpenURL(res.checkout_url);
        if (ok) await Linking.openURL(res.checkout_url);
        else Alert.alert("Demo checkout", res.checkout_url);
      } catch (e: unknown) {
        Alert.alert("Billing demo failed", e instanceof Error ? e.message : String(e));
      } finally {
        setBillingBusy(false);
      }
    })();
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Card style={styles.card}>
        <AppText variant="title">Listing business</AppText>
        <AppText variant="labelSmall" tone="tertiary">
          Create a business profile for promoters (stored locally on device after create).
        </AppText>
        {loading ? (
          <AppText tone="secondary">Loading…</AppText>
        ) : business ? (
          <>
            <AppText variant="labelSmall" tone="tertiary">
              Business ID
            </AppText>
            <AppText selectable tone="secondary">
              {business.business_id}
            </AppText>
            <AppText variant="labelSmall" tone="tertiary">
              Verified
            </AppText>
            <AppText tone="secondary">{business.verified ? "Yes" : "No"}</AppText>
          </>
        ) : null}

        <AppText variant="labelSmall" tone="tertiary">
          Name
        </AppText>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="Your venue or brand"
          placeholderTextColor={colors.textTertiary}
        />
        <AppText variant="labelSmall" tone="tertiary">
          WhatsApp E.164 (optional)
        </AppText>
        <TextInput
          style={styles.input}
          value={whatsapp}
          onChangeText={setWhatsapp}
          placeholder="+15551234567"
          placeholderTextColor={colors.textTertiary}
          keyboardType="phone-pad"
        />
        <Button
          label={saving ? "Saving…" : business ? "Update" : "Create business"}
          variant="filled"
          loading={saving}
          onPress={createOrReplace}
          fullWidth
        />
      </Card>

      <View style={styles.demoNote}>
        <AppText variant="labelSmall" tone="tertiary">
          Demo — Business billing stub (not real payments).
        </AppText>
        <Button
          label={billingBusy ? "Opening…" : "Open demo checkout"}
          variant="outline"
          loading={billingBusy}
          onPress={openBizBillingDemo}
          fullWidth
        />
      </View>
    </ScrollView>
  );
}
