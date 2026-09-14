import { z } from "zod";
export const origin = z.enum([
  "ai_generated",
  "deterministic_static",
  "template_generated",
  "retrieved_citation",
]);
export const citation = z.object({
  source_id: z.string(),
  title: z.string(),
  url: z.string().nullable().optional(),
  origin,
});
export const stage = z.object({
  stage: z.string(),
  status: z.string(),
  origin,
  model_name: z.string().nullable().optional(),
  prompt_version: z.string().nullable().optional(),
  input_tokens: z.number().nullable().optional(),
  output_tokens: z.number().nullable().optional(),
  latency_ms: z.number(),
  estimated_cost_usd: z.number(),
  failure_category: z.string().nullable().optional(),
});
export const finding = z.object({
  id: z.string(),
  severity: z.enum(["low", "medium", "high"]),
  category: z.string(),
  message: z.string(),
  evidence: z.string(),
  line_start: z.number().nullable().optional(),
  line_end: z.number().nullable().optional(),
  explanation: z.string(),
  suggestion: z.string(),
  citations: z.array(citation),
  origin,
});
export const question = z.object({
  id: z.string(),
  finding_id: z.string().nullable().optional(),
  question: z.string(),
  intent: z.string(),
  difficulty: z.enum(["easy", "medium", "hard"]),
  citations: z.array(citation),
  origin,
});
export const review = z.object({
  findings: z.array(finding),
  questions: z.array(question),
  mode: z.enum(["model", "static_fallback", "retrieval_only"]),
  confidence: z.number(),
  citations_used: z.array(citation),
  provenance: z.array(stage),
  request_id: z.string(),
  latency_ms: z.number(),
});
export const ingestion = z.object({
  source_type: z.string(),
  owner: z.string(),
  repository: z.string(),
  files_included: z.array(z.string()),
  skipped_file_count: z.number(),
  total_bytes: z.number(),
  truncated: z.boolean(),
});
export const githubReview = z.object({ ingestion, review });
export const turn = z.object({
  interview_session_id: z.string(),
  status: z.enum(["active", "completed"]),
  turn_number: z.number(),
  question: question.nullable(),
  assessment: z
    .object({
      score: z.number(),
      strengths: z.array(z.string()),
      gaps: z.array(z.string()),
      feedback: z.string(),
      citations: z.array(citation),
      origin,
      provenance: stage.nullable().optional(),
    })
    .nullable(),
  provenance: z.array(stage),
  completed: z.boolean(),
});
export const report = z.object({
  session_id: z.string(),
  strengths: z.array(z.string()),
  recurring_issues: z.array(z.string()),
  recommended_tasks: z.array(z.string()),
  interview_readiness_summary: z.string(),
  supporting_findings: z.array(
    finding
      .omit({ evidence: true, citations: true })
      .extend({ citation_ids: z.array(z.string()) }),
  ),
  origin,
  aggregation_label: z.string(),
});
export const progress = z.object({
  user_id: z.string(),
  time_window: z.string(),
  improved_areas: z.array(z.string()),
  persistent_issues: z.array(z.string()),
  next_practice_tasks: z.array(z.string()),
  evidence_sessions: z.array(z.string()),
});
export type Review = z.infer<typeof review>;
export type Turn = z.infer<typeof turn>;
export type Report = z.infer<typeof report>;
export type Progress = z.infer<typeof progress>;
export type Ingestion = z.infer<typeof ingestion>;
export const labels: Record<z.infer<typeof origin>, string> = {
  ai_generated: "AI-generated",
  deterministic_static: "Rule-based",
  template_generated: "Template-generated",
  retrieved_citation: "Retrieved source",
};
export const sample = `def add_item(item, items=[]):\n    items.append(item)\n    return items`;
export function githubUrl(value: string): string | null {
  try {
    const url = new URL(value.trim());
    if (
      url.protocol !== "https:" ||
      url.hostname !== "github.com" ||
      url.port ||
      url.username ||
      url.password ||
      !/^\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\/pull\/[1-9]\d*)?\/?$/.test(
        url.pathname,
      )
    )
      return null;
    if (url.pathname.split("/").some((p) => p === "." || p === ".."))
      return null;
    return `https://github.com${url.pathname.replace(/\/$/, "")}`;
  } catch {
    return null;
  }
}
export function safeHref(value?: string | null): string | undefined {
  try {
    const url = new URL(value ?? "");
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}
