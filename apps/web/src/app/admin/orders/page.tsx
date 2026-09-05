"use client";

import { useCallback, useEffect, useState } from "react";
import AdminNav from "../AdminNav";
import styles from "../products/admin.module.css";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ACTOR_STORAGE_KEY = "tcp_admin_actor";
const CREDS_STORAGE_KEY = "tcp_admin_creds";

type OrderRow = {
  order_id: string;
  public_order_number: string;
  customer_email: string;
  customer_name: string | null;
  customer_phone: string | null;
  status: string;
  total_cents: number;
  currency: string;
  created_at: string;
  payment_provider: string | null;
  payment_status: string | null;
};

type OrderDetail = OrderRow & {
  shipping_address: {
    line1: string;
    line2?: string | null;
    city: string;
    region: string;
    postal_code: string;
    country: string;
  } | null;
  subtotal_cents: number;
  shipping_cents: number;
  tax_cents: number;
  items: {
    display_name_at_purchase: string;
    sku_snapshot: string;
    supplier_sku_at_purchase: string;
    supplier_name_at_purchase: string;
    quantity: number;
    unit_price_cents: number;
    total_price_cents: number;
  }[];
  payments: { provider: string; status: string; amount_cents: number; provider_payment_id: string | null }[];
  events: { event_type: string; data: Record<string, unknown> | null; created_at: string }[];
};

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

