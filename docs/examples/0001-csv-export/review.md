---
id: 0001
verdict: PASS
commit: 9f8e7d6c5b4a39281706f5e4d3c2b1a098765432
score: 88/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-03-11
---

# Review: CSV export of account data

<!-- WORKED EXAMPLE (state 5 output). Written from fresh-context persona reports. The human still decides the merge. -->

## Summary
All five ACs are met and proven by tests that failed first. Cross-account access and formula injection are covered. One MINOR
finding. PASS at 88/100. Merge decision: the CODEOWNER.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/billing/test_exports_api.py:14` · `web/settings/DataExport.test.tsx:22` |
| AC-2 | ✅ met | `tests/billing/test_csv_writer.py:9` |
| AC-3 | ✅ met | `tests/billing/test_exports_api.py:41` (two accounts, asserts no job row) |
| AC-4 | ✅ met | `tests/billing/test_export_expiry.py:18` |
| AC-5 | ✅ met | `tests/billing/test_csv_writer.py:30` |

## Security
- None found with a plausible exploit path. All spec flags are mitigated: authz on `account_id` (`billing/api/exports.py:27`), random key + signed URL (`billing/jobs/export_invoices.py:52`), URL not logged, escaping (`billing/export/csv_writer.py:18`).
- The bucket lifecycle rule is confirmed by SRE in the infra repo (outside this diff).

## Plan conformance
All 6 steps ticked. One deviation (S3 page size) is logged with its reason. No out-of-scope changes.

## Test-first evidence
Every step commit carries `Red:` output (for example S4: `test_other_account_gets_403 … 404 != 403`), followed by `Green: make check passed`.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 40 | |
| Security | 25 | 23 | MINOR: the audit log lacks row_count on failure |
| Test quality & test-first | 20 | 17 | the S3 perf test is slow (40s) |
| Plan conformance | 10 | 10 | |
| Maintainability | 5 | 4 | |
| **Total** | 100 | 88 | PASS |
