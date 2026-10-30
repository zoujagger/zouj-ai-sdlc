---
name: policy-compliance
description: Organization compliance policy (advisory). Apply when writing spec.md or reviewing changes involving personal data, retention, regulated domains, audit, accessibility obligations, or third-party data processors.
user-invocable: false
---

# Compliance policy (advisory)

<!-- Replace with your obligations (GDPR, SOC 2, HIPAA, PCI-DSS, ISO 27001, sector rules). -->

## Checks for every spec
- **Personal data:** what's collected, the lawful basis, purpose limitation, the retention period, and the deletion/export path (data-subject rights).
- **Processors:** any new third party handling data needs a DPA and a vendor review. Flag it.
- **Data residency:** where the data is stored and processed.
- **Audit:** changes to regulated data paths must be traceable (who, what, when).
- **Accessibility:** user-facing features meet WCAG 2.2 AA.
- **Change management:** high-risk changes (see below) need tech-lead sign-off on spec.md.

## High-risk triggers (add the tech lead to the spec gate)
Payments, authentication, personal data schema changes, data deletion, cross-region data transfer, public API breaking changes.

## How to apply
List each applicable obligation in spec.md under **Compliance**. Anything unresolved goes under **Flags** or **Policy conflicts**, with the owner who must decide.
