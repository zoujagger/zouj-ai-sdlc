---
name: release
description: Prepares a release covering the SemVer bump, CHANGELOG, release notes linking intents, and a readiness checklist. Never tags, publishes, or deploys to production.
argument-hint: "[major|minor|patch]"
disable-model-invocation: true
---

# /zouj-ai-sdlc:release: prepare a release

Bump override: `$ARGUMENTS`

1. Delegate to the **release-manager** subagent.
2. Show the proposed version, the CHANGELOG diff, the notes draft, and the checklist (including rollback tested in staging and band metrics added).
3. Check that `sdlc status` shows every shipped intent as DONE (review.md on main). The state is derived, so there's nothing to mark.
4. Print the commands for the human to run: `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z` (this triggers `claude-release-notes.yml`, which drafts the release), then the production approval in the `deploy` workflow.
