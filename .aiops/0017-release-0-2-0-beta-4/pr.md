<!-- PR description for intent 0017, generated in state 5. `gh pr create --body-file` it. -->
## Release 0.2.0-beta.4

**Intent:** `.aiops/0017-release-0-2-0-beta-4/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 98/100 at `02ec52a`

### What and why
Intent 0016 (the intent skill reads the domain model and a PRD first, and starts from a clean `main`; PR #31) is
on main but in no release since `v0.2.0-beta.3`. This bumps the current version to **0.2.0-beta.4** so the tag's
tree describes itself: `sdlc init` writes the `plugin.json` version as the scaffold's CI pin.

- `plugin.json` `0.2.0-beta.4`; the README status line, both marketplace commands and the settings `"ref"`.
- CHANGELOG: `[Unreleased]`'s 0016 entry moves unchanged into `## [0.2.0-beta.4] - 2026-11-21`, with the beta
  banner and a lead line; compare links updated.
- `defaults/scaffold-history.json`: a `0.2.0-beta.4` entry equal to beta.3's (no scaffold file changed).
- The two release tests expect beta.4; the beta.3 checks move to an explicit slice.

No engine, hook, skill, template or schema behaviour changes.

### Acceptance criteria
- [x] AC-1: `plugin.json` and the newest CHANGELOG release agree on beta.4, with the compare link (`test_version_matches_changelog`, `test_changelog_has_the_release`)
- [x] AC-2: `[Unreleased]` empty; the 0016 entry moved unchanged after the banner and lead line (`test_changelog_has_the_release`, CHANGELOG diff)
- [x] AC-3: every README pin names beta.4 (`test_changelog_has_the_release`)
- [x] AC-4: the beta.4 history entry equals beta.3's, released entries unchanged; only the planned files; `make check` (576, 3 skipped), `make validate`, `scaffold-history.py --check` pass

### Deviations from plan
None. (The spec was re-approved once before planning: its tag AC moved to Rollout, since it can only hold after
the merge.)

### Risks and rollback
- The README pins name `v0.2.0-beta.4`, which exists only after the merge: right after it, the merge commit is
  tagged (unsigned, annotated, `zouj-ai-sdlc 0.2.0-beta.4`) and published as a GitHub pre-release with the
  CHANGELOG section as notes.
- If the merge lands after 2026-11-21, the CHANGELOG date is corrected in this PR first.
- **Rollback:** revert the PR, and delete the tag and the release if published.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
