<!-- PR description for intent 0010, generated in state 5. `gh pr create --body-file` it. -->
## Release 0.2.0-beta.2

**Intent:** `.aiops/0010-release-0-2-0-beta-2/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 96/100 at `3f60008`

### What and why
Stack auto-detection (intent 0009, PR #23) and the README funnel (PR #22) are on main but not in any release. This
bumps the current release to **0.2.0-beta.2**:
- `plugin.json`;
- the CHANGELOG: the `[Unreleased]` entries move unchanged into `[0.2.0-beta.2] - 2026-11-18`, with the beta banner
  and a lead line, and the compare links are updated;
- the scaffold history: `unreleased` becomes `0.2.0-beta.2`, released entries unchanged;
- the README status line and pins, and the roadmap entries;
- the two tests that pin the current release.

No behaviour changes.

### Acceptance criteria
- [x] AC-1: version, newest CHANGELOG heading and compare links (`tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog`)
- [x] AC-2: `[Unreleased]` moved byte-for-byte; `[Unreleased]` empty; beta banner (`tests/test_cli.py::Docs::test_changelog_has_the_release`, `::test_release_banner_is_beta`)
- [x] AC-3: history key renamed, released entries unchanged (`tests/test_rules.py::History`, `scripts/scaffold-history.py --check`, S2's check against `origin/main`)
- [x] AC-4: README pins name beta.2 (`tests/test_cli.py::Docs::test_changelog_has_the_release`)
- [x] AC-5: only the planned files changed (`git diff --name-only origin/main`)
- [x] AC-6: `make check` 513 OK, `claude plugin validate .` passed, eval `profile-by-setup-command` with the plugin 1.00 ×3
- [x] AC-7: beta.1 preset-wired Makefiles keep their recipes on upgrade (`tests/test_lifecycle.py::Detected::test_beta1_state_unchanged`)

### Deviations from plan
One: `Docs::test_docs_name_stack_detection` (0009) searches everything newer than `[0.2.0-beta.1]`, because the
release moves its entries out of `[Unreleased]`.

### Risks and rollback
- **The pins point at an untagged release.** The README pins and the scaffold's rendered ref point at
  `v0.2.0-beta.2`, which doesn't exist until you tag it. Tag it on the merge commit right after merging.
- **The date.** If the merge happens after 2026-11-18, the CHANGELOG date is corrected in this PR before the merge.
- **Rollback:** revert this PR, and delete the tag if one was pushed.

### After the merge (human steps)
1. `git tag v0.2.0-beta.2 <merge commit> && git push origin v0.2.0-beta.2`.
2. Publish the GitHub release the tag drafts.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
