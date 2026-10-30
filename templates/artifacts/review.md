---
id: NNNN
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: <git rev-parse HEAD of the reviewed code>
score: 0/100
reviewers: code-reviewer, security-reviewer
created: YYYY-MM-DD
---

# Review: <Title>

<!-- State 5 PRE-REVIEW. Written by fresh-context reviewer personas that did not write the code. -->

## Summary
<Two or three sentences: what changed, overall risk, the verdict and why.>

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met / ❌ not met / ⚠️ partial | `tests/...::test_...` |

## Security
<Findings with a plausible exploit path only, as `[SEVERITY] path:line: problem → fix`. "None found" is valid.>

## Plan conformance
<Steps done vs plan.md, deviations logged or not, out-of-scope changes shipped.>

## Test-first evidence
<Per step: was the proof test committed or run red before the code? Cite commits or run output.>

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | | |
| Security | 25 | | |
| Test quality & test-first | 20 | | |
| Plan conformance | 10 | | |
| Maintainability | 5 | | |
| **Total** | 100 | | PASS needs ≥ 80, no BLOCKER, every AC met |
