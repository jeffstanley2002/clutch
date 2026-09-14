import "server-only";
import { cookies } from "next/headers";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import { profileId, sign, verify } from "./security";
export const sessionCookie = "clutch_session";
export const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: 60 * 60 * 24 * 7,
};
export function localMode() {
  return (
    !process.env.VERCEL && process.env.CLUTCH_ALLOW_LOCAL_ANONYMOUS === "true"
  );
}
export function authConfigured() {
  return Boolean(
    process.env.STYTCH_PROJECT_ID &&
    process.env.STYTCH_SECRET &&
    process.env.CLUTCH_SESSION_SECRET?.length &&
    process.env.CLUTCH_SESSION_SECRET.length >= 32,
  );
}
export function sessionSecret() {
  const secret = process.env.CLUTCH_SESSION_SECRET;
  if (secret && secret.length >= 32) return secret;
  if (localMode()) return "local-development-only-session-signing-key";
  throw new Error("Authentication unavailable");
}
export async function stytch(path: string, body: unknown) {
  if (!authConfigured()) throw new Error("Authentication unavailable");
  const base = ["live", "production", "prod"].includes(
    process.env.STYTCH_ENVIRONMENT ?? "test",
  )
    ? "https://api.stytch.com/v1"
    : "https://test.stytch.com/v1";
  const response = await fetch(`${base}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Basic ${Buffer.from(`${process.env.STYTCH_PROJECT_ID}:${process.env.STYTCH_SECRET}`).toString("base64")}`,
    },
    body: JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error("Authentication failed");
  return response.json() as Promise<unknown>;
}
export async function getIdentity(): Promise<{
  profile: string;
  email: string;
} | null> {
  const value = (await cookies()).get(sessionCookie)?.value;
  if (!value) return null;
  if (localMode() && value.startsWith("local.")) {
    const [, id, signature] = value.split(".");
    return id && signature && verify(id, signature, sessionSecret())
      ? { profile: profileId(id), email: "Local practice" }
      : null;
  }
  try {
    const result = z
      .object({
        user: z.object({
          user_id: z.string(),
          emails: z.array(z.object({ email: z.string() })).optional(),
        }),
      })
      .parse(await stytch("/sessions/authenticate", { session_token: value }));
    return {
      profile: profileId(result.user.user_id),
      email: result.user.emails?.[0]?.email ?? "Signed in",
    };
  } catch {
    return null;
  }
}
export async function startLocalSession() {
  const id = randomUUID();
  (await cookies()).set(
    sessionCookie,
    `local.${id}.${sign(id, sessionSecret())}`,
    cookieOptions,
  );
}
export async function authorizeInterview(id: string, profile: string) {
  const token = (await cookies()).get(`clutch_i_${id}`)?.value;
  return Boolean(token && verify(`${profile}:${id}`, token, sessionSecret()));
}
export async function rememberInterview(id: string, profile: string) {
  const jar = await cookies();
  // Bound capability cookies so a long practice history cannot exceed header limits.
  const owned = jar
    .getAll()
    .filter((cookie) => cookie.name.startsWith("clutch_i_"));
  for (const old of owned.slice(0, Math.max(0, owned.length - 11)))
    jar.delete(old.name);
  jar.set(
    `clutch_i_${id}`,
    sign(`${profile}:${id}`, sessionSecret()),
    cookieOptions,
  );
}
