---
name: changelog-standards
description: "Changelog standards: Keep a Changelog sections, entry style, semantic versioning and breaking changes, and antsibull-changelog fragments for Ansible collections. Use when writing a release entry, reviewing a CHANGELOG, or deciding which commits are user-facing."
---
# Changelog Standards

A comprehensive guide to writing and maintaining changelogs following the Keep a Changelog specification and semantic versioning best practices. This document serves as the knowledge base for the changelog pattern.

## Table of Contents

1. [Core Principles](#core-principles)
2. [Changelog Format](#changelog-format)
3. [Change Categories](#change-categories)
4. [Writing Guidelines](#writing-guidelines)
5. [Version Numbering](#version-numbering)
6. [Common Patterns](#common-patterns)
7. [Quality Checklist](#quality-checklist)

---

## Core Principles

### What is a Changelog?

A changelog is a file containing a curated, chronologically ordered list of notable changes for each version of a project.

### Why Keep a Changelog?

| Benefit | Description |
|---------|-------------|
| User awareness | Help users understand what changed |
| Upgrade decisions | Help users decide when to upgrade |
| Release tracking | Document release history |
| Team communication | Share changes across team |

### Guiding Principles

1. Changelogs are for **humans**, not machines
2. There should be an entry for **every version**
3. The same types of changes should be **grouped**
4. Versions and sections should be **linkable**
5. Latest version comes **first**
6. Release **date** of each version is displayed
7. Follow **Semantic Versioning**

---

## Changelog Format

### File Structure

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Added support for custom output templates

## [1.0.0] - 2026-01-10

### Added
- Released initial version with core features

[Unreleased]: https://github.com/user/repo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/user/repo/releases/tag/v1.0.0
```

### Version Header Format

```markdown
## [X.Y.Z] - YYYY-MM-DD
```

Components:

- `X.Y.Z` - Semantic version number
- `YYYY-MM-DD` - ISO 8601 date format
- Square brackets for linkability

---

## Change Categories

### Standard Categories

Include only the categories that apply to a release (omit empty headings), always in this exact order:

| Category | Description | Examples |
|----------|-------------|----------|
| **Added** | New features | New API endpoint, new command |
| **Changed** | Changes to existing functionality | Modified behavior, updated dependency |
| **Deprecated** | Features marked for removal | Deprecated function, deprecated flag |
| **Removed** | Removed features | Deleted endpoint, removed command or field |
| **Fixed** | Bug fixes | Corrected error, fixed crash |
| **Security** | Security fixes | Patched vulnerability, fixed auth issue |

### Category Guidelines

**Added:**

- New features, capabilities, or functionality
- New modules, commands, or API endpoints
- New configuration options

**Changed:**

- Modifications to existing functionality
- Updated dependencies (major versions)
- Changed default behaviors
- Renamed items

**Deprecated:**

- Features that will be removed in future versions
- Include migration path when possible
- Specify target removal version if known

**Removed:**

- Public features, commands, endpoints, flags, or configuration fields that have been deleted
- Removing part of the public API (even one deprecated in an earlier release) is backwards-incompatible and requires a MAJOR version bump once past `1.0.0`
- Prefer deprecating for at least one minor release before removing when practical

**Fixed:**

- Bug corrections
- Error handling improvements
- Performance fixes

**Security:**

- Security vulnerability fixes
- Authentication/authorization fixes
- Data protection improvements
- Include CVE numbers when applicable

---

## Writing Guidelines

### Entry Format

Begin every bullet directly with a past-tense verb (`Added`, `Changed`, `Updated`, `Renamed`, `Deprecated`, `Removed`, `Fixed`, `Patched`) as the first word after `-`. Place callouts such as `(**BREAKING**)`, migration notes, and issue or PR references (`(#123)`) after the opening verb phrase, never as a prefix ahead of the verb.

**Good entries:**

```markdown
- Added `--verbose` flag to enable detailed output (#123)
- Fixed crash when processing empty files (#128)
- Changed default timeout from 30s to 60s
- Deprecated `OldFunction()` in favor of `NewFunction()`
- Removed deprecated `LegacyOption` field (**BREAKING**; use `TimeoutOption` instead)
```

**Bad entries:**

```markdown
- Fixed bug  # Too vague
- Various improvements  # Not specific
- Updated code  # Meaningless
- Bumped version  # Not user-relevant
- **BREAKING:** Removed `LegacyOption`  # Prefix displaces the leading past-tense verb
- `--verbose` flag for detailed output  # Noun phrase instead of past-tense verb
```

### Style Guidelines

| Guideline | Example |
|-----------|---------|
| Use past-tense verbs | "Added", "Fixed", "Removed" in changelogs (commits use imperative "Add", "Fix") |
| Lead with the verb | First word after `-` is the past-tense verb; place `(**BREAKING**)` or `(#123)` after |
| Be specific | Name the function, command, field, or behavior that changed |
| Include references | Issue numbers, PR links, or CVEs where known |
| Keep entries concise | One change per entry |

### What to Include

**Include:**

- User-facing changes
- API changes
- Breaking changes
- Security fixes
- Significant bug fixes
- Deprecation notices

**Exclude:**

- Internal refactoring (unless affecting user-visible performance or behavior)
- Code formatting or style-only sweeps (e.g., `gofmt`, `prettier`, `rustfmt`)
- Version-bump commits
- Development tooling changes
- Minor dependency updates
- Typo fixes (unless in user-facing content)
- CI/CD changes (unless affecting releases)

### Reference Linking

```markdown
- Fixed authentication bypass vulnerability ([CVE-2026-1234])
- Added new export command (#456)
- Changed configuration format (see [Migration Guide])

[CVE-2026-1234]: https://nvd.nist.gov/vuln/detail/CVE-2026-1234
[Migration Guide]: docs/migration.md
```

---

## Version Numbering

### Semantic Versioning (SemVer)

Format: `MAJOR.MINOR.PATCH`

| Component | When to Increment |
|-----------|-------------------|
| MAJOR | Breaking/incompatible API changes |
| MINOR | New functionality (backwards-compatible) |
| PATCH | Bug fixes (backwards-compatible) |

When a release combines multiple types of changes (for example, a new feature, a bug fix, and a removed public field), the highest-impact change determines the version bump (`MAJOR` overrides `MINOR` and `PATCH`).

### Pre-release Versions

```markdown
## [1.0.0-alpha.1] - 2026-01-01
## [1.0.0-beta.1] - 2026-01-05
## [1.0.0-rc.1] - 2026-01-08
## [1.0.0] - 2026-01-10
```

### Breaking Changes

Removing a public function, flag, endpoint, or configuration field (even one deprecated in a prior release), renaming a public symbol without keeping an alias, or making an incompatible signature or behavior change warrants a **MAJOR** bump (`1.4.2` -> `2.0.0`).

Group each breaking entry under the standard category that matches the change (`Removed` for deleted symbols/fields, `Changed` for renames or incompatible behavior modifications) and highlight it with `(**BREAKING**)` **after** the opening past-tense verb phrase so every bullet still starts with a past-tense verb:

```markdown
## [2.0.0] - 2026-01-10

### Changed

- Renamed `config.yaml` to `settings.yaml` (**BREAKING**; rename existing config files before upgrading)
- Changed API response format for `/users` endpoint (**BREAKING**)

### Removed

- Removed deprecated `Client.LegacyMode` field (**BREAKING**; use `Client.Timeout` instead)
```

---

## Common Patterns

### Initial Release

```markdown
## [1.0.0] - 2026-01-10

### Added

- Released initial version of the CLI and library
- Added core functionality for X, Y, and Z
- Added command-line interface with basic commands
- Added configuration file support
- Added documentation and examples
```

### Feature Release

```markdown
## [1.1.0] - 2026-02-15

### Added

- Added `export` command for data export (#234)
- Added support for YAML configuration files
- Added plugin system for custom extensions

### Changed

- Improved error messages with more context
- Changed default timeout from 30s to 60s

### Fixed

- Fixed memory leak in long-running processes (#245)
```

### Bug Fix Release

```markdown
## [1.0.1] - 2026-01-15

### Fixed

- Fixed crash when input file is empty (#201)
- Fixed incorrect calculation in edge cases
- Fixed typo in error messages

### Security

- Fixed authentication bypass vulnerability ([CVE-2026-1234])
```

### Deprecation and Removal

```markdown
## [1.2.0] - 2026-03-01

### Deprecated

- Deprecated `OldFunction()` in favor of `NewFunction()` (scheduled for removal in v2.0.0)

## [2.0.0] - 2026-06-01

### Removed

- Removed `OldFunction()`, deprecated in v1.2.0 (**BREAKING**; use `NewFunction()` instead)
```

---

## Special Formats

### Ansible/antsibull-changelog Format

Ansible collections that use antsibull-changelog do not take Keep a Changelog
headings. Each change is a YAML fragment in `changelogs/fragments/`, and the
section keys must be ones the collection allows.

The allowed keys come from the `sections` list in `changelogs/config.yaml`. When
that file keeps the defaults, the keys are `major_changes`, `minor_changes`,
`breaking_changes`, `deprecated_features`, `removed_features`,
`security_fixes`, `bugfixes` and `known_issues`, plus the special
`release_summary`. Read `changelogs/config.yaml` before writing anything, and
use only the keys it lists: a collection can rename or add sections, and an
unknown key fails `antsibull-changelog lint`.

```yaml
---
release_summary: "Brief 1-2 sentence overview of this release"
minor_changes:
  - "role_name - Added new feature X"
  - "module_name - Added Y capability"
bugfixes:
  - "role_name - Fixed issue with W"
```

**Rules for antsibull-changelog:**

- `release_summary` is a single string, not a list
- All other sections are lists of strings
- Map Keep a Changelog categories onto the configured keys (with the
  defaults: Added and most Changed go to `minor_changes`, Fixed to
  `bugfixes`, Security to `security_fixes`, Deprecated to
  `deprecated_features`, Removed to `removed_features`, incompatible changes
  to `breaking_changes`)
- Prefix changes with module/role/plugin name
- Use past tense: "Added", "Enhanced", "Fixed"
- Quote every entry; in an unquoted entry a space followed by `#` starts a
  YAML comment and silently truncates the entry
- Validate with `antsibull-changelog lint`
- Output only raw YAML content

---

## Quality Checklist

### Before Release

- [ ] All user-facing changes documented
- [ ] Changes grouped by category
- [ ] Categories in standard order
- [ ] Entries are specific and actionable
- [ ] Breaking changes highlighted
- [ ] Version follows SemVer
- [ ] Date in ISO 8601 format
- [ ] References linked (issues, PRs, CVEs)
- [ ] Unreleased section updated

### Entry Quality

- [ ] Begins directly with a past-tense verb (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`), with `(**BREAKING**)` placed after the verb phrase rather than before
- [ ] Specific about what changed
- [ ] Includes reference numbers
- [ ] Single change per entry
- [ ] Written for users, not developers

---

## Anti-Patterns

### Don't Do This

```markdown
# Bad Examples

## v1.0
- Various bug fixes
- Updated dependencies
- Code cleanup
- Misc improvements
```

### Do This Instead

```markdown
# Good Examples

## [1.0.0] - 2026-01-10

### Added
- Added `export` command for CSV data export (#123)

### Changed
- Updated authentication library to v2.0 for security improvements

### Fixed
- Fixed crash when processing files over 1GB (#456)
```

---

## References

- [Keep a Changelog](https://keepachangelog.com/)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [antsibull-changelog](https://github.com/ansible-community/antsibull-changelog)
