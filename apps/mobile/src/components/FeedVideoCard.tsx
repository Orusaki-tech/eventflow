import React, { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  Image,
  Linking,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import type { UnifiedFeedVideo } from "../api/eventflow";
import { AppText } from "../design/components";
import { pressedOpacityStyle } from "../design/tokens";
import { useTheme } from "../design/theme";
import { navigationRef } from "../navigation/navigationRef";

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get("window");

let NativeVideo: React.ComponentType<{
  source: { uri: string };
  style?: Record<string, unknown>;
  resizeMode?: string;
  shouldPlay?: boolean;
  isMuted?: boolean;
  isLooping?: boolean;
  onPlaybackStatusUpdate?: (status: Record<string, unknown>) => void;
  ref?: React.Ref<unknown>;
}> | null = null;

try {
  NativeVideo = require("expo-av").Video;
} catch {
  // expo-av not installed, will use thumbnail fallback
}

type Props = {
  item: UnifiedFeedVideo;
  isActive: boolean;
  onWatch?: (itemId: string) => void;
};

export function FeedVideoCard({ item, isActive, onWatch }: Props) {
  const { colors } = useTheme();
  const videoRef = useRef<unknown>(null);
  const [loaded, setLoaded] = useState(false);
  const [muted, setMuted] = useState(true);
  const [playingExternally, setPlayingExternally] = useState(false);
  const watchLogged = useRef(false);

  const handlePlaybackStatusUpdate = useCallback(
    (status: Record<string, unknown>) => {
      if (!status.isLoaded) return;
      if (!loaded) setLoaded(true);
      if (
        !watchLogged.current &&
        typeof status.durationMillis === "number" &&
        typeof status.positionMillis === "number"
      ) {
        if (status.positionMillis >= 3000 || status.positionMillis >= status.durationMillis * 0.5) {
          watchLogged.current = true;
          onWatch?.(item.item_id);
        }
      }
    },
    [item.item_id, loaded, onWatch]
  );

  React.useEffect(() => {
    if (!NativeVideo || !videoRef.current) return;
    const v = videoRef.current as { playAsync?: () => void; pauseAsync?: () => void };
    if (isActive) {
      v.playAsync?.();
    } else {
      v.pauseAsync?.();
    }
  }, [isActive]);

  const hasVideo = !!item.video_uri;
  const useNative = !!NativeVideo && hasVideo && !playingExternally;

  const openVideoExternally = () => {
    if (item.video_uri) {
      setPlayingExternally(true);
      Linking.openURL(item.video_uri);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.bg }]}>
      {/* Native video player (expo-av) */}
      {useNative ? (
        <NativeVideo
          ref={videoRef}
          source={{ uri: item.video_uri }}
          style={styles.video as Record<string, unknown>}
          resizeMode="cover"
          shouldPlay={isActive}
          isMuted={muted}
          isLooping
          onPlaybackStatusUpdate={handlePlaybackStatusUpdate}
        />
      ) : item.thumbnail_uri ? (
        <Image source={{ uri: item.thumbnail_uri }} style={styles.video} resizeMode="cover" />
      ) : hasVideo ? (
        <Pressable onPress={openVideoExternally} style={styles.video}>
          <View style={[styles.video, styles.videoPlaceholder, { backgroundColor: colors.surface1 }]}>
            <AppText tone="tertiary">Tap to play video</AppText>
          </View>
        </Pressable>
      ) : (
        <View style={[styles.video, styles.videoPlaceholder, { backgroundColor: colors.surface1 }]}>
          <AppText tone="tertiary">No video</AppText>
        </View>
      )}

      {/* Loading spinner for native video */}
      {!loaded && useNative && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator color="#fff" size="large" />
        </View>
      )}

      {/* External play button fallback */}
      {!NativeVideo && hasVideo && (
        <Pressable style={styles.externalPlayBtn} onPress={openVideoExternally}>
          <AppText style={styles.externalPlayText}>▶</AppText>
        </Pressable>
      )}

      {/* Top bar: business info */}
      <View style={styles.topBar}>
        {item.business_logo ? (
          <Image source={{ uri: item.business_logo }} style={styles.bizLogo} />
        ) : (
          <View style={[styles.bizLogo, { backgroundColor: "rgba(255,255,255,0.2)" }]} />
        )}
        <AppText style={styles.bizName} numberOfLines={1}>
          {item.business_name ?? "Business"}
        </AppText>
        <Pressable
          style={({ pressed }) => [styles.muteBtn, pressedOpacityStyle(pressed)]}
          onPress={() => setMuted((m) => !m)}
        >
          <AppText style={styles.muteText}>{muted ? "Muted" : "Sound"}</AppText>
        </Pressable>
      </View>

      {/* Bottom bar: event info + CTA */}
      <View style={styles.bottomBar}>
        {item.event_title ? (
          <Pressable
            onPress={() => {
              if (item.community_event_id && navigationRef.isReady()) {
                navigationRef.navigate("CommunityListingDetail", {
                  communityEventId: item.community_event_id,
                  organizerUserId: "",
                  title: item.event_title!,
                  start_time: "",
                  venue: "",
                  whatsapp_e164: item.whatsapp_e164 ?? null,
                  business_id: item.business_id,
                });
              }
            }}
          >
            <AppText style={styles.eventTitle} numberOfLines={2}>
              {item.event_title}
            </AppText>
          </Pressable>
        ) : null}
        <AppText style={styles.views}>
          {item.views} views
        </AppText>
        <AppText style={styles.title}>{item.title}</AppText>
        {item.whatsapp_e164 ? (
          <Pressable
            style={({ pressed }) => [styles.whatsappBtn, pressedOpacityStyle(pressed)]}
            onPress={() => {
              const clean = item.whatsapp_e164!.replace(/^\+/, "");
              Linking.openURL(`https://wa.me/${clean}`);
            }}
          >
            <AppText style={styles.whatsappText}>Chat on WhatsApp</AppText>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

export function feedVideoCardHeight() {
  return SCREEN_HEIGHT;
}

const styles = StyleSheet.create({
  container: {
    width: SCREEN_WIDTH,
    height: SCREEN_HEIGHT,
  },
  video: {
    ...StyleSheet.absoluteFillObject,
  },
  videoPlaceholder: {
    justifyContent: "center",
    alignItems: "center",
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
  },
  topBar: {
    position: "absolute",
    top: 60,
    left: 16,
    right: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  bizLogo: {
    width: 32,
    height: 32,
    borderRadius: 16,
  },
  bizName: {
    flex: 1,
    fontSize: 15,
    fontWeight: "700",
    color: "#fff",
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  muteBtn: {
    padding: 8,
  },
  bottomBar: {
    position: "absolute",
    bottom: 100,
    left: 16,
    right: 16,
    gap: 4,
  },
  eventTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#fff",
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  title: {
    fontSize: 14,
    color: "rgba(255,255,255,0.8)",
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  views: {
    fontSize: 12,
    color: "rgba(255,255,255,0.6)",
  },
  muteText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "600",
  },
  externalPlayBtn: {
    position: "absolute",
    top: "40%",
    alignSelf: "center",
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
  },
  externalPlayText: {
    color: "#fff",
    fontSize: 28,
  },
  whatsappBtn: {
    alignSelf: "flex-start",
    backgroundColor: "#25D366",
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    marginTop: 4,
  },
  whatsappText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 13,
  },
});
