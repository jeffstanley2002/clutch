import { createHash, createHmac, timingSafeEqual } from "node:crypto";
export function profileId(identity: string) {
  return `user_${createHash("sha256").update(identity).digest("hex").slice(0, 40)}`;
}
export function sign(value: string, secret: string) {
  return createHmac("sha256", secret).update(value).digest("base64url");
}
export function verify(value: string, signature: string, secret: string) {
  const expected = Buffer.from(sign(value, secret));
  const actual = Buffer.from(signature);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
export function sameOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const presented = new URL(origin);
    const target = new URL(request.url);
    const host = request.headers.get("host") ?? target.host;
    // Next's internal request URL can use localhost behind a reverse proxy.
    const protocol = process.env.VERCEL ? "https:" : target.protocol;
    return presented.host === host && presented.protocol === protocol;
  } catch {
    return false;
  }
}
export function allowedRoute(path: string[], method: string): boolean {
  const route = path.join("/");
  return (
    (method === "POST" &&
      [
        "review",
        "review/github",
        "interview/turn",
        "progress/snapshots",
      ].includes(route)) ||
    (method === "GET" &&
      (route === "progress" ||
        /^interview\/[A-Za-z0-9_-]{1,120}\/feedback$/.test(route)))
  );
}
