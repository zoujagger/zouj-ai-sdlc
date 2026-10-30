---
name: policy-security
description: Organization security policy (advisory). Apply when writing spec.md, designing, implementing, or reviewing anything touching authentication, authorization, data handling, secrets, external input, dependencies, or infrastructure.
user-invocable: false
---

# Security policy (advisory: hooks enforce the absolute rules)

<!-- Replace these defaults with your organization's policy. -->

## Requirements
- **Authn/Authz:** every endpoint or action has an explicit authorization check. Deny by default.
- **Data classification:** label the data in spec.md (Public / Internal / Confidential / Restricted). Restricted data (PII, credentials, payment) must be encrypted at rest and in transit, and must never be logged.
- **Secrets:** come only from the secret manager or env. Never in code, config, logs, or tests.
- **Input:** validate at trust boundaries, use parameterized queries, encode output by context.
- **Dependencies:** a new dependency needs justification (maintenance, license, popularity), pinned versions, and no install scripts from unknown sources.
- **Logging & audit:** security-relevant events (login, permission change, data export) are audit-logged.
- **CI:** least-privilege `permissions:`. Never interpolate `${{ github.event.* }}` directly in `run:`.

## How to apply in spec.md
Add the data classification and threats (STRIDE-lite) under **Design → Security**. Any conflict with this policy goes under **Policy conflicts** for the compliance owner.
