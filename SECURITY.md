# Security Policy

## Reporting a vulnerability
Do **not** open a public issue. Use GitHub private vulnerability reporting
(Security → Report a vulnerability) or email the maintainers listed in `.github/CODEOWNERS`.
We aim to acknowledge reports within 3 business days.

## Built-in safeguards
- `.claude/hooks/guard-bash.sh` and `guard-files.sh` block destructive commands, secret reads, and credential writes by AI agents.
- `.claude/settings.json` deny rules prevent reading `.env*` and `secrets/`.
- Every PR gets an automated Claude security review (`claude-pr-review.yml`), and `/security-check` is available locally.
- Dependabot keeps GitHub Actions pinned and updated.
