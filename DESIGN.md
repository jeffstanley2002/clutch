---
version: v3-editorial
name: "Clutch"
description: "A restrained, evidence-led code-review workbench that turns findings into interview practice."
colors:
  bg: "#F7F6F3"
  surface: "#FFFFFF"
  surface-2: "#F1F1EE"
  border: "#E1E1DC"
  accent: "#267A5B"
  accent-strong: "#1B5C44"
  accent-muted: "#E3F0E9"
  text: "#171717"
  text-muted: "#666666"
  warning: "#8A5A00"
  danger: "#B3261E"
  success: "#267A5B"
  scroll-thumb: "#C7C7C0"
  scroll-track: "#F1F1EE"
  scroll-hover: "#666666"
  scroll-active: "#267A5B"
typography:
  sans:
    fontFamily: '"Avenir Next", "Segoe UI", sans-serif'
  mono:
    fontFamily: '"SFMono-Regular", Consolas, monospace'
rounded:
  DEFAULT: "0.5rem"
  sm: "0.35rem"
  md: "0.5rem"
  lg: "0.6rem"
spacing:
  section-gap: "2rem"
  page-max: "76rem"
components:
  page:
    backgroundColor: "{colors.bg}"
  code-highlight:
    backgroundColor: "{colors.accent-muted}"
    textColor: "{colors.accent-strong}"
  status-success:
    backgroundColor: "{colors.success}"
    textColor: "#FFFFFF"
  scrollbar:
    backgroundColor: "{colors.scroll-track}"
  scrollbar-thumb:
    backgroundColor: "{colors.scroll-thumb}"
  scrollbar-thumb-hover:
    backgroundColor: "{colors.scroll-hover}"
  scrollbar-thumb-active:
    backgroundColor: "{colors.scroll-active}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
  button-primary-hover:
    backgroundColor: "{colors.accent-strong}"
  focus-ring:
    backgroundColor: "{colors.accent}"
    size: "2px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  card-muted:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text-muted}"
  divider:
    backgroundColor: "{colors.border}"
    height: "1px"
  status-warning:
    backgroundColor: "{colors.warning}"
    textColor: "#FFFFFF"
  status-danger:
    backgroundColor: "{colors.danger}"
    textColor: "#FFFFFF"
  provenance-label:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text-muted}"
---

# Clutch Design System

## Overview

### v3 direction note

Clutch went through two prior visual registers: v1 was a restrained light
"annotated review notebook" (cobalt accent, no gradients); v2 was a bold,
requested dark-mode departure with a violet-to-cyan gradient. v3 reverses
course deliberately, after concrete feedback that v2 read as a generic
"AI-generated landing page" — gradient headline text, glowing dots, glass
panels, a purple/blue palette associated with contemporary AI-product
branding, and an abstract workflow diagram in place of the actual product.
v3 keeps v1's restraint and v2's native-Streamlit-widget habits (badges,
`st.status`, `st.metric`, `st.toast`, sidebar navigation), but returns to a
light, editorial developer-tool palette with a green accent, shows an actual
annotated code-review mock in the hero instead of an abstract pipeline
diagram, and rewrites marketing copy to describe concrete product behavior
instead of generic transformation language ("X turns Y into Z"). The
evidence-first product principles (provenance, grounded citations, honest
confidence, no fake certainty) are unchanged across all three versions.

### Creative North Star

Clutch should read as a serious, practical developer tool — closer to a
code-review or linting product than an AI marketing site. The hero shows the
product itself (an annotated finding with a follow-up question) in the first
few seconds rather than asking the visitor to interpret an abstract workflow
diagram. One muted green accent marks primary actions and the small set of
semantic tags; it is not a gradient and does not glow. The authenticated
workbench and the public sign-in gate share the same restrained palette and
component language.

### Product context and register

- **Audience and primary job:** Junior engineers reviewing code before an
  interview and turning weaknesses into practice prompts.
- **Target market and evidence:** Global English-language portfolio demo, as
  defined by `PRD.md`; no market-specific workflow is assumed.
- **Locale and language policy:** English-only v1. User code remains verbatim.
- **Usage scene:** Laptop-first, focused sessions with dense code and concise
  feedback; narrow layouts must still reflow without horizontal page scroll.
- **Register:** Product, editorial, developer-tool — not marketing/SaaS.
- **Memorable signature:** Each review moves from evidence to an interviewer
  follow-up; the hero demonstrates this directly with one real-looking
  annotated finding instead of describing it abstractly.
