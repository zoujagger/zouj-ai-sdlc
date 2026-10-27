# Contract targets. This is the ONLY build interface that Claude hooks and CI call.
# Replace each placeholder recipe with your stack's real command, e.g.:
#   lint:      npm run lint      | ruff check .        | golangci-lint run
#   typecheck: npx tsc --noEmit  | mypy .              | go vet ./...
#   test:      npm test          | pytest -q          | go test ./...
# A target still printing "not configured" counts as a pass, so the fresh template stays green.
# Presets: scripts/bootstrap.sh <name> [org] --stack python|node|go (templates/stacks/). `make doctor` flags unwired targets.

ENV ?= staging

.DEFAULT_GOAL := help
.PHONY: help format lint typecheck test build check deploy rollback evals validate-template doctor

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

format: ## Auto-format the codebase (runs after every edit via hook; keep fast)
	@echo "[format] not configured - edit Makefile"

lint: ## Run static analysis (runs after every edit via hook; keep fast)
	@echo "[lint] not configured - edit Makefile"

typecheck: ## Run type checking
	@echo "[typecheck] not configured - edit Makefile"

test: ## Run the test suite
	@echo "[test] not configured - edit Makefile"

build: ## Build artifacts
	@echo "[build] not configured - edit Makefile"

check: lint typecheck test ## lint + typecheck + test (definition of done)

deploy: ## Deploy to ENV=staging|prod (prod: humans only, enforced by guard-deploy hook + GitHub Environment)
	@echo "[deploy] ENV=$(ENV) not configured - edit Makefile"

rollback: ## Roll back ENV=staging|prod in ONE command (pre-approved runbook; test it in staging)
	@echo "[rollback] ENV=$(ENV) not configured - edit Makefile"

evals: ## Run the agent eval suite (needs claude CLI + ANTHROPIC_API_KEY + pyyaml)
	@python3 scripts/run-evals.py

doctor: ## Check your setup (tools, Makefile wiring, placeholders, GitHub) and print fixes
	@bash scripts/doctor.sh

validate-template: ## Validate Claude config, hooks, evals, bands, and workflows
	@bash scripts/validate-template.sh
