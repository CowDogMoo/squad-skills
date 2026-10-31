#!/usr/bin/env bash
# Print the context needed to cut an Ansible collection release: last tag,
# galaxy.yml version, user-facing commits, collapsed dependency bumps, a
# suggested next version, and warnings. Run from the collection root.
#
# Usage: release-context.sh [FROM_TAG]
#   FROM_TAG overrides the detected last release tag.
set -euo pipefail

if [ ! -f galaxy.yml ]; then
	echo "error: galaxy.yml not found; run from the collection root" >&2
	exit 1
fi

warn() { printf 'WARNING: %s\n' "$*"; }

# Release tags are usually created on GitHub (gh release create), so a local
# clone may lack the newest one and git describe would pick an older tag.
if ! git fetch --tags --quiet 2>/dev/null; then
	warn "git fetch --tags failed; the last tag below may be stale"
fi

last_tag=${1:-$(git describe --tags --abbrev=0 2>/dev/null || true)}
if [ -n "$last_tag" ] && ! git rev-parse --verify --quiet "refs/tags/${last_tag}" >/dev/null; then
	echo "error: tag ${last_tag} not found" >&2
	exit 1
fi
galaxy_version=$(sed -n 's/^version:[[:space:]]*//p' galaxy.yml | tr -d "\"'" | head -n 1)

echo "== Release context"
echo "galaxy.yml version: ${galaxy_version:-unknown}"
echo "last tag:           ${last_tag:-none}"

if [ -n "$last_tag" ]; then
	range="${last_tag}..HEAD"
	# Compare without a leading v: version sort ranks v1.3.0 above 2.8.0.
	newest_tag=$(git tag | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$' | sed 's/^v//' | sort -V | tail -n 1)
	if [ -n "$newest_tag" ] && [ "$newest_tag" != "${last_tag#v}" ]; then
		warn "newest tag overall is ${newest_tag}, but ${last_tag} is the nearest ancestor of HEAD"
	fi
	if git show-ref --verify --quiet "refs/heads/${last_tag}"; then
		warn "a local branch is named ${last_tag}, the same as the tag; delete it (git branch -D ${last_tag})"
	fi
	if [ "${last_tag#v}" != "${galaxy_version}" ]; then
		warn "galaxy.yml version (${galaxy_version}) does not match the last tag (${last_tag})"
	fi
else
	range="HEAD"
	warn "no tags found; treating every commit as unreleased"
fi

subjects=$(git log "$range" --no-merges --format='%s')
total=$(printf '%s\n' "$subjects" | sed '/^$/d' | wc -l | tr -d ' ')
echo "range:              ${range} (${total} commits)"

dep_re='^(chore|build|fix)\(deps\)'
user_facing=$(printf '%s\n' "$subjects" | grep -Ev "$dep_re" | sed '/^$/d' || true)
deps=$(printf '%s\n' "$subjects" | grep -E "$dep_re" || true)

echo
echo "== User-facing candidates (excluding dependency bumps)"
if [ -n "$user_facing" ]; then
	printf '%s\n' "$user_facing" | sed 's/^/  /'
else
	echo "  (none)"
fi

echo
echo "== Dependency bumps, newest version per dependency (git log is newest first)"
if [ -n "$deps" ]; then
	printf '%s\n' "$deps" | awk '
		{
			line = $0
			pr = ""
			if (match(line, /\(#[0-9]+\)$/)) {
				pr = substr(line, RSTART + 1, RLENGTH - 2)
				line = substr(line, 1, RSTART - 2)
			}
			sub(/^[a-z]+\(deps\): (update|pin) /, "", line)
			sub(/^dependency /, "", line)
			n = split(line, parts, / to /)
			if (n < 2) { next }
			name = parts[1]; ver = parts[n]
			if (!(name in newest)) { newest[name] = ver; order[++count] = name }
			prs[name] = (prs[name] == "" ? pr : prs[name] ", " pr)
		}
		END {
			for (i = 1; i <= count; i++) {
				name = order[i]
				printf "  %s -> %s (%s)\n", name, newest[name], prs[name]
			}
		}'
else
	echo "  (none)"
fi

# SemVer suggestion from conventional-commit markers only; Step 2 of the skill
# says when to override it.
bump="patch"
if git log "$range" --no-merges --format='%s%n%b' | grep -Eq '^[a-z]+(\([^)]*\))?!:|BREAKING CHANGE'; then
	bump=major
elif printf '%s\n' "$user_facing" | grep -Eq '^feat(\([^)]*\))?:'; then
	bump=minor
fi

base=${last_tag#v}
if printf '%s' "$base" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
	IFS=. read -r major minor patch <<<"$base"
	case "$bump" in
	major) next="$((major + 1)).0.0" ;;
	minor) next="${major}.$((minor + 1)).0" ;;
	*) next="${major}.${minor}.$((patch + 1))" ;;
	esac
	prefix=""
	[ "$last_tag" != "$base" ] && prefix="v"
	echo
	echo "== Suggested next version: ${prefix}${next} (${bump}, from commit prefixes)"
fi

echo
echo "== Repo release tooling"
if [ -f changelogs/config.yaml ]; then
	sections=$(python3 -c 'import sys,yaml; print(", ".join(s[0] for s in yaml.safe_load(open(sys.argv[1])).get("sections", [])))' changelogs/config.yaml 2>/dev/null || echo "unreadable (is PyYAML installed?)")
	echo "changelog sections: ${sections}"
else
	warn "changelogs/config.yaml not found; this may not be an antsibull-changelog collection"
fi
for doc in docs/releases.md RELEASING.md; do
	[ -f "$doc" ] && echo "release doc:        ${doc} (read it before proceeding)"
done
for f in Taskfile.yaml Taskfile.yml; do
	if [ -f "$f" ]; then
		for t in release release-finalize gen-changelog-fragment; do
			grep -Eq "^  ${t}:" "$f" && echo "task:               ${t} (${f})"
		done
	fi
done
for wf in .github/workflows/*; do
	[ -f "$wf" ] || continue
	case "$(basename "$wf")" in
	*release* | *publish* | *galaxy*) echo "publish workflow:   $(basename "$wf")" ;;
	esac
done
