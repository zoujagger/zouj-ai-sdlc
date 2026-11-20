<!-- PR description for intent 0011, generated in state 5. `gh pr create --body-file` it. -->
## Scope sizing: cap acceptance criteria per intent

**Intent:** `.aiops/0011-scope-sizing/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 93/100 at `60c1e4c`

### What and why
Specs here grew to 15-30 ACs (0002 has 29), because nothing sized an intent: epics passed as one intent and cost
review time at every gate. This adds:

- **A validator check:** `sdlc validate` counts the distinct AC ids in `spec.md`'s `## Acceptance criteria`.
  - More than 5: a warning suggesting the intent be split.
  - More than 8 while the spec's gate is closed: `Spec exceeds maximum of 8 acceptance criteria; consolidate
    behavioral outcomes or split into smaller intents. (spec.md has N.)`. `approve` refuses such a spec.
  - Approved specs only warn, so 0001-0010 and CI stay green.
- **Advice:** the `intent` skill runs a scope check before creating `intent.md`, and asks the human whether to
  split work that covers several workflows or more than 5 outcomes. The `spec` skill and `product-analyst` aim for
  3 to 5 user-observable ACs (never more than 7), and flag an oversized intent with a **Scope:** callout. The
  templates, `docs/state-machine.md` and the CHANGELOG name the rule.

### Acceptance criteria
- [x] AC-1: 5 or fewer ACs give no scope message (`tests/test_engine.py::ScopeSizing::test_five_or_fewer_is_quiet`,
  `::test_counts_distinct_ids_in_the_section`)
- [x] AC-2: 6 to 8 ACs in a Draft spec warn, exit 0 (`::test_six_to_eight_warn`,
  `tests/test_cli.py::Lifecycle::test_validate_scope_size_exit_codes`)
- [x] AC-3: 9 or more with the gate closed error, exit 1, approval refused (`::test_nine_draft_is_an_error`,
  `::test_nine_stale_is_an_error`, `::test_approved_eight_plus_ninth_is_stale`, `::test_approve_refuses_nine`)
- [x] AC-4: approved specs with 9 or more ACs only warn, and this repo stays green (`::test_nine_approved_only_warns`,
  `::test_this_repos_specs_have_no_scope_error`)
- [x] AC-5: the advice ships, and `make check` passes (`tests/test_cli.py::Docs::test_scope_sizing_guidance`)

### Deviations from plan
- **S2:** `Docs::test_changelog_has_the_release` no longer asserts that `[Unreleased]` holds no `### ` heading.
  0010 added that assertion for its own release commit, and any later CHANGELOG entry fails it.
- **S3:** the `intent-first` eval scored 0.89 with the plugin against 1.00 without. One run hit
  `Read-only file system` in the eval sandbox; no run stopped at the new scope check.

### Risks and rollback
- **No override:** a Draft spec with more than 8 ACs can't be approved until it is split or trimmed, and nothing in
  config lifts that.
- Adopting repos get the rule with the next plugin release. Their approved specs only warn.
- **Rollback:** revert the PR.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
