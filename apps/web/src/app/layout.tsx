import type { Metadata } from "next";
import { Inter, Inter_Tight } from "next/font/google";
import { CartProvider } from "@/lib/cart-context";
import "./globals.css";

// Modern, clean, minimal (David, 2026-10-22): one family. Inter Tight at
// tight tracking for headings, labels, nav and buttons; Inter for body.
const displayFont = Inter_Tight({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display-sans",
  display: "swap",
});

const bodyFont = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "TimeChain Peptides",
    template: "%s | TimeChain Peptides",
  },
  description:
    "Research peptides in pre-filled auto-injector pens and lyophilized vials, supplied to research organizations and medical practices. For laboratory research use only.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${displayFont.variable} ${bodyFont.variable}`}>
      <body>
        <CartProvider>{children}</CartProvider>
      </body>
    </html>
  );
}
