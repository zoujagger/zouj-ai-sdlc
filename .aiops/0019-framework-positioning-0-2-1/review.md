---
id: 0019
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 6f420d5
score: 95/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-25
---

# Review: Framework positioning and release 0.2.1

<!-- State 5 PRE-REVIEW. As in 0018, written in the implementing session, not by a fresh-context reviewer: the
     three personas' checklists were applied to `origin/main...6f420d5` (origin/main = dae6461) and every result was
     re-run. The human may ask for a fresh-context review before merging. -->

## Summary
The project's identity is stated as an AI-native software engineering framework, implemented as a Claude Code
plugin, in the README, both manifests and `CLAUDE.md`; `docs/sdlc.md` gains an Engineering practices section that
ties each practice to its mechanism and states the limits; and the release moves to 0.2.1. No id, prefix, skill,
hook, schema or behaviour changes. **PASS, 95/100**: every AC is met, no BLOCKER and no CRITICAL/HIGH/MEDIUM
finding.

Re-run: `make check` (577 OK, 3 skipped); `make validate` (passed, one existing warning: root `CLAUDE.md`);
`scaffold-history.py --check` (up to date); README link check (all relative links and anchors resolve).

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `.claude-plugin/plugin.json:4` and `marketplace.json:9` carry R-1/R-2's text; none of `orchestration`, `guarantee`, `sandbox`; `CLAUDE.md:3` opens with R-3's sentence; `test_cli.py::Docs::test_framework_positioning` passes |
| AC-2 | ✅ met | `docs/sdlc.md` `## Engineering practices` lists the six practices with their mechanisms, the review caveat and the Limits paragraph (deterrent, not a sandbox; XP borrowed, not claimed); README's practices bullet links `docs/sdlc.md#engineering-practices`; same test |
| AC-3 | ✅ met | `plugin.json:3` `0.2.1`; `CHANGELOG.md` `## [0.2.1] - 2026-11-25` newest, compare link from `v0.2.0`; `### Changed` positioning, `### Added` the two entries moved unchanged; `[Unreleased]` empty; `test_version_matches_changelog`, `test_changelog_has_the_release` pass |
| AC-4 | ✅ met | README status line `0.2.1`, `@v0.2.1` twice, `checkout v0.2.1`, `"ref": "v0.2.1"`; no pre-release string above `## Lifecycle`; the License section's "From 0.2.0" kept as history |
| AC-5 | ✅ met | `0.2.1` history entry equals `0.2.0`'s, every `origin/main` entry unchanged; `git diff --name-only origin/main...HEAD` lists only S1-S2's files and `.aiops/0019-*`; checks green (Deviation log, S3) |

**Claims check:** the new text says "aims to", "help agents follow", "guardrails"; it names Claude Code as the only
supported environment; the review section says nothing checks how a `review.md` was produced; no XP, correctness
or compliance claim. Each mechanism named in `## Engineering practices` exists: `covers_spec_acs` (schemas), the
implementer's red-green-refactor (`agents/implementer.md`), the `/fix` test lock, the post-edit schema hook and the
Stop hook (`docs/architecture.md`), `aiops-gates` (CI).

## Security
None found. No engine, hook, guard, approval, secret-path or CI-audit file changed; `CLAUDE.md` changed only in its
opening sentence (no rule moved).

Spec flags:
- **Overclaiming:** mitigated by the Limits paragraph, the README's "deterrent, not a sandbox", and the test that
  bans `guarantee`/`sandbox`/`orchestration` from the manifest descriptions.
- **Pins to a tag that doesn't exist yet:** installs fail closed until R-9 tags right after the merge.

The three approval commits (5414164, 4c80b25, 89f652d) each touch one file and carry an `AIOps-Approval` trailer
with the matching digest.

## Plan conformance
- S1 and S2 changed exactly the planned files; S3's commands and results are in the Deviation log.
- [NIT] The README intro was rewritten before the intent (docs-only, zoujagger's wording) and committed in S1, as
  the plan says.
- [NIT] `CLAUDE.md`'s "Docs:" references moved to their own line to keep the 120-column wrap; same content.

## Test-first evidence
| Step | Red (tests only) | Green |
|---|---|---|
| S1 | 7f3f31a (`test_framework_positioning` fails on the manifest description) | 435188b |
| S2 | f439e8a (both release tests fail `'0.2.0' != '0.2.1'`) | 3490821 |
| S3 | n/a (verification) | 6f420d5 (`plan.md` only) |

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 40 | every AC met; claims match the mechanisms |
| Security | 25 | 25 | trust model unchanged; overclaiming flag handled |
| Test quality & test-first | 20 | 18 | red before green in both steps; wording is pinned by phrases, not full text |
| Plan conformance | 10 | 9 | file-by-file; README intro predates the intent (logged here) |
| Maintainability | 5 | 3 | review written in the implementing session, not fresh context |
| **Total** | 100 | **95** | PASS needs ≥ 80, no BLOCKER, every AC met |
