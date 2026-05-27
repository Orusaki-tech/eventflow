import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Image, Pressable, StyleSheet, View } from "react-native";
import { getUserPublicProfile, type PublicProfileEventRow, postFollowUser, deleteFollowUser, listFollowing } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { navigationRef } from "../navigation/navigationRef";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "UserPublicProfile">;

export function UserPublicProfileScreen({ route }: Props) {
  const { userId, displayName } = route.params;
  const { colors } = useTheme();
  const { accessToken, apiBaseUrl } = useAuth();
  
  const [profile, setProfile] = useState<{ display_name: string; avatar_url: string | null; events: PublicProfileEventRow[]; total: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [isFollowing, setIsFollowing] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void (async () => {
      try {
        const [res, f] = await Promise.all([
          getUserPublicProfile(apiBaseUrl, accessToken, userId),
          listFollowing(apiBaseUrl, accessToken),
        ]);
        if (!cancelled) {
          setProfile(res as any);
          setIsFollowing(f.some((r) => r.following_user_id === userId));
        }
      } catch {
        if (!cancelled) setProfile({ display_name: displayName ?? "User", avatar_url: null, events: [], total: 0 });
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [userId, displayName, accessToken, apiBaseUrl]);

  const toggleFollow = async () => {
    if (!accessToken) return;
    try {
      if (isFollowing) {
        await deleteFollowUser(apiBaseUrl, accessToken, userId);
      } else {
        await postFollowUser(apiBaseUrl, accessToken, userId);
      }
      setIsFollowing((p) => !p);
    } catch {
      // silently fail
    }
  };

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.textSecondary} />
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
        if (navigationRef.isReady()) {
          navigationRef.navigate("CommunityListingDetail", {
            communityEventId: item.community_event_id,
            organizerUserId: userId,
            title: item.title,
            start_time: item.start_time,
            venue: item.venue,
            viewMode: "viewer",
          });
        }
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

  const initial = (profile?.display_name ?? "U").charAt(0).toUpperCase();

  return (
    <FlatList
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: tokens.spacing[16], gap: tokens.spacing[12], paddingBottom: 50 }}
      data={profile?.events ?? []}
      keyExtractor={(item) => `${item.role}-${item.community_event_id}`}
      ListHeaderComponent={
        <View style={styles.header}>
          {profile?.avatar_url ? (
            <Image source={{ uri: profile.avatar_url }} style={styles.avatar} />
          ) : (
            <View style={[styles.avatar, styles.avatarLetter, { backgroundColor: colors.surface2 }]}>
              <AppText style={{ fontSize: 32, fontWeight: "900" }}>{initial}</AppText>
            </View>
          )}
          <AppText variant="headline" style={{ marginTop: 12 }}>
            {profile?.display_name ?? "User"}
          </AppText>
          <AppText tone="tertiary" variant="labelSmall" style={{ marginBottom: 16 }}>
            {userId.slice(0, 12)}...
          </AppText>
          <Button
            label={isFollowing ? "Unfollow" : "Follow"}
            variant={isFollowing ? "outline" : "filled"}
            onPress={() => void toggleFollow()}
            fullWidth
          />
          <AppText tone="secondary" style={{ marginTop: 24, alignSelf: "flex-start" }}>
            {profile?.events?.length ?? 0} public event{(profile?.events?.length ?? 0) !== 1 ? "s" : ""}
          </AppText>
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

const styles = StyleSheet.create({
  header: { alignItems: "center", paddingBottom: tokens.spacing[12] },
  avatar: { width: 96, height: 96, borderRadius: 48 },
  avatarLetter: { alignItems: "center", justifyContent: "center" },
});
