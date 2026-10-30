---
id: 0001
title: CSV export of account data
status: Approved
risk: low
intent: ./intent.md
created: 2026-03-04
approved-by: Product Lead <po@example.com>
approved-at: 2026-03-04T16:40:00Z
approved-via: prompt
approved-sha256: <stamped by the engine>
---

# Spec: CSV export of account data

<!-- WORKED EXAMPLE (state 2 output). Business goals from intent.md, translated into requirements, schema, contracts and flags. -->

## Summary
Account admins can request a CSV export of their invoices and payments from the dashboard. The file is generated in the
background and offered as a download link that expires after 24 hours. This removes the manual support export (intent: desired outcome).

## Requirements
- **R-1** (US-1): an account admin downloads their invoices and payments as CSV to analyse them in a spreadsheet.
- **R-2** (US-2): support stops running manual SQL exports.
- Edge cases: zero invoices → header row only; a second request while one is running returns the running job; a failed job shows "Export failed, try again" and logs the job id.
- Non-functional: 200k invoices in under 2 minutes with flat memory (streamed); `export_job_failure_rate` added to `ops/bands.yaml`; button and status are keyboard-reachable and announced to screen readers.

## Acceptance criteria
- **AC-1**: Given an admin on Settings → Data, when they click "Export CSV", then an export job is queued and the page shows "Preparing your export".
- **AC-2**: Given a finished export, when the admin opens the link, then they get a UTF-8 CSV with a header row and one row per invoice (id, date, customer, amount, currency, status, paid_at).
- **AC-3**: Given a non-admin user, or an admin of another account, when they call the export endpoints, then they get 403 and no job is queued.
- **AC-4**: Given an export older than 24 hours, when anyone opens its link, then they get 410 Gone and the file has been deleted.
- **AC-5**: Given a cell value starting with `=`, `+`, `-` or `@`, when it is written to the CSV, then it is prefixed with `'` (no formula injection).

## Data model
New table, additive and reversible (`migrations/0042_exports.py`):

| Column | Type | Constraints | Classification |
|---|---|---|---|
| id | uuid | PK | internal |
| account_id | uuid | FK accounts, indexed | internal |
| requested_by | uuid | FK users | personal (pseudonymous) |
| status | enum(queued, running, ready, failed, expired) | not null | internal |
| storage_key | text | random 128-bit, unique, nullable | secret |
| row_count | int | nullable | internal |
| created_at, expires_at | timestamptz | not null; expires_at = created_at + 24h | internal |

## API contracts
| Method & path | Auth | Request | Responses |
|---|---|---|---|
| `POST /api/exports` | session, role `admin` of the account | none | `202 {id, status}` · `200 {id, status}` if one is already running · `403` |
| `GET /api/exports/:id` | session, admin of `exports.account_id` | none | `200 {status, url?, expires_at}` (url = signed, valid until expires_at) · `403` · `404` · `410` once expired |

Errors use the standard `{error: {code, message}}` envelope. Never echo internal ids of other accounts.

## Security & data-leak flags
- ⚠️ **Cross-account access (IDOR)** on `GET /api/exports/:id`: authorise by `account_id` + admin role, not by id alone → AC-3 test with two accounts. (backend lead)
- ⚠️ **Guessable download links**: random `storage_key` plus a signed URL expiring at `expires_at`. Never log the URL. (backend lead)
- ⚠️ **Formula injection** when the file is opened in Excel → AC-5. (backend lead)
- ⚠️ **PII leaving the system** (customer names and emails): admin-only, 24h retention, audit log entry (who, when, row count). The policy-compliance conflict was resolved by the compliance owner on 2026-03-04.
- ⚠️ The bucket needs a 24h lifecycle rule as a second line of defence behind the sweeper. (SRE)

## Architecture
`POST /api/exports` enqueues an `ExportInvoicesJob`. The job streams rows from `billing` in pages, writes the CSV to object
storage under the random key, and updates the export record. A daily sweeper deletes expired files.
Alternatives: synchronous generation (times out at 200k rows and blocks a web worker); emailing the file (puts PII in mailboxes we don't control).
UX states: idle → preparing (spinner + text) → ready (download link + expiry time) → failed (retry). No ADR (nothing hard to reverse).

## Rollout & rollback
Behind the `csv_export` flag, internal accounts first, then everyone. Rollback: turn the flag off (the migration is additive).
Watch `export_job_failure_rate` and dashboard p95 latency.

## Open questions
- [x] Who may export? → admins only (product lead, 2026-03-03)
- [x] Retention? → 24 hours (compliance owner, 2026-03-04)
