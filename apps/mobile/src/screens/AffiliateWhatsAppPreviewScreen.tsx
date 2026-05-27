import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React from "react";
import { Image, Linking, View, Pressable, ScrollView } from "react-native";
import { AppText, Button } from "../design/components";
import { useTheme } from "../design/theme";
import { tokens } from "../design/tokens";
import type { RootStackParamList } from "../navigation/types";
import { whatsAppMeUrlFromE164 } from "../lib/whatsappLink";
import { useAuth } from "../auth/AuthContext";
import { postListingAnalytics } from "../api/eventflow";

type Props = NativeStackScreenProps<RootStackParamList, "AffiliateWhatsAppPreview">;

export function AffiliateWhatsAppPreviewScreen({ route, navigation }: Props) {
  const { whatsapp_e164, seller_name, price_minor_units, image_uri, event_title, communityEventId } = route.params;
  const { colors } = useTheme();
  const { apiBaseUrl, accessToken } = useAuth();

  const handleProceed = async () => {
    if (communityEventId && accessToken) {
      try {
        await postListingAnalytics(apiBaseUrl, accessToken, {
          metric_type: "whatsapp_tap",
          community_event_id: communityEventId,
        });
      } catch (e) {
        // Ignore analytics failure
      }
    }
    const url = whatsAppMeUrlFromE164(whatsapp_e164);
    if (!url) {
      alert("Invalid WhatsApp number");
      return;
    }
    await Linking.openURL(url).catch(() => alert("Failed to open WhatsApp"));
  };

  const formattedPrice = price_minor_units != null ? `$${(price_minor_units / 100).toFixed(2)}` : "Price not specified";

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: tokens.spacing[20], paddingBottom: 50, flexGrow: 1, justifyContent: "center" }}>
      <View style={{ backgroundColor: colors.surface1, padding: tokens.spacing[16], borderRadius: tokens.radii.md, borderWidth: 1, borderColor: colors.border, alignItems: "center" }}>
        
        {image_uri ? (
          <Image source={{ uri: image_uri }} style={{ width: 120, height: 120, borderRadius: tokens.radii.sm, marginBottom: tokens.spacing[16] }} resizeMode="cover" />
        ) : (
          <View style={{ width: 120, height: 120, borderRadius: tokens.radii.sm, backgroundColor: colors.surface2, marginBottom: tokens.spacing[16], alignItems: "center", justifyContent: "center" }}>
            <AppText tone="tertiary">No Image</AppText>
          </View>
        )}

        <AppText variant="title" style={{ textAlign: "center", marginBottom: tokens.spacing[4] }}>{event_title}</AppText>
        <AppText tone="secondary" style={{ textAlign: "center", marginBottom: tokens.spacing[12] }}>Offered by {seller_name}</AppText>
        
        <View style={{ backgroundColor: colors.surface2, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, marginBottom: tokens.spacing[24] }}>
          <AppText style={{ fontWeight: "700" }}>{formattedPrice}</AppText>
        </View>

        <AppText tone="tertiary" style={{ textAlign: "center", marginBottom: tokens.spacing[24] }}>
          You are about to leave the app and message this affiliate on WhatsApp.
        </AppText>

        <View style={{ width: "100%", gap: tokens.spacing[12] }}>
          <Button label="Proceed to WhatsApp" variant="filled" size="lg" onPress={handleProceed} />
          <Button label="Cancel" variant="outline" size="lg" onPress={() => navigation.goBack()} />
        </View>
      </View>
    </ScrollView>
  );
}
