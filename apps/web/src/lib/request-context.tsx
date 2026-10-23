"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

// The order request list (David, 2026-10-22): the site's replacement for
// a cart. A line is a catalog variant and a quantity, nothing else; there
// is no price to carry. Kept in localStorage so a practice can build a
// list across visits, and resolved against the live catalog when shown
// (lib/useResolvedRequest.ts). Submitting it is /request.
const STORAGE_KEY = "tc_order_request";

export type RequestLine = { variantId: string; quantity: number };

type RequestContextValue = {
  lines: RequestLine[];
  hydrated: boolean;
  addItem: (variantId: string, quantity?: number) => void;
  removeItem: (variantId: string) => void;
  setQuantity: (variantId: string, quantity: number) => void;
  clear: () => void;
  totalQuantity: number;
  lineCount: number;
  // The slide-in panel (components/request/RequestDrawer.tsx).
  drawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
};

const RequestContext = createContext<RequestContextValue | null>(null);

function readStored(): RequestLine[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (line): line is RequestLine =>
        typeof line === "object" &&
        line !== null &&
        typeof (line as RequestLine).variantId === "string" &&
        typeof (line as RequestLine).quantity === "number" &&
        (line as RequestLine).quantity > 0
    );
  } catch {
    return [];
  }
}

export function RequestProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<RequestLine[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Empty on the server render, read from localStorage on mount: avoids a
  // hydration mismatch.
  useEffect(() => {
    setLines(readStored());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
    } catch {
      // Private mode or blocked storage: the list still works for this visit.
    }
  }, [lines, hydrated]);

  const addItem = useCallback((variantId: string, quantity = 1) => {
    setLines((current) => {
      const existing = current.find((line) => line.variantId === variantId);
      if (existing) {
        return current.map((line) =>
          line.variantId === variantId ? { ...line, quantity: line.quantity + quantity } : line
        );
      }
      return [...current, { variantId, quantity }];
    });
  }, []);

  const removeItem = useCallback((variantId: string) => {
    setLines((current) => current.filter((line) => line.variantId !== variantId));
  }, []);

  const setQuantity = useCallback((variantId: string, quantity: number) => {
    setLines((current) => {
      if (quantity <= 0) return current.filter((line) => line.variantId !== variantId);
      return current.map((line) => (line.variantId === variantId ? { ...line, quantity } : line));
    });
  }, []);

  const clear = useCallback(() => setLines([]), []);
  const openDrawer = useCallback(() => setDrawerOpen(true), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  const totalQuantity = useMemo(() => lines.reduce((sum, line) => sum + line.quantity, 0), [lines]);

  const value = useMemo(
    () => ({
      lines,
      hydrated,
      addItem,
      removeItem,
      setQuantity,
      clear,
      totalQuantity,
      lineCount: lines.length,
      drawerOpen,
      openDrawer,
      closeDrawer,
    }),
    [lines, hydrated, addItem, removeItem, setQuantity, clear, totalQuantity, drawerOpen, openDrawer, closeDrawer]
  );

  return <RequestContext.Provider value={value}>{children}</RequestContext.Provider>;
}

export function useOrderRequest(): RequestContextValue {
  const ctx = useContext(RequestContext);
  if (!ctx) throw new Error("useOrderRequest must be used within a RequestProvider");
  return ctx;
}
