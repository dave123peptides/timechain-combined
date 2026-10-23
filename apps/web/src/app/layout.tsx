import type { Metadata } from "next";
import { Instrument_Serif, Inter, Inter_Tight } from "next/font/google";
import { CartProvider } from "@/lib/cart-context";
import { RequestProvider } from "@/lib/request-context";
import "./globals.css";

// B2B redesign (David, 2026-10-22): a serif display face with an italic
// for the accent word, Inter for body copy, Inter Tight for the uppercase
// labels, nav and buttons. See globals.css for the tokens.
const displayFont = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-display-serif",
  display: "swap",
});

const labelFont = Inter_Tight({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-label-sans",
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
    <html lang="en" className={`${displayFont.variable} ${labelFont.variable} ${bodyFont.variable}`}>
      <body>
        <CartProvider>
          <RequestProvider>{children}</RequestProvider>
        </CartProvider>
      </body>
    </html>
  );
}
