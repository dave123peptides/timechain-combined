import Link from "next/link";

export default function NotFound() {
  return (
    <main className="container" style={{ padding: "6rem 0", textAlign: "center" }}>
      <span className="eyebrow">404</span>
      <h1 style={{ margin: "0.75rem 0 1.25rem" }}>Not Found</h1>
      <p style={{ marginBottom: "2rem" }}>That page, or that product, isn&apos;t available.</p>
      <Link href="/shop" className="button buttonPrimary">
        Back to Shop
      </Link>
    </main>
  );
}
