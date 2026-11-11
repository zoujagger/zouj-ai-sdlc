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
  - **A human for each signature** (`approval_key_policy: "human"`, the default): `sdlc approve` and `sdlc doctor`
    accept only an `sk-` key (touch) or a passphrase-protected key that isn't loaded in ssh-agent. An agent running
    as you can't sign without you, whatever the shell guards miss.
  - CI can't see how a key is protected. Keep the key protected, and keep `.aiops/config/` under CODEOWNERS.
  - Options, strongest first: a separate OS user or clean clone for approving, an `sk-` key (without
    `no-touch-required`), a dedicated passphrase key kept out of ssh-agent. `"approval_key_policy": "any"` is the
    human-owned escape hatch; its cost is that anything running as you can sign approvals
    ([approval isolation](docs/architecture.md#approval-isolation)).
  - Approval commits are made with a pinned `ssh-keygen`, no hooks and no repo-local signing config.
- **The profile** (how an approval is proven) lives in the human-owned `.aiops/config.json`. A repo's first
  profile is set by the human typing `Setup Profile solo|team|strict` as their whole prompt, only while the
  config is the untouched template and nothing is approved. It is committed alone and unsigned, as
  `chore(aiops): Setup Profile <name>`; it opens no gate, and CI reads the config from the target branch. Later
  changes are made in the human's own terminal. Known gap: a session the agent starts can type a phrase too
  ([ADR 0003](docs/adr/0003-first-profile-by-typed-phrase.md)); under `team` and `strict` an approval still
  needs the human's signature.
- **Trust model of the plugin itself:** enabling the plugin trusts github.com/zoujagger/zouj-ai-sdlc at that ref. Its
  hooks run as the user on every tool call, and `bin/sdlc` is what the human runs to approve. The scaffold's marketplace
  snippet (`.claude/settings.json`) and the README commands therefore pin a release tag, like the CI's
  `ZOUJ_SDLC_REF`. Move to a new release through a reviewed change.
- **Consumer scaffolding:**
  - `templates/scaffold/.claude/settings.json` ships Read/Edit deny rules for `.env*`, `secrets/`, `*.pem` and `*.key`.
  - The scaffold's CI loads this plugin from a pinned ref.
- See [docs/architecture.md](docs/architecture.md#threat-model) for the threat model and the residual risks.
