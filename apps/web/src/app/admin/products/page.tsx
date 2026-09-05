"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AdminNav from "../AdminNav";
import styles from "./admin.module.css";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ACTOR_STORAGE_KEY = "timechain_admin_actor";

type AdminProductRow = {
  variant_id: string;
  timechain_product: string;
  format: string;
  strength: string | null;
  wholesale_cost_cents: number | null;
  retail_price_cents: number;
  sellable: boolean;
  supplier_product_id: number | null;
  supplier_sku: string | null;
  supplier_name: string | null;
  confidence: string | null;
  mapping_status: string;
};

type SupplierProductOption = {
  supplier_product_id: number;
  supplier_sku: string;
  supplier_name: string;
};

function formatMoney(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

function MappingStatusPill({ status }: { status: string }) {
  const classMap: Record<string, string> = {
    MAPPED: styles.pillMapped,
    UNMAPPED: styles.pillUnmapped,
    MISSING: styles.pillMissing,
    CHANGED: styles.pillChanged,
  };
  return <span className={`${styles.pill} ${classMap[status] ?? styles.pillNeutral}`}>{status}</span>;
}

function ConfidencePill({ confidence }: { confidence: string | null }) {
  if (!confidence) return <span className={styles.mono}>—</span>;
  const classMap: Record<string, string> = {
    EXACT: styles.pillExact,
    LIKELY: styles.pillLikely,
    AMBIGUOUS: styles.pillAmbiguous,
    NO_MATCH: styles.pillNoMatch,
    MANUAL: styles.pillManual,
  };
  return <span className={`${styles.pill} ${classMap[confidence] ?? styles.pillNeutral}`}>{confidence}</span>;
}

async function postAction<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export default function AdminProductsPage() {
  const [rows, setRows] = useState<AdminProductRow[] | null>(null);
  const [supplierOptions, setSupplierOptions] = useState<SupplierProductOption[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actor, setActor] = useState("");
  const [pendingVariantId, setPendingVariantId] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [changingVariantId, setChangingVariantId] = useState<string | null>(null);
  const [changeSelection, setChangeSelection] = useState<string>("");

  useEffect(() => {
    const stored = window.localStorage.getItem(ACTOR_STORAGE_KEY);
    if (stored) setActor(stored);
  }, []);

  const loadData = useCallback(() => {
    setLoadError(null);
    Promise.all([
      fetch(`${API_BASE_URL}/admin/products`).then((r) => {
        if (!r.ok) throw new Error(`Failed to load products (${r.status})`);
        return r.json() as Promise<AdminProductRow[]>;
      }),
      fetch(`${API_BASE_URL}/admin/supplier-products`).then((r) => {
        if (!r.ok) throw new Error(`Failed to load supplier products (${r.status})`);
        return r.json() as Promise<SupplierProductOption[]>;
      }),
    ])
      .then(([products, suppliers]) => {
        setRows(products);
        setSupplierOptions(suppliers);
      })
      .catch((err: Error) => setLoadError(err.message));
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleActorChange = (value: string) => {
    setActor(value);
    window.localStorage.setItem(ACTOR_STORAGE_KEY, value);
  };

  const updateRow = (updated: AdminProductRow | null, variantId: string) => {
    setRows((current) => {
      if (!current) return current;
      if (updated === null) return current;
      return current.map((row) => (row.variant_id === variantId ? updated : row));
    });
  };

  const runAction = async (variantId: string, path: string, body: unknown) => {
    if (!actor.trim()) {
      setRowErrors((prev) => ({ ...prev, [variantId]: "Enter your name above first." }));
      return;
    }
    setPendingVariantId(variantId);
    setRowErrors((prev) => ({ ...prev, [variantId]: "" }));
    try {
      const updated = await postAction<AdminProductRow | null>(path, { ...(body as object), actor });
      updateRow(updated, variantId);
      setChangingVariantId(null);
    } catch (err) {
      setRowErrors((prev) => ({ ...prev, [variantId]: (err as Error).message }));
    } finally {
      setPendingVariantId(null);
    }
  };

  const supplierOptionsSorted = useMemo(
    () => [...supplierOptions].sort((a, b) => a.supplier_name.localeCompare(b.supplier_name)),
    [supplierOptions]
  );

  return (
    <main className={styles.page}>
      <div className={styles.header}>
        <AdminNav current="products" />
        <div>
          <h1>Product &amp; Supplier Mappings</h1>
          <p className={styles.subtitle}>
            Every TimeChain variant, its supplier mapping, and sellable status. Every mapping and sellable change is
            recorded in the audit log.
          </p>
        </div>
        <label className={styles.actorField}>
          Your name
          <input
            type="text"
            placeholder="e.g. dave"
            value={actor}
            onChange={(e) => handleActorChange(e.target.value)}
          />
        </label>
      </div>

      {loadError && <p className={styles.rowError}>{loadError}</p>}
      {rows === null && !loadError && <p className={styles.loading}>Loading…</p>}

      {rows !== null && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>TimeChain product</th>
                <th>Format</th>
                <th>Strength</th>
                <th>Wholesale</th>
                <th>Retail</th>
                <th>Sellable</th>
                <th>Supplier ID</th>
                <th>Supplier SKU</th>
                <th>Supplier name</th>
                <th>Confidence</th>
                <th>Mapping status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isPending = pendingVariantId === row.variant_id;
                const isChanging = changingVariantId === row.variant_id;
                const canApprove = row.mapping_status !== "MAPPED" && row.supplier_product_id !== null;

                return (
                  <tr key={row.variant_id}>
                    <td className={styles.wrap}>{row.timechain_product}</td>
                    <td>{row.format}</td>
                    <td className={styles.mono}>{row.strength ?? "—"}</td>
                    <td className={styles.mono}>{formatMoney(row.wholesale_cost_cents)}</td>
                    <td className={styles.mono}>{formatMoney(row.retail_price_cents)}</td>
                    <td className={row.sellable ? styles.sellableYes : styles.sellableNo}>
                      {row.sellable ? "Yes" : "No"}
                    </td>
                    <td className={styles.mono}>{row.supplier_product_id ?? "—"}</td>
                    <td className={styles.mono}>{row.supplier_sku ?? "—"}</td>
                    <td className={styles.wrap}>{row.supplier_name ?? "—"}</td>
                    <td>
                      <ConfidencePill confidence={row.confidence} />
                    </td>
                    <td>
                      <MappingStatusPill status={row.mapping_status} />
                    </td>
                    <td>
                      <div className={styles.actions}>
                        {canApprove && (
                          <button
                            disabled={isPending}
                            onClick={() =>
                              runAction(row.variant_id, `/admin/products/${row.variant_id}/approve`, {
                                supplier_product_id: row.supplier_product_id,
                              })
                            }
                          >
                            Approve
                          </button>
                        )}
                        <button
                          disabled={isPending}
                          onClick={() => {
                            setChangingVariantId(isChanging ? null : row.variant_id);
                            setChangeSelection(row.supplier_product_id ? String(row.supplier_product_id) : "");
                          }}
                        >
                          Change
                        </button>
                        {row.mapping_status === "MAPPED" && (
                          <button
                            disabled={isPending}
                            onClick={() => runAction(row.variant_id, `/admin/products/${row.variant_id}/unmap`, {})}
                          >
                            Unmap
                          </button>
                        )}
                        {row.sellable ? (
                          <button
                            disabled={isPending}
                            onClick={() =>
                              runAction(row.variant_id, `/admin/products/${row.variant_id}/disable`, {})
                            }
                          >
                            Disable
                          </button>
                        ) : (
                          <button
                            disabled={isPending}
                            onClick={() => runAction(row.variant_id, `/admin/products/${row.variant_id}/enable`, {})}
                          >
                            Enable
                          </button>
                        )}
                      </div>

                      {isChanging && (
                        <div className={styles.changeRow}>
                          <select value={changeSelection} onChange={(e) => setChangeSelection(e.target.value)}>
                            <option value="">Select supplier product…</option>
                            {supplierOptionsSorted.map((option) => (
                              <option key={option.supplier_product_id} value={option.supplier_product_id}>
                                {option.supplier_sku} — {option.supplier_name}
                              </option>
                            ))}
                          </select>
                          <button
                            disabled={!changeSelection || isPending}
                            onClick={() =>
                              runAction(row.variant_id, `/admin/products/${row.variant_id}/change`, {
                                supplier_product_id: Number(changeSelection),
                              })
                            }
                          >
                            Confirm
                          </button>
                        </div>
                      )}

                      {rowErrors[row.variant_id] && <p className={styles.rowError}>{rowErrors[row.variant_id]}</p>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
