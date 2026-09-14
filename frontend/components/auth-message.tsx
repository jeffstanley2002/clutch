"use client";
import { useSearchParams } from "next/navigation";
export function AuthMessage() {
  const params = useSearchParams();
  return params.get("auth") === "failed" ? (
    <p className="error-banner" role="alert">
      That login link has expired or could not be verified. Request a fresh link
      below.
    </p>
  ) : null;
}
