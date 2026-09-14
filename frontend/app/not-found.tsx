import Link from "next/link";
import { Brand } from "@/components/brand";
export default function NotFound() {
  return (
    <main id="main" className="empty">
      <Brand />
      <h1 style={{ marginTop: 40 }}>This page isn’t here.</h1>
      <p>Return to your workspace to continue practicing.</p>
      <Link href="/workspace" className="button primary">
        Open workspace
      </Link>
    </main>
  );
}
