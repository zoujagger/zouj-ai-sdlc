#!/usr/bin/env bash
# First-run setup after creating a repo from this template.
# Usage: scripts/bootstrap.sh <project-name> [github-org]
set -euo pipefail
cd "$(dirname "$0")/.."

name=${1:-}
org=${2:-your-org}
[[ -z "$name" ]] && { echo "usage: $0 <project-name> [github-org]" >&2; exit 1; }

for bin in git jq make; do
  command -v "$bin" >/dev/null || { echo "missing dependency: $bin" >&2; exit 1; }
done
command -v claude >/dev/null || echo "note: Claude Code CLI not found - install: npm i -g @anthropic-ai/claude-code"
command -v gh >/dev/null || echo "note: GitHub CLI not found - needed for /pr, /retro, triage"

chmod +x .claude/hooks/*.sh scripts/*.sh

# Personalise placeholders
sed -i "s/^# AI-Native SDLC Template$/# $name/" README.md
sed -i "s/@your-org/@$org/g" .github/CODEOWNERS

[[ -f .claude/settings.local.json ]] || cp .claude/settings.local.json.example .claude/settings.local.json

if [[ ! -d .git ]]; then
  git init -q -b main
  echo "Initialised git repository (branch: main)"
fi

cat <<MSG

Bootstrap complete for '$name'. Next steps:
  1. Edit Makefile: wire format/lint/typecheck/test/build/deploy/rollback to your stack.
  2. Fill in "Project notes" in CLAUDE.md, the policy skills (.claude/skills/policy-*), and .claude/test-paths.
  3. Point ops/bands.yaml queries at your monitoring; add CI toolchain setup in .github/workflows/ci.yml.
  4. gh secret set ANTHROPIC_API_KEY   (or run /install-github-app in Claude Code)
  5. Branch protection + staging/production environments: docs/branch-protection.md
  6. Org admins: roll out governance/managed-settings.example.json (docs/governance.md)
  7. pip install pyyaml && make validate-template && make check
  8. Start: claude  →  /onboard  →  /intent "your first need"
MSG
