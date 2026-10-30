---
name: deploy
description: Deploys to staging and prepares the production handoff. The agent does everything up to the production gate and nothing past it. Use after a PR is merged.
argument-hint: "[staging]"
disable-model-invocation: true
---

# /zouj-ai-sdlc:deploy: up to the production gate

1. Preconditions: the PR is merged, CI is green on `main`, and the `CHANGELOG.md` `[Unreleased]` section is filled in.
2. **Staging.** Run `make deploy ENV=staging` (or the staging deploy MCP tool, if configured). Then run the smoke checks and report.
3. **Rollback readiness.** Confirm that `make rollback ENV=staging` works (it should have been exercised in staging) and print the exact prod rollback command.
4. **Production handoff.** The agent can't deploy to production. `guard-deploy.sh` blocks it. Produce a handoff note covering: what's shipping (intents and PRs), the staging evidence, the risks, the rollback command, and the monitoring to watch (`ops/bands.yaml` metrics).
   A named human then approves the `production` environment in the `deploy` GitHub workflow, or runs `make deploy ENV=prod`.
