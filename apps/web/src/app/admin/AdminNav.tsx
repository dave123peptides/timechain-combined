import Link from "next/link";
import styles from "./products/admin.module.css";

// The admin screens. Both sit behind the same basic-auth gate
// (middleware.ts for the page, app/core/admin_auth.py for the API).
export default function AdminNav({ current }: { current: "orders" | "products" }) {
  return (
    <nav className={styles.nav} aria-label="Admin">
      <Link href="/admin/orders" className={current === "orders" ? styles.navActive : styles.navLink}>
        Orders
      </Link>
      <Link href="/admin/products" className={current === "products" ? styles.navActive : styles.navLink}>
        Products
      </Link>
    </nav>
  );
}
