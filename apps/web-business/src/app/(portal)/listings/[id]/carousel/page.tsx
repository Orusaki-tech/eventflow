"use client";

import { IconPhoto, IconVideo } from "@tabler/icons-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { getListingCarousel, type ListingCarouselResponse } from "@/lib/eventflow-api";

export default function ListingCarouselPage() {
  const { token } = usePortalAuth();
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : "";
  const [carousel, setCarousel] = useState<ListingCarouselResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!id) return;
      try {
        const c = await getListingCarousel(token, id);
        if (!cancelled) setCarousel(c);
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [token, id]);

  if (!id) return <p className="portal-error">Invalid listing id.</p>;
  if (err) return <p className="portal-error">{err}</p>;
  if (!carousel) return <p className="portal-status">Loading carousel…</p>;

  const slideIcon = (kind: string) => {
    if (kind === "video") return <IconVideo size={14} stroke={1.5} />;
    return <IconPhoto size={14} stroke={1.5} />;
  };

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Carousel</div>
          <span className="portal-tag portal-tag-get">GET</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 14px", fontSize: 12, color: "var(--portal-muted)" }}>
            {carousel.slides.length} slide{carousel.slides.length !== 1 ? "s" : ""} — poster
            followed by approved promo videos.
          </p>
          {carousel.slides.length === 0 ? (
            <div className="portal-empty">
              <p>No carousel slides. Add a poster image and promo videos.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {carousel.slides.map((slide, i) => (
                <div
                  key={`${slide.kind}-${i}`}
                  className="portal-info-box"
                  style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    {slideIcon(slide.kind)}
                    <span style={{ fontWeight: 600, fontSize: 12, textTransform: "capitalize" }}>
                      {slide.kind}
                    </span>
                    <span className="portal-tag portal-tag-info" style={{ marginLeft: "auto" }}>
                      Slide {i + 1}
                    </span>
                  </div>
                  {slide.title && (
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{slide.title}</div>
                  )}
                  {slide.subtitle && (
                    <div style={{ fontSize: 11, color: "var(--portal-muted)" }}>{slide.subtitle}</div>
                  )}
                  {slide.kind === "video" && slide.uri ? (
                    <video
                      src={slide.uri}
                      controls
                      poster={slide.image_uri ?? undefined}
                      style={{
                        maxWidth: "100%",
                        maxHeight: 240,
                        borderRadius: 6,
                        background: "#000",
                      }}
                    />
                  ) : slide.image_uri ? (
                    <img
                      src={slide.image_uri}
                      alt={slide.title ?? "Slide"}
                      style={{
                        maxWidth: "100%",
                        maxHeight: 200,
                        borderRadius: 6,
                        objectFit: "cover",
                      }}
                    />
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <Link href={`/listings/${id}`} className="portal-link-back">← Listing detail</Link>
    </>
  );
}
