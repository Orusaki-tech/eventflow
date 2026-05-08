import { useFlushPendingShare, useShareHandoff } from "../hooks/useShareHandoff";

export function ShareBootstrap({ navReady }: { navReady: boolean }) {
  useShareHandoff(navReady);
  useFlushPendingShare(navReady);
  return null;
}
