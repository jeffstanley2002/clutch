---
version: alpha
name: "Clutch"
description: "A focused code-review workbench that turns evidence into interview practice."
colors:
  primary: "#365FD9"
  primary-strong: "#2448B5"
  focus: "#88A4FF"
  background: "#F5F7FB"
  surface: "#FFFFFF"
  surface-muted: "#EEF2F8"
  text: "#172033"
  text-muted: "#5E6A7D"
  border: "#D9E0EC"
  warning: "#C77700"
  danger: "#B42318"
typography:
  sans:
    fontFamily: '"Avenir Next", Avenir, "Segoe UI", sans-serif'
  mono:
    fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace'
rounded:
  DEFAULT: "0.55rem"
  sm: "0.35rem"
  md: "0.55rem"
  lg: "0.8rem"
spacing:
  section-gap: "2rem"
  page-max: "76rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
  button-primary-hover:
    backgroundColor: "{colors.primary-strong}"
  focus-ring:
    backgroundColor: "{colors.focus}"
    size: "3px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  card-muted:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text-muted}"
  divider:
    backgroundColor: "{colors.border}"
    height: "1px"
  status-warning:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.text}"
  status-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.surface}"
  provenance-label:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text-muted}"
---

# Clutch Design System

## Overview

### Creative North Star

Clutch should feel like an engineer's annotated review notebook: precise,
calm, and evidence-led, with blue review marks connecting a concrete code
observation to the question it creates. The authenticated product is a working
surface; its public sign-in gate should preview that same workflow rather than
switching to a generic marketing aesthetic.

### Product context and register

- **Audience and primary job:** Junior engineers reviewing code before an
  interview and turning weaknesses into practice prompts.
- **Target market and evidence:** Global English-language portfolio demo, as
  defined by `PRD.md`; no market-specific workflow is assumed.
- **Locale and language policy:** English-only v1. User code remains verbatim.
- **Usage scene:** Laptop-first, focused sessions with dense code and concise
  feedback; narrow layouts must still reflow without horizontal page scroll.
- **Register:** Product.
- **Memorable signature:** Each review moves from evidence to an interviewer
  follow-up, visually joined by the same restrained cobalt accent.
- **Restraint:** Code, findings, citations, and recovery guidance take priority
  over decoration or animation.
- **Anti-references:** Avoid cyberpunk terminal styling, acid-on-black AI
  dashboards, generic gradient hero cards, and gamified interview scoring.
- **Token ownership/runtime mapping:** This file owns visual intent and exact
  design tokens. `.streamlit/config.toml` maps supported theme tokens; the small
  style adapter in `frontend/app.py` maps font, focus, textarea, width, and
  scrollbar behavior that Streamlit does not expose in its theme file.

## Colors

Cobalt `primary` marks the single main action and connective review emphasis.
Blue-gray surfaces keep long code sessions quiet. `warning` and `danger` are
semantic only and must always appear with text, never as the sole signal.
`focus` is deliberately lighter than the action color so keyboard location is
unambiguous. In forced-colors mode, system colors own focus and scrollbars.

## Typography

Use Avenir Next where available, then Segoe UI and system sans for product
copy. Code and technical evidence use SFMono-Regular or a platform monospace.
Sentence case is standard; uppercase is reserved for short utility eyebrows
and severity labels. Body copy stays at a 16px baseline with compact but
readable line lengths.

## Layout

The workbench uses one centered column up to 76rem. Input precedes results so
keyboard and screen-reader order follows the task. Major sections use a 2rem
rhythm; related finding details stay inside one bordered container. At narrow
widths, all content stacks and code owns any necessary internal overflow.
Loading, errors, and empty guidance occupy the result region without moving the
input controls.

The public sign-in gate uses one bordered, cobalt-ruled hero with two balanced
columns: concise product value and login on the left, the real three-step
practice loop on the right. The login explanation stays directly below its
button. At narrow widths, the value, action, and workflow preview become one
natural reading order without horizontal page overflow.

## Elevation & Depth

Hierarchy comes from surface tone, border, spacing, and type—not decorative
shadows. Static finding and question cards remain flat. Overlays may use the
Streamlit platform elevation until the app introduces a shared overlay system.

## Shapes

Controls and review containers use the 0.55rem working radius. The 0.8rem large
radius is reserved for high-level grouped surfaces. Avoid pills except for
compact status tokens whose shape communicates their token-like behavior.

## Components

### Foundational visual states

Interactive controls need visible hover, pressed, disabled/busy, and a 3px
`focus` outline. Loading uses one stable spinner message. Empty states explain
what useful input looks like; errors state the failure and the next recovery
step. Success, warning, and error never rely on color alone.

### Buttons and actions

One solid cobalt action starts a review. Secondary actions use Streamlit's
neutral treatment. Button labels use concrete verbs and retain their geometry
while busy. Destructive actions are out of scope for read-only v1.

### Navigation and data display

The product uses one horizontal workflow rail—Review → Interview → Progress—
because these are actual stages in the practice loop. Streamlit's segmented
control owns its keyboard and selection behavior. Navigation remains above the
active work surface, uses the same stage names everywhere, and stacks naturally
with the document at narrow widths. Request metadata is utility copy,
subordinate to findings and questions.

GitHub scope is always rendered as a compact factual line—files included,
files skipped, truncation, and `full-codebase analysis: no`. This line is part
of the result contract, not optional diagnostic decoration.

### Provenance and trust labels

Every finding, follow-up question, interview assessment, retrieved citation,
and final aggregation names its origin in text. Model success uses the calm
primary/success treatment; missing or failed model calls use a persistent
warning adjacent to the affected output. Provenance labels stay visually quiet
through `surface-muted` and `text-muted`, but they appear before the content
they qualify so a user never needs to infer whether AI ran. A disclosure may
show model, prompt version, tokens, latency, estimated cost, and safe failure
category; it never shows raw prompts, code, answers, or provider payloads.

### Forms and overlays

Labels name user concepts: “Target role” and “Python code.” Help text states
limits and privacy behavior. Validation preserves input and gives a correction.
The code textarea has a generous fixed starting height and no manual resize.
No browser-native alerts or destructive confirmation flows are used.

### Iconography

Use Streamlit's established icons only when an icon improves scanning. Actions
retain text labels; decorative code or AI glyphs are avoided.

### Motion

Motion communicates loading or a state transition only. Do not add ambient or
decorative animation. Respect the platform's reduced-motion behavior.

### Content and data visualization

Voice is direct and practical: identify evidence, explain why it matters, and
name the next action. Confidence is supporting metadata, not a performance
score. Future charts require a textual summary and use semantic colors from
this palette.

## Do's and Don'ts

- **Do:** Keep the evidence-to-question relationship visible and predictable.
- **Do:** Explain empty, error, and fallback states in plain language.
- **Do:** State bounded GitHub analysis scope and output provenance literally.
- **Don't:** Style the product like a terminal or imply model certainty it does
  not have.
- **Don't:** Use “AI” as a generic label for deterministic or template output.
- **Don't:** Let metadata, badges, or decoration compete with submitted code and
  actionable findings.
