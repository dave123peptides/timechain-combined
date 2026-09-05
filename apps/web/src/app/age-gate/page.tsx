import styles from "./page.module.css";

export default async function AgeGatePage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  // Only internal paths may round-trip through the gate.
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/";

  return (
    <main className={styles.wrap}>
      <div className={styles.card}>
        <div className={styles.wordmark}>TimeChain Peptides</div>
        <span className={styles.eyebrow}>Research Use Only</span>
        <form action="/age-gate/enter" method="post" className={styles.form}>
          <input type="hidden" name="next" value={safeNext} />
          <p className={styles.statement}>I confirm that I am at least 21 years old.</p>
          <button type="submit" className={styles.enterButton}>
            Enter Site
          </button>
        </form>
      </div>
    </main>
  );
}
