<!-- PR description for intent 0014, generated in state 5. `gh pr create --body-file` it. -->
## Sharper specs: N/A brevity, diagrams, AC traceability, query hygiene

**Intent:** `.aiops/0014-spec-quality/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 92/100 at `22ff5f2`

### What and why
The human reads the engineering half of every spec at the gate. This makes the architect write that half for a fast
review:

- **N/A brevity:** an untouched `## Data model`, `## API contracts` or `## Rollout & rollback` reads exactly
  `None (no changes)`. Security and Architecture always show the reasoning.
- **One diagram:** a multi-step flow, a state transition or a DB table gets one Mermaid diagram in `## Architecture`
  (`sequenceDiagram`, `flowchart` or `erDiagram`, at most 12 lines).
- **AC traceability:** every table, column and endpoint cites its `[AC-N]`. Unrequested scope is removed or raised
  as an open question.
- **Query hygiene:** when stored data is added or read, `## Data model` ends with Queries: each pattern, the
  composite index that serves it (the tenant key leading in multi-tenant data), and N+1 prevention.

All of it is guidance in `agents/architect.md`, `skills/spec/SKILL.md` and the spec template. One rule is enforced:
the new `mermaid_size` check fails a draft spec whose ```mermaid block has more than 12 non-blank lines
(CommonMark fences, one linear pass; approved specs exempt).

### Acceptance criteria
- [x] AC-1: the 12-line cap and its fence rules (`tests/test_engine.py::MermaidSize`)
- [x] AC-2: `None (no changes)` in the three implementation sections only
  (`tests/test_cli.py::Docs::test_spec_quality_guidance`)
- [x] AC-3: one diagram, at most 12 lines (same test)
- [x] AC-4: `[AC-N]` on tables, columns and endpoints (same test)
- [x] AC-5: Queries, composite indexes with the tenant key, N+1; `docs/state-machine.md`; `make check` green (same
  test)

### Deviations from plan
- **S1:** the fence regex follows CommonMark more closely than the spec's sketch:
  - the indent is spaces only;
  - the info string's first word must be `mermaid`;
  - a backtick opener can't hold a backtick.

  Logged after the review, in b6c8ee7.

### Risks and rollback
- **Non-blocking backlog** (review.md):
  - comment stripping lets a crafted spec hide a long diagram;
  - a few CommonMark edge cases are untested;
  - blocks inside blockquotes and lists aren't counted;
  - the existing quadratic `COMMENT_RE`.
- **Rollback:** revert the PR.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
