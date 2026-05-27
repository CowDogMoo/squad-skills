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

Skills live in a directory containing a single `SKILL.md`. Wire a host
to this repo by pointing it at the directory or referencing the file:

```bash
# From a squad agent — reference the skill from its task.md / prompts
# (the squad runner loads the SKILL.md body verbatim).

# From any host that supports a user-skills directory — drop the
# folder in place.
cp -r add-groceries-to-whole-foods-cart /path/to/host/skills/
```

## Available Skills

| Skill                                                                    | Description                                                                                                                                       |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| [add-groceries-to-whole-foods-cart](./add-groceries-to-whole-foods-cart) | Parse a weekly grocery list from a Google Doc planner and add non-completed items to an Amazon/Whole Foods cart. Stops at cart, never checks out. |

## Skill Structure

```text
skill-name/
└── SKILL.md
```

`SKILL.md` is markdown with YAML frontmatter:

```markdown
---
name: skill-name
description: One sentence that tells the host when to use this skill. Be specific — this is the only thing the host sees at routing time.
---

# Body

Objective, inputs, step-by-step instructions, host-portability notes,
and guardrails ("never check out", "stop if you see a sign-in page").
```

### Frontmatter rules

| Field         | Required | Notes                                                                                  |
| ------------- | -------- | -------------------------------------------------------------------------------------- |
| `name`        | yes      | Must match the directory name exactly.                                                 |
| `description` | yes      | Single line. Drives skill selection — vague descriptions get the skill missed.         |

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

See [`add-groceries-to-whole-foods-cart/SKILL.md`](./add-groceries-to-whole-foods-cart/SKILL.md)
for a worked example.

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
- `description` would let the host pick it correctly from a list of 30
  unrelated skills.
- The body is followable cold — no relying on conversation history.
- Guardrails are explicit ("never X", "stop if Y").

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
