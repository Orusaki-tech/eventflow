/** Backend allows 1–180 inclusive (`SnoozeAlertRequest`). */
export const SNOOZE_MIN_MIN = 1;
export const SNOOZE_MIN_MAX = 180;

export function clampSnoozeMinutes(raw: number): number {
  if (!Number.isFinite(raw)) return SNOOZE_MIN_MIN;
  const n = Math.floor(raw);
  return Math.min(SNOOZE_MIN_MAX, Math.max(SNOOZE_MIN_MIN, n));
}

export function parseSnoozeMinutesInput(text: string): number | null {
  const t = text.trim();
  if (!t.length) return null;
  const n = Number.parseInt(t, 10);
  if (!Number.isFinite(n)) return null;
  return clampSnoozeMinutes(n);
}
