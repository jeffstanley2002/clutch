import Link from "next/link";
import { Suspense } from "react";
import { AuthMessage } from "@/components/auth-message";
import {
  ArrowDown,
  ArrowUpRight,
  Code2,
  GitPullRequest,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { Login } from "@/components/login";
// Vercel never exposes anonymous practice; this value is determined at build time.
const local =
  !process.env.VERCEL && process.env.CLUTCH_ALLOW_LOCAL_ANONYMOUS === "true";
export default function Home() {
  return (
    <div className="landing">
      <header className="masthead">
        <Brand />
        <nav aria-label="Main">
          <a href="#how-it-works">How it works</a>
          <Link href="/workspace" className="nav-link">
            Workspace <ArrowUpRight size={16} />
          </Link>
        </nav>
      </header>
      <main id="main">
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="small-rule" /> CODE REVIEW MEETS INTERVIEW
              PRACTICE
            </div>
            <h1>
              Good code.
              <br />A better
              <br />
              <span>explanation.</span>
            </h1>
            <p className="hero-description">
              Find what needs work in your code. Then practice the questions an
              interviewer would ask about it.
            </p>
            <Suspense fallback={null}>
              <AuthMessage />
            </Suspense>
            <Login local={local} />
            <div className="trust">
              <ShieldCheck size={16} />
              Read-only reviews. Your repository stays yours.
            </div>
          </div>
          <div className="hero-example">
            <div className="example-top">
              <span className="eyebrow">A LOOK INSIDE CLUTCH</span>
              <span className="sample-label">Example session</span>
            </div>
            <div className="example-code">
              <div className="code-top">
                <span>
                  <Code2 size={15} /> collection.py
                </span>
                <span>Python</span>
              </div>
              <div className="code-lines">
                <div className="highlight-line">
                  <i>1</i>
                  <code>
                    <b>def</b> add_item(item, items=[]):
                  </code>
                </div>
                <div>
                  <i>2</i>
                  <code> items.append(item)</code>
                  <span className="line-dot" />
                </div>
                <div>
                  <i>3</i>
                  <code>
                    {" "}
                    <b>return</b> items
                  </code>
                </div>
              </div>
            </div>
            <div className="annotation">
              <div className="annotation-top">
                <span className="severity medium">Medium</span>
                <span>Correctness · line 1</span>
              </div>
              <h3>One default. Shared across calls.</h3>
              <p>
                The default list is created once. Calling this function again
                can return items from a previous call.
              </p>
              <details>
                <summary>See the suggested revision</summary>
                <pre>{`def add_item(item, items=None):\n    items = [] if items is None else items\n    items.append(item)\n    return items`}</pre>
              </details>
              <span className="source-label">
                Source · Python documentation: default arguments
              </span>
            </div>
            <div className="example-connector">
              <span />
              <ArrowDown size={17} />
              <span />
            </div>
            <div className="example-question">
              <span className="eyebrow">
                <MessageSquareText size={15} /> THE INTERVIEW FOLLOW-UP
              </span>
              <h3>“How would you test that two calls don’t share state?”</h3>
              <p>Understand the finding. Explain the decision.</p>
            </div>
          </div>
        </section>
        <section id="how-it-works" className="how">
          <div className="section-heading">
            <span className="eyebrow">A MORE USEFUL PRACTICE LOOP</span>
            <h2>
              Work on the code.
              <br />
              And the thinking behind it.
            </h2>
          </div>
          <div className="feature-grid">
            <article>
              <Code2 />
              <h3>Bring your real code</h3>
              <p>
                Paste a Python function or link a GitHub repository or pull
                request. Choose the role you’re preparing for.
              </p>
            </article>
            <article>
              <GitPullRequest />
              <h3>Follow the evidence</h3>
              <p>
                See the line, the concern, and a concrete improvement, with
                sources you can inspect.
              </p>
            </article>
            <article>
              <MessageSquareText />
              <h3>Practice your reasoning</h3>
              <p>
                Answer questions based on your review. Use the feedback to
                choose what to practice next.
              </p>
            </article>
          </div>
        </section>
      </main>
      <footer className="landing-footer">
        <Brand />
        <span>Built for the work before the interview.</span>
        <Link href="/workspace">
          Open workspace <ArrowUpRight size={15} />
        </Link>
      </footer>
    </div>
  );
}
