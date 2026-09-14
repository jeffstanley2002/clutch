"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, LoaderCircle } from "lucide-react";
export function Login({ local }: { local: boolean }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  async function submit(anonymous = false) {
    if (busy) return;
    if (!anonymous && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email address to receive your login link.");
      document.getElementById("email")?.focus();
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `/api/auth/${anonymous ? "local" : "login"}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim() }),
        },
      );
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      if (anonymous) router.push("/workspace");
      else setSent(true);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Sign-in is unavailable. Try again shortly.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <form
      className="login-form"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <label htmlFor="email">Your email</label>
      <div className="login-row">
        <input
          id="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setSent(false);
          }}
          aria-invalid={!!error}
          aria-describedby="login-status"
          disabled={busy}
        />
        <button className="button primary" disabled={busy} aria-busy={busy}>
          {busy ? (
            <LoaderCircle className="spin" size={17} />
          ) : (
            <>
              Send login link <ArrowUpRight size={17} />
            </>
          )}
        </button>
      </div>
      <div
        id="login-status"
        className="form-message"
        role={error ? "alert" : "status"}
      >
        {error ||
          (sent
            ? "Check your inbox. Your link will bring you to the workspace."
            : "A private workspace. One email link to sign in.")}
      </div>
      {local && (
        <button
          type="button"
          className="text-button"
          disabled={busy}
          onClick={() => void submit(true)}
        >
          Open local practice workspace <ArrowUpRight size={15} />
        </button>
      )}
    </form>
  );
}
