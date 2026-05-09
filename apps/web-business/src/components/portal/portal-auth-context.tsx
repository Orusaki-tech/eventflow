"use client";

import { createContext, useContext } from "react";

export type PortalAuthContextValue = {
  token: string;
};

const PortalAuthContext = createContext<PortalAuthContextValue | null>(null);

export function PortalAuthProvider({
  token,
  children,
}: {
  token: string;
  children: React.ReactNode;
}) {
  return <PortalAuthContext.Provider value={{ token }}>{children}</PortalAuthContext.Provider>;
}

export function usePortalAuth(): PortalAuthContextValue {
  const v = useContext(PortalAuthContext);
  if (!v) throw new Error("usePortalAuth must be used inside PortalAuthProvider");
  return v;
}
