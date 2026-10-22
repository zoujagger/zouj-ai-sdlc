---
name: security-check
description: Security review (REVIEW.md Pass 2) of the current diff or a path, covering OWASP, secrets, authz, injection, supply chain, and CI, checked against the spec's Security section and policy-security. Use before PRs touching sensitive areas.
argument-hint: "[base-branch | path]"
---

# /security-check

Target: `$ARGUMENTS` (default `main`)

1. Collect the diff against the base (or read the given path), plus the linked `spec.md` Security section.
2. Delegate to the **security-reviewer** subagent.
3. Present the verdict. A CRITICAL or HIGH finding means the work isn't ready for a PR. Offer fixes.
4. If a fix is broad (beyond this change), suggest a new `/intent` rather than widening the PR.
