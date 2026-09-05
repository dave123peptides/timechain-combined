"use client";

import { useRouter, useSearchParams } from "next/navigation";
import type { ProductSort } from "@/lib/api";
import { SORT_OPTIONS } from "./sort";
import styles from "./ShopSort.module.css";

// A <select> that navigates on change, preserving whatever search terms
// are already in the URL. Deliberately a client component with
// router.push rather than a <form action={...}> server action —
// MPA-submitted server actions 500 in Next 15.5 production builds (see
// app/age-gate/enter/route.ts for the note). `basePath` is the page the
// grid lives on: the homepage and /shop both render the full catalog
// (Core reference, 9/4) and each sorts in place.
export default function ShopSort({ value, basePath }: { value: ProductSort; basePath: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  return (
    <label className={styles.sortLabel}>
      <span className="sr-only">Sort products</span>
      <select
        className={styles.sortSelect}
        value={value}
        onChange={(event) => {
          const next = new URLSearchParams(searchParams.toString());
          next.set("sort", event.target.value);
          router.push(`${basePath}?${next.toString()}`);
        }}
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
