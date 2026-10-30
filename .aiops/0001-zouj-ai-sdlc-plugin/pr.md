<!-- PR description for intent 0001, generated in state 5. `gh pr create --body-file` it. -->
## zouj-ai-sdlc plugin: state 5 review (CHANGES_REQUESTED)

**Intent:** `.aiops/0001-zouj-ai-sdlc-plugin/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** CHANGES_REQUESTED, 66/100, at `c26f6913a328ba25e8840215ddf225bf12b3a3bd`

### What and why
Records the fresh-context state-5 review of the plugin that shipped in #5 (v0.1.0). The verifier, code-reviewer and
security-reviewer each worked independently against base `fb975f6`. The build is green and the tests are behavioural.
But the read-only lock and the approval gate can be bypassed, and the gates were opened after the merge.

### Acceptance criteria
- [x] AC-1, AC-2, AC-5, AC-6, AC-7, AC-8, AC-9: met (tests cited in review.md)
- [ ] AC-3: not met. Approvals can be forged (heredoc write of a stamp; obfuscated `sdlc approve` with env vars cleared)
- [ ] AC-4: not met. `cat <<EOF > src/app.py` bypasses the lock
- [ ] AC-10: not met. The CI audit accepts an agent-run approval commit
- [ ] AC-11: partial. Safety guards are dormant without `.aiops/`

### Deviations from plan
12 logged in plan.md. Unlogged: the S7 cutover landed as a commit instead of the human-run script, and the code was
merged and released before the gates were opened (a bootstrap exception, not recorded).

### Risks and rollback
Until the fixes land, treat the local guards as advisory. The real control is CODEOWNERS review of `.aiops/`. Turn on
`require_signed_approvals` in consumer repos. Rollback: v0.1.0 can be superseded by v0.1.1. No consumer migration is needed.

### Human decision
The agent does not merge. Merging this PR records the review. The fixes come next: re-plan under 0001 (needs
`Plan Approved 0001` again) or open a new hardening intent.
