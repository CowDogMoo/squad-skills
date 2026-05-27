# Squad Skills

**Portable [Anthropic Agent Skills](https://www.anthropic.com/news/agent-skills)
for Claude Code, Claude Desktop, and the
[squad](https://github.com/cowdogmoo/squad) CLI.**

[![License](https://img.shields.io/github/license/CowDogMoo/squad-skills?label=License&style=flat&color=blue&logo=github)](https://github.com/CowDogMoo/squad-skills/blob/main/LICENSE)
[![Pre-Commit](https://github.com/CowDogMoo/squad-skills/actions/workflows/pre-commit.yaml/badge.svg)](https://github.com/CowDogMoo/squad-skills/actions/workflows/pre-commit.yaml)
[![Validate Skills](https://github.com/CowDogMoo/squad-skills/actions/workflows/validate-skills.yaml/badge.svg)](https://github.com/CowDogMoo/squad-skills/actions/workflows/validate-skills.yaml)

---

## Overview

A companion repository to
[squad-agents](https://github.com/cowdogmoo/squad-agents) for the
*skill* side of the Claude stack. Skills are single-file procedures
(`SKILL.md`) that ship a name, a one-line description, and a body of
instructions — Claude reads the description to decide when to invoke
the skill, then follows the body.

Skills in this repository are written to be **host-portable**: the
same `SKILL.md` works whether it's loaded by Claude Code, dropped into
Claude Desktop, or referenced by a squad runner agent. Each skill
resolves the right MCP tool names from whatever host it lands in.

## Quick Start

### Claude Code

Drop a skill directory into your user skills directory:

```bash
mkdir -p ~/.claude/skills
cp -r add-groceries-to-whole-foods-cart ~/.claude/skills/
```

Claude Code will read `SKILL.md` and surface the skill when its
description matches what you're asking for. Invoke it explicitly with
`/<skill-name>` or let Claude pick it.

### Claude Desktop

Skills go in the Desktop skills directory; the layout is the same — a
folder containing a `SKILL.md` with frontmatter.

### squad

```bash
go install github.com/cowdogmoo/squad/cmd/squad@latest
squad skills add official https://github.com/cowdogmoo/squad-skills.git
squad skills list
```

## Available Skills

| Skill                                                                            | Description                                                                                                       |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| [add-groceries-to-whole-foods-cart](./add-groceries-to-whole-foods-cart)         | Parse a weekly grocery list from a Google Doc planner and add non-completed items to an Amazon/Whole Foods cart. Stops at cart, never checks out. |

More skills land here as they're written. See
[Creating a Skill](#creating-a-skill) below.

## Skill Structure

Each skill directory contains a single `SKILL.md`:

```text
skill-name/
└── SKILL.md
```

`SKILL.md` is a markdown file with YAML frontmatter:

```markdown
---
name: skill-name
description: One sentence that tells Claude when to use this skill. Be specific — this is the only thing Claude sees at routing time.
---

# Body

The full procedure: objective, inputs, step-by-step instructions,
host-portability notes, and any guardrails ("never check out", "stop
if you see a sign-in page", etc.).
```

### Frontmatter rules

| Field         | Required | Notes                                                                                |
| ------------- | -------- | ------------------------------------------------------------------------------------ |
| `name`        | yes      | Must match the directory name exactly. Used by `/skill-name` slash commands.         |
| `description` | yes      | One line. Drives skill selection — vague descriptions make Claude miss the skill.    |

### Body conventions

The body is freeform markdown, but skills in this repo follow a few
conventions:

- **Lead with a "Host-environment translation" section** if the skill
  uses MCP tools whose names differ between hosts (Claude Code vs.
  Desktop vs. squad). Map the tool names once at the top instead of
  forking the prose.
- **State the objective and guardrails up front** — what counts as
  done, what counts as "stop and ask".
- **Treat the skill as a runbook**, not a manual. Steps should be
  numbered and executable, not narrative.

## Host Portability

The skills here target three hosts and the MCP tool surface differs
across them. The pattern that works:

1. Write the skill against an abstract action ("read the Google Doc as
   HTML", "navigate the browser", "ask the user a go/no-go question").
2. Provide a translation table at the top of `SKILL.md` mapping the
   abstract action to each host's actual tool name.
3. Pick the richer fallback path when the host exposes it (e.g. a
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
- `description` would let Claude pick it correctly from a list of 30
  unrelated skills.
- The body is followable cold — no relying on conversation history.
- Guardrails are explicit ("never X", "stop if Y").

## Contributing

PRs welcome. Before opening one:

```bash
pre-commit install        # one-time
pre-commit run --all-files
```

The CI pipeline runs the same checks:

- `SKILL.md` exists in every non-hidden top-level directory.
- Frontmatter has `name` and `description`, both non-empty.
- `name` matches the directory name.
- Markdown lints clean (`markdownlint`), YAML lints clean
  (`yamllint`), and frontmatter parses.

---

**Maintained by [Jayson Grace](https://github.com/CowDogMoo)** |
[Issues](https://github.com/cowdogmoo/squad-skills/issues) |
[squad-agents](https://github.com/cowdogmoo/squad-agents) |
[squad CLI](https://github.com/cowdogmoo/squad)
