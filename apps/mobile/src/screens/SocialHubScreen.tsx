import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import React, { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Pressable,
  RefreshControl,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  deleteFollowUser,
  EventflowApiError,
  listFollowing,
  listGroups,
  postCreateGroup,
  postJoinGroupByToken,
  type FollowingRow,
  type GroupRow,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "SocialHub">;

type Segment = "groups" | "following";
type RoleFilter = "all" | "owner" | "member";

export function SocialHubScreen({ navigation }: Props) {
  const { colors, mode, toggle } = useTheme();
  const { apiBaseUrl, accessToken, refreshSession } = useAuth();

  const styles = useThemedStyles((c) => ({
    safe: { flex: 1, backgroundColor: c.bg },
    header: {
      flexDirection: "row" as const,
      alignItems: "center" as const,
      justifyContent: "space-between" as const,
      paddingHorizontal: tokens.spacing[12],
      paddingVertical: tokens.spacing[10],
      borderBottomWidth: 1,
      borderBottomColor: c.border,
      backgroundColor: c.surface1,
    },
    headerTitle: { flex: 1, textAlign: "center" as const },
    iconBtn: {
      width: 40,
      height: 40,
      alignItems: "center" as const,
      justifyContent: "center" as const,
      borderRadius: tokens.radii.sm,
    },
    segmentRow: {
      flexDirection: "row" as const,
      paddingHorizontal: tokens.spacing[16],
      paddingTop: tokens.spacing[12],
      gap: tokens.spacing[8],
    },
    segment: {
      flex: 1,
      paddingVertical: tokens.spacing[10],
      alignItems: "center" as const,
      borderRadius: tokens.radii.sm,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surface1,
    },
    segmentActive: {
      borderColor: c.textPrimary,
      backgroundColor: c.surface2,
    },
    filterRow: {
      flexDirection: "row" as const,
      flexWrap: "wrap" as const,
      paddingHorizontal: tokens.spacing[16],
      paddingTop: tokens.spacing[12],
      gap: tokens.spacing[8],
      alignItems: "center" as const,
    },
    chip: {
      paddingVertical: 6,
      paddingHorizontal: 12,
      borderRadius: tokens.radii.sm,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surface1,
    },
    chipActive: {
      borderColor: c.textPrimary,
      backgroundColor: c.surface2,
    },
    search: {
      flexGrow: 1,
      minWidth: 120,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      paddingHorizontal: tokens.spacing[12],
      paddingVertical: tokens.spacing[10],
      color: c.textPrimary,
      backgroundColor: c.surface1,
    },
    actions: {
      flexDirection: "row" as const,
      gap: tokens.spacing[8],
      paddingHorizontal: tokens.spacing[16],
      paddingTop: tokens.spacing[12],
    },
    list: { padding: tokens.spacing[16], flexGrow: 1 },
    row: {
      padding: tokens.spacing[12],
      borderRadius: tokens.radii.sm,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surface1,
      marginBottom: tokens.spacing[10],
      gap: tokens.spacing[8],
    },
    rowMeta: { flexDirection: "row" as const, flexWrap: "wrap" as const, gap: tokens.spacing[8], alignItems: "center" as const },
    badge: {
      paddingHorizontal: 8,
      paddingVertical: 2,
      borderRadius: 4,
      backgroundColor: c.surface2,
    },
    center: { flex: 1, justifyContent: "center" as const, alignItems: "center" as const, padding: 24 },
    modalBackdrop: {
      flex: 1,
      backgroundColor: c.overlay,
      justifyContent: "center" as const,
      padding: tokens.spacing[20],
    },
    modalCard: {
      backgroundColor: c.surface1,
      borderRadius: tokens.radii.sm,
      padding: tokens.spacing[16],
      gap: tokens.spacing[12],
      borderWidth: 1,
      borderColor: c.border,
    },
    modalInput: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      paddingHorizontal: tokens.spacing[12],
      paddingVertical: tokens.spacing[10],
      color: c.textPrimary,
    },
  }));

  const [segment, setSegment] = useState<Segment>("groups");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");
  const [groupSearch, setGroupSearch] = useState("");
  const [followingSearch, setFollowingSearch] = useState("");
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [following, setFollowing] = useState<FollowingRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [joinOpen, setJoinOpen] = useState(false);
  const [joinToken, setJoinToken] = useState("");
  const [joinBusy, setJoinBusy] = useState(false);

  const load = useCallback(async () => {
    if (!accessToken) {
      setGroups([]);
      setFollowing([]);
      setLoading(false);
      return;
    }
    setError(null);
    try {
      const [g, f] = await Promise.all([listGroups(apiBaseUrl, accessToken), listFollowing(apiBaseUrl, accessToken)]);
      setGroups(g);
      setFollowing(f);
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) await refreshSession().catch(() => undefined);
      setError(e instanceof Error ? e.message : String(e));
      setGroups([]);
      setFollowing([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [accessToken, apiBaseUrl, refreshSession]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      void load();
    }, [load])
  );

  const filteredGroups = useMemo(() => {
    const q = groupSearch.trim().toLowerCase();
    return groups.filter((row) => {
      if (roleFilter !== "all" && row.my_role !== roleFilter) return false;
      if (q && !row.name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [groups, groupSearch, roleFilter]);

  const filteredFollowing = useMemo(() => {
    const q = followingSearch.trim().toLowerCase();
    if (!q) return following;
    return following.filter((row) => row.following_user_id.toLowerCase().includes(q));
  }, [following, followingSearch]);

  const onRefresh = () => {
    setRefreshing(true);
    void load();
  };

  const openOverflow = () => {
    Alert.alert("Menu", undefined, [
      {
        text: "Profile & settings",
        onPress: () =>
          navigation.navigate("Main", {
            screen: "Profile",
            params: { screen: "ProfileHome" },
          }),
      },
      { text: "Cancel", style: "cancel" },
    ]);
  };

  const submitCreate = async () => {
    const name = createName.trim();
    if (!name || !accessToken) return;
    setCreateBusy(true);
    try {
      await postCreateGroup(apiBaseUrl, accessToken, { name });
      setCreateOpen(false);
      setCreateName("");
      await load();
    } catch (e: unknown) {
      Alert.alert("Could not create group", e instanceof Error ? e.message : String(e));
    } finally {
      setCreateBusy(false);
    }
  };

  const submitJoin = async () => {
    const tok = joinToken.trim();
    if (!tok || !accessToken) return;
    setJoinBusy(true);
    try {
      await postJoinGroupByToken(apiBaseUrl, accessToken, tok);
      setJoinOpen(false);
      setJoinToken("");
      await load();
    } catch (e: unknown) {
      Alert.alert("Could not join", e instanceof Error ? e.message : String(e));
    } finally {
      setJoinBusy(false);
    }
  };

  const unfollowRow = (userId: string) => {
    if (!accessToken) return;
    Alert.alert("Unfollow?", "You can follow again from a listing.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Unfollow",
        style: "destructive",
        onPress: () =>
          void (async () => {
            try {
              await deleteFollowUser(apiBaseUrl, accessToken, userId);
              await load();
            } catch (e: unknown) {
              Alert.alert("Unfollow failed", e instanceof Error ? e.message : String(e));
            }
          })(),
      },
    ]);
  };

  const copyToken = async (token: string | null | undefined) => {
    if (!token?.trim()) return;
    await Clipboard.setStringAsync(token.trim());
    Alert.alert("Copied", "Invite token copied to clipboard.");
  };

  if (!accessToken) {
    return (
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <View style={styles.header}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Close"
            onPress={() => navigation.goBack()}
            style={({ pressed }) => [styles.iconBtn, pressedOpacityStyle(pressed)]}
          >
            <Ionicons name="close" size={22} color={colors.textPrimary} />
          </Pressable>
          <AppText variant="title" style={styles.headerTitle}>
            Connections
          </AppText>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.center}>
          <AppText tone="secondary" style={{ textAlign: "center", marginBottom: 12 }}>
            Sign in to see groups and organizers you follow.
          </AppText>
          <Button label="Close" variant="outline" onPress={() => navigation.goBack()} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
      <View style={styles.header}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Close"
          onPress={() => navigation.goBack()}
          style={({ pressed }) => [styles.iconBtn, pressedOpacityStyle(pressed)]}
        >
          <Ionicons name="close" size={22} color={colors.textPrimary} />
        </Pressable>
        <AppText variant="title" style={styles.headerTitle}>
          Connections
        </AppText>
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            onPress={() => toggle()}
            style={({ pressed }) => [styles.iconBtn, pressedOpacityStyle(pressed)]}
          >
            <Ionicons name={mode === "dark" ? "sunny-outline" : "moon-outline"} size={22} color={colors.textPrimary} />
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="More options"
            onPress={openOverflow}
            style={({ pressed }) => [styles.iconBtn, pressedOpacityStyle(pressed)]}
          >
            <Ionicons name="ellipsis-horizontal" size={22} color={colors.textPrimary} />
          </Pressable>
        </View>
      </View>

      <View style={styles.segmentRow}>
        <Pressable
          accessibilityLabel="Groups tab"
          onPress={() => setSegment("groups")}
          style={({ pressed }) => [
            styles.segment,
            segment === "groups" && styles.segmentActive,
            pressedOpacityStyle(pressed),
          ]}
        >
          <AppText variant="label">Groups</AppText>
        </Pressable>
        <Pressable
          accessibilityLabel="Following tab"
          onPress={() => setSegment("following")}
          style={({ pressed }) => [
            styles.segment,
            segment === "following" && styles.segmentActive,
            pressedOpacityStyle(pressed),
          ]}
        >
          <AppText variant="label">Following</AppText>
        </Pressable>
      </View>

      {segment === "groups" ? (
        <>
          <View style={styles.filterRow}>
            {(["all", "owner", "member"] as const).map((r) => (
              <Pressable
                accessibilityLabel="Filter by role"
                key={r}
                onPress={() => setRoleFilter(r)}
                style={({ pressed }) => [
                  styles.chip,
                  roleFilter === r && styles.chipActive,
                  pressedOpacityStyle(pressed),
                ]}
              >
                <AppText variant="labelSmall">{r === "all" ? "All" : r === "owner" ? "Owner" : "Member"}</AppText>
              </Pressable>
            ))}
            <TextInput
              style={styles.search}
              placeholder="Search groups"
              placeholderTextColor={colors.textTertiary}
              value={groupSearch}
              onChangeText={setGroupSearch}
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>
          <View style={styles.actions}>
            <Button label="New group" variant="outline" size="md" onPress={() => setCreateOpen(true)} />
            <Button label="Join with token" variant="outline" size="md" onPress={() => setJoinOpen(true)} />
          </View>
        </>
      ) : (
        <View style={[styles.filterRow, { paddingBottom: 4 }]}>
          <TextInput
            style={[styles.search, { flex: 1, minWidth: "100%" as const }]}
            placeholder="Search by user id"
            placeholderTextColor={colors.textTertiary}
            value={followingSearch}
            onChangeText={setFollowingSearch}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>
      )}

      {loading && !refreshing ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.textSecondary} />
        </View>
      ) : segment === "groups" ? (
        <FlatList<GroupRow>
          style={styles.list}
          data={filteredGroups}
          keyExtractor={(g) => g.group_id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <AppText tone="secondary" style={{ textAlign: "center", marginTop: 24 }}>
              {error ?? "No groups match your filters."}
            </AppText>
          }
          renderItem={({ item: g }) => {
            const isOwner = g.my_role === "owner";
            return (
              <View style={styles.row}>
                <AppText variant="title">{g.name}</AppText>
                <View style={styles.rowMeta}>
                  <View style={styles.badge}>
                    <AppText variant="labelSmall">{g.my_role ?? "member"}</AppText>
                  </View>
                  {g.group_type ? (
                    <AppText variant="labelSmall" tone="tertiary">
                      {g.group_type}
                    </AppText>
                  ) : null}
                </View>
                {isOwner && g.invite_token ? (
                  <Button label="Copy invite token" variant="outline" size="md" onPress={() => void copyToken(g.invite_token)} />
                ) : null}
              </View>
            );
          }}
        />
      ) : (
        <FlatList<FollowingRow>
          style={styles.list}
          data={filteredFollowing}
          keyExtractor={(f) => f.following_user_id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <AppText tone="secondary" style={{ textAlign: "center", marginTop: 24 }}>
              {error ?? "You are not following anyone yet."}
            </AppText>
          }
          renderItem={({ item: f }) => (
            <View style={styles.row}>
              <AppText variant="labelSmall" tone="tertiary" style={{ fontFamily: "monospace" }}>
                {f.following_user_id}
              </AppText>
              <Button label="Unfollow" variant="outline" size="md" onPress={() => unfollowRow(f.following_user_id)} />
            </View>
          )}
        />
      )}

      <Modal visible={createOpen} transparent animationType="fade" onRequestClose={() => setCreateOpen(false)}>
        <Pressable accessibilityLabel="Close create group" style={styles.modalBackdrop} onPress={() => setCreateOpen(false)}>
          <Pressable style={styles.modalCard} onPress={(e) => e.stopPropagation()}>
            <AppText variant="title">New group</AppText>
            <TextInput
              style={styles.modalInput}
              placeholder="Group name"
              placeholderTextColor={colors.textTertiary}
              value={createName}
              onChangeText={setCreateName}
            />
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Button label="Cancel" variant="outline" onPress={() => setCreateOpen(false)} />
              <Button label="Create" loading={createBusy} onPress={() => void submitCreate()} />
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={joinOpen} transparent animationType="fade" onRequestClose={() => setJoinOpen(false)}>
        <Pressable accessibilityLabel="Close join group" style={styles.modalBackdrop} onPress={() => setJoinOpen(false)}>
          <Pressable style={styles.modalCard} onPress={(e) => e.stopPropagation()}>
            <AppText variant="title">Join with invite token</AppText>
            <TextInput
              style={styles.modalInput}
              placeholder="Paste token"
              placeholderTextColor={colors.textTertiary}
              value={joinToken}
              onChangeText={setJoinToken}
              autoCapitalize="none"
            />
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Button label="Cancel" variant="outline" onPress={() => setJoinOpen(false)} />
              <Button label="Join" loading={joinBusy} onPress={() => void submitJoin()} />
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}
