# Contributing to Genie Learning

Thanks for your interest in improving Genie Learning. This guide covers how to set the project up locally, how the codebase is organized, and how to add new subagents or skills.

## Setup

Requirements:

- [Claude Code](https://claude.com/claude-code) — the runtime for skills and subagents.
- Python 3.10 or newer — for the deterministic renderer (`scripts/render_course.py`) and Gemini TTS (`scripts/gemini_podcast.py`). Both scripts are stdlib-only — no `pip install` step.
- (Optional) A Google AI Studio API key — only required if you want to generate podcast audio. Without a key, every step still works; only the `<audio>` element is omitted from the rendered page.

Steps:

1. Clone the repository and `cd` into it.
2. (Optional) Copy `.env.example` to `.env` and fill `GEMINI_API_KEY` with your key from [aistudio.google.com](https://aistudio.google.com/).
3. Open Claude Code in the project root.
4. Try a quick run: `/genie-learn https://github.com/sindresorhus/is-plain-obj pt-BR`.
5. Render the result: `/genie-render sindresorhus-is-plain-obj`, then open `content/sindresorhus-is-plain-obj/index.html` in any browser.

`repos/` (cloned source) and `content/` (generated artifacts) are gitignored — they get rebuilt on every run. Don't commit them.

## Project structure

```text
.claude/
├── agents/                      # One Markdown file per subagent (frontmatter + prompt body)
│   ├── repo-cartographer.md
│   ├── tutorial-writer.md
│   ├── jargon-extractor.md
│   ├── module-teacher.md
│   ├── quiz-generator.md
│   ├── podcast-scriptwriter.md
│   ├── course-validator.md
│   └── post-run-course-auditor.md
└── skills/                      # User-invocable skills (slash commands)
    ├── genie-learn/SKILL.md     # Orchestrator — fans out to all 8 subagents
    └── genie-render/SKILL.md    # Renderer — pure orchestration around scripts/

scripts/
├── render_course.py             # stdlib-only — Markdown → single-file Vue 3 HTML
├── gemini_podcast.py            # stdlib-only — multi-speaker Gemini TTS → WAV
└── templates/
    └── course.html              # Vue 3 + Tailwind template, /* GENIE_DATA */ injection

CLAUDE.md                        # Project-level guidance loaded by Claude Code
DESIGN.md                        # Notion-inspired design tokens for the renderer
README.md                        # User-facing introduction
```

Generated artifacts land in `content/<owner>-<name>/` — see the README for the full file map.

## Adding a new subagent

1. Create `.claude/agents/<name>.md` with YAML frontmatter:

   ```markdown
   ---
   name: my-new-agent
   description: One sentence describing what this agent produces and when the orchestrator should invoke it.
   tools: Read, Glob, Grep, Write
   ---

   # My New Agent — <role>

   You are running as the `my-new-agent` subagent. Your job is to ...
   ```

2. Grant **only the tools you actually need**. Defaults from existing agents:
   - `Read, Glob, Grep, Write` — content writers.
   - Add `Bash` only if the agent must execute shell commands (currently only `repo-cartographer` does).
3. Document inputs as a list (path arguments, language code, parent module info).
4. Document outputs as concrete file paths under `content/<owner>-<name>/`.
5. Wire the agent into the orchestrator by editing `.claude/skills/genie-learn/SKILL.md` — explain when to dispatch it, what to pass, and what file(s) it writes.
6. Test with `/genie-learn https://github.com/sindresorhus/is-plain-obj pt-BR` — a tiny single-module repo that exercises the full pipeline in seconds.

## Adding a new skill

Skills live under `.claude/skills/<skill-name>/SKILL.md`. They're user-invocable (`/<skill-name>`) and own end-to-end orchestration.

1. Create the directory and `SKILL.md` with frontmatter:

   ```markdown
   ---
   name: my-new-skill
   description: What the skill does, when to trigger it, and how it complements the existing skills.
   allowed-tools: Read, Glob, Bash(python:*)
   ---

   # My New Skill — <one-line role>

   You are running the `my-new-skill` skill. Your job is to ...
   ```

2. Keep `allowed-tools` minimal. For Bash, restrict to specific binaries (e.g. `Bash(python:*)`).
3. Structure the body in numbered steps (`## Step 0 — Parse arguments`, `## Step 1 — ...`).
4. Include `## Failure handling` and `## Anti-patterns` sections — they keep future iterations honest.
5. If the skill spawns subagents, declare them by name; the runtime resolves project subagents from `.claude/agents/`.

## Code style

- **Python**: stdlib-only by default. New dependencies require strong justification — the appeal of `gemini_podcast.py` is that it runs without `pip install`. Use type hints, `pathlib.Path`, `argparse`, and clear `print` messages prefixed with the script name.
- **HTML / templates**: keep `scripts/templates/course.html` self-contained. Vue 3 inline templates, Tailwind via Play CDN, marked.js via CDN — no build step, no bundler.
- **Markdown**: 80–100 char soft wrap, fenced code blocks with language tags, no trailing whitespace.
- **Subagent prompts**: write in second person ("You are running..."), include explicit anti-patterns, declare exact output paths. Multilingual content agents must enumerate per-language label translations to avoid drift.

## Commit convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — a new agent, skill, or user-visible capability.
- `fix:` — a bug or regression in an agent, skill, or script.
- `docs:` — README, CONTRIBUTING, CLAUDE.md, agent prompt clarifications.
- `chore:` — gitignore tweaks, dependency-free housekeeping, file moves.
- `refactor:` — internal restructuring with no behavior change.

Keep the subject line under 72 characters. Use the body for the why.

## Pull requests

1. Fork the repo and create a topic branch from `main`: `git checkout -b feat/my-thing`.
2. Make your changes. If you added or modified an agent, run `/genie-learn` against a small repo to verify end-to-end behavior.
3. Open a PR against `main`. There is no automated CI yet, so include in the PR body:
   - What you changed and why.
   - The command(s) you ran to verify.
   - Any generated artifacts you inspected (paste a relevant snippet — don't attach the full course).
4. Be patient — review is manual.

## Reporting issues

Open a GitHub issue with:

- The exact command you ran (`/genie-learn ...` or `/genie-render ...`).
- The repo URL you targeted (if applicable).
- The error message or unexpected output (redact any API keys).
- Your OS and Python version.

## Code of conduct

Be respectful. Assume good intent. Critique ideas, not people.
