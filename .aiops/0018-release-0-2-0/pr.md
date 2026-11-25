<!-- PR description for intent 0018, generated in state 5. `gh pr create --body-file` it. -->
## Release 0.2.0

**Intent:** `.aiops/0018-release-0-2-0/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 96/100 at `e7b6177`

### What and why
PR #36 put the GNU Affero GPL v3 LICENSE on main, and PRs #33-#35 added the README demo and Quick start, but the
tree still said `0.2.0-beta.4` and `"license": "MIT"`. This bumps the release to **0.2.0** under
**AGPL-3.0-or-later** so the tag's tree describes itself (`sdlc init` writes the `plugin.json` version as the
scaffold's CI pin).

- `plugin.json`: `version` `0.2.0`, `license` `AGPL-3.0-or-later`.
- README: status line `0.2.0` (no longer beta); the marketplace, clone and settings pins name `v0.2.0`; a License
  section (AGPL from 0.2.0, MIT up to beta.4).
- CHANGELOG: `## [0.2.0] - 2026-11-25` without the beta banner (license change, README demo and Quick start);
  compare links updated.
- `defaults/scaffold-history.json`: a `0.2.0` entry equal to beta.4's (no scaffold file changed).
- Release tests expect 0.2.0 and the AGPL SPDX id; `test_release_banner_is_beta` → `..._is_not_prerelease`.

No engine, hook, skill, template or schema behaviour changes.

### Acceptance criteria
- [x] AC-1: `plugin.json` (0.2.0, AGPL-3.0-or-later) and the newest CHANGELOG release agree, with the compare link (`test_version_matches_changelog`, `test_changelog_has_the_release`)
- [x] AC-2: `[Unreleased]` empty; the 0.2.0 section has no beta banner and names the license change and the README work (`test_changelog_has_the_release`, `test_release_banner_is_not_prerelease`)
- [x] AC-3: README status line, every pin and the License section (`test_changelog_has_the_release`, `test_release_banner_is_not_prerelease`)
- [x] AC-4: the 0.2.0 history entry equals beta.4's, released entries unchanged; only the planned files; `make check` (576, 3 skipped), `make validate`, `scaffold-history.py --check` pass

### Deviations from plan
None.

### Risks and rollback
- The README pins name `v0.2.0`, which exists only after the merge: right after it, the merge commit is tagged
  (unsigned, annotated, `zouj-ai-sdlc 0.2.0`) and published as a GitHub release (not a pre-release, marked latest)
  with the CHANGELOG section as notes.
- If the merge lands after 2026-11-25, the CHANGELOG date is corrected in this PR first.
- **Rollback:** revert the PR, and delete the tag and the release if published.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
