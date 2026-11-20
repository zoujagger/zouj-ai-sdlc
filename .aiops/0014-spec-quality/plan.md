---
id: 0014
title: Sharper specs: N/A brevity, diagrams, AC traceability, query hygiene
status: Approved
spec: ./spec.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T19:27:13Z
approved-via: cli
approved-sha256: eab402eb92b786ac2c406a97dc349a5eb8561a02b5b3d0fd51916731e83f1922
---

# Plan: Sharper specs: N/A brevity, diagrams, AC traceability, query hygiene

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Two TDD steps and a verification step. As in 0012 and 0013, each code step gets a commit holding only its red
tests, then the code that turns them green.

1. **S1, the one engine change:** the `mermaid_size` check.
2. **S2, the guidance:** the architect agent, the spec skill, the spec template and the docs, proven by a docs test.
3. **S3, verification.**

Code reused:
- **The check:** 0011's check protocol and `schema._gate_open` (`lib/sdlc_engine/schema.py:101`), registered in
  `CHECKS` (`:127`) and in `schemas/spec.json`. `A.COMMENT_RE` strips comments, as `_domain_dsl` does.
- **The tests:** the fixtures of `ScopeSizing` (`tests/test_engine.py:675`): `helpers.SPEC`, and an approved spec
  written with its own `approval_hash`.
- **The guidance:** `agents/architect.md` steps 3, 4, 6 and 7, and `skills/spec/SKILL.md` steps 5 and 8.
  `templates/artifacts/spec.md` isn't part of the scaffold history (checked in 0011), so no regeneration is needed.

## Steps
- [ ] **S1**: Fail a draft spec whose ` ```mermaid ` block has more than 12 non-blank lines.
  - **Files:**
    - `tests/test_engine.py` (modify): a new `MermaidSize(RepoCase)` class whose helper `spec_with(block,
      approved=False)` puts the block in `## Architecture`. Its tests:
      - `test_short_blocks_pass`: 12 non-blank lines; 12 plus blank lines; a ` ```python ` block of 20 lines;
        no block at all (AC-1);
      - `test_long_block_fails`: 13 lines give exactly
        `` a ```mermaid block has 13 lines (more than 12): keep one diagram to the main flow, states or tables,
        and move detail into the prose `` (AC-1);
      - `test_fences`: a `~~~~mermaid` block of 13 lines is counted; a ` ``` ` line inside a `~~~` block doesn't
        close it; an indented (≤ 3 spaces) fence opens; `mermaid` with trailing words after it opens (AC-1);
      - `test_unclosed_fence_counts_to_the_end` (AC-1);
      - `test_two_long_blocks_two_errors`;
      - `test_block_in_a_comment_is_ignored`;
      - `test_approved_spec_is_exempt`: a long block with `status: Approved` and the matching hash gives no error;
        with the hash of other text, it errors (AC-1).
    - `lib/sdlc_engine/schema.py` (modify): `MERMAID_MAX = 12`, a fence regex without backtracking, and
      `_mermaid_size` (spec Architecture), registered in `CHECKS`.
    - `schemas/spec.json` (modify): `checks` gains `mermaid_size`.
  - **Test first:** `test_long_block_fails`, `test_fences`, the unclosed and two-block tests, and the stale half of
    `test_approved_spec_is_exempt` fail, because no check exists.
  - Covers: AC-1
- [ ] **S2**: Write the N/A, diagram, traceability and query-hygiene guidance.
  - **Files:**
    - `tests/test_cli.py` (modify): `Docs::test_spec_quality_guidance` checks that:
      - `agents/architect.md` and `skills/spec/SKILL.md` contain `None (no changes)` with the three section names,
        and say Security and Architecture never take it (AC-2);
      - they contain `sequenceDiagram`, `flowchart`, `erDiagram` and "12 lines" (AC-3);
      - they contain `[AC-N]` and say unrequested scope is removed or raised as an open question (AC-4);
      - they contain "Queries", "composite index", "tenant key" and "N+1" (AC-5);
      - `templates/artifacts/spec.md` names `None (no changes)`, Mermaid, `[AC-N]` and Queries in its comments;
      - `docs/state-machine.md` has `` `mermaid_size` ``;
      - the CHANGELOG `[Unreleased]` names `.aiops/0014-spec-quality/` (AC-5).
    - `agents/architect.md` (modify): step 3 (Data model): the `[AC-N]` tags and the Queries list; step 4 (API
      contracts): the `[AC-N]` tags; step 6 (Architecture): the diagram rule; step 7 (Rollout): the N/A rule; and a
      Rules line covering R-1 and R-4 (unrequested scope).
    - `skills/spec/SKILL.md` (modify): step 5 names the four rules; step 8's gate presentation shows the diagram and
      the `[AC-N]` tags; step 7 names the Mermaid check.
    - `templates/artifacts/spec.md` (modify): guidance comments in `## Data model`, `## API contracts`,
      `## Architecture` and `## Rollout & rollback`. The placeholders stay, so the placeholder warning still fires.
    - `docs/state-machine.md` (modify): the `mermaid_size` row.
    - `CHANGELOG.md` (modify): `[Unreleased]` `### Added`, naming `.aiops/0014-spec-quality/`.
  - **Test first:** `test_spec_quality_guidance` fails on the missing phrases.
  - Covers: AC-2, AC-3, AC-4, AC-5
- [ ] **S3**: Prove the change.
  - **Commands:**
    - `make check`;
    - `make validate`;
    - `bin/sdlc validate --all`: every existing spec still validates, since none has a Mermaid block;
    - `git diff --name-only main...HEAD`: only the files S1 and S2 name, and `.aiops/0014-*`.
  - **Files:** none. The results go in the Deviation log and in review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-1, AC-5

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The fence rules disagree with how Markdown renders (indent, tilde, a longer closing fence) | medium | low: a miscount in an edge case | Follow CommonMark's fence rules (≤ 3 spaces indent; closed by the same character, at least as long); S1's `test_fences` covers each rule |
| A slow path through the scan on an agent-written spec | low | low | A single pass over lines, with an anchored regex per line that has no nested quantifiers |
| The template comments make every new spec longer to read | low | low | Keep each comment to two or three lines; the placeholders are replaced when the spec is written |
| Anaconda's `ruff` on PATH reformats the repo if the hooks load | high if the hooks load | high | `git status` after each edit; restore anything outside the step |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_engine.py::MermaidSize` (`test_short_blocks_pass`, `test_long_block_fails`, `test_fences`, `test_unclosed_fence_counts_to_the_end`, `test_two_long_blocks_two_errors`, `test_block_in_a_comment_is_ignored`, `test_approved_spec_is_exempt`); S3 `sdlc validate --all` | unit, repo | the cap, its fence rules, the exemption, and history green |
| AC-2 | `tests/test_cli.py::Docs::test_spec_quality_guidance` (N/A part) | doc | the three sections, never Security or Architecture |
| AC-3 | same test (diagram part) | doc | the diagram types and the 12-line cap |
| AC-4 | same test (traceability part) | doc | `[AC-N]` on tables, columns and endpoints; unrequested scope removed or raised |
| AC-5 | same test (query and docs parts); S3 `make check` | doc | Queries, composite indexes with the tenant key, N+1; the docs row |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
