# Shared fixture helpers for eval scaffold scripts (sourced). Runs in the empty eval workspace, as the operator.
set -euo pipefail
LIB=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PLUGIN=$(cd "$LIB/../.." && pwd)
SDLC="python3 $PLUGIN/bin/sdlc"

# init_repo: git repo + `sdlc init` scaffold + a tiny Python app, all committed on main.
init_repo() {
  git init -q -b main
  git config user.name "Eval Human"; git config user.email "eval@example.com"; git config commit.gpgsign false
  $SDLC init >/dev/null
  cat > Makefile <<'MK'
.PHONY: format lint typecheck test build check
format:
lint:
typecheck:
test:
	python3 -m unittest discover -s tests
build:
check: lint typecheck test
MK
  mkdir -p src tests
  printf 'def list_contacts():\n    return [{"name": "Ada", "tenant": "t1"}]\n' > src/contacts.py
  touch src/__init__.py tests/__init__.py
  git add -A && git commit -qm "chore: fixture"
}

# intent_at <state>: create intent 0001 on feat/0001-csv-export and advance it to state 1 (draft), 2, 3 or 4.
intent_at() {
  local d=.aiops/0001-csv-export
  git switch -qc feat/0001-csv-export
  mkdir -p "$d"
  cp "$LIB/artifacts/intent.md" "$d/intent.md"
  if [[ $1 -ge 2 ]]; then $SDLC approve 0001 intent >/dev/null; cp "$LIB/artifacts/spec.md" "$d/spec.md"; fi
  if [[ $1 -ge 3 ]]; then $SDLC approve 0001 spec >/dev/null; cp "$LIB/artifacts/plan.md" "$d/plan.md"; fi
  if [[ $1 -ge 4 ]]; then $SDLC approve 0001 plan >/dev/null; fi
  git add -A && git commit -qm "docs(aiops): fixture state $1" || true
}
