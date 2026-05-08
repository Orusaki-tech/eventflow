export const CAROUSEL_SIDE_PAD = 20;
export const CAROUSEL_CARD_GAP = 14;

export type CarouselPickMetrics = {
  cardWidth: number;
  cardHeight: number;
  stride: number;
};

/** Card geometry for the Instagram slide picker — pass `screenWidth` from `Dimensions.get("window").width`. */
export function carouselPickMetrics(screenWidth: number): CarouselPickMetrics {
  const cardWidth = Math.min(340, screenWidth - CAROUSEL_SIDE_PAD * 2);
  const stride = cardWidth + CAROUSEL_CARD_GAP;
  return {
    cardWidth,
    cardHeight: Math.round(cardWidth * 1.22),
    stride,
  };
}

/** Maps horizontal scroll offset to active slide — `stride` must match `snapToOffsets` / `getItemLayout`. */
export function scrollXToActiveIndex(x: number, slideCount: number, stride: number): number {
  if (slideCount <= 1) return 0;
  const idx = Math.round(x / stride);
  return Math.min(Math.max(0, idx), slideCount - 1);
}
