import { carouselPickMetrics, scrollXToActiveIndex } from "../carouselSlidePickLayout";

describe("carouselPickMetrics", () => {
  it("caps card width at 340 when screen is wide", () => {
    const m = carouselPickMetrics(430);
    expect(m.cardWidth).toBe(340);
    expect(m.stride).toBe(354);
  });

  it("narrows card when screen is small", () => {
    const m = carouselPickMetrics(320);
    expect(m.cardWidth).toBe(280);
    expect(m.stride).toBe(294);
  });
});

describe("scrollXToActiveIndex", () => {
  const stride = 354;

  it("returns 0 for single slide", () => {
    expect(scrollXToActiveIndex(0, 1, stride)).toBe(0);
    expect(scrollXToActiveIndex(900, 1, stride)).toBe(0);
  });

  it("maps scroll offset to nearest slide index", () => {
    expect(scrollXToActiveIndex(0, 5, stride)).toBe(0);
    expect(scrollXToActiveIndex(stride * 2 - 20, 5, stride)).toBe(2);
    expect(scrollXToActiveIndex(stride * 4 + 100, 5, stride)).toBe(4);
  });

  it("clamps to valid range", () => {
    expect(scrollXToActiveIndex(-stride, 3, stride)).toBe(0);
    expect(scrollXToActiveIndex(stride * 99, 3, stride)).toBe(2);
  });
});
