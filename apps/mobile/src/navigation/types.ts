import type { NavigatorScreenParams } from "@react-navigation/native";

/** Stack inside Inbox tab */
export type InboxStackParamList = {
  InboxHome: undefined;
};

/** Stack inside Calendar tab */
export type CalendarStackParamList = {
  CalendarHome: { segment?: "today" | "upcoming" } | undefined;
};

/** Stack inside Capture tab */
export type CaptureStackParamList = {
  CaptureHome: undefined;
};

/** Stack inside Discover tab */
export type DiscoverStackParamList = {
  DiscoverHome: undefined;
};

/** Stack inside Profile tab */
export type ProfileStackParamList = {
  ProfileHome: undefined;
  BusinessProfile: undefined;
};

/** Bottom tabs (each tab is a nested stack) */
export type MainTabParamList = {
  Inbox: NavigatorScreenParams<InboxStackParamList>;
  Calendar: NavigatorScreenParams<CalendarStackParamList>;
  Capture: NavigatorScreenParams<CaptureStackParamList>;
  Discover: NavigatorScreenParams<DiscoverStackParamList>;
  Profile: NavigatorScreenParams<ProfileStackParamList>;
};

/** Root stack: auth + main tabs + shared flow screens */
export type RootStackParamList = {
  Onboarding: undefined;
  Auth: undefined;
  Main: NavigatorScreenParams<MainTabParamList> | undefined;
  Processing: { rawText?: string; urls?: string[]; carouselSlideIndices?: number[] } | undefined;
  ImportLink: undefined;
  CarouselSlidePick: { rawText: string; instagramUrl: string };
  SharedMediaImport: { payloadJson: string };
  PosterImport: undefined;
  DraftDetail: { draftId: string; sharedUrl?: string };
  DraftEdit: { draftId: string; sharedUrl?: string };
  Confirmed: { eventId: string; sharedUrl?: string };
  EventDetail: {
    eventId: string;
    title: string;
    start_time: string;
    venue: string;
    sharedUrl?: string;
    price?: string | null;
    /** Owner of the event (for cancel). Omit when unknown. */
    ownerUserId?: string;
  };
  ManualVenue: { eventId: string; venueHint?: string | null };
  CommunityListingDetail: {
    communityEventId: string;
    organizerUserId: string | null;
    title: string;
    start_time: string;
    venue: string;
    whatsapp_e164?: string | null;
    business_id?: string | null;
  };
  BusinessProfileView: { businessId: string; businessName?: string };
  SocialHub: undefined;
  Subscription: undefined;
};
