# zouj-ai-sdlc plugin development. Consumers get their own Makefile contract from templates/scaffold/ (sdlc init).

.DEFAULT_GOAL := help
.PHONY: help format lint typecheck test build check validate evals dev

PY := python3
SHELLS := $(wildcard hooks/*.sh) bin/sdlc-worktree

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

format: ## Format Python with ruff when installed (no-op otherwise)
	@if command -v ruff >/dev/null; then ruff format -q lib tests bin/sdlc; fi

lint: ## bash -n + shellcheck (if installed) on hooks; ruff (if installed) on the engine
	@for f in $(SHELLS); do bash -n "$$f" || exit 1; done
	@if command -v shellcheck >/dev/null; then shellcheck -S warning $(SHELLS); fi
	@if command -v ruff >/dev/null; then ruff check -q lib tests bin/sdlc; fi
	@$(PY) -c 'import json,sys; [json.load(open(f)) for f in sys.argv[1:]]' hooks/hooks.json .claude-plugin/*.json schemas/*.json

typecheck: ## Byte-compile the engine (stdlib only, Python >= 3.9)
	@$(PY) -m compileall -q lib bin tests

test: ## Engine, guard and hook tests (stdlib unittest)
	@$(PY) -m unittest discover -s tests

build: validate ## Alias for validate

check: lint typecheck test ## lint + typecheck + test (the definition of done)

validate: ## claude plugin validate (manifest, layout, components)
	@if command -v claude >/dev/null; then claude plugin validate .; else echo "[validate] claude CLI not installed, skipped"; fi

evals: ## Behavioural evals against a live model (needs claude + ANTHROPIC_API_KEY)
	claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit --no-publish

dev: ## Start Claude Code with this checkout loaded as the plugin
	claude --plugin-dir .
