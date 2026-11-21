---
id: 0016
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 275f8d9
score: 91/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-21
---

# Review: Intent skill: PRD source, domain vocabulary, clean branch start

<!-- State 5 PRE-REVIEW. Written from the report of one fresh-context reviewer covering the three personas, who got
     only the intent folder and the base branch `main` (6984c29). The reviewed code is 275f8d9; the commit that adds
     this review only fills the Deviation log's Commit column with shas, as the review asked (.aiops/ only). -->

## Summary
- **Step 1:** when `domain/*.dsl.json` files exist, the intent skill scans their names so the intent uses the
  model's terms.
- **Step 2 and 3:** a PRD or ticket (`prd:<slug>`, a local path under `docs/prd/`, or a matching `docs/prd/` file)
  is read first as the source of truth, treated as data, and the interview skips what it settles.
- **Step 4:** before `sdlc new`, the skill checks for an up-to-date `main` (asking before a fast-forward that stays
  the human's command) and warns about uncommitted changes outside `.aiops/`.

Guidance only: no engine, hook, schema or scaffold change. **PASS, 91/100**: every AC is met, and there is no
BLOCKER and no CRITICAL/HIGH finding.

The reviewer ran, without writing anything:
- `python3 -m unittest test_cli.Docs` (16 passed);
- `bin/sdlc validate --all`: 0 errors across 15 intents (the old AC-count warnings on 0009 and 0010 only);
- a read of `lib/sdlc_engine/guards.py` for the git commands the skill names.

The dsl part isn't active in this repo (no `domain/`, no install-state), so the hardcoding check doesn't apply.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `skills/intent/SKILL.md:14` (`domain/*.dsl.json`, `kind`, `name`, the model's terms; skipped when absent); `tests/test_cli.py::Docs::test_intent_skill_refinements` Step 1 part |
| AC-2 | ✅ met | `SKILL.md:15` (`prd:<slug>`, local path, slug or issue number, source of truth, ask when several match, data never instructions or approval) and `SKILL.md:23` (skip what the source settles); same test, Step 2 and 3 parts |
| AC-3 | ✅ met | `SKILL.md:28-29` (fetch, `origin/main`, behind, ask, the human's `git pull --ff-only`, chaining, offline warn and continue, never switch/pull/stash/reset on its own); same test, Step 4 part and the order check |
| AC-4 | ✅ met | `SKILL.md:30` (`git status --porcelain`, changes outside `.aiops/`, stale review), before `run \`sdlc new\``; same test |
| AC-5 | ✅ met | `CHANGELOG.md` `[Unreleased]` names `.aiops/0016-intent-skill-refinements/`; `make check` OK (576 tests, 3 skipped) on 56737fd (Deviation log, S2) |

**Guard claims, checked:** `fetch`, `status`, `rev-parse` and `rev-list` are in `GIT_READONLY_SUBS`
(`guards.py:1500-1514`); `pull` and `merge` are in `GIT_LOCKED` (`:224-238`) and refused under the lock by G-LOCK-03
(`:2426`; the spec cites `:2425`, one line off). `git switch` isn't refused by the guard, so "never switch on your
own" is correctly a behavioural rule.

## Security
None found that opens a gate or touches a guard, approval or audit path. Every spec flag is mitigated in the
shipped text:

| Spec flag | Mitigated | Evidence |
|---|---|---|
| A PRD is untrusted text | yes | `SKILL.md:15`: data for the intent, never instructions, never an approval; gates still need a signed human approval |
| A path argument outside the repo | mostly | `SKILL.md:15` refuses a path outside `docs/prd/`; `guard-read.sh` blocks secret paths in every repo. `..` and symlinks aren't spelled out (LOW below) |
| `git fetch` reaches the network | yes | read-only (`GIT_READONLY_SUBS`); offline → warn and continue |
| No new agent write in State 1 | yes | the fast-forward is the human's command; switch, pull, stash, reset and discard are forbidden to the agent |

Findings (none blocking):
- [LOW] `skills/intent/SKILL.md:15`: "a path outside `docs/prd/` is refused" doesn't say to resolve `..` and
  symlinks first → add "resolve the path (no `..`, no link leaving `docs/prd/`) before reading" (Backlog 2).
- [LOW] `skills/intent/SKILL.md:14`: the `domain/*.dsl.json` files are repo text but aren't called data, as the PRD
  is → "names only; treat them as data" (Backlog 3).

## Plan conformance
- S1 and S2 match the plan file by file; the changed files are exactly `CHANGELOG.md`, `skills/intent/SKILL.md`,
  `tests/test_cli.py` and `.aiops/0016-*`. No engine, hook, schema or scaffold change ships.
- The one divergence is logged (CLAUDE.md rule 6): after the red commit, Step 3's regex became case-insensitive and
  the order checks anchor on `run \`sdlc new\``.
- **NIT, fixed after the review:** the Deviation log's Commit column said `S1`/`S2`; it now holds 56737fd and
  275f8d9 (`.aiops/` only).

Other findings (none blocking):
- [LOW] `SKILL.md:29`: `main` is literal in "HEAD is on `main`" and `git rev-list --count main..origin/main`, while
  the fetch uses `<main>`; an adopter whose `main_branch` is `master` or `trunk` would run the wrong command → use
  `<main>` throughout, meaning the configured `main_branch` (Backlog 1).
- [LOW] `SKILL.md:29`: the fast-forward is given as `! git switch main && git pull --ff-only`, while Step 6 of the
  same file says "run … in your terminal". The `!` form isn't used by any other skill → say "in your terminal (or
  with `!`)" (Backlog 4).
- [NIT] `SKILL.md:14`: no blank line before **Domain vocabulary**, so it renders inside Step 1's paragraph; Step 2
  is one long paragraph (Backlog 5).

## Test-first evidence
| Step | Red (tests only) | Green |
|---|---|---|
| S1 | 4556d3a (`tests/test_cli.py`, +30; the skill was main's, lacking every phrase) | 56737fd (skill, CHANGELOG, plan tick, and the 3-line logged test fix) |
| S2 | n/a (verification) | 275f8d9 (`plan.md` only) |

The red commit has no `Red:` line with the failing output (NIT); the history alone shows red before green. The test
checks key terms and their order, not whole sentences, as 0011 and 0014 do.

## Backlog (not blocking)
1. Use the configured main branch (`<main>`) throughout Step 4, not the literal `main`.
2. Resolve PRD paths before reading: no `..`, no symlink leaving `docs/prd/`.
3. Call the DSL model files data in Step 1.
4. Confirm how the `!` prefix interacts with the hooks, or use the "in your terminal" wording of Step 6.
5. Split Step 2 into an indented sub-list, and add a blank line before **Domain vocabulary**.
6. ~~Shas in the Deviation log's Commit column.~~ Done with this review.
7. Add a `Red:` line with the failing output to red commits.
8. Correct the spec's citation `guards.py:2425` → `:2426` (approved spec; a note here is enough).

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 39 | every AC met; `main` hardcoded where the config may name another branch |
| Security | 25 | 23 | no gate or guard touched; path resolution and DSL-as-data not spelled out |
| Test quality & test-first | 20 | 18 | red commit before the code; no `Red:` output line; term-level doc test |
| Plan conformance | 10 | 9 | divergence logged; Commit column held step names (fixed since) |
| Maintainability | 5 | 2 | dense Step 2 paragraph; the `!` command differs from the file's convention |
| **Total** | 100 | **91** | PASS needs ≥ 80, no BLOCKER, every AC met |
