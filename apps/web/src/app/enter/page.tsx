import { redirect } from "next/navigation";
import { siteLocked } from "@/lib/access";
import styles from "./page.module.css";

// Optional lock page (shown only while SITE_ACCESS_PASSWORD is set). Deliberately plain — no branding, no hints about
// what's behind it, just the password field.
export default async function EnterPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const { next, error } = await searchParams;
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
  // No password configured: nothing to enter, carry on to the page.
  if (!siteLocked()) redirect(safeNext);

  return (
    <main className={styles.wrap}>
      <div className={styles.card}>
        <div className={styles.wordmark}>TimeChain Peptides</div>
        <span className={styles.eyebrow}>Private Preview</span>
        <form action="/enter/submit" method="post" className={styles.form}>
          <input type="hidden" name="next" value={safeNext} />
          {error ? (
            <p className={styles.error} role="alert">
              That password isn&apos;t right — try again.
            </p>
          ) : (
            <p className={styles.statement}>
              This site is in private preview. Enter the access password to continue.
            </p>
          )}
          <input
            type="password"
            name="password"
            autoComplete="off"
            placeholder="Password"
            className={styles.input}
            required
          />
          <button type="submit" className={styles.enterButton}>
            Enter Site
          </button>
        </form>
      </div>
    </main>
  );
}
