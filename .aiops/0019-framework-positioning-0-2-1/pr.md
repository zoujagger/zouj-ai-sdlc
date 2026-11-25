<!-- PR description for intent 0019, generated in state 5. `gh pr create --body-file` it. -->
## Framework positioning and release 0.2.1

**Intent:** `.aiops/0019-framework-positioning-0-2-1/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 95/100 at `6f420d5`

### What and why
zouj-ai-sdlc is now presented as an **AI-native software engineering framework, currently implemented as a Claude
Code plugin**, consistently in every place that states its identity, and released as **0.2.1** together with the
copyright and contribution-licensing docs already on main (#38, #39).

- **README:** new intro (zoujagger's wording) and a list separating category, current implementation (Claude Code is
  the only supported environment), core mechanism, engineering practices, workflow model and objective/limits.
- **`plugin.json` / `marketplace.json`:** descriptions updated to match.
- **`CLAUDE.md`:** the opening sentence only.
- **`docs/sdlc.md`:** new `## Engineering practices`: SDD, TDD workflows, small planned steps, continuous validation,
  fresh-context review, a human at every gate, each tied to its mechanism, plus the limits (hooks are a deterrent,
  not a sandbox; XP borrowed, not claimed).
- **Release 0.2.1:** version, CHANGELOG `[0.2.1]`, README pins, scaffold history, release tests.

No change to the plugin id, command prefix, skills, hooks, schemas, behaviour, license or copyright.

### Acceptance criteria
- [x] AC-1: manifest and marketplace descriptions, `CLAUDE.md` sentence, no overclaiming words (`test_framework_positioning`)
- [x] AC-2: `docs/sdlc.md` Engineering practices and the README link (`test_framework_positioning`)
- [x] AC-3: `0.2.1` in `plugin.json` and the newest CHANGELOG section, entries moved, `[Unreleased]` empty (`test_version_matches_changelog`, `test_changelog_has_the_release`)
- [x] AC-4: README status line and pins (`test_changelog_has_the_release`, `test_release_banner_is_not_prerelease`)
- [x] AC-5: history entry, scope, `make check` (577, 3 skipped), `make validate`, `scaffold-history.py --check`

### Deviations from plan
None.

### Risks and rollback
- The README pins name `v0.2.1`, which exists only after the merge: right after it, the merge commit is tagged and
  published as the latest GitHub release, and the repository description is updated.
- If the merge lands after 2026-11-25, the CHANGELOG date is corrected in this PR first.
- **Rollback:** revert the PR, delete the tag and release, restore the previous repository description.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
