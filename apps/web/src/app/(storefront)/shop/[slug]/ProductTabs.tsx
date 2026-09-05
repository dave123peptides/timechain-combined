"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import styles from "./sections.module.css";

export type ProductTab = {
  // Also the URL hash that opens this tab (#lab-reports), so the buy box
  // and external links can land on a specific tab.
  id: string;
  label: string;
  badge?: number;
  content: ReactNode;
};

export const LAB_REPORTS_TAB_ID = "lab-reports";

// The About / Lab reports / Specifications / Questions block under the buy
// box (the Real Peptides PDP pattern). Every panel stays in the DOM and is
// toggled with `hidden`, so the content is server-rendered and crawlable
// regardless of which tab is showing; only the selection is client state.
//
// Hash handling: each tab BUTTON carries the tab's id, so a #lab-reports
// URL is a plain anchor — the browser itself scrolls to the tab strip on
// load (before hydration, even) and on every hash link, and the only job
// left to script is switching the panel. scroll-margin-top on the button
// keeps it clear of the sticky header.
//
// Two scroll behaviours, on purpose. On mount the re-scroll is "instant":
// the browser's own fragment jump happened before hydration, and this
// corrects for anything that shifted the layout since (fonts, the panel
// switch) without an animation that could be cut short. Note "auto" would
// NOT do that — it defers to the CSS scroll-behavior, which globals.css
// sets to smooth. On hashchange (a link click, including a re-click on the
// same hash — see LabReportLink) it is "auto" so the scroll animates like
// every other in-page link and still honours prefers-reduced-motion.
export default function ProductTabs({ tabs }: { tabs: ProductTab[] }) {
  const sectionRef = useRef<HTMLElement>(null);
  const buttonRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [activeId, setActiveId] = useState(tabs[0]?.id ?? "");
  const tabIds = tabs.map((tab) => tab.id).join("|");

  useEffect(() => {
    const ids = tabIds.split("|");
    const applyHash = (behavior: ScrollBehavior) => {
      const id = window.location.hash.slice(1);
      const index = ids.indexOf(id);
      if (index === -1) return;
      setActiveId(id);
      buttonRefs.current[index]?.scrollIntoView({ block: "start", behavior });
    };
    applyHash("instant");
    const onHashChange = () => applyHash("auto");
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [tabIds]);

  if (tabs.length === 0) return null;

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = tabs.findIndex((tab) => tab.id === activeId);
    let next: number | null = null;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    if (next === null) return;
    event.preventDefault();
    setActiveId(tabs[next].id);
    buttonRefs.current[next]?.focus();
  };

  return (
    <section ref={sectionRef} className={styles.tabsSection} id="product-information">
      <div role="tablist" aria-label="Product information" className={styles.tabList} onKeyDown={onKeyDown}>
        {tabs.map((tab, index) => {
          const active = tab.id === activeId;
          return (
            <button
              key={tab.id}
              ref={(el) => {
                buttonRefs.current[index] = el;
              }}
              type="button"
              role="tab"
              id={tab.id}
              aria-selected={active}
              aria-controls={`${tab.id}-panel`}
              tabIndex={active ? 0 : -1}
              className={`${styles.tab} ${active ? styles.tabActive : ""}`}
              onClick={() => setActiveId(tab.id)}
            >
              {tab.label}
              {tab.badge !== undefined && tab.badge > 0 && <span className={styles.tabBadge}>{tab.badge}</span>}
            </button>
          );
        })}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`${tab.id}-panel`}
          aria-labelledby={tab.id}
          hidden={tab.id !== activeId}
          className={styles.tabPanel}
        >
          {tab.content}
        </div>
      ))}
    </section>
  );
}
