import { ExtensionStorage } from "@bacons/apple-targets";
import Constants from "expo-constants";

import { IOS_EXTENSION_HANDOFF_KEY } from "./constants";

export function readIosExtensionHandoff(): string | null {
  const group = (Constants.expoConfig?.extra as { appGroup?: string } | undefined)?.appGroup;
  if (!group) return null;
  try {
    const store = new ExtensionStorage(group);
    const text = store.get(IOS_EXTENSION_HANDOFF_KEY);
    if (text) {
      store.remove(IOS_EXTENSION_HANDOFF_KEY);
      return text;
    }
  } catch {
    /* Expo Go or native module unavailable */
  }
  return null;
}
