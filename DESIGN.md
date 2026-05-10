---
version: 1.0.0
name: Paper & Ink
description: "Claude Design–inspired editorial course template for genie-learning — warm paper tones, Instrument Serif display type, oklch accent system, per-module tint cycling, dark mode, and a hidden Tweaks panel for theme/accent/density customization."
designer: Claude Design (Anthropic) — adapted for genie-learning by Café
colors:
  # Paper & ink (light)
  paper:       "#FAF7EF"
  paper-2:     "#F4F0E5"
  paper-3:     "#ECE7D7"
  ink:         "#1A1714"
  ink-soft:    "#2A2620"
  muted:       "#756E60"
  muted-soft:  "#9A9384"

  # Accent — moss (default), terracotta, indigo variants
  # All defined in oklch for perceptual uniformity
  accent-light:
    moss:       "oklch(0.48 0.10 145)"      # Default green-moss
    terracotta: "oklch(0.58 0.13 35)"       # Warm earth
    indigo:     "oklch(0.50 0.13 265)"      # Cool blue
  accent-dark:
    moss:       "oklch(0.78 0.10 145)"
    terracotta: "oklch(0.78 0.12 35)"
    indigo:     "oklch(0.78 0.12 265)"

  # Per-module tints (cycling, 6 hues)
  # Same chroma (0.035) — only hue rotates
  tint-hues: [80, 145, 35, 260, 200, 320]

  # Semantic
  correct:     "oklch(0.55 0.12 150)"
  correct-bg:  "oklch(0.95 0.05 150)"
  wrong:       "oklch(0.52 0.16 25)"
  wrong-bg:    "oklch(0.95 0.04 25)"

  # Flashcard back
  lavender:     "oklch(0.92 0.04 290)"
  lavender-deep:"oklch(0.30 0.08 290)"

typography:
  display-serif:
    fontFamily: "Instrument Serif"
    fontWeight: 400
    lineHeight: 0.98
    letterSpacing: -0.012em
  body:
    fontFamily: Inter
    fontSize: 16.5px
    lineHeight: 1.72
  body-mini:
    fontFamily: Inter
    fontSize: 14.5px
    lineHeight: 1.6
  mono:
    fontFamily: "JetBrains Mono"
    fontSize: 13px
  eyebrow:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: 600
    letterSpacing: 0.16em
    textTransform: uppercase
  button:
    fontFamily: Inter
    fontSize: 14.5px
    fontWeight: 500

rounded:
  radius: 14px       # Cards
  radius-sm: 10px    # Buttons, inputs
  badge: 9999px      # Pill badges
  hero: 22px         # Hero section

spacing:
  container: 1180px
  sidebar: 268px
  section-y: 48px
  density-y: 24px    # Reduced to 14px in compact mode

layout:
  structure: "sticky header + sidebar-left + content-main"
  sidebar-behavior: "desktop: fixed sticky at 80px; mobile: drawer overlay from left"
  header: "sticky top-0, frosted glass (92% paper + blur(8px)), 60px height"
  content-max-w: "68ch for prose; modules grid: 3-col (1 sm:2 xl:3)"
  hero: "rounded-22px, paper border, gradient ornament + stitch footer"

components:
  hero:
    structure: "eyebrow + display-serif title + subtitle + dual CTA + 4-col meta strip"
    ornament: "radial gradient accent-soft at top-right + paper-to-paper-2 linear bg"
    stitch: "dashed hairline border at bottom edge"
    meta-strip: "modules/glossary/quizzes/flashcards counts in serif 28px"
  module-card:
    structure: "02-number (instrument serif italic 44px) + title + purpose + footer with name + arrow"
    tint: "cycles through 6 oklch hues per module index"
    hover: "translateY(-2px) + box-shadow + border-color darken"
    aspect: "auto-height grid card"
  flashcard:
    aspect-ratio: "16/10"
    max-height: 480px
    flip: "3D rotateY(180deg) at 0.55s cubic-bezier(.2,.7,.2,1)"
    front: "paper background"
    back: "lavender background, lavender-deep text"
    perspective: 1400px
  quiz:
    option: "row with JetBrains Mono key badge, 12px rounded border"
    states: "default → hover (ink border) → selected (ink bg) → correct (correct green) → wrong (error red)"
    pill-nav: "rounded-full chips for quiz selection with progress counter"
  glossary:
    search: "sticky search bar at 60px, rounded-xl, search icon prefix"
    letter-column: "instrument serif 96px italic accent for alphabetical groups"
    term-card: "serif 22px term + prose-mini definition, border-b hairline"
  tweaks-panel:
    trigger: "fixed bottom-18 right-18, 44px circular, ink bg, gear/cog icon"
    panel: "280px width, 16px rounded, shadow-elevated, origin-bottom-right"
    controls: "segmented-control toggle (3-seg) for theme + swatch-row for 3 accent colors + seg-control for density"
    segments: "grid auto-flow-column with active state (paper bg + shadow)"
  sidebar-nav:
    item: "row with 4px accent mark + label + mono count badge"
    active: "paper-2 bg + 600 weight + accent mark"
    hover: "paper-2 bg"
  mobile-drawer:
    backdrop: "fixed fullscreen, rgba(0,0,0,0.4)"
    panel: "280px width, left slide-in, paper bg, hairline-2 border-right"
    close: "X button top-right + backdrop click"
  footer:
    type: "minimal — only lock icon + progress hint text in sidebar bottom"
    no-page-footer: "content ends after last section"

behaviors:
  page-navigation:
    type: "SPA — client-side Vue 3 view switching"
    sections: "overview → tutorial → modules (list + detail) → glossary → quizzes → flashcards → podcast"
    transitions: "fadeUp 0.35s cubic-bezier(.2,.7,.2,1)"
    keyboard: "Escape closes drawer/modal; Enter triggers nav items"
  progress:
    storage: "localStorage keyed by course slug"
    persistence: "quiz answers, flashcard seen state, current view"
  responsive:
    breakpoint: "1024px — sidebar collapses to drawer"
    mobile: "single column, drawer nav, full-width content"
    tablet: "2-col module grid"
    desktop: "sidebar + 3-col module grid, sticky search"
  reduced-motion:
    strategy: "prefers-reduced-motion: reduce → all animations 0.001s, flip-card transition none"
  paper-grain:
    type: "SVG fractalNoise filter overlay (fixed, pointer-events-none)"
    light-mode: "multiply blend, 0.5 opacity"
    dark-mode: "screen blend, 0.4 opacity"
    source: "<svg> feTurbulence baseFrequency=0.85 numOctaves=2 feColorMatrix alpha=0.045"

dark-mode:
  inversion: "paper → dark (#131211), ink → light (#ECE7DA)"
  accent: "lightens (e.g. moss 0.48→0.78)"
  tint: "darkens to 0.26 chroma; tint-ink lightens to 0.88"
  grain: "screen blend instead of multiply"
  shadows: "black-based instead of ink-based"
  btn-primary: "paper bg, ink text (inverted)"

design-tokens-format:
  system: "CSS custom properties on :root and [data-theme][data-accent] selectors"
  color-space: "oklch throughout for perceptual uniformity"
  dark-mode: "separate [data-theme='dark'] block overriding each token"
  accent-variants: "separate [data-accent='terracotta'] and [data-accent='indigo'] blocks"
  density: "single --density-y var toggled by [data-density]"
  no-tailwind-design-tokens: "all tokens in CSS; Tailwind only for layout grid/flex/typography utilities"
