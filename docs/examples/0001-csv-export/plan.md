---
id: 0001
title: CSV export of account data
status: Done           # Draft | Accepted | In Progress | Done
engineer: "@backend-dev"
intent: ./intent.md
spec: ./spec.md
created: 2026-03-05
---

# Plan: CSV export of account data

<!-- WORKED EXAMPLE. Produced in Plan mode, challenged by the engineer, then accepted. Shows a finished plan with one logged deviation. -->

## Approach
Build from the data layer up so each task leaves `make check` green: migration and model, the CSV writer (pure, easy to test),
the job, the API with authz, then the UI behind the flag. The sweeper comes last because nothing depends on it.

## Stress test
- *What if an account has 2M invoices, not 200k?* Streaming in 5k pages keeps memory flat; runtime scales linearly. Added a job timeout of 15 min.
- *Can two admins race and create two exports?* T4 checks for a running job inside the same transaction that creates one.
- *Is the migration safe on the live table?* It only adds a new table; no lock on `invoices`.
- *Which test would catch a cross-account leak?* AC-3 test uses two accounts and asserts a 403 plus no job row.

## Tasks
<!-- Status: [ ] todo · [~] in progress · [x] done. Each task leaves `make check` green and maps to AC IDs. -->
- [x] **T1**: Add the `exports` table and model
  - AC: AC-1, AC-4
  - Files: `migrations/0042_exports.py`, `billing/models/export.py`
  - Tests: `tests/billing/test_export_model.py`
  - Done when: migration applies and reverts cleanly
- [x] **T2**: CSV writer with formula-injection escaping
  - AC: AC-2, AC-5
  - Files: `billing/export/csv_writer.py`
  - Tests: `tests/billing/test_csv_writer.py`
  - Done when: header, empty account and `=cmd` cases pass
- [x] **T3**: `ExportInvoicesJob` streaming 5k pages to storage
  - AC: AC-2
  - Files: `billing/jobs/export_invoices.py`
  - Tests: `tests/billing/test_export_job.py`
  - Done when: a 200k-row fixture exports in under 2 min with flat memory
- [x] **T4**: `POST/GET /api/exports` with admin authz and duplicate check
  - AC: AC-1, AC-3
  - Files: `billing/api/exports.py`
  - Tests: `tests/billing/test_exports_api.py`
  - Done when: 202 for admins, 403 for others, running job returned on repeat
- [x] **T5**: Settings → Data UI states behind `csv_export` flag
  - AC: AC-1
  - Files: `web/settings/DataExport.tsx`
  - Tests: `web/settings/DataExport.test.tsx`
  - Done when: all four states render; screenshot attached to PR
- [x] **T6**: Expiry: 410 after 24h and daily sweeper
  - AC: AC-4
  - Files: `billing/jobs/sweep_exports.py`, `billing/api/exports.py`
  - Tests: `tests/billing/test_export_expiry.py`
  - Done when: expired link returns 410 and the file is gone

## Parallelisation
T2 and T5 touch disjoint files and can run in separate worktrees (`/parallel`). T3 needs T1 and T2; T4 needs T1.

## Verification
`make check`; the AC-1…AC-5 tests listed above; screenshot of the four UI states; `/verify 0001` returns VERIFIED.

## Deviation log
| Date | Task | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-03-09 | T3 | Pages of 2k rows instead of 5k | 5k pages exceeded the 30s DB statement timeout on the largest test account | `a1b2c3d` |