- **Restraint:** Code, findings, citations, and recovery guidance take
  priority over decoration. No gradients, glassmorphism, glow, or ambient
  motion anywhere in the product.
- **Anti-references:** Avoid cyberpunk terminal styling, dark purple/blue
  "AI product" gradients and glow, gamified interview scoring, oversized
  gradient display type, generic two-column SaaS hero layouts, and vague
  transformation copy ("X turns Y into Z").
- **Copy discipline:** Prefer concrete, observable behavior over abstract
  claims. E.g. "Questions an interviewer might ask next" beats "realistic
  follow-up questions"; "Review a pull request before the interview" beats
  "GitHub repo review."
- **Token ownership/runtime mapping:** This file owns visual intent and exact
  design tokens. `.streamlit/config.toml` maps supported theme tokens; the
  small style adapter in `frontend/app.py` maps font, focus, textarea, width,
  and scrollbar behavior that Streamlit does not expose in its theme file.

## Colors

The Streamlit config explicitly sets `base = "light"`; the application CSS
uses `color-scheme: light`. These apply to the app, not the host-owned Cloud
wake screen. Landing styles consume the same `--clutch-*` semantic variables
as the workbench; scope custom typography under `.stApp` to override
Streamlit Markdown defaults predictably.

The app runs on a warm off-white (`bg`) page with white (`surface`) cards and
a light neutral (`surface-2`) for the sidebar and code chrome. One muted green
`accent` marks the primary action, links, active nav, and the small set of
semantic tags (e.g. a finding's category); `accent-muted` is its pale
background for tag chips. `warning` and `danger` are semantic only and must
always appear with text or an icon, never as the sole signal. `focus` reuses
`accent` at 2px so keyboard location is visible without introducing a second
color. In forced-colors mode, system colors own focus and scrollbars. Scrollbar
tokens map to `--clutch-scroll-*` globally, with standards-based rules and
WebKit fallbacks for track, thumb, hover, and active behavior.

## Typography

Use Avenir Next, Segoe UI, and system sans for product copy. Code and
technical evidence use SFMono-Regular, Consolas, or a platform monospace.
Fonts are system-local: no Google Fonts stylesheet, remote font face, or
late font swap. The Streamlit theme and CSS use the same family stacks.
Sentence case is standard; short uppercase tags
(severity, category, difficulty, status badges) are the only intentional use
of letter-spacing and all-caps — never body copy or headlines. Hero headline
sizing uses `clamp(2rem, 3.2vw, 3rem)` with a 22ch maximum line length,
well short of full-bleed display type. Body copy stays at a 16px baseline
with compact but readable line lengths (~17–19px in the hero column).

## Layout

The workbench uses one centered column up to 76rem. Input precedes results so
keyboard and screen-reader order follows the task. Major sections use a 2rem
rhythm; related finding details stay inside one bordered container. At narrow
widths, all content stacks and code owns any necessary internal overflow.
Loading, errors, and empty guidance occupy the result region without moving
the input controls. Review source and submit controls disable during a pending
review. The empty review includes a copyable example inside a native expander.

The public sign-in gate uses one thin-bordered white hero card with two
balanced columns: a plain wordmark, a concrete two-line headline, one short
paragraph, a trust line, and the sign-in form on the left; an actual annotated
code-review mock (filename, code, one finding with tag/explanation, one
interview follow-up) on the right, labeled "Example finding" so it is never
mistaken for a live result. Below the hero, three plain feature blocks
(heading + one sentence, no cards or icons) state real product behavior, and
the three technical-credibility panels (pipeline / agent boundary /
production signals) live inside an “Under the hood” disclosure for readers
who want implementation detail. The code example highlights the finding line
and offers a suggested revision in a native HTML details/summary disclosure.
These disclosures work without Python reruns, requests, or JavaScript. A small
masthead and footer link directly to the project source and notes. At narrow
widths, the columns stack in natural reading order without
horizontal overflow. The authenticated workbench moves navigation into the
sidebar (wordmark, workflow switcher, live session metrics) so the main
column is reserved for the active page.

## Elevation & Depth

Hierarchy comes from surface tone, thin 1px borders, spacing, and type — not
shadows, glow, or gradient fills. Cards are flat at rest and on hover; the
code and explanation inside a card are the loudest thing in it. Overlays
(`st.status`, `st.expander`) use the Streamlit platform elevation.

## Shapes

Controls and containers use a 0.5rem working radius — small and square-ish,
not pill-like. The 0.6rem large radius is reserved for the hero and other
high-level grouped surfaces. Pills/rounded-full shapes are reserved for
short status tags (severity, difficulty, origin badges); marketing chips and
decorative pill rows are avoided.

## Components

### Foundational visual states

Interactive controls need visible hover, pressed, disabled/busy, and a 2px
`accent` focus outline. Loading uses one stable spinner message. Empty states
explain what useful input looks like; errors state the failure and the next
recovery step. Success, warning, and error never rely on color alone.

### Buttons and actions

One solid `accent`-filled primary action starts a review, starts/submits an
interview turn, or saves a snapshot; each carries a concrete-verb label (e.g.
"Email me a login link", "Review code", "Submit answer") and a matching
Material icon — never vague labels like "Get started" or "Explore." Secondary
actions use Streamlit's neutral treatment. Buttons retain their geometry
while busy and never scale, glow, or lift on hover. Destructive actions are
out of scope for read-only v1.

### Navigation and data display

Workflow navigation—Review → Interview → Progress—lives in the sidebar as a
vertical native radio group with short stage descriptions, alongside the
wordmark and live session metrics
(confidence, finding count, interview turn) rendered with `st.metric`.
Streamlit's radio group owns its keyboard and selection behavior. Vertical
stacking avoids wrapped navigation labels at the default sidebar width. The
same stage names are used everywhere, and the sidebar stacks above the main
column at narrow widths. Request metadata is utility copy, subordinate to
findings and questions.

GitHub scope is always rendered as a compact factual line—files included,
files skipped, truncation, and `full-codebase analysis: no`. This line is part
of the result contract, not optional diagnostic decoration.

### Provenance and trust labels

Every finding, follow-up question, interview assessment, retrieved citation,
and final aggregation names its origin in text. Model success uses
`st.success` with an icon; missing or failed model calls use a persistent
`st.warning` adjacent to the affected output. Provenance labels stay visually
quiet through `surface-2` and `text-muted` captions, but they appear before
the content they qualify so a user never needs to infer whether AI ran.
Per-stage disclosure uses one collapsed `st.status` row per stage (icon
communicates running/complete/error) that expands to badges and `st.metric`
values for model, prompt version, tokens, latency, and estimated cost; it
never shows raw prompts, code, answers, or provider payloads.

### Forms and overlays

Labels name user concepts: "Target role" and "Python code." Help text states
limits and privacy behavior. Validation preserves input and gives a
correction. The code textarea has a generous fixed starting height and no
manual resize. No browser-native alerts or destructive confirmation flows are
used.

### Iconography

Use Streamlit's established Material icons only when an icon improves
scanning (button actions, sidebar metrics, status states). No decorative
glowing dots, AI glyphs, or ornamental icon use in marketing copy.

### Motion

Motion communicates loading, a state transition, or a one-time completion
moment only (`st.balloons` on finishing an interview, `st.toast` for a
transient save confirmation). No hover lift, glow, or ambient/looping
animation anywhere. The shared stylesheet disables animation and transitions
when reduced motion
is requested.

### Content and data visualization

Voice is direct, concrete, and practical: identify evidence, explain why it
matters, and name the next action. Avoid abstract marketing formulas
("X turns Y into Z") and vague feature claims; describe observable behavior
instead. Confidence is supporting metadata, shown as an `st.metric`, not a
performance score or leaderboard. Progress charts (`st.bar_chart`) summarize
only real derived counts (e.g. improved vs. recurring categories), never a
fabricated trend, and use the `accent` color from this palette.

## Do's and Don'ts

- **Do:** Keep the evidence-to-question relationship visible and predictable.
- **Do:** Show the actual product (an annotated finding) in the hero instead
  of an abstract workflow diagram.
- **Do:** Explain empty, error, and fallback states in plain language.
- **Do:** State bounded GitHub analysis scope and output provenance literally.
- **Do:** Reach for native Streamlit widgets (`st.badge`, `st.status`,
  `st.metric`, `st.toast`) before hand-rolled HTML wherever one exists.
- **Don't:** Use gradients, glassmorphism, glow, or a dark purple/blue palette
  — these read as generic contemporary AI-product branding, not as this
  product.
- **Don't:** Imply model certainty the system does not have, or gamify the
  interview score into a leaderboard/streak mechanic.
- **Don't:** Use "AI" as a generic label for deterministic or template output.
- **Don't:** Use vague CTAs ("Get started", "Explore") or abstract
  transformation copy where a concrete action or behavior would do.
