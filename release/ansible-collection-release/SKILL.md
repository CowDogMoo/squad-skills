---
name: ansible-collection-release
description: "Cut a release of an Ansible collection that uses antsibull-changelog, a galaxy.yml version, and a tag-triggered Galaxy publish workflow: pick the SemVer bump from commits since the last tag, write and validate the changelog fragment, run the Taskfile release flow (task release, then task release-finalize after the PR merges), and verify the GitHub release and Galaxy publish. Use when asked to create a new release, cut a release, bump the collection version, publish to Ansible Galaxy, or finish a release whose PR has merged."
license: MIT
compatibility: "Needs git, gh (authenticated), antsibull-changelog, python3 with PyYAML, and network access to GitHub and galaxy.ansible.com. go-task is optional; the manual path covers repos without a Taskfile."
allowed-tools: Bash, Read, Edit, Write
metadata:
  author: Jayson Grace
  version: 1.0.0
---

# Ansible Collection Release

Turn the commits merged since the last release into a published collection
version: a changelog fragment, a `galaxy.yml` bump, a release PR, a tag, a
GitHub release, and a Galaxy upload. Run every step from the collection root
(the directory holding `galaxy.yml`).

## Guardrails

- **Follow the repo's own release doc first.** If `docs/releases.md` (or a
  `RELEASING.md`) exists, read it before anything else; this skill fills gaps
  and fixes known failure modes, it does not override the doc. When the doc and
  the repo disagree (a task calls a tool that no longer exists), say so and use
  the doc's manual path rather than inventing a third flow.
- **Ask before anything public and permanent.** Merging the release PR,
  creating the tag, and publishing to Galaxy cannot be cleanly undone — a
  Galaxy version can never be re-uploaded. Get an explicit go-ahead for those
  steps unless the user already gave one for this release.
- **Never skip hooks.** If pre-commit rejects the release commit, fix the files
  and commit again. Never `--no-verify`.
- **Never hand-edit released history.** Only the new version's section in
  `changelogs/changelog.yaml` and `CHANGELOG.rst` may change; prior entries stay
  byte-identical.
- **Honor the host's commit and PR rules.** If the user's instructions require
  a specific commit or PR tool (for example `squad_commit` and `squad_pr`), use
  it in place of the hand-written `git commit -m` / `gh pr create` that release
  Taskfiles often contain.

## Step 1 — Gather the release context

```bash
bash "$SKILL_DIR/scripts/release-context.sh"
```

`$SKILL_DIR` is this skill's directory (`$SQUAD_SKILL_DIR` in squad,
`${CLAUDE_SKILL_DIR}` in Claude Code). The script fetches tags, finds the last
release tag, prints the `galaxy.yml` version, the user-facing commits, the
dependency bumps collapsed to their newest version, a suggested next version,
and warnings. Read its warnings before going on.

It fetches tags first for a reason: `gh release create` makes the tag on
GitHub only, so a clone that cut the previous release may not have that tag
locally, and `git describe` silently falls back to an older one — doubling the
changelog range.

## Step 2 — Choose the version

Apply SemVer to what users of the collection observe:

| Bump  | When                                                                                     |
| ----- | ---------------------------------------------------------------------------------------- |
| Major | A role, variable, or default was removed or renamed, or behavior changed incompatibly     |
| Minor | Any new role, variable, toggle, or capability, with nothing breaking                       |
| Patch | Only fixes and dependency bumps                                                          |

The script's suggestion reads commit prefixes only. Override it when a body
reveals a breaking change, and look at major-version bumps of required
collections (for example `amazon.aws` 11 → 12) — they can break users even
when no role changed. Match the existing tag style (`2.8.0` vs `v2.8.0`).

## Step 3 — Write the changelog fragment

If the repo's `release` task generates the fragment itself (an agent or
pattern call), let it run, then review its output with Step 4 instead of
writing one by hand.

Otherwise write `changelogs/fragments/<version>.yaml` (create the
`fragments/` directory; it is often absent between releases):

```yaml
---
release_summary: |
  One to three sentences on what this release brings.
added:
  - Added the ``herdr`` role (#1084)
changed:
  - 'Updated Go to v1.27.3 (#1117, #1119)'
fixed:
  - Fixed tmux status-left truncation (#1026)
```

