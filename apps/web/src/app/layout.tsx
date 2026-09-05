import type { Metadata } from "next";
import { Inter, Inter_Tight } from "next/font/google";
import { CartProvider } from "@/lib/cart-context";
import "./globals.css";

// Bold grotesque sans for headlines — David's committed display register
// (restored 8/31 after a brief Fraunces serif experiment he declined; see
// globals.css's theme note).
const displayFont = Inter_Tight({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
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
  title: "TCP",
  description: "Research compounds sourced and handled to exacting standards, for laboratory and research use.",
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
