#!/usr/bin/env bash
# Set up a workspace where an agent reorganizes an iPhone Home Screen through the
# open-source Unjiggle CLI over USB. It never writes to the phone.
#
#   bash setup_workspace.sh [target-dir]   (default: ~/src/iphone-homescreen)
#
#   1. Creates the workspace (plans/, state/) and a Python venv in it
#   2. Installs unjiggle==0.3.3 (GPL-3.0, github.com/chungty/unjiggle; uses pymobiledevice3)
#   3. Turns off Unjiggle's one-time analytics prompt (an interactive prompt hangs an agent)
#   4. Writes CLAUDE.md (+ AGENTS.md link) with the ground rules, and .claude/settings.json:
#      read-only commands allowed, every phone write forced to ask, risky commands denied
#   5. Smoke-tests the CLI and checks for a connected iPhone (read-only)
#
# Existing CLAUDE.md and settings.json are backed up, not overwritten in place.

set -euo pipefail

UNJIGGLE_VERSION="0.3.3"
DIR="${1:-$HOME/src/iphone-homescreen}"

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() {
	printf '\033[1;31mxx\033[0m %s\n' "$*" >&2
	exit 1
}

[[ "$(uname -s)" == "Darwin" ]] || die "Unjiggle's CLI is macOS-only (it reaches the iPhone through macOS usbmuxd)."

PY=""
for cand in python3 python3.14 python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3; do
	if command -v "$cand" >/dev/null 2>&1 &&
		"$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
		PY="$(command -v "$cand")"
		break
	fi
done
[[ -n "$PY" ]] || die "Need Python 3.10+. Install one (brew install python) and rerun."
say "Using $("$PY" --version) at $PY"

mkdir -p "$DIR"/{plans,state,.claude}
cd "$DIR"

if [[ ! -x .venv/bin/python ]]; then
	say "Creating venv in $DIR/.venv"
	"$PY" -m venv .venv
fi
say "Installing unjiggle==$UNJIGGLE_VERSION"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet "unjiggle==$UNJIGGLE_VERSION"

.venv/bin/python - <<'PY'
import json, pathlib
p = pathlib.Path.home() / ".unjiggle" / "config.json"
p.parent.mkdir(parents=True, exist_ok=True)
try:
    cfg = json.loads(p.read_text())
except Exception:
    cfg = {}
cfg.setdefault("analytics_prompted", True)
cfg.setdefault("analytics_enabled", False)
p.write_text(json.dumps(cfg, indent=2))
PY

backup_if_present() {
	if [[ -f "$1" ]]; then
		cp "$1" "$1.bak.$(date +%Y%m%d%H%M%S)"
	fi
}

backup_if_present CLAUDE.md
cat >CLAUDE.md <<'MD'
# iPhone Home Screen workspace

This folder drives the iPhone Home Screen through the Unjiggle CLI (`.venv/bin/unjiggle`, pinned
to 0.3.3) over USB. Load the `organize-iphone-home-screen` skill for the full runbook.

## Ground rules

- Never write to the phone without explicit approval in chat for that exact plan. Approval covers
  one apply. A new or changed plan needs new approval. A restore is a write too.
- Every Unjiggle write goes through `json check-operations` then `json apply-checked`. Never use
  `json apply`, `suggest`, `go`, `restore` without approval, or `safety-test --write-roundtrip`.
- The one other write path is the skill's `installed_first.py apply`, only after the user approves
  its preview.
- If anything after a write looks off, stop. Don't retry, don't restore on your own. Rescan
  (read-only), diff, and report what happened and the backup path.
- Unjiggle never uninstalls apps. `move_to_app_library` only takes the icon off the Home Screen.
- Keep scans in `state/` and plans in `plans/`. Run every command from this folder.
MD
ln -sf CLAUDE.md AGENTS.md

backup_if_present .claude/settings.json
cat >.claude/settings.json <<'JSON'
{
  "permissions": {
    "allow": [
      "Bash(.venv/bin/unjiggle json status)",
      "Bash(.venv/bin/unjiggle json scan *)",
      "Bash(.venv/bin/unjiggle json inventory *)",
      "Bash(.venv/bin/unjiggle json diagnose *)",
      "Bash(.venv/bin/unjiggle json check-operations *)",
      "Bash(.venv/bin/unjiggle json pending-checked *)",
      "Bash(.venv/bin/unjiggle scan *)",
      "Bash(.venv/bin/unjiggle score *)",
      "Bash(.venv/bin/unjiggle backup *)",
      "Bash(.venv/bin/unjiggle --help)",
      "Bash(.venv/bin/unjiggle json --help)",
      "Edit(/plans/**)",
      "Edit(/state/**)"
    ],
    "ask": [
      "Bash(.venv/bin/unjiggle json apply-checked *)",
      "Bash(.venv/bin/unjiggle json restore *)",
      "Bash(.venv/bin/unjiggle json restore-checked *)",
      "Bash(.venv/bin/unjiggle restore *)",
      "Bash(.venv/bin/python *installed_first.py apply*)"
    ],
    "deny": [
      "Bash(.venv/bin/unjiggle go *)",
      "Bash(.venv/bin/unjiggle suggest *)",
      "Bash(.venv/bin/unjiggle analyze *)",
      "Bash(.venv/bin/unjiggle mirror *)",
      "Bash(.venv/bin/unjiggle obituary *)",
      "Bash(.venv/bin/unjiggle report *)",
      "Bash(.venv/bin/unjiggle safety-test --write-roundtrip*)",
      "Bash(.venv/bin/unjiggle json apply *)",
      "Bash(unjiggle go *)",
      "Bash(unjiggle suggest *)",
      "Bash(unjiggle json apply *)"
    ]
  }
}
JSON

printf '.venv/\nstate/\n' >.gitignore

say "Smoke test: unjiggle demo (no phone)"
if .venv/bin/unjiggle demo </dev/null >/dev/null 2>&1; then
	say "CLI works"
else
	warn "unjiggle demo failed; run '.venv/bin/unjiggle demo' to see why"
fi

say "Checking for a connected iPhone (read-only)"
STATUS="$(.venv/bin/unjiggle json status </dev/null 2>/dev/null || true)"
echo "    $STATUS"
if [[ "$STATUS" == *'"connected": true'* ]]; then
	say "iPhone connected."
else
	warn "No iPhone yet. Plug it in over USB, unlock it, tap Trust This Computer, then run:"
	warn "    $DIR/.venv/bin/unjiggle json status"
fi

say "Done. Workspace: $DIR (nothing touches the phone until a checked plan is approved)"
