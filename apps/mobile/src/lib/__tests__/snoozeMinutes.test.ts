import { clampSnoozeMinutes, parseSnoozeMinutesInput, SNOOZE_MIN_MAX, SNOOZE_MIN_MIN } from "../snoozeMinutes";

describe("clampSnoozeMinutes", () => {
  it("clamps below minimum", () => {
    expect(clampSnoozeMinutes(0)).toBe(SNOOZE_MIN_MIN);
    expect(clampSnoozeMinutes(-5)).toBe(SNOOZE_MIN_MIN);
  });
  it("clamps above maximum", () => {
    expect(clampSnoozeMinutes(200)).toBe(SNOOZE_MIN_MAX);
    expect(clampSnoozeMinutes(181)).toBe(SNOOZE_MIN_MAX);
  });
  it("floors fractional values", () => {
    expect(clampSnoozeMinutes(10.9)).toBe(10);
  });
});

describe("parseSnoozeMinutesInput", () => {
  it("parses valid integers", () => {
    expect(parseSnoozeMinutesInput("45")).toBe(45);
  });
  it("returns null for empty or invalid", () => {
    expect(parseSnoozeMinutesInput("")).toBeNull();
    expect(parseSnoozeMinutesInput("  ")).toBeNull();
    expect(parseSnoozeMinutesInput("abc")).toBeNull();
  });
});
