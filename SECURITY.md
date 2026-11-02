# Security Policy

## Reporting a vulnerability
Do **not** open a public issue. Use GitHub private vulnerability reporting
(Security → Report a vulnerability) or email the maintainers listed in `.github/CODEOWNERS`.
We aim to acknowledge reports within 3 business days.

## Built-in safeguards
- **In every repo where the plugin is installed**:
  - `hooks/guard-bash.sh` blocks destructive commands, force pushes, history rewrites and secret reads.
  - `hooks/guard-files.sh` blocks writes to secret paths (`defaults/secret-paths`) and credential-looking content.
  - `hooks/guard-read.sh` blocks Read/Grep/Glob on secret files.
  - `hooks/guard-deploy.sh` keeps production behind a human gate.
- **In repos initialized with `sdlc init`**, the state-engine gates are added (`bin/sdlc hook …`):
  - the read-only lock in states 1-3
  - human-only approvals
  - `.aiops/` integrity
  - schema validation
- **Gate approvals:**
  - Each approval is a single-file commit signed by a key in `.aiops/config/allowed-signers`.
  - `sdlc validate --ci --base <target>` verifies the signature against the *target branch's* signer list, so a change can't vouch for itself.
  - Use a passphrase-protected key (or `ssh-add -c`), so nothing can sign silently as you.
- **Consumer scaffolding:**
  - `templates/scaffold/.claude/settings.json` ships Read/Edit deny rules for `.env*`, `secrets/`, `*.pem` and `*.key`.
  - The scaffold's CI loads this plugin from a pinned ref.
- See [docs/architecture.md](docs/architecture.md#threat-model) for the threat model and the residual risks.
