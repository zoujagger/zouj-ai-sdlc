---
id: 0016
title: Intent skill: PRD source, domain vocabulary, clean branch start
status: Approved
spec: ./spec.md
created: 2026-11-21
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-21T11:44:05Z
approved-via: cli
approved-sha256: 7621f08395d361bbc039b5b27747bfde24247c973b221814bec432cd8de2dc14
---

# Plan: Intent skill: PRD source, domain vocabulary, clean branch start

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
One TDD step for the guidance and one verification step. As in 0014, the guidance step gets a commit holding only
its red test, then the commit that turns it green.

1. **S1, the guidance:** `skills/intent/SKILL.md` Steps 1 to 4 and a red-flag row, plus the CHANGELOG entry, proven
   by a docs test.
2. **S2, verification.**

Code reused:
- **The test:** the `Docs` class in `tests/test_cli.py` and its `self.text()` helper; the shape of
  `test_scope_sizing_guidance` (`tests/test_cli.py:993`), which slices the skill by its `\n3. ` and `\n4. `
  step markers, and of `test_spec_quality_guidance` (`:1064`), which reads everything newer than `0.2.0-beta.3`
  in the CHANGELOG (0015's pattern).
- **The facts the skill relies on**, checked read-only in `lib/sdlc_engine/guards.py`: `git fetch`, `status` and
  `rev-parse` are in `GIT_READONLY_SUBS` (`:1500`); `git pull` and `git merge` are in `GIT_LOCKED` (`:224`) and
  refused under the read-only lock (G-LOCK-03, `:2425`); `git switch` is not refused. So the agent can fetch and
  inspect in State 1, but a fast-forward is the human's command.
- **The DSL terms:** the model keys from `templates/scaffold/domain/README.md` (`kind`, `name`, `states`,
  `transitions[].event`, `rules[].id`, and the workflow's steps).

## Steps
- [x] **S1**: Write the domain-vocabulary, PRD-source and clean-branch guidance into the intent skill.
  - **Files:**
    - `tests/test_cli.py` (modify): `Docs::test_intent_skill_refinements` slices the skill by step and checks:
      - Step 1 names `domain/*.dsl.json` and the model's names and terms (AC-1);
      - Step 2 names `docs/prd/`, `prd:<slug>`, a local path, the slug or issue number, "source of truth",
        and asking when several match; and that a PRD is data, never instructions or an approval (AC-2);
      - Step 3 says the interview skips what the source settles (AC-2);
      - Step 4 names `git fetch`, `origin/main`, "behind", asking before a fast-forward, the human's
        `git pull --ff-only` command, "chain", offline/no remote → warn and continue, `git status --porcelain`,
        changes outside `.aiops/`, and "stale"; and that it never switches, pulls, stashes or resets on its own
        (AC-3, AC-4);
      - the order: the checks come before `sdlc new` in Step 4 (AC-3, AC-4);
      - a red-flag row about a stale main or a dirty tree;
      - the CHANGELOG `[Unreleased]` (everything before `## [0.2.0-beta.3]`) names
        `.aiops/0016-intent-skill-refinements/` (AC-5).
    - `skills/intent/SKILL.md` (modify): Steps 1, 2, 3 and 4 per spec R-1 to R-4, and the red-flag row (R-5). The
      new sub-lists are indented, so the `\n3. ` / `\n4. ` / `\n5. ` markers the existing tests split on stay unique
      and the step numbers 1 to 6 are unchanged.
    - `CHANGELOG.md` (modify): `[Unreleased]` `### Changed`, naming `.aiops/0016-intent-skill-refinements/`.
  - **Test first:** `test_intent_skill_refinements` fails on the missing phrases.
  - Covers: AC-1, AC-2, AC-3, AC-4, AC-5
- [x] **S2**: Prove the change.
  - **Commands:**
    - `make check` (includes `test_scope_sizing_guidance` and the `test_shell_hooks.py` checks that read the
      intent skill);
    - `make validate`;
    - `bin/sdlc validate --all`;
    - `git diff --name-only main...HEAD`: only the files S1 names, and `.aiops/0016-*`.
  - **Files:** none. The results go in the Deviation log and in review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-5

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A new line in the skill starts with `3. `/`4. ` and breaks the step slicing in `test_scope_sizing_guidance` | medium | low: a red test | Indent every sub-list; S2's `make check` runs that test |
| The skill tells the agent to run a git command the guard refuses in State 1, so it hits a block at Step 4 | low | medium: a confusing block | Only `fetch`, `status`, `rev-parse`/`rev-list` are run by the agent (read-only set, checked above); the fast-forward is printed as the human's `!` command |
| The skill text grows and slows every intent | low | low | One or two lines per refinement; Step 4's checks are a short sub-list |
| A test that pins wording makes the skill hard to edit later | medium | low | Check key terms and order, not whole sentences, as the 0011 and 0014 tests do |
| Anaconda's `ruff` on PATH reformats the repo if the hooks load | high if the hooks load | high | `git status` after each edit; restore anything outside the step |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_cli.py::Docs::test_intent_skill_refinements` (Step 1 part) | doc | the DSL scan and the model's terms |
| AC-2 | same test (Step 2 and Step 3 parts) | doc | the PRD order, source of truth, asking on several matches, skipping settled questions, PRD as data |
| AC-3 | same test (Step 4 main part) | doc | fetch, behind `origin/main`, ask before the human's fast-forward, chaining, offline warn |
| AC-4 | same test (Step 4 dirty-tree part) | doc | `git status --porcelain`, changes outside `.aiops/`, stale review warning, before `sdlc new` |
| AC-5 | same test (CHANGELOG part); S2 `make check` | doc, repo | the entry, the existing intent-skill tests, everything green |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-21 | S1 | After the red commit (4556d3a), two test fixes: Step 3's `skip…settle` regex became case-insensitive (the sentence starts with "Skip"), and the order checks find `run `sdlc new`` instead of the first `sdlc new` (Step 4's heading names it) | Both were test bugs, not missing guidance; the assertions are unchanged in substance | 56737fd |
| 2026-11-21 | S2 | Results: `make check` OK (576 tests, 3 skipped) on the S1 content (56737fd); `make validate` passed with two warnings unrelated to this change (the root `CLAUDE.md`, and the plugin has no icon); `sdlc validate --all` 0 errors across 15 intents; `git diff --name-only main...HEAD` lists only `CHANGELOG.md`, `skills/intent/SKILL.md`, `tests/test_cli.py` and `.aiops/0016-*` | The verification itself; no deviation from the plan | 275f8d9 |
