import { NextResponse } from "next/server";
import { z } from "zod";
import { authorizeInterview, getIdentity, rememberInterview } from "@/lib/auth";
import { allowedRoute, sameOrigin } from "@/lib/security";
import {
  githubReview,
  githubUrl,
  progress,
  question,
  report,
  review,
  turn,
} from "@/lib/contracts";
export const runtime = "nodejs";
export const maxDuration = 180;
const id = z.string().regex(/^[A-Za-z0-9_-]{1,120}$/);
const role = z.string().trim().max(120).default("backend intern");
const failure = (error: string, status: number) =>
  NextResponse.json(
    { error },
    { status, headers: { "Cache-Control": "no-store" } },
  );
async function handle(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (!allowedRoute(path, request.method)) return failure("Not found.", 404);
  if (request.method !== "GET" && !sameOrigin(request))
    return failure("Request origin not allowed.", 403);
  const identity = await getIdentity();
  if (!identity)
    return failure("Your session has expired. Sign in again to continue.", 401);
  let route = path.join("/");
  let payload: unknown;
  let schema: z.ZodType = review;
  try {
    if (request.method === "POST" && !route.startsWith("progress")) {
      const raw = await request.text();
      if (raw.length > 200000)
        return failure(
          "This input is too large. Use a smaller code sample.",
          413,
        );
      const body: unknown = JSON.parse(raw);
      if (route === "review")
        payload = {
          ...z
            .object({
              code: z
                .string()
                .max(50000)
                .refine((v) => !!v.trim()),
              role_context: role,
            })
            .parse(body),
          language: "python",
          session_id: identity.profile,
        };
      if (route === "review/github") {
        const input = z
          .object({
            source_url: z.string().max(500),
            ref: z.string().trim().min(1).max(200).optional(),
            role_context: role,
          })
          .parse(body);
        const source = githubUrl(input.source_url);
        if (!source)
          return failure("Use a GitHub repository or pull request URL.", 422);
        payload = {
          ...input,
          source_url: source,
          session_id: identity.profile,
        };
        schema = githubReview;
      }
      if (route === "interview/turn") {
        const input = z
          .object({
            interview_session_id: id.optional(),
            review_session_id: id.optional(),
            questions: z.array(question).max(5).optional(),
            answer: z
              .string()
              .max(10000)
              .refine((v) => !!v.trim())
              .optional(),
            role_context: role,
          })
          .parse(body);
        if (input.interview_session_id) {
          if (
            !input.answer ||
            !(await authorizeInterview(
              input.interview_session_id,
              identity.profile,
            ))
          )
            return failure(
              "This interview is unavailable. Start a new review.",
              403,
            );
          payload = {
            interview_session_id: input.interview_session_id,
            answer: input.answer,
          };
        } else {
          if (
            !input.questions?.length ||
            !input.review_session_id ||
            !(await authorizeInterview(
              input.review_session_id,
              identity.profile,
            ))
          )
            return failure(
              "Complete a review before starting an interview.",
              422,
            );
          payload = { ...input, profile_id: identity.profile };
        }
        schema = turn;
      }
    }
    if (route.startsWith("progress")) {
      route = `progress/${identity.profile}${request.method === "POST" ? "/snapshots" : ""}`;
      schema = progress;
    }
    if (path[0] === "interview" && path[2] === "feedback") {
      if (!(await authorizeInterview(path[1], identity.profile)))
        return failure(
          "This interview is unavailable. Start a new review.",
          403,
        );
      schema = report;
    }
    const base = process.env.CLUTCH_API_BASE_URL || "http://localhost:8000";
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (process.env.CLUTCH_API_KEY)
      headers["X-Clutch-API-Key"] = process.env.CLUTCH_API_KEY;
    const response = await fetch(`${base.replace(/\/$/, "")}/${route}`, {
      method: request.method,
      headers,
      body: payload ? JSON.stringify(payload) : undefined,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(150000),
    });
    if (!response.ok)
      return failure(
        response.status === 422
          ? "The input could not be reviewed. Check the Python syntax or GitHub URL and try again."
          : response.status === 409
            ? "Complete the interview before loading its report."
            : "The service could not complete this request. Your input is still here; try again shortly.",
        response.status >= 500
          ? 502
          : response.status === 401
            ? 503
            : response.status,
      );
    const data = schema.parse(await response.json());
    if (path[0] === "review") {
      const result =
        path.length === 1
          ? review.parse(data)
          : githubReview.parse(data).review;
      id.parse(result.request_id);
      await rememberInterview(result.request_id, identity.profile);
    }
    if (path.join("/") === "interview/turn") {
      const result = turn.parse(data);
      id.parse(result.interview_session_id);
      await rememberInterview(result.interview_session_id, identity.profile);
    }
    return NextResponse.json(data, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    if (error instanceof z.ZodError || error instanceof SyntaxError)
      return failure(
        "The request or response was not valid. Check your input and try again.",
        422,
      );
    return failure(
      "The service is taking too long or is unavailable. Your input is preserved. A submitted turn may have completed; avoid repeated submissions.",
      504,
    );
  }
}
export { handle as GET, handle as POST };
