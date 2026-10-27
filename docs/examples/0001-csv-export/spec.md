---
id: 0001
title: CSV export of account data
status: Accepted       # Draft | In Review | Accepted | Implemented | Superseded
owner: "@product-lead"
accepted_by: "@product-lead, @compliance-owner"
risk: low              # low | high → high adds the tech lead to the gate
intent: ./intent.md
created: 2026-03-04
---

# Spec: CSV export of account data

<!-- WORKED EXAMPLE. Requirements and design produced in one session from intent.md, with the policy skills applied. -->

## Summary
Account admins can request a CSV export of their invoices and payments from the dashboard. The file is generated in the
background and offered as a download link that expires after 24 hours. This removes the manual support export (intent: desired outcome).

## Requirements
### User stories
- **US-1**: As an account admin, I want to download my invoices and payments as CSV so that I can analyse them in a spreadsheet.
- **US-2**: As a support agent, I want customers to self-serve exports so that I stop running manual SQL queries.

### Acceptance criteria
- **AC-1** (US-1): Given an admin on Settings → Data, when they click "Export CSV", then an export job is queued and the page shows "Preparing your export".
- **AC-2** (US-1): Given a finished export, when the admin opens the link, then they get a UTF-8 CSV with a header row and one row per invoice (id, date, customer, amount, currency, status, paid_at).
- **AC-3** (US-1): Given a non-admin user, when they call the export endpoint, then they get 403 and no job is queued.
- **AC-4** (US-2): Given an export older than 24 hours, when anyone opens its link, then they get 410 Gone and the file has been deleted.
- **AC-5** (US-1): Given a cell value starting with `=`, `+`, `-` or `@`, when it is written to the CSV, then it is prefixed with `'` (no formula injection).

### Edge cases & errors
- Account with zero invoices → CSV with the header row only.
- Second export requested while one is running → return the running job; don't queue a duplicate.
- Job fails → the page shows "Export failed, try again" and the failure is logged with the job id.

### Non-functional requirements
- Performance: 200k invoices exported in under 2 minutes, streamed (memory stays flat).
- Observability: add `export_job_failure_rate` to `ops/bands.yaml`.
- Accessibility: the button and status message are keyboard-reachable and announced to screen readers.

## Design
### Approach
`POST /api/exports` (admin only) enqueues an `ExportInvoicesJob`. The job streams rows from `billing` in pages of 5k,
writes the CSV to object storage under a random key, and stores the export record. `GET /api/exports/:id` returns
status and a signed URL valid until `expires_at`. A daily sweeper deletes expired files.

### Interfaces & data
- `POST /api/exports` → `202 {id, status}` · `GET /api/exports/:id` → `{status, url?, expires_at}`
- New table `exports(id, account_id, requested_by, status, storage_key, created_at, expires_at)`. Additive migration, reversible.

### Alternatives considered
| Option | Why not |
|---|---|
| Generate synchronously in the request | 200k rows times out and blocks a web worker |
| Email the file | Puts personal data in mailboxes we don't control (policy-compliance) |

### Security (policy-security)
Data classification: confidential (customer PII). Threats: cross-account access (authz check on account_id + admin role,
AC-3), guessable links (random key + signed URL), formula injection when opened in Excel (AC-5).

### Compliance (policy-compliance)
Personal data leaves the system at the admin's request, which is the purpose of the feature. Files are deleted after 24h (AC-4).
Each export is recorded in the audit log (who, when, row count).

### UX & brand (policy-ux, policy-brand)
States: idle → preparing (spinner + text) → ready (download link + expiry time) → failed (retry). Copy: "Export CSV", "Preparing your export".

### Rollout & rollback
Behind the `csv_export` flag, enabled for internal accounts first, then everyone. Rollback: turn off the flag; the migration is additive.
Watch `export_job_failure_rate` and dashboard p95 latency.

## Flags (points of attention)
- ⚠️ Storage bucket must have a 24h lifecycle rule as a second line of defence behind the sweeper (SRE)

## Policy conflicts
| Requirement | Policy | Conflict | Resolution |
|---|---|---|---|
| Export contains customer emails | policy-compliance: minimise PII leaving the system | Export is the requested feature | Admin-only, 24h retention, audit log (compliance owner, 2026-03-04) |

## Out of scope
- Scheduled exports, non-CSV formats, imports.

## ADRs
- None (no hard-to-reverse decision)
