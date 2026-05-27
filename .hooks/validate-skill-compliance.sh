#!/bin/bash
set -eo pipefail

# Validate skill compliance for any SKILL.md staged by pre-commit.
# Checks:
#   - frontmatter parses
#   - `name` and `description` are present and non-empty
#   - `name` matches the parent directory name
#   - `description` is a single line (skills are routed by it; multi-line
#     descriptions confuse host loaders)

RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m'

errors=0
warnings=0

error() {
	echo -e "${RED}  FAIL${NC} $1"
	errors=$((errors + 1))
}
warn() {
	echo -e "${YELLOW}  WARN${NC} $1"
	warnings=$((warnings + 1))
}
pass() { echo -e "${GREEN}  OK${NC}   $1"; }

check_skill() {
	local skill_md="$1"
	local skill_dir
	local skill_name
	skill_dir=$(dirname "$skill_md")
	skill_name=$(basename "$skill_dir")

	echo "Checking ${skill_name}"

	# Frontmatter must be the first thing in the file, fenced by `---` lines.
	if ! head -1 "$skill_md" | grep -qx -- '---'; then
		error "${skill_md}: missing YAML frontmatter (file must start with '---')"
		return
	fi

	# Extract frontmatter between the first two `---` lines.
	local fm
	fm=$(awk '
		BEGIN { in_fm = 0; seen = 0 }
		/^---$/ {
			if (in_fm) { exit }
			if (!seen) { in_fm = 1; seen = 1; next }
		}
		in_fm { print }
	' "$skill_md")

	if [ -z "$fm" ]; then
		error "${skill_md}: frontmatter is empty or unterminated"
		return
	fi

	# Parse with Python so we get a real YAML check rather than regex
	# guessing about quoting, multi-line values, etc.
	python3 - "$skill_md" "$skill_name" <<-'PY' || errors=$((errors + 1))
		import sys
		import re

		skill_md, skill_name = sys.argv[1], sys.argv[2]

		try:
		    import yaml
		except ImportError:
		    print(f"  FAIL {skill_md}: pyyaml not installed (pip install pyyaml)", file=sys.stderr)
		    sys.exit(1)

		with open(skill_md, "r", encoding="utf-8") as fh:
		    text = fh.read()

		m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
		if not m:
		    print(f"  FAIL {skill_md}: could not locate frontmatter block", file=sys.stderr)
		    sys.exit(1)

		try:
		    data = yaml.safe_load(m.group(1)) or {}
		except yaml.YAMLError as e:
		    print(f"  FAIL {skill_md}: frontmatter YAML error: {e}", file=sys.stderr)
		    sys.exit(1)

		failed = False

		name = data.get("name", "")
		description = data.get("description", "")

		if not name:
		    print(f"  FAIL {skill_md}: missing or empty 'name'", file=sys.stderr)
		    failed = True
		elif name != skill_name:
		    print(f"  FAIL {skill_md}: name '{name}' does not match directory '{skill_name}'", file=sys.stderr)
		    failed = True

		if not description:
		    print(f"  FAIL {skill_md}: missing or empty 'description'", file=sys.stderr)
		    failed = True
		elif "\n" in description.strip():
		    print(f"  FAIL {skill_md}: 'description' must be a single line", file=sys.stderr)
		    failed = True

		sys.exit(1 if failed else 0)
	PY
}

# Walk each path pre-commit passed in; only act on SKILL.md files.
for path in "$@"; do
	case "$path" in
		*/SKILL.md) check_skill "$path" ;;
	esac
done

if [ "$errors" -gt 0 ]; then
	echo -e "${RED}Skill compliance failed with ${errors} error(s).${NC}"
	exit 1
fi

if [ "$warnings" -gt 0 ]; then
	echo -e "${YELLOW}Skill compliance passed with ${warnings} warning(s).${NC}"
fi

exit 0