- Use only the sections listed in `changelogs/config.yaml` plus
  `release_summary`. Collections often trim the default set (no `security`,
  no `deprecated`).
- Never add `release_date`, `ancestor`, or `releases` — antsibull adds them.
- **Single-quote any entry containing `#` after a space.** In plain YAML,
  `(#1028, #1093)` is cut at `#1093` as a comment and the entry ships as
  `(#1028,`. This has shipped in a real release PR.
- Past tense, one change per entry, user impact over implementation, PR
  number in parentheses. Group related commits into one entry.
- Leave out CI, docs, tests, refactors, and anything a collection user cannot
  observe. Drop changes that were added and then reverted in the same range.
- List each dependency once, at its newest version, with every PR that moved
  it (from the script's collapsed list). Skip CI-only bumps (GitHub Actions,
  Renovate, pre-commit hooks).

## Step 4 — Validate the fragment

```bash
python3 "$SKILL_DIR/scripts/check-fragment.py" changelogs/fragments/<version>.yaml
antsibull-changelog lint
```

`check-fragment.py` catches what `antsibull-changelog lint` does not: sections
outside `config.yaml`, unquoted `#` truncation, and unbalanced parentheses.
Fix every finding before generating the changelog.

## Step 5 — Generate the changelog and open the release PR

Preferred, when the repo's Taskfile has the tasks:

```bash
NEXT_VERSION=<version> task -y release
```

It branches, (optionally) generates the fragment, runs
`antsibull-changelog release`, bumps `galaxy.yml`, commits, pushes, and opens
the PR. If its fragment step fails, fall back to the manual path below rather
than patching the Taskfile mid-release; fix the Taskfile in a separate PR.

Manual path:

```bash
git checkout -b <version>
NEXT_VERSION=<version> task -y ansible:gen-changelog   # or: antsibull-changelog release --version <version>
# bump galaxy.yml `version:` if the task did not
git add galaxy.yml changelogs/
```

Then commit and open the PR (with the host's required tools, if any).

Expect pre-commit to touch the generated `CHANGELOG.rst`: trailing whitespace
and codespell failures are common, because entries copied from commit subjects
often carry misspellings. Apply each fix to both `changelog.yaml` and
`CHANGELOG.rst`, restage, and commit again.

After the PR exists, read its title and body and the rendered
`CHANGELOG.rst` section once more. A truncated entry or a wrong version is
cheapest to fix now.

## Step 6 — Merge

Wait for PR CI to pass, then — with the user's go-ahead — merge. If the repo
uses a merge queue, `gh pr merge --delete-branch` fails; use `gh pr merge
<number>` to enqueue, and expect the queue to rerun the full test matrix (it
can take much longer than the PR checks). Confirm the PR state is `MERGED`
before going on.

## Step 7 — Finalize: tag, GitHub release, Galaxy

```bash
NEXT_VERSION=<version> task -y release-finalize
```

Without the task: `git checkout main && git pull`, then
`gh release create <version> -F changelogs/CHANGELOG.rst`. The tag must point
at the merged commit on `main`, never at the release branch.

The tag push triggers the publish workflow. Verify all three:

```bash
gh release view <version>
gh run list --workflow release.yaml --limit 1     # then: gh run watch <id> --exit-status
curl -fsS "https://galaxy.ansible.com/api/v3/plugin/ansible/content/published/collections/index/<namespace>/<name>/" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['highest_version']['version'])"
```

Take `<namespace>` and `<name>` from `galaxy.yml`, and the workflow file name
from `.github/workflows/`.

## Step 8 — Clean up

- Delete the local release branch if it is named exactly like the tag
  (`git branch -D <version>`). Otherwise every later `git log <version>..HEAD`
  warns `refname '<version>' is ambiguous` and may resolve to the branch.
- `git fetch --tags` so the new tag exists locally for the next release.

## Report

End with: the version and why that bump, the PR URL and merge state, the tag
and GitHub release URL, the publish workflow result, the version Galaxy now
reports, and anything skipped or awaiting the user's go-ahead.
