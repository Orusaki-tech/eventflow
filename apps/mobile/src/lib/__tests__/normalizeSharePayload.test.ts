import {
  extractUrls,
  normalizeSharePayload,
  pickPrimaryUrl,
} from "../normalizeSharePayload";

describe("extractUrls", () => {
  it("dedupes and preserves order", () => {
    const t = "see https://a.com/x and https://b.com also https://a.com/x";
    expect(extractUrls(t)).toEqual(["https://a.com/x", "https://b.com"]);
  });

  it("returns empty when no urls", () => {
    expect(extractUrls("no links here")).toEqual([]);
  });
});

describe("pickPrimaryUrl", () => {
  it("prefers tiktok over generic shortener", () => {
    const urls = ["https://t.co/abc", "https://www.tiktok.com/@x/video/1"];
    expect(pickPrimaryUrl(urls)).toBe("https://www.tiktok.com/@x/video/1");
  });
});

describe("normalizeSharePayload", () => {
  it("uses url mode when a URL exists", () => {
    const r = normalizeSharePayload("Check this https://example.com/event cool");
    expect(r.mode).toBe("url");
    expect(r.url).toBe("https://example.com/event");
  });

  it("uses text mode when no URL", () => {
    const r = normalizeSharePayload("Jazz night Friday 8pm at Blue Note");
    expect(r.mode).toBe("text");
    expect(r.text).toBe("Jazz night Friday 8pm at Blue Note");
  });
});
