"use client";

import { useEffect, useRef } from "react";

// Cal.com's own inline embed (their documented snippet, 2026-10-23): the
// script builds and sizes the iframe itself and takes the theme from
// config, which is the only reliable way to get the light calendar. A
// bare <iframe> of the booking page follows the visitor's system theme
// and ignores ?theme=; a bare <iframe> of the /embed route waits for
// this script's handshake and stays blank. `calLink` is the path after
// cal.com, e.g. "timechain/30min".
type CalApi = ((...args: unknown[]) => void) & { loaded?: boolean; ns?: Record<string, unknown>; q?: unknown[] };

declare global {
  interface Window {
    Cal?: CalApi;
  }
}

function loadCal(): CalApi {
  if (window.Cal) return window.Cal;
  const cal = ((...args: unknown[]) => {
    cal.q = cal.q ?? [];
    cal.q.push(args);
  }) as CalApi;
  cal.ns = {};
  window.Cal = cal;
  const script = document.createElement("script");
  script.src = "https://app.cal.com/embed/embed.js";
  script.async = true;
  document.head.appendChild(script);
  cal("init", { origin: "https://cal.com" });
  return cal;
}

export default function CalEmbed({ calLink }: { calLink: string }) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const cal = loadCal();
    // `config` becomes query parameters on the frame the script builds;
    // theme=light there is what the booking page actually honours (the
    // "ui" call alone loses to the account's dark preference, checked
    // 2026-10-23).
    cal("inline", { elementOrSelector: element, calLink, layout: "month_view", config: { theme: "light", layout: "month_view" } });
    cal("ui", { theme: "light", layout: "month_view", hideEventTypeDetails: false, cssVarsPerTheme: { light: { "cal-brand": "#0f766e" } } });
    return () => {
      element.innerHTML = "";
    };
  }, [calLink]);

  return <div ref={host} style={{ width: "100%", minHeight: "40rem", overflow: "auto" }} />;
}
