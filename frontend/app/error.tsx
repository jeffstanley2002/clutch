"use client";
import Link from "next/link";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main id="main" className="empty">
      <h1>The workspace couldn’t load.</h1>
      <p>Try loading it again, or return to the home page.</p>
      <button className="button primary" onClick={reset}>
        Try again
      </button>
      <Link href="/">Clutch home</Link>
    </main>
  );
}
