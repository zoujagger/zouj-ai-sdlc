#!/usr/bin/env bash
# First-run setup after creating a repo from this template.
# Usage: scripts/bootstrap.sh <project-name> [github-org] [--stack python|node|go|none]
set -euo pipefail
cd "$(dirname "$0")/.."

stack=none
args=()
while (( $# )); do
  case $1 in
    --stack) stack=${2:-}; shift 2 || { echo "--stack needs a value" >&2; exit 1; } ;;
    --stack=*) stack=${1#--stack=}; shift ;;
    *) args+=("$1"); shift ;;
  esac
done
name=${args[0]:-}
org=${args[1]:-your-org}
[[ -z "$name" ]] && { echo "usage: $0 <project-name> [github-org] [--stack python|node|go|none]" >&2; exit 1; }
if [[ "$stack" != none && ! -f templates/stacks/$stack.recipes ]]; then
  echo "unknown stack '$stack' (available: $(cd templates/stacks && ls ./*.recipes | sed 's|^\./||; s|\.recipes$||' | tr '\n' ' ')none)" >&2
  exit 1
fi

for bin in git make python3; do
  command -v "$bin" >/dev/null || { echo "missing dependency: $bin (see README → Install prerequisites)" >&2; exit 1; }
done
command -v jq >/dev/null || echo "note: jq not found - optional, hooks fall back to python3"
command -v claude >/dev/null || echo "note: Claude Code CLI not found - install: curl -fsSL https://claude.ai/install.sh | bash"
command -v gh >/dev/null || echo "note: GitHub CLI not found - needed for /pr, /retro, triage"

chmod +x .claude/hooks/*.sh scripts/*.sh

# Personalise placeholders (sed -i.bak works with both GNU and BSD sed)
sed -i.bak "s/^# AI-Native SDLC Template$/# $name/" README.md && rm -f README.md.bak
sed -i.bak "s/@your-org/@$org/g" .github/CODEOWNERS && rm -f .github/CODEOWNERS.bak

# Wire the Makefile contract targets from a stack preset
if [[ "$stack" != none ]]; then
  python3 - "templates/stacks/$stack.recipes" <<'PY'
import re, sys
recipes = {}
for line in open(sys.argv[1]):
    parts = line.strip().split(None, 1)
    if len(parts) == 2 and not parts[0].startswith("#"):
        recipes[parts[0]] = parts[1]
src = open("Makefile").read()
wired = []
for target, cmd in recipes.items():
    src, n = re.subn(rf'^\t@echo "\[{target}\] not configured - edit Makefile"$', "\t" + cmd.replace("\\", "\\\\"), src, flags=re.M)
    if n:
        wired.append(target)
open("Makefile", "w").write(src)
if wired:
    print(f"Makefile: wired {', '.join(wired)} from {sys.argv[1]}")
else:
    print("Makefile: no unconfigured targets left, preset not applied (edit the Makefile directly)")
PY
fi

[[ -f .claude/settings.local.json ]] || cp .claude/settings.local.json.example .claude/settings.local.json

if [[ ! -d .git ]]; then
  git init -q -b main
  echo "Initialised git repository (branch: main)"
fi

if [[ "$stack" != none ]]; then
  step1="Review the Makefile ($stack preset applied) and wire deploy/rollback to your platform."
else
  step1="Edit Makefile: wire format/lint/typecheck/test/build/deploy/rollback to your stack (or re-run with --stack)."
fi

cat <<MSG

Bootstrap complete for '$name'. Next steps:
  1. $step1
  2. Fill in "Project notes" in CLAUDE.md, the policy skills (.claude/skills/policy-*), and .claude/test-paths.
  3. Point ops/bands.yaml queries at your monitoring; add CI toolchain setup in .github/workflows/ci.yml.
  4. gh secret set ANTHROPIC_API_KEY   (or run /install-github-app in Claude Code)
  5. Branch protection + staging/production environments: docs/branch-protection.md
  6. Org admins: roll out governance/managed-settings.example.json (docs/governance.md)
  7. make doctor   (checks all of the above and tells you how to fix what's missing)
  8. Start: claude  →  /onboard  →  /intent "your first need"
MSG
