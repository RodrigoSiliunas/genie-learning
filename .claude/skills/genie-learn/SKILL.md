---
name: genie-learn
description: Generate educational content (overview, lessons, tutorial, glossary, quizzes, podcast script, validation report, post-run audit) about a public GitHub repository. Clones the repo into ./repos/, writes a structured course into ./content/<owner>-<name>/, and dispatches multiple subagents in parallel. Trigger with /genie-learn <repo-url> [language] [max-workers].
allowed-tools: Bash(mkdir:*), Bash(test:*), Read, Glob, Write
---

# Genie Learn — Orchestrator

You are running the `genie-learn` skill. The user has invoked you with arguments. Your job is to coordinate eight subagents (`repo-cartographer`, `module-teacher`, `tutorial-writer`, `jargon-extractor`, `quiz-generator`, `podcast-scriptwriter`, `course-validator`, `post-run-course-auditor`) to produce and audit a complete educational package for a GitHub repository.

Subagent dispatch follows Claude Code's standard subagent mechanism: explicitly name or @-mention the project subagent for each task. No separate `Agent` entry is required in this skill's `allowed-tools`; the runtime resolves project subagents from `.claude/agents/`.

## Step 0 — Parse arguments

The user invoked `/genie-learn <args>`. Parse `args` as:

- **Position 1 (required)**: `repo_url` — must start with `https://github.com/` or `git@github.com:`.
- **Position 2 (optional, default `pt-BR`)**: `language` — IETF code like `pt-BR`, `en`, `es`, `fr`, `ja`.
- **Position 3 (optional, default `5`)**: `max_workers` — integer, cap on parallel subagents (between 2 and 10).

Derive `owner_name` from the URL: `https://github.com/foo/bar` → `foo-bar` (lowercase, slashes→hyphens, strip trailing `.git`).

If `repo_url` is missing or malformed, **stop and tell the user** the correct invocation format. Do not proceed.

The project root is the current working directory (the directory where `.claude/` lives). All paths below are relative to it.

## Step 1 — Cartography (sequential, blocks everything else)

Invoke the `repo-cartographer` subagent explicitly by name or @-mention. Pass it a prompt like:

> Clone and analyze the repository at `<repo_url>` for the genie-learning project at project root `<absolute project root>`. Target language for prose: `<language>`. Write the overview to `content/<owner_name>/00-overview.md` and return the JSON inventory at the end of your response.