// The manual-fulfillment worksheet (David, 9/4): every order with the
// customer record, what to order from the supplier, and the buttons to
// confirm a Venmo / Zelle transfer arrived. The API's /admin routes need
// HTTP Basic auth and live on another origin, so credentials are asked
// for once here and sent explicitly (sessionStorage — gone when the tab
// closes). Same user/password as the page's own gate (middleware.ts).
export default function AdminOrdersPage() {
  const [creds, setCreds] = useState<{ user: string; password: string } | null>(null);
  const [credUser, setCredUser] = useState("");
  const [credPassword, setCredPassword] = useState("");
  const [actor, setActor] = useState("");
  const [rows, setRows] = useState<OrderRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<OrderDetail | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<"all" | "PAYMENT_PENDING" | "PAID">("PAYMENT_PENDING");

  useEffect(() => {
    const storedActor = window.localStorage.getItem(ACTOR_STORAGE_KEY);
    if (storedActor) setActor(storedActor);
    const storedCreds = window.sessionStorage.getItem(CREDS_STORAGE_KEY);
    if (storedCreds) {
      try {
        setCreds(JSON.parse(storedCreds));
      } catch {
        window.sessionStorage.removeItem(CREDS_STORAGE_KEY);
      }
    }
  }, []);

  const authHeader = useCallback(
    (): Record<string, string> =>
      creds ? { Authorization: `Basic ${btoa(`${creds.user}:${creds.password}`)}` } : {},
    [creds]
  );

  const load = useCallback(() => {
    if (!creds) return;
    setLoadError(null);
    fetch(`${API_BASE_URL}/admin/orders`, { headers: authHeader() })
      .then((r) => {
        if (r.status === 401) throw new Error("Those admin credentials were rejected.");
        if (!r.ok) throw new Error(`Failed to load orders (${r.status})`);
        return r.json() as Promise<OrderRow[]>;
      })
      .then(setRows)
      .catch((err: Error) => {
        setRows(null);
        setLoadError(err.message);
      });
  }, [creds, authHeader]);

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = async (orderId: string) => {
    if (openId === orderId) {
      setOpenId(null);
      setDetail(null);
      return;
    }
    setOpenId(orderId);
    setDetail(null);
    const r = await fetch(`${API_BASE_URL}/admin/orders/${orderId}`, { headers: authHeader() });
    if (r.ok) setDetail((await r.json()) as OrderDetail);
  };

  const act = async (row: OrderRow, path: string, body: Record<string, unknown>) => {
    if (!actor.trim()) {
      setRowErrors((prev) => ({ ...prev, [row.order_id]: "Enter your name above first." }));
      return;
    }
    setBusyId(row.order_id);
    setRowErrors((prev) => ({ ...prev, [row.order_id]: "" }));
    try {
      const r = await fetch(`${API_BASE_URL}/admin/orders/${row.order_id}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify({ actor, ...body }),
      });
      if (!r.ok) {
        const payload = (await r.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? `Request failed (${r.status})`);
      }
      const updated = (await r.json()) as OrderRow | null;
      if (updated) setRows((current) => current?.map((x) => (x.order_id === row.order_id ? updated : x)) ?? current);
      if (openId === row.order_id) openDetail(row.order_id).then(() => openDetail(row.order_id));
    } catch (err) {
      setRowErrors((prev) => ({ ...prev, [row.order_id]: (err as Error).message }));
    } finally {
      setBusyId(null);
    }
  };

  const shown = (rows ?? []).filter((row) => filter === "all" || row.status === filter);
  const csvHref = `${API_BASE_URL}/admin/orders/export.csv${filter === "all" ? "" : `?status=${filter}`}`;

  return (
    <main className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Orders</h1>
          <p className={styles.subtitle}>
            Confirm Venmo / Zelle transfers here, then place paid orders with the supplier by hand. The CSV has the
            same rows for a spreadsheet.
          </p>
        </div>
        <AdminNav current="orders" />
      </div>

      {!creds ? (
        <form
          className={styles.credsForm}
          onSubmit={(event) => {
            event.preventDefault();
            const next = { user: credUser.trim(), password: credPassword };
            window.sessionStorage.setItem(CREDS_STORAGE_KEY, JSON.stringify(next));
            setCreds(next);
          }}
        >
          <p className={styles.subtitle}>Enter the admin user and password to load orders from the API.</p>
          <label className={styles.actorField}>
            User <input value={credUser} onChange={(e) => setCredUser(e.target.value)} autoComplete="username" />
          </label>
          <label className={styles.actorField}>
            Password{" "}
            <input type="password" value={credPassword} onChange={(e) => setCredPassword(e.target.value)} autoComplete="current-password" />
          </label>
          <button type="submit" className={styles.button}>
            Load orders
          </button>
        </form>
      ) : (
        <>
          <div className={styles.toolbar}>
            <label className={styles.actorField}>
              Your name
              <input
                value={actor}
                placeholder="who is confirming"
                onChange={(e) => {
                  setActor(e.target.value);
                  window.localStorage.setItem(ACTOR_STORAGE_KEY, e.target.value);
                }}
              />
            </label>
            <label className={styles.actorField}>
              Show
              <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
                <option value="PAYMENT_PENDING">Awaiting payment</option>
                <option value="PAID">Paid — to place</option>
                <option value="all">All orders</option>
              </select>
            </label>
            <a className={styles.button} href={csvHref}>
              Download CSV
            </a>
            <button
              type="button"
              className={styles.buttonGhost}
              onClick={() => {
                window.sessionStorage.removeItem(CREDS_STORAGE_KEY);
                setCreds(null);
                setRows(null);
              }}
            >
              Sign out
            </button>
          </div>

          {loadError && <p className={styles.error}>{loadError}</p>}
          {rows && shown.length === 0 && <p className={styles.subtitle}>No orders in this view.</p>}

          {rows && shown.length > 0 && (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Placed</th>
                    <th>Customer</th>
                    <th>Method</th>
                    <th>Payment</th>
                    <th>Total</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((row) => (
                    <FragmentRow
                      key={row.order_id}
                      row={row}
                      open={openId === row.order_id}
                      detail={openId === row.order_id ? detail : null}
                      busy={busyId === row.order_id}
                      error={rowErrors[row.order_id]}
                      onToggle={() => openDetail(row.order_id)}
                      onMarkPaid={() =>
                        act(row, "mark-paid", {
                          provider: row.payment_provider ?? "manual",
                          note: `${row.payment_provider ?? "transfer"} confirmed by ${actor}`,
                        })
                      }
                      onMarkFailed={() => act(row, "mark-payment-failed", { reason: "No transfer received" })}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </main>
  );
}

function FragmentRow({
  row,
  open,
  detail,
  busy,
  error,
  onToggle,
  onMarkPaid,
  onMarkFailed,
}: {
  row: OrderRow;
  open: boolean;
  detail: OrderDetail | null;
  busy: boolean;
  error?: string;
  onToggle: () => void;
  onMarkPaid: () => void;
  onMarkFailed: () => void;
}) {
  const address = detail?.shipping_address;
  return (
    <>
      <tr>
        <td className={styles.mono}>{row.public_order_number}</td>
        <td>{when(row.created_at)}</td>
        <td>
          <div>{row.customer_name ?? "—"}</div>
          <div className={styles.muted}>{row.customer_email}</div>
          {row.customer_phone && <div className={styles.muted}>{row.customer_phone}</div>}
        </td>
        <td>{row.payment_provider ?? "—"}</td>
        <td>{row.payment_status ?? "—"}</td>
        <td className={styles.mono}>{money(row.total_cents)}</td>
        <td>
          <span className={`${styles.pill} ${row.status === "PAID" ? styles.pillMapped : row.status === "PAYMENT_PENDING" ? styles.pillChanged : styles.pillNeutral}`}>
            {row.status}
          </span>
        </td>
        <td className={styles.actions}>
          <button type="button" className={styles.buttonGhost} onClick={onToggle}>
            {open ? "Hide" : "Details"}
          </button>
          {row.status === "PAYMENT_PENDING" && (
            <>
              <button type="button" className={styles.button} disabled={busy} onClick={onMarkPaid}>
                Mark paid
              </button>
              <button type="button" className={styles.buttonGhost} disabled={busy} onClick={onMarkFailed}>
                No payment
              </button>
            </>
          )}
          {error && <div className={styles.error}>{error}</div>}
        </td>
      </tr>
      {open && (
        <tr className={styles.detailRow}>
          <td colSpan={8}>
            {!detail ? (
              <p className={styles.muted}>Loading…</p>
            ) : (
              <div className={styles.detailGrid}>
                <div>
                  <h3>Ship to</h3>
                  <p className={styles.detailBlock}>
                    <strong>{detail.customer_name ?? "—"}</strong>
                    <br />
                    {address?.line1}
                    {address?.line2 ? <><br />{address.line2}</> : null}
                    <br />
                    {address?.city}, {address?.region} {address?.postal_code}
                    <br />
                    {address?.country}
                    <br />
                    {detail.customer_phone ?? "—"} · {detail.customer_email}
                  </p>
                </div>
                <div>
                  <h3>Order with the supplier</h3>
                  <table className={styles.innerTable}>
                    <thead>
                      <tr>
                        <th>Qty</th>
                        <th>Supplier SKU</th>
                        <th>Supplier product</th>
                        <th>Sold as</th>
                        <th>Line</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.items.map((item, i) => (
                        <tr key={i}>
                          <td className={styles.mono}>{item.quantity}</td>
                          <td className={styles.mono}>{item.supplier_sku_at_purchase}</td>
                          <td>{item.supplier_name_at_purchase}</td>
                          <td className={styles.muted}>{item.display_name_at_purchase}</td>
                          <td className={styles.mono}>{money(item.total_price_cents)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className={styles.muted}>
                    Subtotal {money(detail.subtotal_cents)} · Shipping {money(detail.shipping_cents)} · Total{" "}
                    <strong>{money(detail.total_cents)}</strong> · memo the customer was told to use:{" "}
                    <span className={styles.mono}>{detail.public_order_number}</span>
                  </p>
                </div>
                <div>
                  <h3>History</h3>
                  <ul className={styles.events}>
                    {detail.events.map((event, i) => (
                      <li key={i}>
                        <span className={styles.mono}>{when(event.created_at)}</span> {event.event_type}
                        {event.data?.source ? ` · ${String(event.data.source)}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
