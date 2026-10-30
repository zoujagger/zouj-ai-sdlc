## Summary
<!-- What and why, in 1-3 sentences. -->

## Artifacts
- Intent: `.aiops/NNNN-slug/intent.md`
- Spec: `.aiops/NNNN-slug/spec.md` (ACs covered: AC-1, AC-2)
- Plan: `.aiops/NNNN-slug/plan.md` (deviations logged: yes / none)
- Review: `.aiops/NNNN-slug/review.md`
- Closes #

## Evidence (mechanical checks; reviewers focus on intent and risk)
- [ ] `make check` passes
- [ ] `.aiops/NNNN-slug/review.md`: verdict PASS, score ≥ 80, not stale
- [ ] Screenshots (UI changes)

## Risk & rollback
<!-- Blast radius, feature flag, migration, rollback command, metrics to watch in ops/bands.yaml. -->

## Checklist
- [ ] Docs / CHANGELOG `[Unreleased]` updated
- [ ] No secrets, PII, or debug code

## AI assistance
- [ ] Substantially authored with Claude Code. I've reviewed it and take responsibility. (The authoring agent doesn't approve its own PR.)
