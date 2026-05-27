import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Image, Pressable, View } from "react-native";
import { getUserPublicProfile, type PublicProfileEventRow } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { navigationRef } from "../navigation/navigationRef";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "UserPublicProfile">;

export function UserPublicProfileScreen({ route }: Props) {
  const { userId } = route.params;
  const { colors } = useTheme();
  const { accessToken, apiBaseUrl } = useAuth();
  const [profile, setProfile] = useState<{ display_name: string; avatar_url: string | null; events: PublicProfileEventRow[] } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await getUserPublicProfile(apiBaseUrl, accessToken, userId);
        if (!cancelled) setProfile(res);
      } catch {
        if (!cancelled) setProfile(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [userId, accessToken, apiBaseUrl]);

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  if (!profile) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg }}>
        <AppText tone="tertiary">Profile not found</AppText>
      </View>
    );
  }

  const renderEvent = ({ item }: { item: PublicProfileEventRow }) => (
    <Pressable
      style={({ pressed }) => [{
        flexDirection: "row",
        gap: 12,
        padding: tokens.spacing[12],
        borderRadius: tokens.radii.sm,
        backgroundColor: colors.surface1,
        borderWidth: 1,
        borderColor: colors.border,
      }, pressedOpacityStyle(pressed)]}
      onPress={() => {
        navigationRef.navigate("CommunityListingDetail", {
          communityEventId: item.community_event_id,
          organizerUserId: userId,
          title: item.title,
          start_time: item.start_time,
          venue: item.venue,
          viewMode: "viewer",
        });
      }}
    >
      {item.poster_image_uri ? (
        <Image source={{ uri: item.poster_image_uri }} style={{ width: 60, height: 60, borderRadius: 8 }} resizeMode="cover" />
      ) : (
        <View style={{ width: 60, height: 60, borderRadius: 8, backgroundColor: colors.surface2 }} />
      )}
      <View style={{ flex: 1, gap: 4 }}>
        <AppText style={{ fontWeight: "700" }} numberOfLines={2}>{item.title}</AppText>
        <AppText tone="secondary" style={{ fontSize: 12 }}>{item.venue}</AppText>
        <AppText style={{ fontSize: 11, color: item.role === "organizer" ? "#4CAF50" : "#FF9800" }}>
          {item.role === "organizer" ? "Organized" : "Attended"}
        </AppText>
      </View>
    </Pressable>
  );

  return (
    <FlatList
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: tokens.spacing[16], gap: tokens.spacing[12] }}
      data={profile.events}
      keyExtractor={(item) => `${item.role}-${item.community_event_id}`}
      ListHeaderComponent={
        <View style={{ gap: 8, paddingBottom: 8 }}>
          {profile.avatar_url ? (
            <Image source={{ uri: profile.avatar_url }} style={{ width: 80, height: 80, borderRadius: 40 }} />
          ) : (
            <View style={{ width: 80, height: 80, borderRadius: 40, backgroundColor: colors.surface2 }} />
          )}
          <AppText variant="headline">{profile.display_name}</AppText>
          <AppText tone="secondary">{profile.events.length} past event{profile.events.length !== 1 ? "s" : ""}</AppText>
        </View>
      }
      ListEmptyComponent={
        <View style={{ paddingVertical: 40, alignItems: "center" }}>
          <AppText tone="tertiary">No public events yet.</AppText>
        </View>
      }
      renderItem={renderEvent}
    />
  );
}
