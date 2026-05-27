import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Dimensions, Image, Linking, Pressable, ScrollView, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import {
  CarouselSlide,
  deleteFollowBusiness,
  deleteFollowUser,
  EventflowApiError,
  getFollowBusiness,
  getListingCarousel,
  listFollowing,
  postBillingCheckoutStub,
  postFollowBusiness,
  postFollowUser,
  postListingAnalytics,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button, Card } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { formatFriendlyEventDateTime } from "../lib/eventDateTime";
import { whatsAppMeUrlFromE164 } from "../lib/whatsappLink";
import type { RootStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";

type Props = NativeStackScreenProps<RootStackParamList, "CommunityListingDetail">;

const WINDOW_WIDTH = Dimensions.get("window").width;
const CAROUSEL_WIDTH = Math.min(WINDOW_WIDTH - tokens.spacing[16] * 2, 360);

export function CommunityListingDetailScreen({ route }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    scrollContent: { padding: tokens.spacing[16], gap: tokens.spacing[16], paddingBottom: 40 },
    center: { paddingVertical: 24, alignItems: "center" as const },
    headlineCard: { padding: tokens.spacing[16], gap: tokens.spacing[8] },
    slidePoster: {
      width: CAROUSEL_WIDTH,
      minHeight: 160,
      padding: tokens.spacing[16],
      backgroundColor: c.surface1,
      borderRadius: tokens.radii.md,
      borderWidth: 1,
      borderColor: c.border,
      justifyContent: "center" as const,
    },
    demoBanner: {
      padding: tokens.spacing[12],
      borderRadius: tokens.radii.sm,
      backgroundColor: c.surface1,
      borderWidth: 1,
      borderColor: c.border,
    },
  }));

  const { communityEventId, organizerUserId, title, start_time, venue, whatsapp_e164, business_id, viewMode } =
    route.params;
  const { accessToken, apiBaseUrl, refreshSession, session } = useAuth();
  const authUserId = session?.user?.id ?? null;
  const isOwner =
    Boolean(
      organizerUserId &&
        authUserId &&
        organizerUserId.toLowerCase() === authUserId.toLowerCase()
    );
  const effectiveViewMode: "viewer" | "owner" = viewMode ?? "viewer";
  const showOwnerControls = effectiveViewMode === "owner" && isOwner;

  const [slides, setSlides] = useState<CarouselSlide[]>([]);
  const [carouselLoading, setCarouselLoading] = useState(true);
  const [carouselError, setCarouselError] = useState<string | null>(null);
  const [following, setFollowing] = useState(false);
  const [followBusy, setFollowBusy] = useState(false);
  const [bizFollowing, setBizFollowing] = useState(false);
  const [bizFollowBusy, setBizFollowBusy] = useState(false);
  const [billingBusy, setBillingBusy] = useState(false);

  useFocusEffect(
    useCallback(() => {
      if (!accessToken) return undefined;
      let cancelled = false;
      void (async () => {
        try {
          await postListingAnalytics(apiBaseUrl, accessToken, {
            metric_type: "impression",
            community_event_id: communityEventId,
            business_id: business_id ?? null,
          });
        } catch (e: unknown) {
          if (!cancelled && e instanceof EventflowApiError && e.status === 401) await refreshSession().catch(() => undefined);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [accessToken, apiBaseUrl, business_id, communityEventId, refreshSession])
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setCarouselLoading(true);
      setCarouselError(null);
      try {
        const [res, followRes, userFollowRes] = await Promise.all([
          getListingCarousel(apiBaseUrl, accessToken, communityEventId),
          business_id && accessToken ? getFollowBusiness(apiBaseUrl, accessToken, business_id) : Promise.resolve(null),
          organizerUserId && accessToken ? listFollowing(apiBaseUrl, accessToken) : Promise.resolve(null),
        ]);
        if (!cancelled) {
          setSlides(res.slides ?? []);
          if (followRes) setBizFollowing(followRes.following);
          if (userFollowRes) setFollowing(userFollowRes.some((f) => f.following_user_id === organizerUserId));
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setCarouselError(e instanceof Error ? e.message : String(e));
          setSlides([]);
        }
      } finally {
        if (!cancelled) setCarouselLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, apiBaseUrl, communityEventId, business_id, organizerUserId]);

  const canFollow =
    Boolean(accessToken && organizerUserId && authUserId && organizerUserId.toLowerCase() !== authUserId.toLowerCase());

  const toggleFollow = () => {
    if (!accessToken || !organizerUserId) return;
    setFollowBusy(true);
    void (async () => {
      try {
        if (!following) {
          await postFollowUser(apiBaseUrl, accessToken, organizerUserId);
          setFollowing(true);
        } else {
          await deleteFollowUser(apiBaseUrl, accessToken, organizerUserId);
          setFollowing(false);
        }
      } catch (e: unknown) {
        if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
        Alert.alert("Follow failed", e instanceof Error ? e.message : String(e));
      } finally {
        setFollowBusy(false);
      }
    })();
  };

  const canFollowBiz = Boolean(accessToken && business_id);

  const toggleFollowBiz = () => {
    if (!accessToken || !business_id) return;
    setBizFollowBusy(true);
    void (async () => {
      try {
        if (!bizFollowing) {
          await postFollowBusiness(apiBaseUrl, accessToken, business_id);
          setBizFollowing(true);
        } else {
          await deleteFollowBusiness(apiBaseUrl, accessToken, business_id);
          setBizFollowing(false);
        }
      } catch (e: unknown) {
        if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
        Alert.alert("Follow failed", e instanceof Error ? e.message : String(e));
      } finally {
        setBizFollowBusy(false);
      }
    })();
  };

  const openBillingDemo = () => {
    setBillingBusy(true);
    void (async () => {
      try {
        if (accessToken) {
          await postListingAnalytics(apiBaseUrl, accessToken, {
            metric_type: "save",
            community_event_id: communityEventId,
            meta: { cta: "promote_listing_demo" },
          });
        }
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

  const openOrganizerWhatsApp = () => {
    const raw = whatsapp_e164?.trim();
    if (!raw) return;
    const url = whatsAppMeUrlFromE164(raw);
    if (!url) return;
    void (async () => {
      try {
        if (accessToken) {
          await postListingAnalytics(apiBaseUrl, accessToken, {
            metric_type: "whatsapp_tap",
            community_event_id: communityEventId,
            business_id: business_id ?? null,
          });
        }
      } catch {
        /* ignore analytics failure */
      }
      const ok = await Linking.canOpenURL(url);
      if (ok) await Linking.openURL(url);
      else Alert.alert("WhatsApp", url);
    })();
  };

  const renderSlide = ({ item }: { item: CarouselSlide }) => {
    if (item.kind === "poster") {
      const img = item.image_uri?.trim();
      return (
        <View style={styles.slidePoster}>
          {img ? (
            <Image
              source={{ uri: img }}
              style={{
                width: CAROUSEL_WIDTH - tokens.spacing[16] * 2,
                height: 180,
                borderRadius: tokens.radii.sm,
                marginBottom: tokens.spacing[8],
              }}
              resizeMode="cover"
            />
          ) : null}
          {item.title ? (
            <AppText variant="title" style={{ marginBottom: 6 }}>
              {item.title}
            </AppText>
          ) : null}
          {item.subtitle ? <AppText tone="secondary">{item.subtitle}</AppText> : null}
        </View>
      );
    }
    const uri = item.uri?.trim();
    return (
      <View style={[styles.slidePoster, { alignItems: "stretch" as const }]}>
        <AppText variant="labelSmall" tone="tertiary">
          Video
        </AppText>
        {uri ? (
          <View style={{ marginTop: tokens.spacing[8] }}>
            <Button label="Open video" variant="outline" size="md" onPress={() => void Linking.openURL(uri)} />
          </View>
        ) : (
          <AppText tone="secondary">No playable URL</AppText>
        )}
      </View>
    );
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.scrollContent}>
      <Card style={styles.headlineCard}>
        <AppText variant="headline">{title}</AppText>
        <AppText tone="secondary">{formatFriendlyEventDateTime(start_time)}</AppText>
        <AppText tone="secondary">{venue}</AppText>
      </Card>

      {canFollow ? (
        <Button
          label={following ? "Following" : "Follow organizer"}
          variant={following ? "filled" : "outline"}
          loading={followBusy}
          onPress={toggleFollow}
          fullWidth
        />
      ) : showOwnerControls ? (
        <AppText tone="tertiary">This is your listing.</AppText>
      ) : null}

      {canFollowBiz ? (
        <View style={{ gap: 8 }}>
          <Button
            label={bizFollowing ? "Following business" : "Follow business"}
            variant={bizFollowing ? "filled" : "outline"}
            loading={bizFollowBusy}
            onPress={toggleFollowBiz}
            fullWidth
          />
          <Button
            label="View profile"
            variant="outline"
            onPress={() => { if (!business_id) return; navigationRef.navigate("BusinessProfileView", { businessId: business_id }); }}
            fullWidth
          />
        </View>
      ) : null}

      {whatsapp_e164?.trim() && whatsAppMeUrlFromE164(whatsapp_e164.trim()) ? (
        <Button label="Chat on WhatsApp" variant="filled" onPress={openOrganizerWhatsApp} fullWidth />
      ) : null}

      {/* Carousel is optional; in viewer mode we silently hide unauthorized sections. */}
      {(() => {
        const unauthorized =
          carouselError && /not\s+authorized|forbidden|permission|unauthorized/i.test(carouselError);
        const shouldHideCarousel = effectiveViewMode === "viewer" && unauthorized;
        if (shouldHideCarousel) return null;

        return (
          <>
            <AppText variant="title">Carousel</AppText>
            {carouselLoading ? (
              <View style={styles.center}>
                <ActivityIndicator color={colors.textSecondary} />
              </View>
            ) : carouselError ? (
              <AppText tone="secondary">{carouselError}</AppText>
            ) : slides.length === 0 ? (
              <AppText tone="tertiary">No slides for this listing.</AppText>
            ) : (
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {slides.map((item, i) => (
                  <View key={`slide-${i}`} style={{ marginRight: i < slides.length - 1 ? tokens.spacing[12] : 0 }}>
                    {renderSlide({ item })}
                  </View>
                ))}
              </ScrollView>
            )}
          </>
        );
      })()}

      {showOwnerControls ? (
        <View style={styles.demoBanner}>
          <AppText variant="labelSmall" tone="tertiary">
            Demo only — not real checkout.
          </AppText>
          <Button
            label={billingBusy ? "Opening…" : "Promote listing (stub)"}
            variant="outline"
            loading={billingBusy}
            onPress={openBillingDemo}
            fullWidth
          />
        </View>
      ) : null}

      <Pressable
        accessibilityLabel="Open venue in Maps"
        style={({ pressed }) => [pressedOpacityStyle(pressed)]}
        onPress={() => void Linking.openURL(`https://maps.google.com/?q=${encodeURIComponent(venue)}`)}
      >
        <AppText tone="secondary" style={{ textDecorationLine: "underline" }}>
          Open venue in Maps
        </AppText>
      </Pressable>
    </ScrollView>
  );
}
