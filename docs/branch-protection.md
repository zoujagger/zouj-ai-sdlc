# Branch Protection (recommended)

Apply to `main` under Settings → Rules → Rulesets:

- Require a pull request before merging
  - Required approvals: **1** (2 for security-sensitive paths via CODEOWNERS)
  - Dismiss stale approvals on new commits
  - Require review from Code Owners
- Require status checks to pass:
  - `ci / check`
  - `ci / validate-template`
  - (optional) `claude-pr-review / review`
- Require conversation resolution before merging
- Require linear history
- Block force pushes and deletions
- Restrict who can bypass (admins only, logged)
- The authoring agent never counts as an approver. Claude's PR review only comments (REVIEW.md).

## Environments (production gate)
Settings → Environments:
- `staging`: no reviewers. `deploy.yml` deploys automatically on `main`.
- `production`: **required reviewers** (named humans) and a deployment branch rule limited to `main`.
  This is where "the agent does everything up to the production gate and nothing past it" is enforced in CI.
  The local equivalent is the `guard-deploy.sh` hook.

## Secrets
- `ANTHROPIC_API_KEY`: repo or org secret used by the Claude workflows.
- Or install the Claude GitHub App: run `/install-github-app` inside Claude Code.

With the `gh` CLI:
```bash
gh secret set ANTHROPIC_API_KEY
```
