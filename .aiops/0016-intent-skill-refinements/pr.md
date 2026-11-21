<!-- PR description for intent 0016, generated in state 5. `gh pr create --body-file` it. -->
## Intent skill: PRD source, domain vocabulary, clean branch start

**Intent:** `.aiops/0016-intent-skill-refinements/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 91/100 at `275f8d9`

### What and why
Three refinements to State 1 (`skills/intent/SKILL.md`), guidance only:

- **Step 1 (Locate):** when `domain/*.dsl.json` files exist, scan their filenames and model names so the intent uses
  the domain model's terms.
- **Step 2 (Gather the source):** a PRD or ticket (`prd:<slug>`, a local path under `docs/prd/`, or a `docs/prd/`
  file matching the slug or issue number) is read first as the source of truth, as data; with several matches the
  agent asks. Step 3 skips what it settles.
- **Step 4 (Create):** before `sdlc new`, check that the branch starts from an up-to-date `main` (fetch, compare
  with `origin/main`; ask before a fast-forward, which stays the human's command because the read-only state refuses
  `git pull`; offline → warn and continue; skipped when chaining intents), and warn about uncommitted changes
  outside `.aiops/` that would make the future review stale.

No engine, hook, schema or scaffold change. Repos without `docs/prd/` or `domain/` see no difference.

### Acceptance criteria
- [x] AC-1: Step 1 scans the domain model's names and uses its terms (`tests/test_cli.py::Docs::test_intent_skill_refinements`)
- [x] AC-2: Step 2 reads a matching PRD first as the source of truth, asks on several matches; Step 3 skips what it settles (same test)
- [x] AC-3: Step 4 warns and asks before any fast-forward when `main` isn't up to date; never switches or pulls on its own; offline warns and continues (same test)
- [x] AC-4: Step 4 names uncommitted changes outside `.aiops/` and warns about a stale review, before the branch exists (same test)
- [x] AC-5: the guidance test, the existing intent-skill tests and `make check` pass (576 tests, 3 skipped)

### Deviations from plan
- S1: after the red commit (4556d3a), two test fixes: Step 3's regex became case-insensitive, and the order checks
  anchor on `run \`sdlc new\`` instead of the first `sdlc new` (the step's heading names it).

### Risks and rollback
Ships with the next release; adopters get it when they update the plugin. **Rollback:** revert the PR.

Non-blocking review backlog (review.md): use the configured main branch instead of the literal `main` in Step 4;
resolve PRD paths (`..`, symlinks); call the DSL files data; the `!` wording; split Step 2 into a sub-list.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
