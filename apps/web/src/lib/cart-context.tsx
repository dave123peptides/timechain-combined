"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "timechain_cart";

export type CartLine = { variantId: string; quantity: number };

type CartContextValue = {
  lines: CartLine[];
  hydrated: boolean;
  addItem: (variantId: string, quantity?: number) => void;
  removeItem: (variantId: string) => void;
  setQuantity: (variantId: string, quantity: number) => void;
  clear: () => void;
  totalQuantity: number;
  // The slide-in drawer (components/CartDrawer.tsx). Lives here rather
  // than in a second provider because everything that opens it already
  // holds this context: the header's cart button and every Add to Cart.
  drawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
};

const CartContext = createContext<CartContextValue | null>(null);

function readStoredCart(): CartLine[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (line): line is CartLine =>
        typeof line === "object" &&
        line !== null &&
        typeof (line as CartLine).variantId === "string" &&
        typeof (line as CartLine).quantity === "number"
    );
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Cart starts empty on the server render and hydrates from
  // localStorage on mount — avoids a hydration mismatch between server
  // and client markup.
  useEffect(() => {
    setLines(readStoredCart());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
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
      drawerOpen,
      openDrawer,
      closeDrawer,
    }),
    [lines, hydrated, addItem, removeItem, setQuantity, clear, totalQuantity, drawerOpen, openDrawer, closeDrawer]
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within a CartProvider");
  return ctx;
}
