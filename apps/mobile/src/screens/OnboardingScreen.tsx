import AsyncStorage from "@react-native-async-storage/async-storage";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useRef, useState } from "react";
import {
  FlatList,
  NativeSyntheticEvent,
  NativeScrollEvent,
  useWindowDimensions,
  View,
} from "react-native";
import { useAuth } from "../auth/AuthContext";
import { STORAGE_ONBOARDING_DONE } from "../lib/constants";
import type { RootStackParamList } from "../navigation/types";
import { AppText, Button, CarouselDots } from "../design/components";
import { tokens } from "../design/tokens";
import { useThemedStyles } from "../design/useThemedStyles";

const STEPS = [
  {
    title: "Stop replaying flyers and reels",
    body: "Event details live in messy links, screenshots, and social posts. It is easy to lose the when and where before you get to the venue.",
  },
  {
    title: "Share straight into EventFlow",
    body: "Use the system Share sheet and pick EventFlow. On Android we read the text you send; on iOS the share extension hands off to the app.",
  },
  {
    title: "Get a structured plan",
    body: "We turn that content into a draft with title, time, and place. Confirm once, then add reminders or export a calendar file.",
  },
];

type Props = NativeStackScreenProps<RootStackParamList, "Onboarding"> & {
  onOnboardingStored?: () => void;
};

export function OnboardingScreen({ navigation, onOnboardingStored }: Props) {
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg, paddingTop: 48 },
    page: { paddingHorizontal: 28, justifyContent: "center" as const },
    stepTitle: { marginBottom: tokens.spacing[16] },
    stepBody: { fontSize: 16, lineHeight: 24 },
    footer: { padding: tokens.spacing[24], gap: tokens.spacing[16] },
  }));
  const { width } = useWindowDimensions();
  const { session } = useAuth();
  const listRef = useRef<FlatList>(null);
  const [index, setIndex] = useState(0);

  const finish = async () => {
    await AsyncStorage.setItem(STORAGE_ONBOARDING_DONE, "1");
    onOnboardingStored?.();
    navigation.reset({
      index: 0,
      routes: [{ name: session ? "Main" : "Auth" }],
    });
  };

  return (
    <View style={styles.root}>
      <FlatList
        ref={listRef}
        data={STEPS}
        keyExtractor={(_, i) => String(i)}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={(e: NativeSyntheticEvent<NativeScrollEvent>) => {
          const x = e.nativeEvent.contentOffset.x;
          setIndex(Math.round(x / Math.max(width, 1)));
        }}
        renderItem={({ item }) => (
          <View style={[styles.page, { width }]}>
            <AppText variant="headline" style={styles.stepTitle}>
              {item.title}
            </AppText>
            <AppText tone="secondary" style={styles.stepBody}>
              {item.body}
            </AppText>
          </View>
        )}
      />
      <View style={styles.footer}>
        <CarouselDots count={STEPS.length} activeIndex={index} />
        {index < STEPS.length - 1 ? (
          <Button
            label="Next"
            onPress={() =>
              listRef.current?.scrollToOffset({
                offset: width * (index + 1),
                animated: true,
              })
            }
            fullWidth
          />
        ) : (
          <Button label="Get started" onPress={() => void finish()} fullWidth />
        )}
      </View>
    </View>
  );
}
