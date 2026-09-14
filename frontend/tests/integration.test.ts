import assert from "node:assert/strict";
import test from "node:test";
const base = process.env.CLUTCH_TEST_URL;
// Opt in only against an isolated local Next.js + FastAPI pair with no paid model key.
test(
  "HTTP review → interview → feedback → progress, with ownership and CSRF enforcement",
  { skip: !base },
  async () => {
    assert.match(base!, /^http:\/\/(localhost|127\.0\.0\.1):\d+$/);
    function client() {
      const jar = new Map<string, string>();
      return async (path: string, body?: unknown, origin = base!) => {
        const response = await fetch(`${base}${path}`, {
          method: body === undefined ? "GET" : "POST",
          headers: {
            origin,
            "Content-Type": "application/json",
            cookie: [...jar].map(([k, v]) => `${k}=${v}`).join("; "),
          },
          body: body === undefined ? undefined : JSON.stringify(body),
        });
        for (const cookie of response.headers.getSetCookie()) {
          const pair = cookie.split(";")[0];
          const split = pair.indexOf("=");
          jar.set(pair.slice(0, split), pair.slice(split + 1));
        }
        return { status: response.status, data: await response.json() };
      };
    }
    const alice = client();
    const bob = client();
    assert.equal((await alice("/api/clutch/progress")).status, 401);
    assert.equal((await alice("/api/auth/local", {})).status, 200);
    assert.equal((await bob("/api/auth/local", {})).status, 200);
    assert.equal(
      (
        await alice(
          "/api/clutch/review",
          { code: "x=1" },
          "https://evil.example",
        )
      ).status,
      403,
    );
    assert.equal((await alice("/api/clutch/runtime/spend")).status, 404);
    const review = await alice("/api/clutch/review", {
      code: "def add_item(item, items=[]):\n    items.append(item)\n    return items",
      role_context: "backend intern",
      session_id: "victim",
    });
    assert.equal(review.status, 200);
    assert.ok(review.data.questions.length);
    assert.equal(review.data.mode, "static_fallback");
    const start = {
      review_session_id: review.data.request_id,
      questions: review.data.questions.slice(0, 5),
      role_context: "backend intern",
    };
    assert.equal((await bob("/api/clutch/interview/turn", start)).status, 422);
    let turn = await alice("/api/clutch/interview/turn", start);
    assert.equal(turn.status, 200);
    const session = turn.data.interview_session_id;
    assert.equal(
      (await bob(`/api/clutch/interview/${session}/feedback`)).status,
      403,
    );
    assert.equal(
      (
        await bob("/api/clutch/interview/turn", {
          interview_session_id: session,
          answer: "stolen",
        })
      ).status,
      403,
    );
    for (let i = 0; i < 5 && !turn.data.completed; i++) {
      turn = await alice("/api/clutch/interview/turn", {
        interview_session_id: session,
        answer:
          "I would use None as the default, allocate a new list for each call, and test repeated calls independently. The tradeoff is a small allocation for correctness and isolation.",
      });
      assert.equal(turn.status, 200);
    }
    assert.equal(turn.data.completed, true);
    assert.equal(
      (await alice(`/api/clutch/interview/${session}/feedback`)).status,
      200,
    );
    const history = await alice("/api/clutch/progress");
    assert.equal(history.status, 200);
    assert.ok(history.data.evidence_sessions.length);
    assert.equal(
      (await bob("/api/clutch/progress")).data.evidence_sessions.length,
      0,
    );
    assert.equal(
      (await alice("/api/clutch/progress/snapshots", {})).status,
      200,
    );
    assert.equal((await alice("/api/auth/logout", {})).status, 200);
    assert.equal((await alice("/api/clutch/progress")).status, 401);
  },
);
