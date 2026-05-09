import * as Calendar from "expo-calendar";
import {
  deleteDeviceCalendarLink,
  EventflowApiError,
  getDeviceCalendarLink,
  putDeviceCalendarLink,
} from "../api/eventflow";

async function pickWritableCalendarId(): Promise<string | null> {
  const perm = await Calendar.requestCalendarPermissionsAsync();
  if (perm.status !== "granted") return null;
  const cals = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
  const writable = cals.find((c) => c.allowsModifications);
  return writable?.id ?? cals[0]?.id ?? null;
}

export async function syncConfirmedEventToDeviceCalendar(args: {
  apiBaseUrl: string;
  accessToken: string | null;
  eventId: string;
  title: string;
  startIso: string;
  venue: string;
}): Promise<void> {
  const { apiBaseUrl, accessToken, eventId, title, startIso, venue } = args;
  if (!accessToken) return;
  const calId = await pickWritableCalendarId();
  if (!calId) return;
  const start = new Date(startIso);
  if (Number.isNaN(start.getTime())) return;
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  try {
    const nativeId = await Calendar.createEventAsync(calId, {
      title,
      startDate: start,
      endDate: end,
      location: venue,
      timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    });
    await putDeviceCalendarLink(apiBaseUrl, accessToken, eventId, {
      external_event_id: nativeId,
      calendar_id: calId,
    });
  } catch {
    /* non-fatal */
  }
}

export async function removeDeviceCalendarMapping(
  apiBaseUrl: string,
  accessToken: string | null,
  eventId: string
): Promise<void> {
  if (!accessToken) return;
  try {
    const link = await getDeviceCalendarLink(apiBaseUrl, accessToken, eventId);
    try {
      await Calendar.deleteEventAsync(link.external_event_id);
    } catch {
      /* ignore */
    }
    await deleteDeviceCalendarLink(apiBaseUrl, accessToken, eventId);
  } catch (e) {
    if (e instanceof EventflowApiError && e.status === 404) return;
  }
}
