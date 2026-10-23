"use client";

import { useCallback, useEffect, useState } from "react";
import AdminNav from "../AdminNav";
import styles from "../products/admin.module.css";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CREDS_STORAGE_KEY = "tcp_admin_creds";

type RequestItem = {
  product_name: string;
  variant_name: string;
  sku: string;
  form_label: string;
  strength: string | null;
  quantity: number;
};

type RequestRow = {
  id: string;
  reference: string;
  status: string;
  created_at: string;
  contact_name: string;
  organization: string;
  role: string | null;
  email: string;
  phone: string | null;
  region: string | null;
  notes: string | null;
  items: RequestItem[];
  source_path: string | null;
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

// Every order request the storefront has sent (B2B redesign,
// 2026-10-22), newest first, with the lines and notes under each row.
// Same basic-auth pattern as the orders screen: credentials are asked
// for once and kept in sessionStorage for the tab.
export default function AdminRequestsPage() {
  const [creds, setCreds] = useState<{ user: string; password: string } | null>(null);
  const [credUser, setCredUser] = useState("");
  const [credPassword, setCredPassword] = useState("");
  const [rows, setRows] = useState<RequestRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.sessionStorage.getItem(CREDS_STORAGE_KEY);
    if (stored) {
      try {
        setCreds(JSON.parse(stored));
      } catch {
        window.sessionStorage.removeItem(CREDS_STORAGE_KEY);
      }
    }
  }, []);

  const load = useCallback(() => {
    if (!creds) return;
    setLoadError(null);
    fetch(`${API_BASE_URL}/admin/order-requests`, {
      headers: { Authorization: `Basic ${btoa(`${creds.user}:${creds.password}`)}` },
    })
      .then((r) => {
        if (r.status === 401) throw new Error("Those admin credentials were rejected.");
        if (!r.ok) throw new Error(`Failed to load requests (${r.status})`);
        return r.json() as Promise<RequestRow[]>;
      })
      .then(setRows)
      .catch((err: Error) => {
        setRows(null);
        setLoadError(err.message);
      });
  }, [creds]);

  useEffect(() => {
    load();
  }, [load]);

  if (!creds) {
    return (
      <main className={styles.page}>
        <div className={styles.wrap}>
          <AdminNav current="requests" />
          <h1>Order requests</h1>
          <form
            className={styles.credsForm}
            onSubmit={(event) => {
              event.preventDefault();
              const next = { user: credUser, password: credPassword };
              window.sessionStorage.setItem(CREDS_STORAGE_KEY, JSON.stringify(next));
              setCreds(next);
            }}
          >
            <label>
              Admin user
              <input value={credUser} onChange={(e) => setCredUser(e.target.value)} autoComplete="username" />
            </label>
            <label>
              Password
              <input type="password" value={credPassword} onChange={(e) => setCredPassword(e.target.value)} autoComplete="current-password" />
            </label>
            <button type="submit" className={styles.button}>
              Open
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <div className={styles.wrap}>
        <AdminNav current="requests" />
        <div className={styles.header}>
          <div>
            <h1>Order requests</h1>
            <p className={styles.subtitle}>
              Every request sent from the storefront, newest first. The same payload went to the CRM webhook if one is
              configured.
            </p>
          </div>
          <button type="button" className={styles.buttonGhost} onClick={load}>
            Refresh
          </button>
        </div>

        {loadError && <p className={styles.error}>{loadError}</p>}
        {rows === null && !loadError && <p className={styles.loading}>Loading…</p>}
        {rows && rows.length === 0 && <p className={styles.empty}>No requests yet.</p>}

        {rows && rows.length > 0 && (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Received</th>
                  <th>Organization</th>
                  <th>Contact</th>
                  <th>Lines</th>
                  <th>Units</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const units = row.items.reduce((sum, item) => sum + item.quantity, 0);
                  const open = openId === row.id;
                  return (
                    <RowGroup key={row.id} open={open}>
                      <tr>
                        <td className={styles.mono}>{row.reference}</td>
                        <td>{when(row.created_at)}</td>
                        <td>
                          {row.organization}
                          {row.role && <div className={styles.muted}>{row.role}</div>}
                        </td>
                        <td>
                          {row.contact_name}
                          <div className={styles.muted}>
                            <a href={`mailto:${row.email}`}>{row.email}</a>
                            {row.phone ? ` · ${row.phone}` : ""}
                            {row.region ? ` · ${row.region}` : ""}
                          </div>
                        </td>
                        <td>{row.items.length}</td>
                        <td>{units}</td>
                        <td>
                          <button type="button" className={styles.buttonGhost} onClick={() => setOpenId(open ? null : row.id)}>
                            {open ? "Hide" : "Lines"}
                          </button>
                        </td>
                      </tr>
                      {open && (
                        <tr>
                          <td colSpan={7}>
                            <div className={styles.detailBlock}>
                              <table className={styles.innerTable}>
                                <thead>
                                  <tr>
                                    <th>Product</th>
                                    <th>Format</th>
                                    <th>Strength</th>
                                    <th>SKU</th>
                                    <th>Quantity</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {row.items.map((item) => (
                                    <tr key={item.sku}>
                                      <td>{item.product_name}</td>
                                      <td>{item.form_label}</td>
                                      <td>{item.strength ?? "—"}</td>
                                      <td className={styles.mono}>{item.sku}</td>
                                      <td>{item.quantity}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                              {row.notes && (
                                <p>
                                  <strong>Notes:</strong> {row.notes}
                                </p>
                              )}
                              {row.source_path && <p className={styles.muted}>Sent from {row.source_path}</p>}
                            </div>
                          </td>
                        </tr>
                      )}
                    </RowGroup>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}

// A fragment with a key: <tbody> needs each row group keyed, and a bare
// fragment can't take one in JSX without this.
function RowGroup({ children }: { open: boolean; children: React.ReactNode }) {
  return <>{children}</>;
}
