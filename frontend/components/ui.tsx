import { ArrowUpRight, LoaderCircle } from "lucide-react";
import { z } from "zod";
import { citation, labels, safeHref, stage } from "@/lib/contracts";
export function Busy({ text }: { text: string }) {
  return (
    <div className="busy" role="status">
      <LoaderCircle className="spin" size={18} />
      {text}
    </div>
  );
}
export function Citations({ items }: { items: z.infer<typeof citation>[] }) {
  return (
    <div className="citations">
      {Array.from(new Map(items.map((c) => [c.source_id, c])).values()).map(
        (c) =>
          safeHref(c.url) ? (
            <a
              key={c.source_id}
              href={safeHref(c.url)}
              target="_blank"
              rel="noreferrer"
            >
              {c.title}
              <ArrowUpRight size={13} />
              <span className="sr-only">
                {" "}
                (retrieved source, opens in a new tab)
              </span>
            </a>
          ) : (
            <span key={c.source_id}>{c.title} · Retrieved source</span>
          ),
      )}
    </div>
  );
}
export function Provenance({ items }: { items: z.infer<typeof stage>[] }) {
  return (
    <details className="provenance">
      <summary>How this result was produced</summary>
      {items.map((s, i) => (
        <div className="provenance-row" key={`${s.stage}-${i}`}>
          <strong>{s.stage.replaceAll("_", " ")}</strong>
          <span>
            {labels[s.origin]} · {s.status}
          </span>
          <span>
            {s.model_name || "No model call"} ·{" "}
            {s.prompt_version || "No prompt version"}
          </span>
          <span>
            {Math.round(s.latency_ms)} ms · {s.input_tokens ?? 0} input /{" "}
            {s.output_tokens ?? 0} output tokens · $
            {s.estimated_cost_usd.toFixed(6)}
          </span>
          {s.failure_category && (
            <span className="warning-text">
              {s.failure_category.replaceAll("_", " ")}
            </span>
          )}
        </div>
      ))}
    </details>
  );
}
export function TextList({
  title,
  items,
  empty,
}: {
  title: string;
  items: string[];
  empty: string;
}) {
  return (
    <section className="list-section">
      <h3>{title}</h3>
      {items.length ? (
        <ul>
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">{empty}</p>
      )}
    </section>
  );
}
