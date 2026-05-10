---
name: genie-render
description: Render a generated Genie Learning course as a single interactive HTML file (Vue 3 + Tailwind via CDN, Notion-styled). The output lets a learner navigate the overview, tutorial, glossary, modules, quizzes, derived flashcards, and podcast — all in one self-contained page that opens via file://. Trigger with /genie-render <owner-name>.
allowed-tools: Bash(python:*), Bash(py:*), Read, Glob
---

# Genie Render — Course → Single-page HTML

You are running the `genie-render` skill. Your job is to take a course already generated under `content/<owner>-<name>/` (by `/genie-learn`) and turn it into one interactive `index.html` next to those Markdown files.

You are **pure orchestration**. The actual rendering is deterministic and lives in `scripts/render_course.py`. Do not read the course content yourself, do not generate HTML inline.

## Step 0 — Parse the argument

The user invoked `/genie-render <args>`. Expect exactly one positional argument: `owner_name` — the slug used as the directory under `content/` (e.g. `sindresorhus-is-plain-obj`, `automagik-dev-genie`). It must look like `<segment>-<segment>...` (lowercase, hyphens).

If `owner_name` is missing or malformed, stop and tell the user the correct invocation:

```
/genie-render <owner-name>

Examples:
  /genie-render sindresorhus-is-plain-obj
  /genie-render automagik-dev-genie
```

## Step 1 — Verify the course exists

Use `Glob` to confirm `content/<owner_name>/00-overview.md` exists. If not, stop and instruct the user:

> Course not found at `content/<owner_name>/`. Run `/genie-learn <repo-url>` first to generate the course, then re-run `/genie-render <owner-name>`.

(Other artifacts — tutorial, glossary, modules, quizzes, podcast — are optional. The renderer degrades gracefully when any of them is missing.)

## Step 2 — Optional Gemini TTS (pre-render)

Before invoking the renderer, attempt to generate the podcast audio:

```bash
python scripts/gemini_podcast.py <owner_name>
```

This script self-skips (exits 0 with a `[skip]` message) when:
- `.env` has no `GEMINI_API_KEY` (or contains the placeholder `your_gemini_api_key_here`).
- An audio file already exists at `content/<owner_name>/99-podcast/podcast.{wav,mp3,m4a,ogg}`.

If the script generates new audio, it writes `99-podcast/podcast.wav` and prints a one-line summary with size and estimated duration.

**Failure handling:** if the script exits non-zero (network error, quota exceeded, invalid key), do NOT abort the render — fall through to Step 3 anyway. Surface the script's stderr to the user so they can fix the underlying issue, but the renderer will still produce a usable HTML (just without the `<audio>` element). Surface the one-line stdout (`[skip] ...` or `Wrote ...`) regardless of exit code.

## Step 3 — Run the renderer

Invoke the script via Bash from the project root (the directory containing `.claude/`):

```bash
python scripts/render_course.py <owner_name>
```

If `python` is unavailable on the user's PATH, fall back to `py` (Windows launcher):

```bash
py scripts/render_course.py <owner_name>
```

The script:
- Discovers all canonical artifacts under `content/<owner_name>/`.
- Detects the course language from `99-podcast/metadata.json` (defaults to `pt-BR`).
- Parses quizzes (multilingual: `## Perguntas`/`## Gabarito`, `## Questions`/`## Answer key`) into structured questions: multiple-choice, short-answer, trace-the-flow.
- Parses the glossary into `[{letter, terms}]`.
- Derives flashcards from glossary terms and from multiple-choice quiz questions.
- Detects optional audio at `99-podcast/podcast.{mp3,wav,m4a,ogg}` — including any file generated in Step 2.
- Substitutes the `course_data` JSON into `scripts/templates/course.html` and writes `content/<owner_name>/index.html`.

## Step 4 — Report

Forward the renderer's stdout to the user (it already prints the output path, size, counts, and a `file://` URL to open). Add one short line summarizing whether the audio is present (mention if it was generated in this run vs. already existed vs. skipped) and that re-running is safe (idempotent — overwrites the HTML, never the learner's `localStorage` progress in their browser).

## Failure handling

- If `python` exits non-zero, surface stderr verbatim. Do not retry with different arguments.
- If the script reports "missing required file: 00-overview.md" the course was not actually generated — instruct the user to run `/genie-learn` first.
- Do **not** write or modify any course files yourself. Do not attempt to fetch the audio file. Do not call Gemini.
- Do **not** modify the renderer script or the template — those are outside this skill's responsibility.

## Anti-patterns

- Do not read the Markdown course content yourself. The script does that.
- Do not generate HTML inline. The script + template own that surface.
- Do not download CDN assets locally — the rendered page intentionally loads Vue, Tailwind, and marked from CDNs at first open.
- Do not invent default values for `<owner-name>` if the user omitted it. Stop and ask.
