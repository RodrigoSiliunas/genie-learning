# Genie Learning

Project that uses Claude Code subagents to generate educational content about GitHub repositories.

## How to use

There are two skills:

1. **`/genie-learn <github-url> [language] [max-workers]`** — generates the Markdown course.
2. **`/genie-render <owner-name>`** — turns the generated course into one interactive `index.html` (Vue 3 + Tailwind, Paper & Ink design).

Examples:

- `/genie-learn https://github.com/sindresorhus/is-plain-obj pt-BR`
- `/genie-learn https://github.com/expressjs/express en 5`
- `/genie-render sindresorhus-is-plain-obj` (after `/genie-learn` finishes)

The orchestrator (the `genie-learn` skill) clones the repo into `repos/<owner>-<name>/` and produces a course in `content/<owner>-<name>/`:

- `00-overview.md` — what the project is, stack, module map
- `10-tutorial.md` — hands-on walkthrough
- `20-glossary.md` — domain terminology
- `30-modules/NN-<name>.md` — one lesson per module (generated in parallel)
- `40-quizzes/*.md` — general and module-level quizzes
- `90-validation.md` — validation report
- `99-podcast/script.md` and `99-podcast/metadata.json` — podcast text assets
- `index.html` + `assets/style.css` + `assets/app.js` — interactive course bundle (added by `/genie-render`). The course payload is inlined inside `index.html` as base64; `style.css` and `app.js` are referenced via plain `<link>`/`<script src>` with cache-busting `?v=<sha1>` query strings.

The orchestrator also runs a read-only post-run audit in chat after `90-validation.md` is written. `/genie-render` is independent: re-running it overwrites the 3-file bundle byte-for-byte (idempotent) without touching the learner's `localStorage` progress in their browser.

## Architecture

- **`.claude/skills/genie-learn/SKILL.md`** — orchestrator. Parses args, invokes subagents in parallel, runs post-run audit, summarizes.
- **`.claude/agents/repo-cartographer.md`** — clones the repo, writes overview, returns JSON inventory of modules. Runs first, sequentially.
- **`.claude/agents/module-teacher.md`** — writes one lesson per module. Dispatched in parallel when `max_workers >= 3`; with `max_workers=2`, modules are processed one at a time after tutorial/glossary.
- **`.claude/agents/tutorial-writer.md`** — writes the step-by-step tutorial. Runs in parallel with the others.
- **`.claude/agents/jargon-extractor.md`** — writes the glossary. Runs in parallel with the others.
- **`.claude/agents/quiz-generator.md`** — writes quizzes from generated course materials.
- **`.claude/agents/podcast-scriptwriter.md`** — writes podcast script and metadata without calling external APIs.
- **`.claude/agents/course-validator.md`** — validates the final generated package and writes `90-validation.md`.
- **`.claude/agents/course-remediator.md`** — applies automatic, allow-listed fixes to validator findings (clone-path leak, generation-footer leak, English structural headings on non-English courses, tolerance bands on numeric short-answer questions, missing target-language glosses on coined glossary terms, low-confidence path-range fixes, broken-link typos). Idempotent; runs between `course-validator` and `post-run-course-auditor`. Updates `90-validation.md` in place and writes `91-remediation.md`.
- **`.claude/agents/post-run-course-auditor.md`** — performs the final read-only post-run audit and returns a chat report without writing files.
- **`.claude/skills/genie-render/SKILL.md`** — orchestrator for the HTML renderer. Invokes `scripts/render_course.py`.
- **`scripts/render_course.py`** — deterministic Python renderer (stdlib only). Reads `content/<owner>-<name>/`, parses quizzes/glossary/modules, derives flashcards from glossary + multiple-choice questions, writes `content/<owner>-<name>/index.html`, and copies `style.css` + `app.js` into `content/<owner>-<name>/assets/` with a SHA1-based cache-busting version string.
- **`scripts/templates/course.html`** — HTML shell (Vue 3 + Tailwind via CDN, marked.js for client-side Markdown, Tailwind config inline, course payload bootstrap inline as base64). Paper & Ink styled per `DESIGN.md`.
- **`scripts/templates/course_assets/style.css`** — extracted CSS (Paper & Ink theme, components, dark mode, accent variants). Copied verbatim into each course's `assets/style.css` on render.
- **`scripts/templates/course_assets/app.js`** — extracted Vue 3 Options API app (state, persistence, quizzes, flashcards, keyboard navigation, tweaks). Copied verbatim into each course's `assets/app.js` on render.

