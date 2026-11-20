<!-- PR description for intent 0015, generated in state 5. `gh pr create --body-file` it. -->
## Release 0.2.0-beta.3

**Intent:** `.aiops/0015-release-0-2-0-beta-3/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 94/100 at `4a0c6f8`

### What and why
These changes are on main but not in any release since `v0.2.0-beta.2`:
- **Scope sizing** (0011, PR #25);
- **The opt-in `dsl` part** (0012, PR #26) with its **hardening** (0013, PR #27), which must ship together;
- **Sharper specs** (0014, PR #28);
- **The docs audit** (PR #29).

This bumps the current release to **0.2.0-beta.3**:
- `plugin.json`;
- the README status line and pins: both `marketplace add …@v0.2.0-beta.3` commands and the settings `"ref"`;
- the CHANGELOG: the `[Unreleased]` entries move unchanged into `[0.2.0-beta.3] - 2026-11-20`, with the beta banner
  and a lead line naming 0011-0014 and PR #29, and the compare links are updated;
- the scaffold history: `unreleased` becomes `0.2.0-beta.3`, released entries unchanged;
- the two tests that pin the release.

No behaviour changes.

### Acceptance criteria
- [x] AC-1: the version, the newest heading and the compare links (`test_version_matches_changelog`,
  `test_changelog_has_the_release`)
- [x] AC-2: `[Unreleased]` is empty; the beta.3 section holds main's entries byte for byte, after the banner and the
  lead line
- [x] AC-3: the history has a beta.3 entry equal to main's `unreleased` and no `unreleased` key; the released
  entries are unchanged
- [x] AC-4: every README pin says beta.3, and no current pin was missed
- [x] AC-5: only the planned files changed; `make check` (575 OK) and `claude plugin validate .` pass

### Deviations from plan
- **S1:** four docs tests from 0011-0014 now look for their CHANGELOG entry in everything newer than
  `[0.2.0-beta.2]` instead of only `[Unreleased]`, so they hold before and after a release.
- **S1:** the release commit `32f354f` went in with `make check` red on those four tests, because a `| tail` pipe
  hid the exit code. It was fixed in `c84ae3b`, and S2 re-ran with `pipefail`.

### Risks and rollback
- **The pins point at `v0.2.0-beta.3`**, which doesn't exist until you tag it. Installs from the README fail
  closed until then.
- **Rollout:**
  1. Merge.
  2. Tag `v0.2.0-beta.3` on the merge commit and push the tag.
  3. Publish the GitHub release.
- **The date:** if the merge lands after 2026-11-20, correct the heading's date first (spec R-2).
- **Rollback:** revert the PR, and delete the tag if one was pushed.

### Human decision
The agent does not merge or tag. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
