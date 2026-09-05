
export type IconName =
  | "flask"
  | "vial"
  | "pen"
  | "flag"
  | "document"
  | "layers"
  | "bitcoin"
  | "link"
  | "shield"
  | "record"
  | "gate"
  | "loop"
  | "map"
  | "chat"
  // Chrome glyphs (header, drawer, order page).
  | "search"
  | "bag"
  | "menu"
  | "close"
  | "mail"
  | "trash"
  | "chevronLeft"
  | "check"
  | "warning"
  | "copy"
  | "external";

// Minimal inline stroke icons for the homepage trust strip, hero badges
// and the site chrome (header, cart drawer, order page). Hand-rolled
// rather than pulling in an icon package:
// this web app deliberately has only react/next in dependencies, and
// twenty-ish 24px glyphs don't justify changing that. All paths are drawn on a 24x24 grid, stroke-only, and
// inherit currentColor so each section's CSS decides the color.
const PATHS: Record<IconName, React.ReactNode> = {
  flask: (
    <>
      <path d="M9 3h6" />
      <path d="M10 3v5.5L4.8 18a2 2 0 0 0 1.8 3h10.8a2 2 0 0 0 1.8-3L14 8.5V3" />
      <path d="M7.5 14h9" />
    </>
  ),
  vial: (
    <>
      <path d="M8 2h8" />
      <path d="M9 2v3h6V2" />
      <rect x="7" y="5" width="10" height="17" rx="2" />
      <path d="M7 12h10" />
    </>
  ),
  // Auto-injector pen: body, cap band, dose window.
  pen: (
    <>
      <rect x="9" y="2" width="6" height="20" rx="2" />
      <path d="M9 7h6" />
      <path d="M9 17h6" />
      <path d="M11 11h2v3h-2z" />
    </>
  ),
  flag: (
    <>
      <path d="M5 21V4" />
      <path d="M5 4h13l-2.5 4L18 12H5" />
    </>
  ),
  document: (
    <>
      <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z" />
      <path d="M14 2v5h5" />
      <path d="M9 13h6M9 17h6" />
    </>
  ),
  layers: (
    <>
      <path d="m12 2 9 5-9 5-9-5z" />
      <path d="m3 12 9 5 9-5" />
      <path d="m3 17 9 5 9-5" />
    </>
  ),
  bitcoin: (
    <>
      <path d="M8 4h6a3 3 0 0 1 0 6H8zM8 10h7a3 3 0 0 1 0 6H8z" />
      <path d="M8 4v12" />
      <path d="M10 2v2M13 2v2M10 16v2M13 16v2" />
    </>
  ),
  link: (
    <>
      <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" />
      <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" />
    </>
  ),
  shield: (
    <>
      <path d="M12 2 4 5.5V11c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5.5z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  record: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </>
  ),
  gate: (
    <>
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </>
  ),
  loop: (
    <>
      <path d="M21 12a9 9 0 1 1-2.6-6.4" />
      <path d="M21 3v5h-5" />
    </>
  ),
  map: (
    <>
      <path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0z" />
      <circle cx="12" cy="10" r="3" />
    </>
  ),
  chat: (
    <>
      <path d="M21 12a8 8 0 0 1-8 8H4l2.3-2.9A8 8 0 1 1 21 12z" />
      <path d="M8 10h8M8 14h5" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.8-3.8" />
    </>
  ),
  bag: (
    <>
      <path d="M6 8h12l1 13H5z" />
      <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    </>
  ),
  menu: (
    <>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </>
  ),
  close: (
    <>
      <path d="M6 6l12 12M18 6 6 18" />
    </>
  ),
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </>
  ),
  trash: (
    <>
      <path d="M4 7h16" />
      <path d="M10 11v6M14 11v6" />
      <path d="M6 7l1 13h10l1-13" />
      <path d="M9 7V4h6v3" />
    </>
  ),
  chevronLeft: (
    <>
      <path d="m15 5-7 7 7 7" />
    </>
  ),
  check: (
    <>
      <path d="m5 12 5 5L20 7" />
    </>
  ),
  warning: (
    <>
      <path d="M12 3 2.5 20h19z" />
      <path d="M12 9v5M12 17.5v.5" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </>
  ),
  external: (
    <>
      <path d="M14 4h6v6M20 4l-9 9" />
      <path d="M20 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h4" />
    </>
  ),
};

export default function SectionIcon({ name, size = 22 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}