## Conventions

- `repos/` and `content/` are gitignored (generated artifacts, not source).
- Each subagent has minimum-privilege tools. Only `repo-cartographer` has `Bash`.
- Subagents communicate with the orchestrator via filesystem (output files) and a JSON contract returned by the cartographer.
- The skill is the only entry point. Do not invoke subagents directly from another context unless debugging.
- The render output is a 3-file bundle (`index.html` + `assets/style.css` + `assets/app.js`). The course payload is inlined inside `index.html` as base64 — never split into a separate JSON file (CORS would break under `file://`). To share a course, zip the entire `content/<owner-name>/` directory; relative paths are preserved.

## Project Objective

- Transform any public GitHub repository into a structured course (overview, tutorial, glossary, lessons per module, quizzes, podcast script, and validation report) generated by Claude Code subagents.

## Main Components

- **Agents**:
  - `repo-cartographer`: Clones the repository, detects stack and module structure, writes the overview, and returns JSON inventory
  - `module-teacher`: Writes one lesson per module (multiple instances in parallel)
  - `tutorial-writer`: Writes step-by-step tutorial (installation → first change)
  - `jargon-extractor`: Extracts domain-specific terminology and produces glossary
  - `quiz-generator`: Produces quizzes grounded in generated course content
  - `podcast-scriptwriter`: Produces podcast text assets (`script.md` + `metadata.json`) consumed by `scripts/gemini_podcast.py` to generate audio
  - `course-validator`: Performs final artifact, structure, link, language, and safety checks
  - `course-remediator`: Resolves deterministic and gated contextual findings from `course-validator` automatically before the post-run audit; updates `90-validation.md` in place and writes `91-remediation.md`
  - `post-run-course-auditor`: Performs read-only post-run artifact audit after `course-remediator`
- **Orchestrator**: `genie-learn` skill — coordinator that receives arguments, invokes subagents sequentially and in parallel, and summarizes results
- **Tools**: Bash (cartographer only), Read, Glob, Grep, Write — each agent has minimum necessary permissions
- **Memory**: Filesystem as contract — cartographer returns JSON, agents read/write files under `content/<owner>-<name>/`
- **State**: `repos/` (clones) and `content/` (generated artifacts) directories — both gitignored
- **Input/Output**: GitHub URL + [language] + [max-workers] → structured Markdown course (`00-overview.md`, `10-tutorial.md`, `20-glossary.md`, `30-modules/*.md`, `40-quizzes/*.md`, `90-validation.md`, `91-remediation.md`, `99-podcast/script.md`, `99-podcast/metadata.json`)
- **Observability**: Final summary to user with elapsed time, generated files, workers used, and post-run audit status
- **Evaluation/Tests**: `course-validator` provides generated-course validation for required artifacts, module lessons, quizzes, podcast metadata, language signals, and secret leakage; `post-run-course-auditor` adds a read-only post-run audit in chat; no automated repository test suite is present yet

## Current Flow

1. **User input/event**: User invokes `/genie-learn <repo-url> [language] [max-workers]` in Claude Code
2. **Interpretation**: Orchestrator parses arguments, validates GitHub URL, derives `owner_name`
3. **Planning**: Orchestrator determines module workers; it uses `max_workers - 2` when possible and falls back to one-at-a-time module batches when `max_workers=2`
4. **Tool calls**:
   - Step 1 (sequential): Invokes `repo-cartographer` to clone and analyze
   - Step 2 (parallel/sequential fallback): Simultaneous dispatch of `tutorial-writer`, `jargon-extractor`, and N instances of `module-teacher` when `max_workers >= 3`; tutorial/glossary first, then one module at a time when `max_workers=2`
   - Step 3 (parallel): Dispatches `quiz-generator` and `podcast-scriptwriter` after primary content exists
   - Step 4 (sequential): Runs `course-validator` after generated content exists
   - Step 4.5 (sequential): Runs `course-remediator` to auto-resolve allow-listed findings; updates `90-validation.md` and writes `91-remediation.md`
   - Step 5 (sequential): Runs `post-run-course-auditor` read-only after `course-remediator`
5. **Coordination by orchestrator**: Parses JSON inventory from cartographer, dispatches agents in parallel when possible, and manages module batches without allowing `max_workers - 2` to skip modules
6. **Final response/action**: Summary to user with generated files, time, workers used, post-run audit status, and a one-line note pointing to `scripts/gemini_podcast.py` for podcast audio generation
7. **Persistence/logs**: Files written to `content/<owner>-<name>/` (including `91-remediation.md` when remediation runs), clones in `repos/`; `.env` remains local-only

