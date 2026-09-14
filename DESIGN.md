---
version: v4-nextjs-workbench
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

### Creative North Star

A focused code-review workbench for junior engineers preparing for interviews.
The signature is an annotated source excerpt connected to a specific follow-up
question: evidence first, explanation next. English-language, global audience;
no Japan-specific business or localization requirements. Product facts come
from `PRD.md`; API behaviors come from `src/clutch/schemas.py`.

### Migration decision — 2026-09-14

The user requested Next.js and Vercel because the Streamlit Community Cloud
startup surface was too slow. v4 preserves the v3 green/light identity, while
using React for immediate navigation and an independent pre-rendered entry.
Prior dark gradients/glow and generic AI marketing visuals were explicitly
rejected; those exclusions remain. Legacy Streamlit CSS is rollback-only.

## Colors

The exact palette in the frontmatter maps to `frontend/app/globals.css` root
variables. `text-muted` maps to `--muted`; `accent` maps to `--accent`;
`surface-2`, `border`, `bg`, `surface`, `accent-strong`, `accent-muted`,
`text`, `warning`, `danger`, and `scroll-*` map to their same-name variables.
Success reuses accent. These variables feed every screen and shared primitive.
DESIGN.md owns colors and font intent; `frontend/tests/design.test.ts` checks
palette drift against the runtime adapter. Do not add independent component
hex values. The legacy `.streamlit/config.toml` is retained only for rollback.

## Typography

Avenir Next / Segoe UI / system sans supplies display and body roles;
SFMono-Regular / Consolas / monospace supplies source, paths, and line numbers.
No remote font loads or late font swap. Sentence-case copy, restrained uppercase
utility labels. Landing display uses 52–76px; workspace headings 28–32px;
main product descriptions 12–17px. Use exact source text, never generated HTML.

## Layout

The landing uses a 1240px centered canvas with a substantial code-to-question
example. The workspace uses a 236px navigation rail and a two-column source /
findings view, collapsing to a single content column below 900px. At 650px the
rail becomes a compact horizontal stage navigator with reachable logout.
Interview uses a primary question/answer column and a quiet explanation guide;
progress uses evidence counts and text, not invented trend charts.
Natural document scrolling owns long forms. Code and long evidence lists have
local scrolling. Input precedes results in keyboard/DOM order. Source drafts,
results, and answers survive stage switching in memory; nothing sensitive is
saved in localStorage or a URL. Reload is intentionally not session recovery.

## Elevation & Depth

Flat white surfaces, 1px borders, subdued code chrome. No shadows, glass,
gradients, glowing decorations, ambient motion, or fake live-status indicators.

## Shapes

Controls use 6px radii, panels 8px, and the example group 10px. Small semantic
tags use 4px. Radius geometry is owned by shared stylesheet classes; the
frontmatter's legacy defaults remain the fallback for new primitives.

## Components

Canonical owners and interaction rules are in `UX-CONTRACT.md`.
`components/brand.tsx`, `ui.tsx`, and shared stylesheet classes own brand,
buttons, form controls, provenance, citations, lists, and feedback.

- Navigation: semantic buttons switch the three in-memory stages; tabs do not
  abandon requests. Disable stage changes during a pending operation.
- Forms: real labels, noValidate, inline errors associated with their fields,
  first-invalid-field focus, retained values on errors, and duplicate-submit
  locks. OS-owned native role selection is intentional; no custom popup shape.
- Findings: five per page, source line range, severity, evidence, suggestion,
  linked retrieved citation, and literal origin. Source text never renders as HTML.
- Output provenance: always distinguish AI-generated, rule-based,
  template-generated, and retrieved sources. Warn on model fallback. Expand
  stage details for model, prompt version, tokens, latency, cost, failure reason.
- Feedback: one stable page-level feedback region, inline validation, no
  browser alert/confirm/prompt. Loading has a labeled spinner and stable buttons.
- Global scrollbar: root standards properties and WebKit fallbacks share tokens;
  forced-colors mode delegates to system colors. Never hide scrollbars.
- Keyboard: visible 2px accent focus, native controls, skip link, reachable
  disclosures. Icons come from one Lucide set and never replace an action name.
- Motion: brief hover feedback and an active-request spinner only; respect
  reduced-motion preferences.

## Do's and Don'ts

Do show actual code concerns and explain the next action. Do preserve privacy
and provenance across all screens. Do use real evidence counts.
Don't promise correctness, invented progress, hosted timing, or model success.
Don't expose provider names/keys/routing in the primary practice flow; keep
safe model provenance in its disclosure. Don't add decorative dashboards,
AI sparkle icons, or unrequested dark themes.
