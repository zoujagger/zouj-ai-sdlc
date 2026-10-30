---
id: 0001
title: CSV export of account data
status: Approved
spec: ./spec.md
created: 2026-03-05
approved-by: Backend Dev <dev@example.com>
approved-at: 2026-03-05T11:05:00Z
approved-via: prompt
approved-sha256: <stamped by the engine>
---

# Plan: CSV export of account data

<!-- WORKED EXAMPLE (state 3 output, read-only). Finished: all steps ticked, one logged deviation. -->

## Approach
Build from the data layer up, so each step leaves `make check` green: migration and model, the CSV writer (pure, easy to test),
the job, the API with authz, then the UI behind the flag. The sweeper comes last because nothing depends on it.
Stress test answered with the engineer: 2M invoices (streaming keeps memory flat, plus a 15-min job timeout); two admins racing
(the duplicate check runs in the same transaction); live-table safety (new table only); cross-account leak (two-account AC-3 test).

## Steps
- [x] **S1**: Add the `exports` table and model
  - Files: `migrations/0042_exports.py` (create), `billing/models/export.py` (create)
  - Test first: `tests/billing/test_export_model.py::test_migration_roundtrip` → fails: no table
  - Covers: AC-1, AC-4
- [x] **S2**: CSV writer with formula-injection escaping
  - Files: `billing/export/csv_writer.py` (create)
  - Test first: `tests/billing/test_csv_writer.py::test_escapes_formula_prefix` → fails: module missing
  - Covers: AC-2, AC-5
- [x] **S3**: `ExportInvoicesJob` streaming pages to storage
  - Files: `billing/jobs/export_invoices.py` (create)
  - Test first: `tests/billing/test_export_job.py::test_streams_200k_rows` → fails: job missing
  - Covers: AC-2
- [x] **S4**: `POST/GET /api/exports` with admin and account authz, plus the duplicate check
  - Files: `billing/api/exports.py` (create), `billing/api/routes.py` (modify)
  - Test first: `tests/billing/test_exports_api.py::test_other_account_gets_403` → fails: 404 route
  - Covers: AC-1, AC-3
- [x] **S5**: Settings → Data UI states behind the `csv_export` flag
  - Files: `web/settings/DataExport.tsx` (create)
  - Test first: `web/settings/DataExport.test.tsx` → fails: component missing
  - Covers: AC-1
- [x] **S6**: Expiry: 410 after 24h and a daily sweeper
  - Files: `billing/jobs/sweep_exports.py` (create), `billing/api/exports.py` (modify)
  - Test first: `tests/billing/test_export_expiry.py::test_expired_link_410` → fails: returns 200
  - Covers: AC-4

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Large accounts exceed DB statement timeouts | medium | medium | paged reads; job timeout 15 min |
| Signed URL leaks via logs | low | high | URL never logged; short expiry |
| Duplicate jobs under concurrency | medium | low | check + insert in one transaction |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/billing/test_exports_api.py::test_admin_queues_job` · `web/settings/DataExport.test.tsx` | integration · ui | job queued, preparing state shown |
| AC-2 | `tests/billing/test_csv_writer.py::test_header_and_rows` | unit | columns, UTF-8, one row per invoice |
| AC-3 | `tests/billing/test_exports_api.py::test_other_account_gets_403` | integration | 403 and no job row, for a non-admin and a foreign admin |
| AC-4 | `tests/billing/test_export_expiry.py::test_expired_link_410` | integration | 410 and file deleted |
| AC-5 | `tests/billing/test_csv_writer.py::test_escapes_formula_prefix` | unit | `=`,`+`,`-`,`@` prefixed with `'` |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-03-09 | S3 | Pages of 2k rows instead of 5k | 5k pages exceeded the 30s DB statement timeout on the largest test account | `a1b2c3d` |