## Strengths Found

- **Parallel execution**: Multiple agents run simultaneously to reduce total time
- **Zero external dependencies**: Pure Claude Code — drop-in in any project
- **Principle of least privilege**: Only cartographer has Bash access
- **Idempotency**: Skips clone if repository already exists
- **Filesystem contract**: No IPC, no mailbox, no daemon — simple and robust
- **Isolated context**: Each subagent has its own context window, keeping orchestrator lean
- **Final validation**: Dedicated validator creates a reviewable quality report after generation, including required artifacts, module lessons, quizzes, podcast script metadata, language, and safety signals
- **Self-healing course**: `course-remediator` automatically resolves recurring findings (clone-path leak, generation-footer leak, English structural headings on non-English courses, missing tolerance bands, and missing target-language glosses) before the post-run audit, so the user doesn't have to fix the same class of issue twice
- **Modular podcast pipeline**: `podcast-scriptwriter` handles text only; `scripts/gemini_podcast.py` handles audio TTS only; `/genie-render` auto-triggers the TTS step when `GEMINI_API_KEY` is set in `.env`

## Risks or Bottlenecks

- **No caching**: Each run regenerates everything from scratch (inefficient for re-runs)
- **No private repo support**: Only anonymous clones
- **Limited automated testing**: Generated-course validation exists, but there is still no executable test suite for the project itself
- **Claude Code dependency**: Doesn't work outside Claude Code environment (roadmap: standalone CLI)
- **Manual batching**: If modules exceed the available module worker count, the orchestrator must manage batches explicitly
- **JSON contract fragility**: Orchestrator depends on a trailing fenced JSON block from `repo-cartographer`

## Improvement Opportunities

- **SHA caching**: Regenerate only if repo changed (roadmap item)
- **Private repo support**: Authentication via SSH/HTTPS token
- **Standalone CLI**: Use Claude Agent SDK to run outside Claude Code
- **Integration tests**: Verify agents produce valid output for a small fixture repo
- **Quality metrics**: Evaluate coherence, completeness, and accuracy of generated content
- **Schema hardening**: Make the cartographer inventory easier to validate and recover from
- **MP3 conversion**: `gemini_podcast.py` outputs WAV (24-30 MB for 10-min episodes); MP3 would shrink ~5×, requires ffmpeg or pydub

## Agent Ideas for Brainstorm

- Diff agent that generates changelog between course versions
- Translation agent that converts courses between languages
- Indexing agent that creates search index for multiple courses
- Curation agent that suggests related courses
- Tutorial-runner agent that checks setup commands in a sandboxed environment

## Recommended Architectural Decisions

- **Keep filesystem as contract**: Simplicity > IPC complexity
- **Preserve parallelism**: It's the main performance differentiator
- **Implement SHA caching**: High priority for UX in re-runs
- **Add smoke tests**: Verify each agent produces valid file
- **Keep podcast modular**: Script generation and TTS execution stay separate
- **Keep secrets out of Git**: `.env` is ignored; `.env.example` is versionable and contains only placeholders

## Gemini Environment

- `.env.example` defines safe placeholder values for `GEMINI_API_KEY`, `GEMINI_TTS_MODEL` (default `gemini-2.5-flash-preview-tts`), and `GEMINI_PODCAST_OUTPUT_FORMAT` (default `wav`).
- Local users copy `.env.example` to `.env` and fill their own key locally.
- `.env` is gitignored and must never be committed or printed.
- `scripts/gemini_podcast.py` reads `.env` via stdlib parser, treats the placeholder key as missing (silent skip), redacts the key from any error message, and writes `99-podcast/podcast.wav` only.
- `/genie-render` invokes `gemini_podcast.py` automatically before the HTML render. The script is idempotent — skips when `99-podcast/podcast.{wav,mp3,m4a,ogg}` already exists. Delete the audio file to force regeneration.
- Voices are hardcoded: Host A → Kore, Host B → Puck (Google's stock multi-speaker pair).

## Roadmap (not in MVP)

- Repo-private support (currently anonymous `git clone` only).
- Incremental regeneration (currently each run rebuilds from scratch).
- Standalone CLI wrapper for use outside Claude Code.
- MP3 conversion of the podcast WAV (currently 24–30 MB per 10-min episode; MP3 would be ~5–8 MB but requires ffmpeg).
- Configurable TTS voices (currently hardcoded Kore + Puck).
