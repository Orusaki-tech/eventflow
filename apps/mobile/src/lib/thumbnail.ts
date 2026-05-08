import AsyncStorage from "@react-native-async-storage/async-storage";

const DRAFT_URL_KEY_PREFIX = "@eventflow/source_url/draft/";
const EVENT_URL_KEY_PREFIX = "@eventflow/source_url/event/";
const DRAFT_POSTER_KEY_PREFIX = "@eventflow/poster_asset/draft/";
const EVENT_POSTER_KEY_PREFIX = "@eventflow/poster_asset/event/";

export function buildThumbnailUri(apiBaseUrl: string, sharedUrl: string): string {
  const base = apiBaseUrl.replace(/\/$/, "");
  return `${base}/api/v1/media/thumbnail?url=${encodeURIComponent(sharedUrl)}`;
}

export function buildResolvedImageUri(apiBaseUrl: string, imageToken: string): string {
  const base = apiBaseUrl.replace(/\/$/, "");
  return `${base}/api/v1/media/image?token=${encodeURIComponent(imageToken)}`;
}

export async function saveDraftSourceUrl(draftId: string, sharedUrl: string): Promise<void> {
  await AsyncStorage.setItem(`${DRAFT_URL_KEY_PREFIX}${draftId}`, sharedUrl);
}

export async function getDraftSourceUrl(draftId: string): Promise<string | null> {
  return await AsyncStorage.getItem(`${DRAFT_URL_KEY_PREFIX}${draftId}`);
}

export async function saveEventSourceUrl(eventId: string, sharedUrl: string): Promise<void> {
  await AsyncStorage.setItem(`${EVENT_URL_KEY_PREFIX}${eventId}`, sharedUrl);
}

export async function getEventSourceUrl(eventId: string): Promise<string | null> {
  return await AsyncStorage.getItem(`${EVENT_URL_KEY_PREFIX}${eventId}`);
}

export function buildPosterAssetUri(apiBaseUrl: string, posterAssetId: string): string {
  const base = apiBaseUrl.replace(/\/$/, "");
  return `${base}/api/v1/media/poster/${encodeURIComponent(posterAssetId)}`;
}

export async function saveDraftPosterAssetId(draftId: string, posterAssetId: string): Promise<void> {
  await AsyncStorage.setItem(`${DRAFT_POSTER_KEY_PREFIX}${draftId}`, posterAssetId);
}

export async function getDraftPosterAssetId(draftId: string): Promise<string | null> {
  return await AsyncStorage.getItem(`${DRAFT_POSTER_KEY_PREFIX}${draftId}`);
}

export async function saveEventPosterAssetId(eventId: string, posterAssetId: string): Promise<void> {
  await AsyncStorage.setItem(`${EVENT_POSTER_KEY_PREFIX}${eventId}`, posterAssetId);
}

export async function getEventPosterAssetId(eventId: string): Promise<string | null> {
  return await AsyncStorage.getItem(`${EVENT_POSTER_KEY_PREFIX}${eventId}`);
}

