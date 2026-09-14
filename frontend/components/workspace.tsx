"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  Code2,
  GitBranch,
  LogOut,
  MessageSquareText,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { Brand } from "./brand";
import { Busy, Citations, Provenance, TextList } from "./ui";
import {
  githubReview,
  githubUrl,
  labels,
  progress as progressSchema,
  report as reportSchema,
  review as reviewSchema,
  sample,
  turn as turnSchema,
  type Ingestion,
  type Progress,
  type Report,
  type Review,
  type Turn,
} from "@/lib/contracts";
type View = "Review" | "Interview" | "Progress";
async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api/clutch/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(165000),
  });
  const data: unknown = await response.json();
  if (!response.ok)
    throw new Error(
      z.object({ error: z.string() }).safeParse(data).data?.error ??
        "The request failed. Try again shortly.",
    );
  const parsed = schema.safeParse(data);
  if (!parsed.success)
    throw new Error(
      "The service returned an incomplete result. Your input is preserved; try again shortly.",
    );
  return parsed.data;
}
export function Workspace() {
  const [identity, setIdentity] = useState<{
    email: string;
    profile: string;
  } | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [view, setView] = useState<View>("Review");
  const [source, setSource] = useState<"code" | "github">("code");
  const [code, setCode] = useState("");
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("");
  const [role, setRole] = useState("backend intern");
  const [reviewRole, setReviewRole] = useState(role);
  const [review, setReview] = useState<Review | null>(null);
  const [ingestion, setIngestion] = useState<Ingestion | null>(null);
  const [interview, setInterview] = useState<Turn | null>(null);
  const [answer, setAnswer] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [validation, setValidation] = useState("");
  const [notice, setNotice] = useState("");
  const [page, setPage] = useState(0);
  const lock = useRef(false);
  const signOutDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    fetch("/api/auth/session", { signal: controller.signal })
      .then((r) => r.json())
      .then((data) => setIdentity(data.identity))
      .catch(() => {})
      .finally(() => setAuthLoading(false));
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);
  useEffect(() => {
    document.title = `${view} · Clutch`;
  }, [view]);
  useEffect(() => {
    if (!code && !url && !answer) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [code, url, answer]);
  async function run(message: string, work: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true;
    setBusy(message);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "The request could not complete. Try again.",
      );
    } finally {
      lock.current = false;
      setBusy("");
    }
  }
  function navigate(next: View) {
    setView(next);
    setError("");
    setValidation("");
    setNotice("");
    if (next === "Progress" && !progress) void loadProgress();
  }
  function loadProgress(save = false) {
    return run(
      save
        ? "Saving your progress snapshot…"
        : "Loading your practice history…",
      async () => {
        setProgress(
          await api(
            save ? "progress/snapshots" : "progress",
            progressSchema,
            save ? {} : undefined,
          ),
        );
        if (save) setNotice("Progress snapshot saved.");
      },
    );
  }
  function submitReview() {
    const invalid = source === "code" ? !code.trim() : !githubUrl(url);
    if (invalid) {
      setValidation(
        source === "code"
          ? "Paste a Python function to review, or use the example."
          : "Use https://github.com/owner/repository or a /pull/123 URL.",
      );
      document.getElementById(source)?.focus();
      return;
    }
    setValidation("");
    void run(
      "Reviewing the code and preparing follow-up questions…",
      async () => {
        if (source === "github") {
          const data = await api("review/github", githubReview, {
            source_url: githubUrl(url),
            ...(ref.trim() ? { ref: ref.trim() } : {}),
            role_context: role,
          });
          setReview(data.review);
          setIngestion(data.ingestion);
        } else {
          setReview(
            await api("review", reviewSchema, { code, role_context: role }),
          );
          setIngestion(null);
        }
        setReviewRole(role);
        setInterview(null);
        setReport(null);
        setAnswer("");
        setProgress(null);
        setPage(0);
        setNotice(
          "Review complete. Explore the findings and practice questions.",
        );
      },
    );
  }
  function startInterview() {
    if (!review) return;
    void run("Preparing your first interview question…", async () => {
      setInterview(
        await api("interview/turn", turnSchema, {
          review_session_id: review.request_id,
          role_context: reviewRole,
          questions: review.questions.slice(0, 5),
        }),
      );
    });
  }
  function submitAnswer() {
    if (!answer.trim()) {
      setValidation("Write your explanation before submitting the answer.");
      document.getElementById("answer")?.focus();
      return;
    }
    setValidation("");
    void run("Assessing your reasoning…", async () => {
      const result = await api("interview/turn", turnSchema, {
        interview_session_id: interview?.interview_session_id,
        answer,
      });
      setInterview(result);
      setAnswer("");
      setProgress(null);
      if (result.completed)
        setNotice("Interview complete. You can now load your feedback report.");
    });
  }
  function signOut() {
    signOutDialog.current?.close();
    void run("Signing out…", async () => {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error("Sign-out failed. Try again shortly.");
      setCode("");
      setUrl("");
      setAnswer("");
      window.location.replace("/");
    });
  }
  const count = review?.findings.length ?? 0;
  return (
    <div className="workspace">
      <aside className="sidebar">
        <Brand preserveWorkspace />
        <span className="sidebar-label">YOUR PRACTICE SPACE</span>
        <nav aria-label="Practice stages">
          {(
            [
              { name: "Review", icon: Code2, sub: "Understand the code" },
              {
                name: "Interview",
                icon: MessageSquareText,
                sub: "Explain your decisions",
              },
              {
                name: "Progress",
                icon: TrendingUp,
                sub: "Build on your practice",
              },
            ] as const
          ).map(({ name, icon: Icon, sub }) => (
            <button
              key={name}
              className={`stage-link ${view === name ? "selected" : ""}`}
              aria-current={view === name ? "page" : undefined}
              disabled={!!busy}
              onClick={() => navigate(name)}
            >
              <Icon size={19} />
              <span>
                <strong>{name}</strong>
                <small>{sub}</small>
              </span>
              {name === "Review" && count > 0 && (
                <span className="nav-count">{count}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <BookOpen size={20} />
          <p>
            The finding is the start.
            <br />
            The explanation is the practice.
          </p>
        </div>
        <div className="account">
          <span className="avatar">
            {identity ? identity.email.charAt(0).toUpperCase() : "C"}
          </span>
          <span className="account-name">
            {identity?.email ?? "Your workspace"}
          </span>
          {identity && (
            <button
              aria-label="Log out"
              title="Log out"
              disabled={!!busy}
              onClick={() => signOutDialog.current?.showModal()}
            >
              <LogOut size={17} />
            </button>
          )}
        </div>
      </aside>
      <dialog
        ref={signOutDialog}
        className="confirm-dialog"
        aria-labelledby="sign-out-title"
        onClick={(e) => {
          if (e.target === e.currentTarget) signOutDialog.current?.close();
        }}
      >
        <form method="dialog" className="confirm-dialog-body">
          <h2 id="sign-out-title">Sign out?</h2>
          <p>You&rsquo;ll need to sign in again to get back to your workspace.</p>
          <div className="confirm-dialog-actions">
            <button type="submit" className="button">
              Cancel
            </button>
            <button
              type="button"
              className="button primary danger"
              onClick={signOut}
            >
              Sign out
            </button>
          </div>
        </form>
      </dialog>
      <div className="workspace-main">
        <header className="workspace-top">
          <span>
            Workspace <span className="crumb">/</span> <strong>{view}</strong>
          </span>
          <span className="readonly">
            <ShieldCheck size={14} /> Read-only practice
          </span>
        </header>
        <main id="main" className="work-content">
          <div className="work-heading">
            <div>
              <span className="eyebrow">
                {view === "Review"
                  ? "A CLOSER LOOK AT YOUR CODE"
                  : view === "Interview"
                    ? "THE THINKING BEHIND THE CODE"
                    : "YOUR PRACTICE, OVER TIME"}
              </span>
              <h1>
                {view === "Review"
                  ? "Make your next review count."
                  : view === "Interview"
                    ? "Talk through the tradeoffs."
                    : "Notice what’s getting better."}
              </h1>
              <p>
                {view === "Review"
                  ? "Bring a function or a repository. Leave with a clearer next step."
                  : view === "Interview"
                    ? "Practice explaining the decisions your code puts on the table."
                    : "Turn recurring patterns into a focused practice plan."}
              </p>
            </div>
          </div>
          {authLoading ? (
            <Busy text="Opening your workspace…" />
          ) : !identity ? (
            <section className="empty panel">
              <ShieldCheck size={30} />
              <h2>Sign in to your practice space</h2>
              <p>
                Your session may have expired. Sign in to review code and see
                your progress.
              </p>
              <Link href="/" className="button primary">
                Go to sign in <ArrowUpRight size={16} />
              </Link>
            </section>
          ) : (
            <>
              <div className="feedback-region" aria-live="polite">
                {busy ? (
                  <Busy text={busy} />
                ) : error ? (
                  <div className="error-banner" role="alert">
                    {error}{" "}
                    {error.includes("Sign in") && (
                      <Link href="/" target="_blank">
                        Sign in in a new tab
                      </Link>
                    )}
                  </div>
                ) : notice ? (
                  <div className="success-message">
                    <Check size={16} />
                    {notice}
                  </div>
                ) : (
                  <span className="muted">
                    {view === "Review"
                      ? "Python supported · Source text stays in this active workspace"
                      : "Your code, answers, and results stay available while switching stages."}
                  </span>
                )}
              </div>
              {view === "Review" && (
                <div className="review-grid">
                  <section className="input-panel panel">
                    <div className="panel-heading">
                      <h2>Your code</h2>
                      <span className="subtle-tag">01 / INPUT</span>
                    </div>
                    <form
                      noValidate
                      onSubmit={(e) => {
                        e.preventDefault();
                        submitReview();
                      }}
                    >
                      <fieldset disabled={!!busy}>
                        <legend className="sr-only">Review input</legend>
                        <div
                          className="source-toggle"
                          role="group"
                          aria-label="Code source"
                        >
                          <button
                            type="button"
                            aria-pressed={source === "code"}
                            className={source === "code" ? "active" : ""}
                            onClick={() => {
                              setSource("code");
                              setValidation("");
                            }}
                          >
                            <Code2 size={15} />
                            Paste code
                          </button>
                          <button
                            type="button"
                            aria-pressed={source === "github"}
                            className={source === "github" ? "active" : ""}
                            onClick={() => {
                              setSource("github");
                              setValidation("");
                            }}
                          >
                            <GitBranch size={15} />
                            GitHub link
                          </button>
                        </div>
                        <label htmlFor="role">Preparing for</label>
                        <select
                          id="role"
                          value={role}
                          onChange={(e) => setRole(e.target.value)}
                        >
                          <option value="backend intern">Backend intern</option>
                          <option value="junior backend engineer">
                            Junior backend engineer
                          </option>
                          <option value="AI engineer intern">
                            AI engineer intern
                          </option>
                          <option value="junior software engineer">
                            Junior software engineer
                          </option>
                        </select>
                        {source === "code" ? (
                          <>
                            <div className="editor-label">
                              <label htmlFor="code">Python source</label>
                              <button
                                type="button"
                                className="text-button"
                                disabled={!!code}
                                title={
                                  code
                                    ? "Clear the editor to load the example"
                                    : undefined
                                }
                                onClick={() => setCode(sample)}
                              >
                                Use example
                              </button>
                            </div>
                            <div className="editor">
                              <div className="editor-chrome">
                                <span>
                                  <Code2 size={14} /> snippet.py
                                </span>
                                <span>Python</span>
                              </div>
                              <textarea
                                id="code"
                                className="code-input resize-none"
                                value={code}
                                onChange={(e) => setCode(e.target.value)}
                                maxLength={50000}
                                spellCheck={false}
                                autoCapitalize="off"
                                autoCorrect="off"
                                placeholder={sample}
                                aria-invalid={!!validation}
                                aria-describedby="input-validation"
                              />
                              <div className="editor-footer">
                                <span>
                                  {code.split("\n").length}{" "}
                                  {code.split("\n").length === 1
                                    ? "line"
                                    : "lines"}
                                </span>
                                <span>
                                  {code.length.toLocaleString("en")} / 50,000
                                  characters
                                </span>
                              </div>
                            </div>
                          </>
                        ) : (
                          <div className="github-input">
                            <label htmlFor="github">
                              Repository or pull request URL
                            </label>
                            <input
                              id="github"
                              type="url"
                              placeholder="https://github.com/owner/repository"
                              value={url}
                              onChange={(e) => setUrl(e.target.value)}
                              maxLength={500}
                              aria-invalid={!!validation}
                              aria-describedby="input-validation"
                            />
                            <label htmlFor="ref">
                              Branch, tag, or commit{" "}
                              <span className="muted">(optional)</span>
                            </label>
                            <input
                              id="ref"
                              placeholder="Default branch"
                              value={ref}
                              onChange={(e) => setRef(e.target.value)}
                              maxLength={200}
                            />
                            <p>
                              Public Python repositories and pull requests.
                              Reviews cover a bounded selection of files.
                            </p>
                          </div>
                        )}
                        <div
                          id="input-validation"
                          className="validation"
                          role="alert"
                        >
                          {validation}
                        </div>
                        <button
                          className="button primary full-width"
                          disabled={!!busy}
                          aria-busy={!!busy}
                        >
                          Review code <ArrowRight size={17} />
                        </button>
                        <p className="input-note">
                          A new review replaces the current practice questions.
                        </p>
                      </fieldset>
                    </form>
                  </section>
                  <section className="results-panel panel" aria-busy={!!busy}>
                    <div className="panel-heading">
                      <h2>
                        Review findings{" "}
                        {review && <span className="count">{count}</span>}
                      </h2>
                      <span className="subtle-tag">02 / UNDERSTAND</span>
                    </div>
                    {!review ? (
                      <div className="empty review-empty">
                        <div className="empty-mark">
                          <Code2 size={30} />
                        </div>
                        <h3>A fresh pair of eyes.</h3>
                        <p>
                          Your findings will appear here, with the exact
                          concern, a suggested improvement, and sources to
                          explore.
                        </p>
                        <div className="empty-flow">
                          <span>Code</span>
                          <ArrowRight size={14} />
                          <span>Findings</span>
                          <ArrowRight size={14} />
                          <span>Practice</span>
                        </div>
                      </div>
                    ) : (
                      <div className="results-body">
                        {review.mode !== "model" && (
                          <div className="warning-banner">
                            This review used{" "}
                            {review.mode === "static_fallback"
                              ? "static analysis"
                              : "retrieval only"}
                            . No successful review model call completed.
                          </div>
                        )}
                        {ingestion && (
                          <details className="source-scope">
                            <summary>
                              {ingestion.owner}/{ingestion.repository} ·{" "}
                              {ingestion.files_included.length} files reviewed
                              {ingestion.truncated ? " · limited scope" : ""}
                            </summary>
                            <p>
                              {ingestion.skipped_file_count} files skipped ·{" "}
                              {ingestion.total_bytes.toLocaleString("en")}{" "}
                              bytes. This is a bounded Python review, not an
                              exhaustive repository audit.
                            </p>
                            <ul>
                              {ingestion.files_included.map((f) => (
                                <li key={f}>
                                  <code>{f}</code>
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                        {count === 0 ? (
                          <div className="empty">
                            <Check size={25} />
                            <h3>No findings in this review</h3>
                            <p>
                              This isn’t a guarantee that the code is
                              issue-free. Try another function or inspect the
                              sources below.
                            </p>
                          </div>
                        ) : (
                          review.findings
                            .slice(page * 5, page * 5 + 5)
                            .map((f) => (
                              <article className="finding" key={f.id}>
                                <div className="finding-meta">
                                  <span className={`severity ${f.severity}`}>
                                    {f.severity}
                                  </span>
                                  <span>{f.category}</span>
                                  {f.line_start && (
                                    <span className="line-ref">
                                      L{f.line_start}
                                      {f.line_end && f.line_end !== f.line_start
                                        ? `–${f.line_end}`
                                        : ""}
                                    </span>
                                  )}
                                </div>
                                <h3>{f.message}</h3>
                                <span className="origin">
                                  {labels[f.origin]}
                                </span>
                                <pre>{f.evidence}</pre>
                                <p>{f.explanation}</p>
                                <div className="suggestion">
                                  <span>Suggested improvement</span>
                                  <p>{f.suggestion}</p>
                                </div>
                                <Citations items={f.citations} />
                              </article>
                            ))
                        )}
                        {count > 5 && (
                          <div className="pagination">
                            <button
                              className="button"
                              disabled={page === 0}
                              onClick={() => setPage((p) => p - 1)}
                              aria-label="Previous findings"
                            >
                              <ChevronLeft size={16} />
                            </button>
                            <span>
                              Page {page + 1} of {Math.ceil(count / 5)}
                            </span>
                            <button
                              className="button"
                              disabled={(page + 1) * 5 >= count}
                              onClick={() => setPage((p) => p + 1)}
                              aria-label="Next findings"
                            >
                              <ChevronRight size={16} />
                            </button>
                          </div>
                        )}
                        <Provenance items={review.provenance} />
                        {review.questions.length > 0 && (
                          <div className="practice-next">
                            <MessageSquareText size={20} />
                            <div>
                              <strong>
                                {review.questions.length}{" "}
                                {review.questions.length === 1
                                  ? "question"
                                  : "questions"}{" "}
                                to practice
                              </strong>
                              <p>
                                Explain the decisions behind these findings.
                              </p>
                            </div>
                            <button
                              className="button"
                              disabled={!!busy}
                              onClick={() => navigate("Interview")}
                            >
                              Practice <ArrowRight size={15} />
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </section>
                </div>
              )}
              {view === "Interview" && (
                <div className="interview-layout">
                  <section className="panel interview-panel">
                    <div className="panel-heading">
                      <h2>
                        {interview?.completed
                          ? "Interview complete"
                          : "Your interview"}
                      </h2>
                      <span className="subtle-tag">
                        {interview
                          ? `TURN ${interview.turn_number}`
                          : "PRACTICE"}
                      </span>
                    </div>
                    {!review?.questions.length ? (
                      <div className="empty">
                        <MessageSquareText size={30} />
                        <h3>Start with something to talk about.</h3>
                        <p>
                          Complete a code review first. Its findings become your
                          interview questions.
                        </p>
                        <button
                          className="button primary"
                          onClick={() => navigate("Review")}
                        >
                          Go to review <ArrowRight size={16} />
                        </button>
                      </div>
                    ) : !interview ? (
                      <div className="interview-body">
                        <span className="eyebrow">
                          BASED ON YOUR LATEST REVIEW
                        </span>
                        <h2>
                          {Math.min(review.questions.length, 5)}{" "}
                          {review.questions.length === 1
                            ? "question"
                            : "questions"}
                          . Space to think.
                        </h2>
                        <p>
                          Explain your approach, name a tradeoff, and describe
                          how you’d test it. You’ll receive feedback after each
                          answer.
                        </p>
                        <button
                          className="button primary"
                          onClick={startInterview}
                          disabled={!!busy}
                        >
                          Start interview <ArrowRight size={16} />
                        </button>
                        <details>
                          <summary>Preview the practice questions</summary>
                          {review.questions.slice(0, 5).map((q) => (
                            <article className="question-preview" key={q.id}>
                              <span className="origin">
                                {labels[q.origin]} · {q.difficulty}
                              </span>
                              <h3>{q.question}</h3>
                              <p>{q.intent}</p>
                              <Citations items={q.citations} />
                            </article>
                          ))}
                        </details>
                      </div>
                    ) : (
                      <div className="interview-body">
                        {interview.assessment && (
                          <section className="assessment">
                            <div className="assessment-heading">
                              <h3>Feedback on your last answer</h3>
                              <strong>
                                {interview.assessment.score}
                                <small> / 5</small>
                              </strong>
                            </div>
                            <span className="origin">
                              {labels[interview.assessment.origin]}
                            </span>
                            {interview.assessment.origin !== "ai_generated" && (
                              <p className="warning-banner">
                                This assessment is rule-based. No successful
                                assessment model call completed.
                              </p>
                            )}
                            <p>{interview.assessment.feedback}</p>
                            <div className="two-columns">
                              <TextList
                                title="What worked"
                                items={interview.assessment.strengths}
                                empty="No strength signal yet."
                              />
                              <TextList
                                title="Go deeper on"
                                items={interview.assessment.gaps}
                                empty="No major gap detected."
                              />
                            </div>
                            <Citations items={interview.assessment.citations} />
                          </section>
                        )}
                        {interview.completed ? (
                          <>
                            <h2>You’ve worked through the questions.</h2>
                            <p>
                              Bring the findings and your answers together in a
                              feedback report.
                            </p>
                            {!report && (
                              <button
                                className="button primary"
                                disabled={!!busy}
                                onClick={() =>
                                  void run(
                                    "Preparing your feedback report…",
                                    async () =>
                                      setReport(
                                        await api(
                                          `interview/${interview.interview_session_id}/feedback`,
                                          reportSchema,
                                        ),
                                      ),
                                  )
                                }
                              >
                                Load feedback report <ArrowRight size={16} />
                              </button>
                            )}
                            {report && (
                              <section className="report">
                                <span className="origin">
                                  {labels[report.origin]} ·{" "}
                                  {report.aggregation_label}
                                </span>
                                <h3>{report.interview_readiness_summary}</h3>
                                <TextList
                                  title="Strengths"
                                  items={report.strengths}
                                  empty="Keep practicing to establish a pattern."
                                />
                                <TextList
                                  title="Recurring issues"
                                  items={report.recurring_issues}
                                  empty="No recurring issues found."
                                />
                                <TextList
                                  title="Recommended practice"
                                  items={report.recommended_tasks}
                                  empty="Review another function to keep practicing."
                                />
                                <details>
                                  <summary>
                                    Supporting findings (
                                    {report.supporting_findings.length})
                                  </summary>
                                  {report.supporting_findings.map((f) => (
                                    <article key={f.id}>
                                      <h4>{f.message}</h4>
                                      <span className="origin">
                                        {labels[f.origin]} · {f.severity} ·{" "}
                                        {f.category}
                                      </span>
                                      <p>{f.explanation}</p>
                                      <p>{f.suggestion}</p>
                                    </article>
                                  ))}
                                </details>
                              </section>
                            )}
                            <button
                              className="button"
                              disabled={!!busy}
                              onClick={() => navigate("Progress")}
                            >
                              View progress <TrendingUp size={16} />
                            </button>
                          </>
                        ) : (
                          interview.question && (
                            <>
                              <div className="question-heading">
                                <span className="severity low">
                                  {interview.question.difficulty}
                                </span>
                                <span className="origin">
                                  {labels[interview.question.origin]}
                                </span>
                              </div>
                              <h2 className="active-question">
                                {interview.question.question}
                              </h2>
                              <p>{interview.question.intent}</p>
                              <Citations items={interview.question.citations} />
                              <form
                                noValidate
                                onSubmit={(e) => {
                                  e.preventDefault();
                                  submitAnswer();
                                }}
                              >
                                <label htmlFor="answer">Your explanation</label>
                                <textarea
                                  id="answer"
                                  className="resize-none"
                                  value={answer}
                                  onChange={(e) => setAnswer(e.target.value)}
                                  maxLength={10000}
                                  disabled={!!busy}
                                  placeholder="I would approach this by…"
                                  aria-invalid={!!validation}
                                  aria-describedby="answer-validation"
                                />
                                <div
                                  id="answer-validation"
                                  className="validation"
                                  role="alert"
                                >
                                  {validation}
                                </div>
                                <button
                                  className="button primary"
                                  disabled={!!busy}
                                  aria-busy={!!busy}
                                >
                                  Submit answer <ArrowRight size={16} />
                                </button>
                              </form>
                            </>
                          )
                        )}
                        <Provenance items={interview.provenance} />
                      </div>
                    )}
                  </section>
                  <aside className="practice-guide">
                    <span className="eyebrow">A GOOD ANSWER HAS SHAPE</span>
                    <h3>Make your reasoning visible.</h3>
                    <dl>
                      <dt>The decision</dt>
                      <dd>What would you change, and why?</dd>
                      <dt>The tradeoff</dt>
                      <dd>What does your approach make easier or harder?</dd>
                      <dt>The evidence</dt>
                      <dd>How would you check that it works?</dd>
                    </dl>
                    <p>
                      Be specific. A small example can say more than a long
                      definition.
                    </p>
                  </aside>
                </div>
              )}
              {view === "Progress" && (
                <section className="panel progress-panel">
                  <div className="panel-heading">
                    <h2>Your practice patterns</h2>
                    <button
                      className="button"
                      disabled={!!busy}
                      onClick={() => void loadProgress()}
                    >
                      Refresh
                    </button>
                  </div>
                  {!progress ? (
                    <div className="empty">
                      <TrendingUp size={30} />
                      <h3>
                        {error
                          ? "Your history is temporarily unavailable."
                          : "Loading your practice history."}
                      </h3>
                      <p>
                        {error
                          ? "Use Refresh to try again."
                          : "Your review evidence will appear here."}
                      </p>
                    </div>
                  ) : !progress.evidence_sessions.length ? (
                    <div className="empty">
                      <TrendingUp size={30} />
                      <h3>Your first review starts the story.</h3>
                      <p>
                        Review code across multiple sessions to see what
                        improves and what needs more practice.
                      </p>
                      <button
                        className="button primary"
                        onClick={() => navigate("Review")}
                      >
                        Review some code <ArrowRight size={16} />
                      </button>
                    </div>
                  ) : (
                    <div className="progress-body">
                      <div className="progress-summary">
                        <div>
                          <strong>{progress.evidence_sessions.length}</strong>
                          <span>review sessions</span>
                        </div>
                        <div>
                          <strong>{progress.improved_areas.length}</strong>
                          <span>improving areas</span>
                        </div>
                        <div>
                          <strong>{progress.persistent_issues.length}</strong>
                          <span>recurring patterns</span>
                        </div>
                      </div>
                      <p className="muted">
                        {progress.time_window} · Based on repeated finding
                        categories, not an overall model score.
                      </p>
                      <div className="two-columns">
                        <TextList
                          title="Getting stronger"
                          items={progress.improved_areas}
                          empty="More sessions will help reveal improvement."
                        />
                        <TextList
                          title="Worth another look"
                          items={progress.persistent_issues}
                          empty="No persistent issue detected yet."
                        />
                      </div>
                      <TextList
                        title="Your next practice steps"
                        items={progress.next_practice_tasks}
                        empty="Try reviewing another function."
                      />
                      <details>
                        <summary>Supporting sessions</summary>
                        <ul className="session-evidence">
                          {progress.evidence_sessions.map((s) => (
                            <li key={s}>
                              <code>{s}</code>
                            </li>
                          ))}
                        </ul>
                      </details>
                      <button
                        className="button primary"
                        disabled={!!busy}
                        onClick={() => void loadProgress(true)}
                      >
                        Save progress snapshot <Check size={16} />
                      </button>
                    </div>
                  )}
                </section>
              )}
            </>
          )}
          <footer className="workspace-footer">
            <span>Clutch / Practice with evidence.</span>
            <span>Review → Explain → Improve</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
