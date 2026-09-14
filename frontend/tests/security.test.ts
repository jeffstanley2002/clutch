import assert from "node:assert/strict";
import test from "node:test";
import {
  allowedRoute,
  profileId,
  sameOrigin,
  sign,
  verify,
} from "../lib/security";
import { githubUrl, safeHref, review } from "../lib/contracts";
test("only explicit product routes are exposed", () => {
  for (const path of [
    "review",
    "review/github",
    "interview/turn",
    "progress/snapshots",
  ])
    assert.equal(allowedRoute(path.split("/"), "POST"), true);
  for (const path of [
    "runtime/spend",
    "health",
    "progress/victim",
    "review/../../runtime/spend",
    "interview/a/b/feedback",
  ])
    assert.equal(allowedRoute(path.split("/"), "GET"), false);
  assert.equal(allowedRoute(["interview", "abc-123", "feedback"], "GET"), true);
  assert.equal(allowedRoute(["review"], "GET"), false);
});
test("ownership signatures cannot be reused across identities or sessions", () => {
  const signature = sign("alice:review-a", "test-signing-secret");
  assert.equal(
    verify("alice:review-a", signature, "test-signing-secret"),
    true,
  );
  assert.equal(verify("bob:review-a", signature, "test-signing-secret"), false);
  assert.equal(
    verify("alice:review-b", signature, "test-signing-secret"),
    false,
  );
  assert.equal(verify("alice:review-a", "bad", "test-signing-secret"), false);
});
test("profile hashing preserves the Streamlit identity mapping", () => {
  assert.equal(
    profileId("abc"),
    "user_ba7816bf8f01cfea414140de5dae2223b00361a3",
  );
});
test("mutations require the exact request origin", () => {
  assert.equal(
    sameOrigin(
      new Request("https://clutch.example/api", {
        headers: { origin: "https://clutch.example" },
      }),
    ),
    true,
  );
  assert.equal(
    sameOrigin(
      new Request("https://clutch.example/api", {
        headers: { origin: "https://other.example" },
      }),
    ),
    false,
  );
  assert.equal(sameOrigin(new Request("https://clutch.example/api")), false);
});
test("GitHub accepts repo/PR links and rejects arbitrary hosts or paths", () => {
  assert.equal(
    githubUrl("https://github.com/org/repo/?tab=readme#start"),
    "https://github.com/org/repo",
  );
  assert.equal(
    githubUrl("https://github.com/org/repo/pull/42"),
    "https://github.com/org/repo/pull/42",
  );
  for (const value of [
    "https://evil.example/org/repo",
    "http://github.com/org/repo",
    "https://github.com/org/repo/tree/main",
    "https://u:p@github.com/org/repo",
    "https://github.com/org/repo/pull/0",
  ])
    assert.equal(githubUrl(value), null);
});
test("untrusted citations cannot introduce executable URLs", () => {
  assert.equal(safeHref("javascript:alert(1)"), undefined);
  assert.equal(safeHref("data:text/html,test"), undefined);
  assert.equal(
    safeHref("https://docs.python.org/3/"),
    "https://docs.python.org/3/",
  );
});
test("malformed review responses are rejected before rendering", () => {
  assert.equal(
    review.safeParse({ findings: [], questions: [] }).success,
    false,
  );
});
