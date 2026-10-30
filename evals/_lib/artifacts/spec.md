---
id: 0001
title: CSV export
status: Draft
risk: low
---
# Spec

## Summary
Export contacts.

## Requirements
- R-1 export

## Acceptance criteria
- **AC-1**: Given contacts, when exporting, then a CSV is returned.
- **AC-2**: Given another tenant, when exporting, then 403.

## Data model
No change.

## API contracts
GET /contacts.csv

## Security & data-leak flags
- tenant isolation

## Architecture
Reuse the list query.

## Rollout & rollback
Flag `csv_export`.

## Open questions
- none
