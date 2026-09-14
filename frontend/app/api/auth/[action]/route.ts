import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { z } from "zod";
import {
  cookieOptions,
  getIdentity,
  localMode,
  sessionCookie,
  startLocalSession,
  stytch,
} from "@/lib/auth";
import { sameOrigin } from "@/lib/security";
export const runtime = "nodejs";
const fail = (message: string, status = 400) =>
  NextResponse.json(
    { error: message },
    { status, headers: { "Cache-Control": "no-store" } },
  );
export async function POST(
  request: Request,
  context: { params: Promise<{ action: string }> },
) {
  if (!sameOrigin(request)) return fail("Request origin not allowed.", 403);
  const { action } = await context.params;
  try {
    if (action === "local" && localMode()) {
      await startLocalSession();
      return NextResponse.json({ ok: true });
    }
    if (action === "logout") {
      const jar = await cookies();
      const token = jar.get(sessionCookie)?.value;
      if (token && !token.startsWith("local."))
        await stytch("/sessions/revoke", { session_token: token });
      for (const cookie of jar.getAll())
        if (cookie.name.startsWith("clutch_")) jar.delete(cookie.name);
      return NextResponse.json({ ok: true });
    }
    if (action !== "login") return fail("Not found.", 404);
    const body = z
      .object({ email: z.email().max(254) })
      .parse(await request.json());
    const redirect = process.env.STYTCH_REDIRECT_URL;
    if (!redirect)
      return fail("Sign-in is being configured. Please try again later.", 503);
    await stytch("/magic_links/email/login_or_create", {
      email: body.email,
      login_magic_link_url: redirect,
      signup_magic_link_url: redirect,
    });
    return NextResponse.json({ ok: true });
  } catch {
    return fail(
      "That request could not be completed. Check your details and try again.",
    );
  }
}
export async function GET(
  request: Request,
  context: { params: Promise<{ action: string }> },
) {
  const { action } = await context.params;
  if (action === "session")
    return NextResponse.json(
      { identity: await getIdentity() },
      { headers: { "Cache-Control": "no-store" } },
    );
  if (action !== "callback") return fail("Not found.", 404);
  const url = new URL(request.url);
  const destination = new URL(process.env.STYTCH_REDIRECT_URL || request.url);
  const token = url.searchParams.get("token");
  if (!token || token.length > 4096)
    return NextResponse.redirect(new URL("/?auth=failed", destination));
  try {
    const result = z.object({ session_token: z.string() }).parse(
      await stytch("/magic_links/authenticate", {
        token,
        session_duration_minutes: 10080,
      }),
    );
    (await cookies()).set(sessionCookie, result.session_token, cookieOptions);
    return NextResponse.redirect(new URL("/workspace", destination));
  } catch {
    return NextResponse.redirect(new URL("/?auth=failed", destination));
  }
}
