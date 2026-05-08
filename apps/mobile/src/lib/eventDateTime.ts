/** Display formatting — API/storage remain ISO 8601. */

const UNKNOWN_TIME_LABEL = "Unknown date/time";

export function formatFriendlyEventDateTime(iso: string | null | undefined): string {
  if (iso == null || !String(iso).trim()) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return new Intl.DateTimeFormat(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }).format(d);
  } catch {
    return String(iso);
  }
}

/** Use on draft/review lines when the API may omit `start_time`. */
export function describeEventStartTime(iso: string | null | undefined): string {
  return formatFriendlyEventDateTime(iso) || UNKNOWN_TIME_LABEL;
}

export function dateFromIsoOrNow(iso: string): Date {
  if (!iso.trim()) return new Date();
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? new Date() : d;
}

export function toIsoUtcString(d: Date): string {
  return d.toISOString();
}

export function mergeDatePart(current: Date, datePicked: Date): Date {
  const out = new Date(current.getTime());
  out.setFullYear(datePicked.getFullYear(), datePicked.getMonth(), datePicked.getDate());
  return out;
}

export function mergeTimePart(current: Date, timePicked: Date): Date {
  const out = new Date(current.getTime());
  out.setHours(timePicked.getHours(), timePicked.getMinutes(), timePicked.getSeconds(), 0);
  out.setMilliseconds(0);
  return out;
}
