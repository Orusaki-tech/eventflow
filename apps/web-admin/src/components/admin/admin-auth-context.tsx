"use client";

import { createContext, useContext } from "react";

export type AdminAuthContextValue = {
  token: string;
};

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null);

export function AdminAuthProvider({
  token,
  children,
}: {
  token: string;
  children: React.ReactNode;
}) {
  return <AdminAuthContext.Provider value={{ token }}>{children}</AdminAuthContext.Provider>;
}

export function useAdminAuth(): AdminAuthContextValue {
  const v = useContext(AdminAuthContext);
  if (!v) throw new Error("useAdminAuth must be used inside AdminAuthProvider");
  return v;
}
