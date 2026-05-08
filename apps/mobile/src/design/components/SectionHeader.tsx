import React from "react";
import { StyleSheet, View } from "react-native";
import { tokens } from "../tokens";
import { AppText } from "./AppText";

export function SectionHeader({ title }: { title: string }) {
  return (
    <View style={styles.root}>
      <AppText variant="title" style={styles.title}>
        {title}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { marginTop: tokens.spacing[16], paddingTop: tokens.spacing[4] },
  title: { letterSpacing: 0.2 },
});

