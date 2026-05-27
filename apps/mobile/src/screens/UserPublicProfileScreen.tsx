import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Image, StyleSheet, View } from "react-native";
import { getUserProfile, postFollowUser, deleteFollowUser, listFollowing } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "UserPublicProfile">;

export function UserPublicProfileScreen({ route }: Props) {
  const { colors } = useTheme();
  const { userId, displayName } = route.params;
  const { apiBaseUrl, accessToken } = useAuth();
  const [profile, setProfile] = useState<{ display_name: string; avatar_url: string | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [isFollowing, setIsFollowing] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    void (async () => {
      try {
        const [p, f] = await Promise.all([
          getUserProfile(apiBaseUrl, accessToken, userId),
          listFollowing(apiBaseUrl, accessToken),
        ]);
        setProfile(p);
        setIsFollowing(f.some((r) => r.following_user_id === userId));
      } catch {
        setProfile({ display_name: displayName ?? "User", avatar_url: null });
      } finally {
        setLoading(false);
      }
    })();
  }, [userId, displayName, apiBaseUrl, accessToken]);

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

  const initial = (profile?.display_name ?? "U").charAt(0).toUpperCase();

  return (
    <View style={[styles.root, { backgroundColor: colors.bg }]}>
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.textSecondary} />
        </View>
      ) : (
        <View style={styles.content}>
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
          <AppText tone="tertiary" variant="labelSmall">
            {userId.slice(0, 12)}...
          </AppText>
          <View style={{ marginTop: 16, width: "100%" }}>
            <Button
              label={isFollowing ? "Unfollow" : "Follow"}
              variant={isFollowing ? "outline" : "filled"}
              onPress={toggleFollow}
              fullWidth
            />
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  content: { alignItems: "center", padding: tokens.spacing[20], paddingTop: 48 },
  avatar: { width: 96, height: 96, borderRadius: 48 },
  avatarLetter: { alignItems: "center", justifyContent: "center" },
});
