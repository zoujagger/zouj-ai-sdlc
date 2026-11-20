---
id: 0014
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 22ff5f2
score: 92/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-20
---

# Review: Sharper specs: N/A brevity, diagrams, AC traceability, query hygiene

<!-- State 5 PRE-REVIEW. Written from the report of one fresh-context reviewer covering the three personas, who got
     only the intent folder and the base branch `main` (919e915). The reviewed code is 22ff5f2; b6c8ee7 only adds the
     Deviation log row the review asked for (.aiops/ only). -->

## Summary
- **The check:** a `mermaid_size` spec check fails a draft spec whose fenced ```mermaid block has more than 12
  non-blank lines.
- **The guidance:** the architect agent, the spec skill and the spec template now ask for:
  - `None (no changes)` in an untouched Data model, API contracts or Rollout & rollback;
  - one small diagram for a flow, a state transition or a table;
  - `[AC-N]` on every table, column and endpoint;
  - a Queries list (patterns, composite indexes with the tenant key first, N+1 prevention).

No gate, guard, approval or audit path changes. **PASS, 92/100**: every AC is met, and there is no BLOCKER and no
CRITICAL/HIGH finding.

The reviewer ran, without writing anything:
- **Targeted tests:** `test_engine` MermaidSize, ScopeSizing and DomainDsl (24 passed); `test_cli` Docs and draft
  (17 passed).
- **`bin/sdlc validate --all`:** 0 errors across 13 intents.
- **In-memory probes:** of the fence rules, the performance, and the drafted template.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_engine.py::MermaidSize` (`:756-814`): 13 lines give the exact R-3 text; 12 lines, 12 plus blanks, a 20-line `python` block and no block pass; an unclosed fence fails; approved and unchanged passes, approved but stale fails. `lib/sdlc_engine/schema.py:129-159`, registered at `:169` and in `schemas/spec.json:10`; `validate --all` green |
| AC-2 | ✅ met | `agents/architect.md` Rules (N/A brevity, the three sections, never Security or Architecture); `skills/spec/SKILL.md` step 5; `tests/test_cli.py::Docs::test_spec_quality_guidance` (`~:1061`) |
| AC-3 | ✅ met | `agents/architect.md` step 6, `skills/spec/SKILL.md` step 5, the template's Architecture comment (sequenceDiagram, flowchart, erDiagram; at most 12 lines); same test |
| AC-4 | ✅ met | `agents/architect.md` steps 3-4 (`[AC-N]`) and the Traceability rule (remove, or raise as an open question); `skills/spec/SKILL.md` steps 5 and 8; same test |
| AC-5 | ✅ met | Queries, composite index, tenant key leading and N+1 in architect step 3, skill step 5 and the template's Data model comment; `docs/state-machine.md:71`; `make check` (Deviation log, S3); same test |

## Security
None found that opens a gate or touches a guard, approval or audit path. The check only adds errors to specs whose
gate is closed, and `validate` runs from the CLI, `approvals` and post-edit, never from a pre-* guard.

- **Performance:** `FENCE_RE` (`^ {0,3}(`{3,}|~{3,})(.*)$`) is anchored, with no nested quantifier, and the scan is
  linear. Probes: 2 MB of backticks in 6 ms; 400k alternating fence lines in 0.22 s; a 1 MB info string in 2 ms.
- **Not new:** `A.COMMENT_RE` (`<!--.*?-->`, `re.S`) is quadratic on many unclosed `<!--`. 40k of them (160 KB)
  take 29 s per pass. `artifacts.sections()` already ran it on every validate on main, and the new check adds a
  second pass. A hostile spec stalls only the agent's own validate or post-edit, so it is self-inflicted
  (Backlog 5).
- **Lint evasion, from the stripping the spec requires:** stripping comments before the scan lets a `<!--` inside
  a code block or span hide a real ```mermaid opener up to the next `-->`, and a Mermaid `-->` arrow counts as a
  closer. A 30-line diagram can then pass. The human still sees the diagram at the gate, so this is not a security
  issue (Backlog 1).

## Plan conformance
- S1-S3 match the plan file by file: the changed files are exactly the planned set and `.aiops/0014-*`.
- **Three departures from spec Architecture's fence sketch were not logged at review time:**

  | Spec says | Implementation does |
  |---|---|
  | indent `\s{0,3}` | ` {0,3}` |
  | `mermaid\b` | the first word must equal `mermaid` |
  | (nothing) | refuses a backtick opener whose info contains a backtick |

  Each is the better choice (CommonMark), but CLAUDE.md rule 6 asks for a log entry. **Fixed after the review:** the
  row was added in b6c8ee7, which touches `.aiops/` only. The score stays as the reviewer gave it.

## Test-first evidence
| Step | Red (tests only) | Green |
|---|---|---|
| S1 | d00ce4f (`test_engine.py`) | f033bc7 (`schema.py`, `spec.json`) |
| S2 | 0879bc0 (`test_cli.py`) | 10b2d90 (docs) |

The red tests filter the `validate` errors on "mermaid", so before the code they fail on every long-block case.

Fence rules the reviewer confirmed by probe:
- **Indent:** up to 3 spaces opens; 4 spaces or a tab doesn't (that is an indented code block).
- **Backticks in the info string:** refused on a backtick fence, accepted on a tilde fence.
- **Closing fences:** a longer closer closes; a closer with trailing text doesn't; a 3-backtick closer inside a
  4-backtick block doesn't; a closer of the other character doesn't.
- **A nested ```mermaid line** inside a `python` block isn't counted.
- **The info word:** `mermaid title=x` counts; `Mermaid`, `mermaidish`, `{mermaid}` and `mermaid-x` don't (GitHub
  renders only lowercase `mermaid`).
- **CRLF** is handled.
- **The template:**
  - a spec drafted from it validates with 0 errors and 4 placeholder warnings;
  - the new one-line comments never trigger `PLACEHOLDER_RE` (sections are comment-stripped);
  - the `## Domain DSL` insertion still works.

## Backlog (not blocking)
1. **Comment stripping around fences.** In `_mermaid_size`, strip comments only outside fences, or not at all.
   Mermaid's `-->` arrows interact badly with `COMMENT_RE`. This needs a one-line spec note, since R-3 requires the
   stripping.
2. **The unlogged departures.** ~~Log the three Architecture departures.~~ Done in b6c8ee7.
3. **More `test_fences` cases:** a backtick in the info string, a closer with trailing text, a longer closer, CRLF,
   and a tab or 4-space indent.
4. **Blockquotes and lists.** A ```mermaid block inside a blockquote (`> ```mermaid`) or a list item indented 4 or
   more spaces isn't counted, though GitHub renders both. Document it or accept it.
5. **`COMMENT_RE` is quadratic.** Make it linear (`<!--(?:[^-]|-(?!->))*-->`, or a `str.find` scan) to remove the
   existing slow path, as its own intent.
6. **A loose test regex.** `Security[^.]*Architecture[^.]*never` in `test_spec_quality_guidance` is loose, which is
   acceptable for a doc test.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | every AC met; the fence sketch differs slightly from the implementation (better) |
| Security | 25 | 24 | no gate or guard touched; the linear scan; the existing `COMMENT_RE` slow path |
| Test quality & test-first | 20 | 17 | a red commit before each code commit; several CommonMark edge cases untested |
| Plan conformance | 10 | 8 | three departures unlogged at review time (logged since, in b6c8ee7) |
| Maintainability | 5 | 5 | |
| **Total** | 100 | **92** | PASS needs ≥ 80, no BLOCKER, every AC met |
