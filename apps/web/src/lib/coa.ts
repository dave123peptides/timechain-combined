import type { ProductCoa } from "@/lib/api";
import { formatStrength } from "@/lib/api";

// Shared by the PDP's Lab reports tab, the buy-box certificate pill and
// /coa. Every certificate control on the site opens the laboratory's own
// PDF in a new tab (David, 9/4 — the in-page viewer was too cramped);
// these helpers only decide WHICH certificate a control points at.

export type CoaCardGroup = {
  key: string;
  // Card heading and optional sub-line. On the PDP the heading is the
  // strength; on /coa it is the product name with the strength beneath.
  title: string;
  subtitle?: string;
  // /coa cards link back to the product page.
  productSlug?: string;
  // Newest first — the API already orders certificates this way.
  coas: ProductCoa[];
};

// Groups an already-ordered certificate list (strength ascending, newest
// first — see StorefrontProductDetail) by strength, preserving that order.
export function groupCoasByStrength(coas: ProductCoa[]): { strength: string | null; coas: ProductCoa[] }[] {
  const groups: { strength: string | null; coas: ProductCoa[] }[] = [];
  for (const coa of coas) {
    const last = groups[groups.length - 1];
    if (last && last.strength === coa.strength) {
      last.coas.push(coa);
    } else {
      groups.push({ strength: coa.strength, coas: [coa] });
    }
  }
  return groups;
}

export function strengthLabel(strength: string | null): string {
  return strength ? formatStrength(strength) : "Unspecified strength";
}

export function coaCardGroupsForProduct(productSlug: string, coas: ProductCoa[]): CoaCardGroup[] {
  return groupCoasByStrength(coas).map((group) => ({
    key: `${productSlug}:${group.strength ?? ""}`,
    title: strengthLabel(group.strength),
    coas: group.coas,
  }));
}

// The most recently certified document across every strength.
export function latestCoa(coas: ProductCoa[]): ProductCoa | null {
  return coas.reduce<ProductCoa | null>(
    (newest, coa) => (newest === null || coa.issued_on > newest.issued_on ? coa : newest),
    null
  );
}

// Newest certificate for one strength. Relies on the API's order
// (strength ascending, newest first within a strength), so the first
// match is the latest.
export function latestCoaForStrength(coas: ProductCoa[], strength: string | null): ProductCoa | null {
  if (!strength) return null;
  return coas.find((coa) => coa.strength === strength) ?? null;
}

// ISO "2026-07-17" -> "Jul 17, 2026". Parsed as calendar parts, not
// through Date's ISO parser, so the day never shifts with the viewer's
// timezone.
export function formatCoaDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function distinctLabs(coas: ProductCoa[]): string[] {
  return Array.from(new Set(coas.map((coa) => coa.lab)));
}
