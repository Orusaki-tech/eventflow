import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  Image,
  Linking,
  Pressable,
  ScrollView,
  Share,
  View,
} from "react-native";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import { useFocusEffect } from "@react-navigation/native";
import {
  CarouselSlide,
  deleteFollowBusiness,
  deleteFollowUser,
  EventflowApiError,
  fetchCommunityEventIcs,
  getBusinessEvents,
  getCommunityEventDetail,
  getFollowBusiness,
  getListingCarousel,
  getRsvpStatus,
  listFollowing,
  listTicketTypes,
  postBillingCheckoutStub,
  postFollowBusiness,
  postFollowUser,
  postListingAnalytics,
  postRsvp,
  purchaseTickets,
  saveCommunityEventToCalendar,
  type BusinessProfileListingRow,
  type TicketTypeRow,
  type UnifiedFeedEvent,
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
  const stylesObj = useThemedStyles((c) => ({
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
    sectionTitle: {
      fontSize: 16,
      fontWeight: "800",
      marginTop: 8,
    },
    rsvpRow: {
      flexDirection: "row" as const,
      gap: 8,
    },
    rsvpBtn: {
      flex: 1,
      paddingVertical: 10,
      borderRadius: 24,
      borderWidth: 1,
      alignItems: "center" as const,
    },
    rsvpBtnActive: {
      backgroundColor: "#4CAF50",
      borderColor: "#4CAF50",
    },
    rsvpBtnActiveMaybe: {
      backgroundColor: "#FF9800",
      borderColor: "#FF9800",
    },
    rsvpBtnActiveNot: {
      backgroundColor: "#666",
      borderColor: "#666",
    },
    rsvpText: { fontSize: 13, fontWeight: "700", color: "#fff" },
    stepperRow: {
      flexDirection: "row" as const,
      alignItems: "center" as const,
      gap: 12,
    },
    stepperBtn: {
      width: 36,
      height: 36,
      borderRadius: 18,
      backgroundColor: c.surface2,
      justifyContent: "center" as const,
      alignItems: "center" as const,
    },
    stepperCount: { fontSize: 16, fontWeight: "700", minWidth: 24, textAlign: "center" as const },
  }));

  const { communityEventId, organizerUserId: paramOrg, title: paramTitle, start_time: paramStart, venue: paramVenue, whatsapp_e164, business_id, viewMode } =
    route.params;
  const { accessToken, apiBaseUrl, refreshSession, session } = useAuth();
  const authUserId = session?.user?.id ?? null;

  // When coming from deep link, params may be missing — fetch from API
  const [fetchedEvent, setFetchedEvent] = useState<UnifiedFeedEvent | null>(null);
  const [fetchBusy, setFetchBusy] = useState(true);
  useEffect(() => {
    if (paramTitle) {
      setFetchBusy(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const ev = await getCommunityEventDetail(apiBaseUrl, accessToken, communityEventId);
        if (!cancelled) setFetchedEvent(ev);
      } catch { /* ignore */ } finally {
        if (!cancelled) setFetchBusy(false);
      }
    })();
    return () => { cancelled = true; };
  }, [communityEventId, paramTitle, accessToken, apiBaseUrl]);

  const title = fetchedEvent?.title ?? paramTitle ?? "";
  const start_time = fetchedEvent?.start_time ?? paramStart ?? "";
  const venue = fetchedEvent?.venue ?? paramVenue ?? "";
  const organizerUserId = fetchedEvent?.organizer_user_id ?? paramOrg ?? null;

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

  const [rsvpStatus, setRsvpStatus] = useState<string | null>(null);
  const [rsvpBusy, setRsvpBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [ticketTypes, setTicketTypes] = useState<TicketTypeRow[]>([]);
  const [ticketTypeQtys, setTicketTypeQtys] = useState<Record<string, number>>({});
  const [purchaseBusy, setPurchaseBusy] = useState(false);
  const [moreEvents, setMoreEvents] = useState<BusinessProfileListingRow[]>([]);

  const updateQty = (ticketTypeId: string, delta: number) => {
    setTicketTypeQtys((prev) => {
      const current = prev[ticketTypeId] ?? 0;
      const next = Math.max(0, Math.min(current + delta, 10));
      return { ...prev, [ticketTypeId]: next };
    });
  };

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
        const [res, followRes, userFollowRes, rsvpRes, tt, savedEvents] = await Promise.all([
          getListingCarousel(apiBaseUrl, accessToken, communityEventId),
          business_id && accessToken ? getFollowBusiness(apiBaseUrl, accessToken, business_id) : Promise.resolve(null),
          organizerUserId && accessToken ? listFollowing(apiBaseUrl, accessToken) : Promise.resolve(null),
          accessToken ? getRsvpStatus(apiBaseUrl, accessToken, communityEventId).catch(() => null) : Promise.resolve(null),
          listTicketTypes(apiBaseUrl, accessToken, communityEventId).catch(() => []),
          getBusinessEvents(apiBaseUrl, accessToken, business_id ?? "").catch(() => []),
        ]);
        if (!cancelled) {
          setSlides(res.slides ?? []);
          if (followRes) setBizFollowing(followRes.following);
          if (userFollowRes) setFollowing(userFollowRes.some((f) => f.following_user_id === organizerUserId));
          if (rsvpRes) setRsvpStatus(rsvpRes.status);
          setTicketTypes(tt);
          setMoreEvents(savedEvents.filter((e) => e.community_event_id !== communityEventId));
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

  const handleRsvp = (status: string) => {
    if (!accessToken) return;
    setRsvpBusy(true);
    void (async () => {
      try {
        const res = await postRsvp(apiBaseUrl, accessToken, communityEventId, status as "going" | "maybe" | "not_going");
        setRsvpStatus(res.status);
      } catch (e: unknown) {
        Alert.alert("RSVP failed", e instanceof Error ? e.message : String(e));
      } finally {
        setRsvpBusy(false);
      }
    })();
  };

  const handleSaveToCalendar = () => {
    setSaveBusy(true);
    void (async () => {
      try {
        await saveCommunityEventToCalendar(apiBaseUrl, accessToken, communityEventId);
        setSaved(true);
        Alert.alert("Saved to Calendar", "This event has been added to your calendar.");
      } catch (e: unknown) {
        Alert.alert("Save failed", e instanceof Error ? e.message : String(e));
      } finally {
        setSaveBusy(false);
      }
    })();
  };

  const handleExportIcs = () => {
    void (async () => {
      try {
        const ics = await fetchCommunityEventIcs(apiBaseUrl, accessToken, communityEventId);
        const uri = FileSystem.cacheDirectory + `event-${communityEventId}.ics`;
        await FileSystem.writeAsStringAsync(uri, ics, { encoding: FileSystem.EncodingType.UTF8 });
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(uri, { mimeType: "text/calendar" });
        } else {
          Alert.alert("ICS", "Sharing not available on this device.");
        }
      } catch (e: unknown) {
        Alert.alert("Export failed", e instanceof Error ? e.message : String(e));
      }
    })();
  };

  const handleShare = () => {
    Share.share({
      message: `Check out ${title} at ${venue}! ${start_time}`,
      url: `eventflow://event/${communityEventId}`,
    });
  };

  const handlePurchase = () => {
    const items = Object.entries(ticketTypeQtys)
      .filter(([, qty]) => qty > 0)
      .map(([ticketTypeId, quantity]) => ({ ticket_type_id: ticketTypeId, quantity }));
    if (items.length === 0) {
      Alert.alert("Select Tickets", "Increase a ticket quantity to at least 1.");
      return;
    }
    setPurchaseBusy(true);
    void (async () => {
      try {
        const res = await purchaseTickets(apiBaseUrl, accessToken, {
          community_event_id: communityEventId,
          items,
        });
        Alert.alert("Order Complete", `Receipt: ${res.receipt_number}\nTickets: ${res.ticket_codes.join(", ")}`);
        setTicketTypeQtys({});
      } catch (e: unknown) {
        Alert.alert("Purchase failed", e instanceof Error ? e.message : String(e));
      } finally {
        setPurchaseBusy(false);
      }
    })();
  };

  const renderSlide = ({ item }: { item: CarouselSlide }) => {
    if (item.kind === "poster") {
      const img = item.image_uri?.trim();
      return (
        <View style={stylesObj.slidePoster}>
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
      <View style={[stylesObj.slidePoster, { alignItems: "stretch" as const }]}>
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

  const hasTickets = ticketTypes.length > 0;
  const totalSelected = Object.values(ticketTypeQtys).reduce((a, b) => a + b, 0);

  if (fetchBusy && !paramTitle) {
    return (
      <View style={[stylesObj.center, { flex: 1 }]}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  return (
    <ScrollView style={stylesObj.root} contentContainerStyle={stylesObj.scrollContent}>
      <Card style={stylesObj.headlineCard}>
        <AppText variant="headline">{title}</AppText>
        <AppText tone="secondary">{formatFriendlyEventDateTime(start_time)}</AppText>
        <AppText tone="secondary">{venue}</AppText>
      </Card>

      {/* RSVP */}
      <View style={{ gap: 8 }}>
        <AppText style={stylesObj.sectionTitle}>RSVP</AppText>
        <View style={stylesObj.rsvpRow}>
          {["going", "maybe", "not_going"].map((s) => (
            <Pressable
              key={s}
              disabled={rsvpBusy}
              style={({ pressed }) => [
                stylesObj.rsvpBtn,
                { borderColor: colors.border },
                rsvpStatus === s && s === "maybe" && stylesObj.rsvpBtnActiveMaybe,
                rsvpStatus === s && s === "not_going" && stylesObj.rsvpBtnActiveNot,
                rsvpStatus === s && s === "going" && stylesObj.rsvpBtnActive,
                pressedOpacityStyle(pressed),
              ]}
              onPress={() => handleRsvp(s)}
            >
              <AppText style={[stylesObj.rsvpText, rsvpStatus !== s && { color: colors.textSecondary }]}>
                {s === "going" ? "Going" : s === "maybe" ? "Maybe" : "Not Going"}
              </AppText>
            </Pressable>
          ))}
        </View>
      </View>

      {/* Ticket Purchase */}
      {hasTickets ? (
        <View style={{ gap: 8 }}>
          <AppText style={stylesObj.sectionTitle}>Tickets</AppText>
          {ticketTypes.map((tt) => (
            <Card key={tt.ticket_type_id} style={{ padding: 12, gap: 6 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                <AppText style={{ fontWeight: "700" }}>{tt.name}</AppText>
                <AppText>KES {(tt.price_minor_units / 100).toLocaleString()}</AppText>
              </View>
              {tt.description ? <AppText tone="secondary" style={{ fontSize: 12 }}>{tt.description}</AppText> : null}
              <View style={stylesObj.stepperRow}>
                <Pressable
                  style={({ pressed }) => [stylesObj.stepperBtn, pressedOpacityStyle(pressed)]}
                  onPress={() => updateQty(tt.ticket_type_id, -1)}
                >
                  <AppText style={{ fontSize: 18, fontWeight: "700" }}>-</AppText>
                </Pressable>
                <AppText style={stylesObj.stepperCount}>{ticketTypeQtys[tt.ticket_type_id] ?? 0}</AppText>
                <Pressable
                  style={({ pressed }) => [stylesObj.stepperBtn, pressedOpacityStyle(pressed)]}
                  onPress={() => updateQty(tt.ticket_type_id, 1)}
                >
                  <AppText style={{ fontSize: 18, fontWeight: "700" }}>+</AppText>
                </Pressable>
              </View>
            </Card>
          ))}
          <Button
            label={purchaseBusy ? "Purchasing..." : `Buy${totalSelected > 0 ? ` (${totalSelected})` : ""}`}
            variant="filled"
            loading={purchaseBusy}
            onPress={handlePurchase}
            fullWidth
          />
        </View>
      ) : null}

      {/* Save to Calendar + ICS + Share */}
      <View style={{ flexDirection: "row", gap: 8 }}>
        <Pressable
          style={({ pressed }) => [{
            flex: 1,
            paddingVertical: 10,
            borderRadius: 24,
            alignItems: "center",
            borderWidth: 1,
            borderColor: colors.border,
          }, saved && { backgroundColor: "#4CAF50", borderColor: "#4CAF50" }, pressedOpacityStyle(pressed)]}
          onPress={handleSaveToCalendar}
          disabled={saveBusy || saved}
        >
          <AppText style={{ fontSize: 13, fontWeight: "700", color: saved ? "#fff" : colors.textSecondary }}>
            {saveBusy ? "Saving..." : saved ? "Saved" : "Save to Calendar"}
          </AppText>
        </Pressable>
        <Pressable
          style={({ pressed }) => [{
            flex: 1,
            paddingVertical: 10,
            borderRadius: 24,
            alignItems: "center",
            borderWidth: 1,
            borderColor: colors.border,
          }, pressedOpacityStyle(pressed)]}
          onPress={handleExportIcs}
        >
          <AppText style={{ fontSize: 13, fontWeight: "700", color: colors.textSecondary }}>Export ICS</AppText>
        </Pressable>
      </View>

      <Button label="Share" variant="outline" onPress={handleShare} fullWidth />

      {/* Follow / Business actions */}
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

      {/* More from this Organizer */}
      {moreEvents.length > 0 ? (
        <View style={{ gap: 8 }}>
          <AppText style={stylesObj.sectionTitle}>More from this Organizer</AppText>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {moreEvents.map((e) => (
              <Pressable
                key={e.community_event_id}
                style={({ pressed }) => [{
                  width: 140,
                  marginRight: 8,
                  borderRadius: tokens.radii.sm,
                  overflow: "hidden",
                  borderWidth: 1,
                  borderColor: colors.border,
                }, pressedOpacityStyle(pressed)]}
                onPress={() => {
                  navigationRef.navigate("CommunityListingDetail", {
                    communityEventId: e.community_event_id,
                    organizerUserId: null,
                    title: e.title,
                    start_time: e.start_time,
                    venue: e.venue,
                    whatsapp_e164: e.whatsapp_e164 ?? null,
                    business_id,
                    viewMode: "viewer",
                  });
                }}
              >
                {e.poster_image_uri ? (
                  <Image source={{ uri: e.poster_image_uri }} style={{ width: 140, height: 100 }} resizeMode="cover" />
                ) : (
                  <View style={{ width: 140, height: 100, backgroundColor: colors.surface1 }} />
                )}
                <View style={{ padding: 6 }}>
                  <AppText numberOfLines={2} style={{ fontSize: 12, fontWeight: "700" }}>{e.title}</AppText>
                  <AppText style={{ fontSize: 10, color: "rgba(255,255,255,0.5)" }}>
                    {new Date(e.start_time).toLocaleDateString()}
                  </AppText>
                </View>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      ) : null}

      {/* Carousel */}
      {(() => {
        const unauthorized =
          carouselError && /not\s+authorized|forbidden|permission|unauthorized/i.test(carouselError);
        const shouldHideCarousel = effectiveViewMode === "viewer" && unauthorized;
        if (shouldHideCarousel) return null;

        return (
          <>
            <AppText variant="title">Carousel</AppText>
            {carouselLoading ? (
              <View style={stylesObj.center}>
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
        <View style={stylesObj.demoBanner}>
          <AppText variant="labelSmall" tone="tertiary">
            Demo only — not real checkout.
          </AppText>
          <Button
            label={billingBusy ? "Opening..." : "Promote listing (stub)"}
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
