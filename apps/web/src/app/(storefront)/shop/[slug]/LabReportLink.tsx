"use client";

import type { ReactNode } from "react";
import { LAB_REPORTS_TAB_ID } from "./ProductTabs";

// Jumps to the Lab reports tab. A plain #hash link is enough on the first
// click, but a second click with the hash already set fires no hashchange
// and ProductTabs would not re-scroll — so the event is dispatched by hand.
export default function LabReportLink({ className, children }: { className?: string; children: ReactNode }) {
  const hash = `#${LAB_REPORTS_TAB_ID}`;
  return (
    <a
      href={hash}
      className={className}
      onClick={(event) => {
        if (window.location.hash !== hash) return;
        event.preventDefault();
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      }}
    >
      {children}
    </a>
  );
}
