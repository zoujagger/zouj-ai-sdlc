---
id: 0001
title: CSV export of account data
status: Validated      # Draft | Validated | Specified | Closed
initiator: "Support ticket #412 (and 37 similar since March)"
owner: "@product-lead"
source: "#412"
created: 2026-03-02
---

# Intent: CSV export of account data

<!-- WORKED EXAMPLE. A filled-in intent for a fictional invoicing app. Real intents live in docs/intents/. -->

## Problem
Customers can't get their data out without asking support. Since March we have had 38 tickets (#412 and linked)
asking for "a spreadsheet of my invoices". Support exports it by hand with a SQL query, which takes about 20 minutes per ticket.
Two enterprise prospects listed data portability as a procurement requirement.

## Desired outcome
- An account admin gets their own invoices and payments as a file they can open in Excel or Sheets, without contacting support.
- "Export my data" support tickets drop to near zero within a month of release.

## Users & systems affected
- Users: account admins (export); support agents (fewer tickets).
- Systems: `billing` service (invoices, payments), web dashboard, background job queue.

## Constraints
- Accounts can have up to 200k invoices. The export must not slow down the dashboard for others.
- Exported files contain customer personal data (names, emails on invoices).
- Must ship before the Q2 enterprise renewal (2026-04-30).

## Out of scope
- Scheduled or recurring exports.
- Formats other than CSV (Excel, JSON).
- Importing data back in.

## Open questions
- [x] Who may export: any user or admins only? → **Admins only** (product lead, 2026-03-03)
- [x] How long do we keep generated files? → **24 hours** (compliance owner, 2026-03-04)

<!-- Gate: the product owner validated this intent (status: Validated). Next: /spec 0001 -->
