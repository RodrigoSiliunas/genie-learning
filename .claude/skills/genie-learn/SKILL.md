---
name: genie-learn
description: Generate educational content (overview, lessons, tutorial, glossary, quizzes, podcast script, validation report, post-run audit) about a public GitHub repository. Clones the repo into ./repos/, writes a structured course into ./content/<owner>-<name>/, and dispatches multiple subagents in parallel. Trigger with /genie-learn <repo-url> [language] [max-workers].
allowed-tools: Bash(mkdir:*), Bash(test:*), Read, Glob, Write
---

# Genie Learn — Orchestrator

You are running the `genie-learn` skill. The user has invoked you with arguments. Your job is to coordinate nine subagents (`repo-cartographer`, `module-teacher`, `tutorial-writer`, `jargon-extractor`, `quiz-generator`, `podcast-scriptwriter`, `course-validator`, `course-remediator`, `post-run-course-auditor`) to produce, remediate, and audit a complete educational package for a GitHub repository.

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

Each `module-teacher` prompt MUST include: `repo_path`, `module_name`, `module_path`, `module_purpose`, `stack_language`, `language`, `output_path`, **and the Pretest reminder block below verbatim**.

> **PRETEST REQUIRED** — Emit a `## Pretest` section at the VERY TOP of the file (before any other prose, even the `## Purpose` heading) with 1-2 predictive questions anchored on something visible BEFORE reading (file path, function name, signature), followed by a blank line and `---` separator. Use the prefix line in the course's target language per your base instructions. **Skip ONLY if one of these three exceptions holds**: (1) the module body is a pure-reference flat list or single table with no prose; (2) the module name is an opaque acronym AND nothing externally-visible (filename, signature, path) can anchor a guess; (3) `module_purpose` is empty or a single word. Otherwise emit. This is not optional.

This reminder is load-bearing: empirically, the agent's base instructions alone produce ~0% Pretest compliance without this reinforcement in the dispatch prompt. Do not omit it, abbreviate it, or paraphrase it — copy verbatim.

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

## Step 4.5 — Automatic remediation

After `course-validator` returns and `content_path/90-validation.md` exists, invoke **one** `course-remediator` with: `content_path`, `owner_name`, `language`, `output_log_path = content_path/91-remediation.md`.

Pass it a prompt like:

> Apply automatic remediation to the Genie Learning course at `<content_path>` (language `<language>`). Read warnings and infos in `<content_path>/90-validation.md`, classify each against your allow-list, apply only the gated fixes, update `90-validation.md` in place to mark resolved findings (do not delete them), and write a remediation log to `<output_log_path>`. Do not regenerate content, do not translate prose in bulk, and do not invent values the validator did not provide.

This step is short — the agent typically applies between 0 and 5 small edits. If it reports `0 applied / 0 skipped`, treat that as success.

If `course-remediator` fails, do not retry, do not block the auditor, do not mutate artifacts further. Note the failure in the final summary and continue to Step 5. The audit in Step 5 will then run against the unremediated state — which is acceptable.

## Step 5 — Post-run external audit

After `course-remediator` returns (or fails), invoke **one** `post-run-course-auditor` with: `content_path`, `owner_name`, `language`, `repo_url`, `repo_path`, `modules`, `command_used = /genie-learn <repo_url> <language> <max_workers>`, and `test_goal = automatic post-run audit after genie-learn`.

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
  - `content/<owner_name>/91-remediation.md`
  - `content/<owner_name>/99-podcast/script.md`
  - `content/<owner_name>/99-podcast/metadata.json`
- Number of `module-teacher` workers used and how many modules remain unprocessed (if you batched, mention it).
- Automatic remediation summary from `course-remediator`: `<N>` findings resolved, `<M>` skipped (out-of-scope or false-positive), `<K>` already clean. Point to `content/<owner_name>/91-remediation.md` for details.
- Post-run audit status from `post-run-course-auditor`, including the final verdict and any main `BLOCKER` or `WARNING` findings.
- One-line note: **"Podcast audio generation is handled by `scripts/gemini_podcast.py` and is auto-invoked by `/genie-render` when `GEMINI_API_KEY` is set."**

Do **not** read back the generated content to the user — they can open the files. Keep the summary concise.

## Failure handling

- A subagent reporting failure does not stop the others. Note failures in the summary.
- If the user passes a private/non-existent repo and clone fails, the cartographer will return an empty modules list — produce only the overview stub and validation report when possible, then give a clear failure note.
- If `max_workers < 3`, you cannot dispatch `tutorial-writer` + `jargon-extractor` + ≥1 `module-teacher` in parallel — fall back to sequential dispatch in that case.
- If primary content is incomplete, still run `quiz-generator`, `podcast-scriptwriter`, and `course-validator` only when they can produce useful partial artifacts from existing files. The validator should record missing artifacts.
- If `course-remediator` fails, the validation report stays unchanged and the post-run auditor still runs. Note the remediation failure in the final summary.
- If `post-run-course-auditor` fails, report the failure and show the manual `/validate-genie-learning-course` fallback command; do not mutate or regenerate artifacts.
- Never print environment variable values, API keys, or secrets in summaries.

## Anti-patterns — do not

- Do not clone the repo yourself; the cartographer owns that.
- Do not read or summarize the cloned code yourself; that's what the subagents are for. You are pure coordination.
- Do not perform the post-run audit yourself; invoke `post-run-course-auditor`.
- Do not perform remediation yourself; invoke `course-remediator`.
- Do not invoke subagents serially when they could go in parallel — the value of this skill is concurrency.
- Do not call Gemini or any external API from the skill or subagents; podcast audio generation belongs to `scripts/gemini_podcast.py`.
