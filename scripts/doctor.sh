#!/usr/bin/env bash
# Setup health check: tools, Makefile wiring, placeholders, GitHub wiring, then the full template validation.
# Every problem prints the command that fixes it. Exits 1 only when something required is missing.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n      fix: %s\n' "$1" "$2"; fail=1; }
warn() { printf '  \033[33m!\033[0m %s\n      fix: %s\n' "$1" "$2"; }

version() { "$1" --version 2>/dev/null | head -n1; }

echo "Required tools"
for bin in git make python3; do
  if command -v "$bin" >/dev/null; then ok "$(version "$bin")"; else bad "$bin not installed" "see README → Install prerequisites"; fi
done
if python3 -c 'import yaml' 2>/dev/null; then ok "pyyaml"; else bad "pyyaml not installed" "pip install pyyaml  (or: sudo apt-get install python3-yaml)"; fi
if command -v claude >/dev/null; then ok "claude $(claude --version 2>/dev/null | head -n1)"; else bad "Claude Code not installed" "curl -fsSL https://claude.ai/install.sh | bash"; fi

echo "Optional tools"
if command -v jq >/dev/null; then ok "$(version jq)"; else warn "jq not installed (hooks fall back to python3)" "sudo apt-get install jq  |  brew install jq"; fi
if command -v gh >/dev/null; then
  if gh auth status >/dev/null 2>&1; then ok "gh (logged in)"; else warn "gh is not logged in" "gh auth login"; fi
else warn "gh not installed (needed for /pr, /retro, /intent #issue)" "sudo apt-get install gh  |  brew install gh"; fi

echo "Makefile contract"
# Same detection as .claude/hooks/post-edit-format.sh
unwired=()
for t in format lint typecheck test build deploy rollback; do
  make -n "$t" 2>/dev/null | grep -q "not configured" && unwired+=("$t")
done
if (( ${#unwired[@]} == 0 )); then ok "all contract targets wired"
elif make -n check 2>/dev/null | grep -q "not configured"; then
  warn "not wired: ${unwired[*]} - 'make check' passes without checking anything" \
       "scripts/bootstrap.sh <name> [org] --stack python|node|go, or edit the Makefile"
else
  warn "not wired: ${unwired[*]}" "edit those Makefile targets for your platform"
fi

echo "Project setup"
if grep -q '@your-org' .github/CODEOWNERS 2>/dev/null; then warn "CODEOWNERS still uses @your-org" "scripts/bootstrap.sh <name> <github-org>"; else ok "CODEOWNERS personalised"; fi
if sed -n '/^## Project notes/,$p' CLAUDE.md | grep -vE '^(## Project notes|<!--.*-->|[[:space:]]*)$' | grep -q .; then ok "CLAUDE.md project notes filled in"
else warn "CLAUDE.md 'Project notes' is empty" "describe your stack, architecture and gotchas there (examples: docs/examples/)"; fi
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ok "git repository"; else bad "not a git repository" "git init -b main"; fi

echo "GitHub"
if remote=$(git remote get-url origin 2>/dev/null); then
  ok "origin: $remote"
  if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
    if secrets=$(gh secret list 2>/dev/null); then
      if grep -q '^ANTHROPIC_API_KEY' <<<"$secrets"; then ok "ANTHROPIC_API_KEY secret set"
      else warn "ANTHROPIC_API_KEY secret missing (Claude workflows will not run)" "gh secret set ANTHROPIC_API_KEY  (or /install-github-app in Claude Code)"; fi
    else warn "cannot list repo secrets (needs admin rights)" "ask a repo admin to check ANTHROPIC_API_KEY"; fi
  fi
else warn "no 'origin' remote - CI, PR review and deploys are inactive" "gh repo create --private --source . --push"; fi

echo "Template validation"
if out=$(bash scripts/validate-template.sh 2>&1); then ok "make validate-template passed"
else bad "make validate-template failed: $(grep -m3 '✗' <<<"$out" | sed 's/^ *//' | tr '\n' ' ')" "make validate-template  (full report)"; fi

echo
if (( fail )); then echo "doctor: required items missing (✗). Fix them and re-run make doctor."; exit 1; fi
echo "doctor: ready. Warnings (!) are optional but recommended. Next: claude → /onboard"
