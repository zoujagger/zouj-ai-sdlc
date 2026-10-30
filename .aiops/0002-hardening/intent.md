---
id: 0002
title: Harden gates and guards (review 0001 findings)
status: Draft
owner: zoujagger
initiator: zoujagger
source: .aiops/0001-zouj-ai-sdlc-plugin/review.md (CHANGES_REQUESTED, 66/100)
created: 2026-10-30
---

# Intent: Harden gates and guards (review 0001 findings)

## Problem
The state-5 review of 0001 (three fresh-context reviewers, at `c26f691`) found that the plugin's two core guarantees
can be bypassed in the released v0.1.0:
- **Read-only lock.** `cat <<EOF > src/app.py` writes code in states 1-3 (BLOCKER, AC-4). So do `git commit <path>`,
  `git -C`, `cp -t`, `find -delete` and `awk -i inplace`.
- **Human-only gates.**
  - A heredoc can write a stamped artifact, which opens a gate locally (AC-3).
  - An agent can run an obfuscated `sdlc approve` with the Claude env vars cleared, and produce an approval commit
    that the CI audit accepts (HIGH, AC-10).
- **Safety guards.** Removing `.aiops/` disables every guard, including the prod-deploy, secret and force-push guards.
  In unrelated repos those guards don't run at all (MEDIUM).
- **Secret reads.** Consumer repos lost the template's Read-tool deny rules for `.env`, `secrets/**`, `*.pem` and
  `*.key` (MEDIUM).
- **Supply chain.** The scaffold's Claude workflows load the plugin unpinned, in jobs with secrets (MEDIUM). This
  repo's own audit runs the PR's own engine, and the CI tools are unpinned (LOW).
- **Process gaps (0001).** The gates were opened after merge and release. The S7 deviation isn't logged, the
  Deviation log has no commit refs, and no commit has red-first evidence.

## Desired outcome
- A gate can only be opened by a commit **signed by a key in an allow-list**. An agent that bypasses every local
  guard still can't produce an approval that `sdlc validate --ci` accepts.
- Every bypass the review reproduced is blocked, and each has a regression test that failed before its fix.
- The safety guards (prod deploy, secret reads and writes, force-push, history rewrite) run in **every** repo where
  the plugin is installed. Only the SDLC gates stay dormant until `sdlc init`.
- `/zouj-ai-sdlc:review` on the result returns PASS (≥ 80, no BLOCKER, no HIGH, every AC met), released as v0.2.0.

## Users & systems affected
- Users: maintainers approving gates (they need a signing key), consumer repos (re-run `sdlc init` for the new
  scaffold files), and agents working under the plugin.
- Systems: `lib/sdlc_engine/{guards,approvals,machine,cli}.py`, `hooks/*`, `defaults/*`,
  `templates/scaffold/{.claude,.github,.aiops}`, plugin CI.

## Constraints
- The engine stays stdlib-only Python (≥ 3.9). The dependencies stay as they are (git, make, python3; gh and jq optional).
- Signing uses git's SSH signing (`gpg.format ssh`, `gpg.ssh.allowedSignersFile`). No GPG requirement.
- 0001's existing unsigned approvals must keep passing the audit through an explicit, auditable legacy list,
  not a blanket opt-out.
- No force pushes or history rewrites on `main` (it's protected).

## Out of scope
- GitHub CODEOWNER-review approval mode (considered; signed commits were chosen).
- Parsing interpreter writes (`python -c`, `node -e`). These stay a documented residual, covered by signing.
- Cursor and OpenCode adapters.

## Open questions
- [x] Approval mechanism? → **signed commits with an allow-listed signer** (zoujagger, 2026-10-30)
- [x] Safety guards outside `.aiops/` repos? → **always on**; only the SDLC gates stay dormant (zoujagger, 2026-10-30)
- [ ] Should a passphrase-protected signing key (or `ssh-add -c` confirmation) be *required* rather than just recommended? An agent running as the user can use an unprotected key (zoujagger)