Wait for completion. **Parse the JSON inventory** from the trailing ```json fence in the cartographer's response. Extract:

- `repo_path`, `content_path`, `owner_name`
- `stack` (object)
- `modules` (array)

If the cartographer's clone failed and `modules` is empty, skip primary and enrichment generation. If `content_path` exists in the inventory, continue directly to Step 4 so the validator can write a partial report; otherwise skip to Step 6 with a clear failure summary.

## Step 2 — Parallel content generation

Plan module batches before dispatching. If `len(modules) = 0`, skip module lessons. If `max_workers >= 3`, set `module_workers = max(1, min(len(modules), max_workers - 2))` and dispatch the first module batch with tutorial and glossary. If `max_workers = 2`, set `module_workers = 1`, dispatch tutorial and glossary first, wait for them, then process modules in sequential batches of 1.

For the first primary-content dispatch, use explicit subagent invocations in one message where parallelism is allowed:

1. **One** `tutorial-writer` invocation with: `repo_path`, `stack`, `language`, `output_path = content_path/10-tutorial.md`.
2. **One** `jargon-extractor` invocation with: `repo_path`, `stack_language = stack.language`, `language`, `output_path = content_path/20-glossary.md`.
3. **Up to `module_workers` `module-teacher` invocations** when `max_workers >= 3`. Each gets a distinct module from the inventory. Output paths follow the pattern `content_path/30-modules/NN-<module-slug>.md` where `NN` is a 2-digit zero-padded index (`01`, `02`, ...).

Each `module-teacher` prompt should include: `repo_path`, `module_name`, `module_path`, `module_purpose`, `stack_language`, `language`, and `output_path`.

**If `len(modules) > module_workers`**: process modules in batches. After the first batch returns, dispatch the next batch (still in single messages with multiple tool calls per batch when `module_workers > 1`). Keep `tutorial-writer` and `jargon-extractor` only in the first batch. Never skip module generation solely because `max_workers - 2` is zero.

Wait until all primary content agents have returned before proceeding.

## Step 3 — Enrichment generation

After the primary course files exist, dispatch these agents concurrently in a single message:

1. **One** `quiz-generator` invocation with: `content_path`, `owner_name`, `language`, `modules`, `output_dir = content_path/40-quizzes`.
2. **One** `podcast-scriptwriter` invocation with: `content_path`, `owner_name`, `language`, `output_dir = content_path/99-podcast`.

These agents must only read generated Markdown under `content_path`; they must not read the cloned repo or call external APIs.

The `40-quizzes/` and `99-podcast/` directories are expected to already exist because `repo-cartographer` creates them during cartography.

## Step 4 — Final validation

After enrichment generation returns, invoke **one** `course-validator` with: `content_path`, `owner_name`, `language`, `modules`, `output_path = content_path/90-validation.md`.

The validator runs last because it checks the final package, including quizzes and podcast script when present.

## Step 5 — Post-run external audit

After `course-validator` returns, invoke **one** `post-run-course-auditor` with: `content_path`, `owner_name`, `language`, `repo_url`, `repo_path`, `modules`, `command_used = /genie-learn <repo_url> <language> <max_workers>`, and `test_goal = automatic post-run audit after genie-learn`.

The auditor runs after the internal validator and returns a Markdown report in chat. It is read-only: it must not write files, alter `content/`, alter `repos/`, execute repository code, call Gemini, or print secrets.

If the auditor cannot be invoked or fails, do not delete artifacts, rerun generation, or modify files. Report the audit failure in the final summary and print this manual fallback command for the user:

```text
/validate-genie-learning-course content_dir=content/<owner_name> language=<language> expected_owner_name=<owner_name> repo_url=<repo_url> command_used="/genie-learn <repo_url> <language> <max_workers>" test_goal="validar resultado pós-execução"
```

## Step 6 — Summary

When all subagents have returned, output a summary to the user containing:

- Total wall-clock time (rough — based on your sense of how long the run took).
- Number of files produced, listed by category:
  - `content/<owner_name>/00-overview.md`
  - `content/<owner_name>/10-tutorial.md`
  - `content/<owner_name>/20-glossary.md`
  - `content/<owner_name>/30-modules/*.md` (count)
  - `content/<owner_name>/40-quizzes/*.md` (count)
  - `content/<owner_name>/90-validation.md`
  - `content/<owner_name>/99-podcast/script.md`
  - `content/<owner_name>/99-podcast/metadata.json`
- Number of `module-teacher` workers used and how many modules remain unprocessed (if you batched, mention it).
- Post-run audit status from `post-run-course-auditor`, including the final verdict and any main `BLOCKER` or `WARNING` findings.
- One-line note: **"Podcast audio generation is handled by `scripts/gemini_podcast.py` and is auto-invoked by `/genie-render` when `GEMINI_API_KEY` is set."**

Do **not** read back the generated content to the user — they can open the files. Keep the summary concise.

## Failure handling

- A subagent reporting failure does not stop the others. Note failures in the summary.
- If the user passes a private/non-existent repo and clone fails, the cartographer will return an empty modules list — produce only the overview stub and validation report when possible, then give a clear failure note.
- If `max_workers < 3`, you cannot dispatch `tutorial-writer` + `jargon-extractor` + ≥1 `module-teacher` in parallel — fall back to sequential dispatch in that case.
- If primary content is incomplete, still run `quiz-generator`, `podcast-scriptwriter`, and `course-validator` only when they can produce useful partial artifacts from existing files. The validator should record missing artifacts.
- If `post-run-course-auditor` fails, report the failure and show the manual `/validate-genie-learning-course` fallback command; do not mutate or regenerate artifacts.
- Never print environment variable values, API keys, or secrets in summaries.

## Anti-patterns — do not

- Do not clone the repo yourself; the cartographer owns that.
- Do not read or summarize the cloned code yourself; that's what the subagents are for. You are pure coordination.
- Do not perform the post-run audit yourself; invoke `post-run-course-auditor`.
- Do not invoke subagents serially when they could go in parallel — the value of this skill is concurrency.
- Do not call Gemini or any external API from the skill or subagents; podcast audio generation belongs to `scripts/gemini_podcast.py`.
