# Squad Skills

**Model-agnostic, host-portable skills for the
[squad](https://github.com/cowdogmoo/squad) ecosystem.**

[![License](https://img.shields.io/github/license/CowDogMoo/squad-skills?label=License&style=flat&color=blue&logo=github)](https://github.com/CowDogMoo/squad-skills/blob/main/LICENSE)
[![Pre-Commit](https://github.com/CowDogMoo/squad-skills/actions/workflows/pre-commit.yaml/badge.svg)](https://github.com/CowDogMoo/squad-skills/actions/workflows/pre-commit.yaml)
[![Validate Skills](https://github.com/CowDogMoo/squad-skills/actions/workflows/validate-skills.yaml/badge.svg)](https://github.com/CowDogMoo/squad-skills/actions/workflows/validate-skills.yaml)

---

## Overview

The skills sibling to
[squad-agents](https://github.com/cowdogmoo/squad-agents). A skill is a
single-file procedure (`SKILL.md`) — a name, a one-line description,
and a body of instructions. The host reads the description to decide
when to invoke the skill, then follows the body.

Skills here are:

- **Model-agnostic.** The body is plain markdown — no model-specific
  prompt syntax. Anything that can read markdown and call MCP tools
  can run them.
- **Host-portable.** Each skill resolves the right MCP tool names from
  whatever host it lands in (squad runners, IDE integrations, desktop
  hosts) instead of hard-coding one host's tool surface.
- **Bounded.** Every skill states its objective and guardrails up
  front — what counts as done, and what counts as "stop and ask".

## Quick Start

### As a Claude Code plugin

This repo is a Claude Code plugin (`.claude-plugin/plugin.json`),
registered in the `cowdogmoo` marketplace hosted by
[squad-agents](https://github.com/cowdogmoo/squad-agents). The
squad-agents plugin declares this one as a dependency — its agents
load skills from here at runtime — and dependencies are not
auto-installed, so install both:

```text
/plugin marketplace add cowdogmoo/squad-agents
/plugin install squad-skills@cowdogmoo
/plugin install squad-agents@cowdogmoo
```

### Any other host

Skills live in a directory containing a single `SKILL.md`. Wire a host
to this repo by pointing it at the directory or referencing the file:

```bash
# From a squad agent — reference the skill from its task.md / prompts
# (the squad runner loads the SKILL.md body verbatim).

# From any host that supports a user-skills directory — drop the
# folder in place.
cp -r comment-scrub-playbook /path/to/host/skills/
```

## Available Skills

| Skill                                                                        | Description                                                                                                                                                                            |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [comment-scrub-playbook](./comment-scrub-playbook)                           | Classify source-code comments into five delete-candidate categories and decide delete vs. trim vs. keep. Caller supplies language, directive list, and build-verify command.           |
| [detect-llm-tells](./detect-llm-tells)                                       | Score prose paragraphs or code comments against 8 LLM-generated-text tell categories with cluster scoring (flag at 3+ converging categories).                                          |
| [doc-comments-discovery-and-fix-loop](./doc-comments-discovery-and-fix-loop) | Discover public/exported declarations missing or carrying deficient doc comments, prioritize by impact, apply proportional fixes in a read-then-edit loop, verify compilation, report. |
| [enqueue-coverage-targets-go](./enqueue-coverage-targets-go)                 | Orchestrator-workers pattern for Go test coverage: compute the queue of packages below target with one Bash command, then drain it by writing `_test.go` files.                        |
| [enqueue-coverage-targets-nodejs](./enqueue-coverage-targets-nodejs)         | Orchestrator-workers pattern for Node.js/TypeScript test coverage: queue source files below target via `vitest`/`jest --coverage`, then drain it by writing `*.test.ts` files.         |
| [enqueue-coverage-targets-python](./enqueue-coverage-targets-python)         | Orchestrator-workers pattern for Python test coverage: queue modules below target via `pytest --cov`, then drain it by writing `test_*.py` files.                                      |
| [enqueue-coverage-targets-rust](./enqueue-coverage-targets-rust)             | Orchestrator-workers pattern for Rust test coverage: queue source files below target via `cargo llvm-cov`, then drain it by writing inline `#[cfg(test)]` blocks.                      |
| [extract-recipe-grocery-list](./extract-recipe-grocery-list)                 | Fetch recipe URLs, extract ingredients (preferring schema.org JSON-LD), and produce a deduplicated grocery list grouped by aisle with per-item dish annotations.                       |
| [guitar-pro](./guitar-pro)                                                   | Read, write, and analyze Guitar Pro tablature (`.gp5`, native `.gp`, MusicXML) via a bundled PyGuitarPro/alphaTab helper; handles the silent-corruption defects in both libraries.                     |
| [quad-cortex-capture-measurement](./quad-cortex-capture-measurement)         | Measure a Quad Cortex capture or preset against its plugin reference: one-pass QC-over-USB recording, bundled `analyze.py` (LUFS offset, banded deltas, coherence, null depth), interpretation thresholds, and the canonical claim ladder. |
| [quad-cortex-plugin-capture](./quad-cortex-plugin-capture)                   | Run a Neural Capture of an amp-sim plugin into the Quad Cortex on Jayson's rig (RME UCX II, Ableton, Cortex Control): cabling, TotalMix routing, capture-safe plugin state, level calibration, V2 capture, A/B verification. |
| [quad-cortex-preset-editing](./quad-cortex-preset-editing)                   | Put a Neural Capture into a Quad Cortex preset via Cortex Control screen control: inventory every block, canonical order, bypass what the reference lacks, makeup on Volume, and report the claim rung reached (configured / structurally faithful / measured). |
| [score-coverage-and-report-gaps](./score-coverage-and-report-gaps)           | Measure baseline test coverage, enumerate zero-coverage functions and untested packages, prioritize, write tests, re-verify, report the before/after delta.                            |
| [test-writer-honesty](./test-writer-honesty)                                 | Shared discipline rules for any test-writing agent: never clobber existing tests, never fall back to `Write` when `Edit` fails, tie the final report to `git diff --stat`.             |

## Skill Structure

Layout follows Anthropic's
[Complete Guide to Building Skills for Claude](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf):

```text
skill-name/
├── SKILL.md       # required — main skill file
├── scripts/       # optional — executable code (Python, Bash, etc.)
├── references/    # optional — supporting docs loaded on demand
└── assets/        # optional — templates, fixtures, fonts, icons
```

Only `SKILL.md` is required. Put a `references/<topic>.md` next to
`SKILL.md` and link to it from the body when you have a lookup table or
catalog that doesn't need to be in context every run — see
[`detect-llm-tells/references/`](./detect-llm-tells/references) for an
example.

**No `README.md` inside a skill folder.** The repo-level README is for
human visitors; all skill-facing documentation belongs in `SKILL.md` or
`references/`.

`SKILL.md` is markdown with YAML frontmatter:

```markdown
---
name: skill-name
description: One sentence covering both WHAT the skill does and WHEN to use it. Mention the file types or trigger phrases a user is likely to say.
---

# Body

Objective, inputs, step-by-step instructions, host-portability notes,
and guardrails ("never check out", "stop if you see a sign-in page").
```

### Frontmatter rules

| Field           | Required | Notes                                                                                                                                                                |
| --------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`          | yes      | kebab-case; must match the directory name exactly. No spaces, capitals, or underscores. Must not contain `claude` or `anthropic` (reserved).                         |
| `description`   | yes      | Single line, ≤1024 chars. Drives skill selection, so it **must** include both WHAT the skill does and WHEN to use it (trigger conditions). No `<` or `>` characters. |
| `license`       | no       | SPDX identifier if the skill is published (e.g. `MIT`, `Apache-2.0`).                                                                                                |
| `compatibility` | no       | 1–500 chars. Environment requirements (target host, system packages, network access).                                                                                |
| `metadata`      | no       | Free-form map. Common keys: `author`, `version`, `mcp-server`.                                                                                                       |
| `allowed-tools` | no       | Claude Code-specific; comma-separated tool allowlist applied when the skill loads.                                                                                   |

### Description heuristics

A description routes the skill, so it needs to read like a routing hint,
not a tagline:

- ✅ `Classify source-code comments into five delete-candidate categories and decide delete vs. trim vs. keep. Use when scrubbing useless or LLM-slop comments from a codebase.`
- ❌ `Helps with comments.` (no WHAT, no WHEN)
- ❌ `Implements the Comment entity model with hierarchical relationships.` (too technical, no user-facing trigger)

Include phrases users would actually say ("scrubbing comments", "doc
comments", "weekly shopping list") and mention file types or commands
when they're a strong signal.

### Body conventions

- **Lead with a "Host-environment translation" section** if MCP tool
  names differ across hosts. Map the abstract action (read a doc as
  HTML, drive a browser, ask the user a go/no-go) to each host's
  actual tool name once at the top instead of forking the prose.
- **State objective and guardrails up front** — what's done, what's
  "stop and ask".
- **Treat the body as a runbook**, not a manual. Numbered, executable
  steps — not narrative.

## Host Portability

Skills here target multiple hosts and the MCP tool surface differs
across them. The pattern that works:

1. Write the skill against an abstract action ("read the doc as HTML",
   "navigate the browser", "ask the user a go/no-go question").
2. Provide a translation table at the top mapping the abstract action
   to each host's actual tool name.
3. Prefer the richer fallback path when the host exposes it (e.g. a
   Drive MCP that returns HTML preserves strikethrough formatting that
   a markdown export would drop).

## Creating a Skill

```bash
# 1. Create the directory
mkdir my-skill

# 2. Write SKILL.md
cat > my-skill/SKILL.md <<'EOF'
---
name: my-skill
description: One sentence describing exactly when to use this.
---

# Objective

# Inputs

# Step-by-step

EOF

# 3. Validate before committing
pre-commit run --all-files
```

A skill is ready when:

- `name` matches the directory.
- `description` covers WHAT and WHEN, and would let the host pick it
  correctly from a list of 30 unrelated skills.
- The body is followable cold — no relying on conversation history.
- Guardrails are explicit ("never X", "stop if Y").
- `SKILL.md` stays under ~5,000 words; bulky lookup tables live in
  `references/`.
- No `README.md` lives inside the skill folder.

## Contributing

```bash
pre-commit install        # one-time
pre-commit run --all-files
```

CI runs the same checks:

- `SKILL.md` exists in every non-hidden top-level directory.
- Frontmatter has `name` and `description`, both non-empty.
- `name` matches the directory name.
- Markdown lints clean (`markdownlint`), YAML lints clean
  (`yamllint`), and frontmatter parses.

---

**Maintained by [Jayson Grace](https://github.com/CowDogMoo)** |
[Issues](https://github.com/cowdogmoo/squad-skills/issues) |
[squad-agents](https://github.com/cowdogmoo/squad-agents) |
[squad](https://github.com/cowdogmoo/squad)
