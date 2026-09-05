"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { formatMoney, listProducts, type ProductSummary } from "@/lib/api";
import SectionIcon from "@/components/SectionIcon";
import styles from "./HeaderSearch.module.css";

const MIN_QUERY_LENGTH = 2;
const MAX_RESULTS = 6;
const DEBOUNCE_MS = 250;

// Results are whatever the query matches on name/slug/description. There
// is deliberately no curated or default suggestion list here: promoting
// specific products from the header is exactly the consumer-demand
// signalling the GLP-class compounds must not receive. Direct lookup by
// name still works for anyone who already knows what they're after —
// that part is intentional.
export default function HeaderSearch() {
  const router = useRouter();
  const listId = useId();
  const [term, setTerm] = useState("");
  const [results, setResults] = useState<ProductSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const blurTimer = useRef<number | undefined>(undefined);

  const trimmed = term.trim();

  useEffect(() => {
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setLoading(false);
      return;
    }
    // apiFetch takes no AbortSignal, so instead of inventing one this uses
    // the same cancelled-flag cleanup the cart page already uses to stop
    // an out-of-order response overwriting a newer one.
    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(() => {
      listProducts({ q: trimmed })
        .then((found) => {
          if (cancelled) return;
          setResults(found.slice(0, MAX_RESULTS));
          setOpen(true);
        })
        // A failing search must never take the header down with it.
        .catch(() => {
          if (!cancelled) setResults([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [trimmed]);

  useEffect(() => () => window.clearTimeout(blurTimer.current), []);

  const close = () => {
    setOpen(false);
    setMobileOpen(false);
  };

  const submit = () => {
    if (!trimmed) return;
    close();
    router.push(`/shop?q=${encodeURIComponent(trimmed)}`);
  };

  const showResults = open && trimmed.length >= MIN_QUERY_LENGTH;

  return (
    <div className={`${styles.wrap} ${mobileOpen ? styles.wrapOpen : ""}`}>
      <button
        type="button"
        className={styles.toggle}
        aria-label={mobileOpen ? "Close search" : "Search"}
        aria-expanded={mobileOpen}
        onClick={() => {
          const next = !mobileOpen;
          setMobileOpen(next);
          if (next) window.setTimeout(() => inputRef.current?.focus(), 0);
        }}
      >
        <SectionIcon name={mobileOpen ? "close" : "search"} size={22} />
      </button>

      <div className={styles.field}>
        <div className={styles.pill}>
          <input
          ref={inputRef}
          type="search"
          className={styles.input}
          placeholder="Search products"
          aria-label="Search products"
          role="combobox"
          aria-expanded={showResults}
          aria-controls={listId}
          aria-autocomplete="list"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          onFocus={() => setOpen(true)}
          // Deferred: a click on a result fires blur first, and closing
          // immediately would unmount the row before its click lands.
          onBlur={() => {
            blurTimer.current = window.setTimeout(() => setOpen(false), 120);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submit();
            }
            if (event.key === "Escape") {
              close();
              inputRef.current?.blur();
            }
          }}
          />
          {/* The Core-reference pill ends in a solid accent search button.
              Same action as Enter; mousedown is swallowed so the input's
              deferred blur never closes the panel before the click lands. */}
          <button
            type="button"
            className={styles.submit}
            aria-label="Search"
            onClick={submit}
            onMouseDown={(event) => event.preventDefault()}
          >
            <SectionIcon name="search" size={18} />
          </button>
        </div>

        {showResults && (
          <div className={styles.panel}>
            <ul className={styles.list} id={listId} role="listbox" aria-label="Search results">
              {results.map((product) => (
                <li key={product.slug} role="option" aria-selected="false">
                  <a
                    href={`/shop/${product.slug}`}
                    className={styles.result}
                    onClick={close}
                    // Keeps focus on the input so the deferred blur close
                    // never races the navigation.
                    onMouseDown={(event) => event.preventDefault()}
                  >
                    <span className={styles.resultName}>{product.name}</span>
                    <span className={styles.resultPrice}>{formatMoney(product.starting_price_cents)}</span>
                  </a>
                </li>
              ))}
              {results.length === 0 && !loading && <li className={styles.noResults}>No products match “{trimmed}”.</li>}
              {results.length > 0 && (
                <li>
                  <a
                    href={`/shop?q=${encodeURIComponent(trimmed)}`}
                    className={styles.seeAll}
                    onClick={close}
                    onMouseDown={(event) => event.preventDefault()}
                  >
                    See all results
                  </a>
                </li>
              )}
            </ul>
          </div>
        )}

        <span className="sr-only" aria-live="polite">
          {showResults && !loading
            ? `${results.length} ${results.length === 1 ? "product" : "products"} found`
            : ""}
        </span>
      </div>
    </div>
  );
}
