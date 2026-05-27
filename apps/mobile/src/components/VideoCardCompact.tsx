import React, { useCallback, useRef, useState } from "react";
import { ActivityIndicator, Image, Pressable, StyleSheet, View } from "react-native";
import type { UnifiedFeedVideo } from "../api/eventflow";
import { AppText } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { navigationRef } from "../navigation/navigationRef";
import { COMPACT_CARD_WIDTH } from "./EventCardCompact";

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
};

export function VideoCardCompact({ item }: Props) {
  const { colors } = useTheme();
  const VideoComponent = NativeVideo;
  const videoRef = useRef<unknown>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loaded, setLoaded] = useState(false);
  
  const handlePlaybackStatusUpdate = useCallback(
    (status: Record<string, unknown>) => {
      console.log("Video playback status update:", status);
      if (!status.isLoaded) return;
      if (!loaded) {
        console.log("Video loaded successfully");
        setLoaded(true);
      }
      
      // Check for errors
      if (status.error) {
        console.error("Video playback error:", status.error);
        // If there's an error, fall back to navigation
        if (item.community_event_id && navigationRef.isReady()) {
          navigationRef.navigate("CommunityListingDetail", {
            communityEventId: item.community_event_id,
            organizerUserId: "",
            title: item.event_title ?? item.title,
            start_time: "",
            venue: "",
            whatsapp_e164: item.whatsapp_e164 ?? null,
            business_id: item.business_id,
            viewMode: "viewer",
          });
        }
      }
    },
    [loaded, item, navigationRef]
  );

  const togglePlay = () => {
    console.log("VideoCardCompact togglePlay called:", {
      hasVideoComponent: !!VideoComponent,
      hasVideoUri: !!item.video_uri,
      videoUri: item.video_uri
    });
    
    if (!VideoComponent || !item.video_uri) {
      console.log("Video component not available or no video URI - falling back to navigation");
      if (item.community_event_id && navigationRef.isReady()) {
        navigationRef.navigate("CommunityListingDetail", {
          communityEventId: item.community_event_id,
          organizerUserId: "",
          title: item.event_title ?? item.title,
          start_time: "",
          venue: "",
          whatsapp_e164: item.whatsapp_e164 ?? null,
          business_id: item.business_id,
          viewMode: "viewer",
        });
      }
      return;
    }
    
    console.log("Toggling video play state:", isPlaying);
    setIsPlaying(!isPlaying);
  };

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressedOpacityStyle(pressed)]}
      onPress={togglePlay}
    >
      <View style={[styles.imageWrap, { backgroundColor: colors.surface1 }]}>
        {VideoComponent && item.video_uri ? (
          <VideoComponent
            ref={videoRef}
            source={{ uri: item.video_uri }}
            style={styles.image as Record<string, unknown>}
            resizeMode="cover"
            shouldPlay={isPlaying}
            isMuted={true}
            isLooping
            onPlaybackStatusUpdate={handlePlaybackStatusUpdate}
          />
        ) : item.thumbnail_uri ? (
          <Image source={{ uri: item.thumbnail_uri }} style={styles.image} resizeMode="cover" />
        ) : null}
        
        {(!isPlaying) && (
          <View style={styles.playOverlay}>
            <AppText style={styles.playIcon}>▶</AppText>
          </View>
        )}
        
        {isPlaying && !loaded && (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator color="#fff" />
          </View>
        )}

        <View style={styles.viewsBadge}>
          <AppText style={styles.viewsText}>{item.views}</AppText>
        </View>
      </View>

      <View style={styles.body}>
        {item.business_name ? (
          <AppText numberOfLines={1} style={styles.business}>
            {item.business_name}
          </AppText>
        ) : null}
        <AppText numberOfLines={2} style={styles.title}>
          {item.title}
        </AppText>
        {item.event_title ? (
          <AppText numberOfLines={1} style={styles.event}>
            {item.event_title}
          </AppText>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: COMPACT_CARD_WIDTH,
    marginRight: tokens.spacing[10],
  },
  imageWrap: {
    width: COMPACT_CARD_WIDTH,
    height: COMPACT_CARD_WIDTH * 1.2,
    borderRadius: tokens.radii.sm,
    overflow: "hidden",
    position: "relative",
  },
  image: {
    width: "100%",
    height: "100%",
  },
  playOverlay: {
    position: "absolute",
    top: "40%",
    alignSelf: "center",
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "center",
    alignItems: "center",
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.3)",
    justifyContent: "center",
    alignItems: "center",
  },
  playIcon: {
    color: "#fff",
    fontSize: 16,
  },
  viewsBadge: {
    position: "absolute",
    bottom: 8,
    right: 8,
    backgroundColor: "rgba(0,0,0,0.7)",
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  viewsText: {
    color: "#fff",
    fontSize: 10,
    fontWeight: "700",
  },
  body: {
    paddingTop: 8,
    gap: 2,
  },
  business: {
    fontSize: 11,
    fontWeight: "700",
    color: "rgba(255,255,255,0.6)",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  title: {
    fontSize: 13,
    fontWeight: "800",
    lineHeight: 16,
  },
  event: {
    fontSize: 11,
    lineHeight: 14,
    color: "rgba(255,255,255,0.5)",
  },
});
