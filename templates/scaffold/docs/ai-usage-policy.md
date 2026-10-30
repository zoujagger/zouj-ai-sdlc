# AI Usage Policy

## Principles
- **Humans are accountable.** Whoever merges a change owns it, regardless of authorship.
- **AI drafts, humans decide.** Specs, designs, merges, and releases need human approval.
- **Transparency.** PRs disclose meaningful AI assistance (PR template checkbox).

## AI agents MAY
- Read the repository, docs, issues, and PRs.
- Draft intents, specs, plans, ADRs, tests, code, docs, release notes, and postmortems.
- Run contract commands (`make *`), deploy to **staging**, and run read-only git/gh commands.
- Open branches and PRs, and comment on issues and PRs (review comments only, never approvals).
- Run unattended in the Maintain loop (alerts, scans) for read-only diagnosis, and propose changes only through PRs.

## AI agents MUST NOT
- Read or write secrets, `.env*` files, credentials, or private keys.
- Force-push, rewrite shared history, push directly to `main`, or delete branches or tags.
- Disable or bypass hooks, CI checks, or branch protection.
- Merge PRs, approve their own PRs, publish releases, or deploy to production. The agent stops at the production gate.
- Edit tests while the `/fix` test lock is active.
- Send proprietary code or data to services that aren't approved.
- Add dependencies without explaining why in the PR (license + maintenance check).

## Data handling
- Do not paste customer PII or production data into prompts. Use synthetic fixtures.
- Only approved MCP servers go in `.mcp.json`. Each one needs an ADR noting its scopes.

## Review requirements
- Every AI-authored change gets the same human review as human-authored code.
- Security-sensitive areas (auth, crypto, payments, PII) need a CODEOWNER review.
