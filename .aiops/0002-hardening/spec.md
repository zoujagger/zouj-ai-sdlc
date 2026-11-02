---
id: 0002
title: Harden gates and guards (review 0001 findings)
status: Approved
risk: high
intent: ./intent.md
created: 2026-10-30
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-02T09:04:45Z
approved-via: cli
approved-sha256: 3f42aa78903276307379d1389da49fb83675fae21e2d696e8c6b70edf63b52c9
---

# Spec: Harden gates and guards (review 0001 findings)

## Summary
This closes every finding from `.aiops/0001-zouj-ai-sdlc-plugin/review.md`. The fixes, in priority order:
1. Signed, allow-listed approval commits are the real gate.
2. The shell guard parses heredocs and more write forms correctly, and protects `.aiops/` itself.
3. The safety guards run in every repo, and secret files can't be read.
4. The plugin is pinned in the scaffold's CI.
5. 0001's process gaps are recorded.

Released as **v0.2.0**: signing is a new requirement for approvers. Users and systems are as listed in intent.md.

## Requirements
- **R-1 Signed approvals.**
  - `sdlc approve` and the prompt hook create the approval commit with `git commit -S`.
  - `sdlc validate --ci` accepts an open gate only if its approval commit has a good signature (`%G?` = `G`) from a key
    in `.aiops/config/allowed-signers`, read from the **base ref** when `--base` is given. The only exceptions are
    commits listed in `.aiops/config/legacy-approvals`.
  - `require_signed_approvals` defaults to `true`.
- **R-2 Shell parsing.** The heredoc stripper removes only the body lines and keeps the rest of the marker line.
  New write forms are recognised: `git commit <pathspec>`, `git -C <dir>`, `cp/mv -t DIR` and `--target-directory`,
  `find … -delete|-exec|-execdir|-ok`, and `awk -i inplace`.
- **R-3 Integrity of `.aiops/`.**
  - Shell writes, deletes and moves whose target is `.aiops`, an intent folder, or anything inside one are blocked in
    every state. `.aiops/README.md` and `.aiops/config.json` follow their existing rules.
  - "Initialized" means `.aiops/` exists on disk **or** is tracked in git.
  - A gate is open only if the front-matter `id` equals the folder id. The agent can't change `id` on an existing artifact.
- **R-4 Engine invocation.**
  - Unsetting or overriding `CLAUDECODE` or `CLAUDE_CODE_CHILD_SESSION` from the agent's shell is blocked. That
    covers `env -u`, `unset`, `export X=`, `X= cmd` and `env X= cmd`.
  - Human-only subcommands (`approve close unlock hook legacy-approvals`) are detected after shell unquoting.
    A dynamic command word (`$x`, `${x}`, `$(…)`, backticks) followed by one of them is blocked.
- **R-5 Always-on safety.**
  - These guards run regardless of `.aiops/`: guard-bash's safety rules, guard-deploy, guard-files' credential scan
    plus `defaults/secret-paths`, and the new read guard.
  - These stay dormant until init: the SDLC gates (engine hooks, read-only lock, approvals, schemas), guard-tests,
    post-edit-format and stop-verify.
- **R-6 Secret reads.**
  - A new PreToolUse `Read|Grep|Glob` guard blocks secret globs.
  - guard-bash also blocks `.env` reads through `awk sed cut sort rg cp mv base64 xxd od strings`. `.env.example`,
    `.env.sample` and `.env.template` stay allowed.
  - The scaffold ships `.claude/settings.json` with the template's old `permissions.deny` list.
- **R-7 Pinning.**
  - The scaffold's Claude workflows and `aiops-gates.yml` fetch the plugin at `ZOUJ_SDLC_REF`, which `sdlc init`
    sets to `v<plugin version>`, with a comment recommending a full sha. The Claude workflows load it with `--plugin-dir`.
  - The plugin repo's own `aiops-gates` job runs the **base branch's** engine on PRs.
  - `ruff` and `@anthropic-ai/claude-code` are pinned in ci.yml.
- **R-8 Smaller fixes.**
  - State 6 no longer depends on the current branch.
  - `defaults/readonly-exempt` no longer exempts CLAUDE.md, REVIEW.md, `skills/` or `agents/`.
  - SECURITY.md paths are fixed.
  - The single-file approval-commit rule gets its own test.
  - Moving an approved artifact back to Draft stays allowed, and is now documented.
- **R-9 Hygiene for 0001.** 0001's Deviation log records the bootstrap exception and the S7 deviation, and each row
  gets a commit ref. 0002 commits carry `Red:` / `Green:` evidence.
- **R-10 A human for each signature (decided after review 0002).**
  - `sdlc approve`, the prompt hook and `sdlc doctor` accept a signing key only if every signature needs the human:
    - a FIDO `sk-` key (touch), or
    - a passphrase-protected private key that is **not** loaded in the reachable `ssh-agent`.
  - Anything else is refused **before stamping**, and `doctor` fails (✗).
  - The human-owned escape hatch is `.aiops/config.json` `"approval_key_policy": "any"`. The default is `"human"`.
  - Approvals that need a passphrase are made with `bin/sdlc approve` in a terminal. The prompt phrase tells Claude to
    hand the approval to the human when signing would need a TTY.
- **R-11 Review 0002 fixes.**
  - Heredoc markers count only outside quotes and comments.
  - R-4 also covers `export -n` / `declare +x` / `typeset +x` / `env -`, wrapper functions or aliases around `sdlc`,
    a non-literal first argument to `sdlc`, `xargs sdlc`, a copied engine binary, and a split `AIOps-Approval` string.
  - The audit fails closed on an unresolvable or empty `--base`. Only a resolvable base that lacks `allowed-signers`
    bootstraps.
  - `.aiops` integrity also covers globs, `$PWD`, `$(pwd)`, `find` start paths, `tar -C` and `git apply/am`.
  - Secret-read guards unquote before matching, resolve symlinks, and exempt `.env.example` per token, not per
    command. `secret-paths` gains `*id_ed25519*`, `*id_ecdsa*`, `*/.ssh/*`, `*/.aws/credentials`, `*/.netrc`,
    `*/.npmrc` and `*/secrets/*`.
  - Legacy entries must be full shas, and `legacy-approvals --write` records only commits that pass every other audit check.
  - Force-push through a `+refspec`, `git --work-tree` and `curl -o` / `wget -O` are caught.
- Non-functional: stdlib only; no new runtime dependencies; every block message keeps "reason + Procedure"; the
  hook median stays under 150 ms per call.

## Acceptance criteria
- **AC-1**: Given states 1-3, when the agent runs `cat <<EOF > src/app.py`, `cat <<'EOF' >> src/app.py` or
  `cat <<-EOF > src/x.py` (body on later lines), then each is blocked. Heredoc *bodies* containing `>` still cause no
  false positive.
- **AC-2**: Given any state, when a heredoc redirect targets an artifact, `.aiops/state/*` or `.aiops/config*`, then
  it is blocked.
- **AC-3**: Given states 1-3, when the agent runs `git commit src/app.py -m x`, `git -C src checkout app.py`,
  `cp -t src README.md`, `find src -delete`, `find src -name x -exec rm {} +` or `awk -i inplace … src/app.py`,
  then each is blocked.
- **AC-4**: Given an initialized repo in any state, when the agent runs `rm -r .aiops`, `mv .aiops x`,
  `rm -r .aiops/0001-x`, `cp -r .aiops/0001-x .aiops/0002-y` or `rmdir .aiops/state`, then each is blocked.
- **AC-5**: Given `.aiops/` is tracked in git but missing from disk, when any SDLC gate hook runs, then the repo
  counts as initialized and the read-only lock still applies.
- **AC-6**: Given an artifact whose front-matter `id` differs from its folder, when `gate()` is evaluated, then it is
  closed. Editing `id` on an existing artifact with Edit/Write is blocked.
- **AC-7**: Given any state, when the agent runs `env -u CLAUDECODE sdlc approve 0001 plan`, `unset CLAUDECODE`,
  `CLAUDECODE= bin/sdlc approve …`, `sdl\c approve 0001 plan`, `"sdlc" approve …`, `s=sdlc; $s approve …` or
  `$(which sdlc) hook prompt`, then each is blocked.
- **AC-8**: Given `require_signed_approvals: true` (the default), when `sdlc approve` runs with no signing key
  configured, then it refuses **before** stamping, with setup instructions. With a key configured, the approval
  commit is signed.
- **AC-9**: Given an open gate, when `sdlc validate --ci [--base REF]` runs, then it fails unless the approval commit
  is signed by a key in `allowed-signers` (from `REF` when given) or is listed in `legacy-approvals`.
  - Fails: unsigned, signed by an unlisted key, or a key added to `allowed-signers` by the PR itself.
  - Passes: an allow-listed signature.
- **AC-10**: Given a repo **without** `.aiops/`, when the agent runs `git push --force`, `make deploy ENV=prod` or
  `cat .env`, or writes a credential or `.env`, then each is blocked. The SDLC gates (read-only lock, approvals,
  make check) stay inactive there.
- **AC-11**: Given any repo, when the agent uses Read/Grep/Glob on `.env`, `secrets/x`, `id.pem` or `x.key`, or runs
  `awk 1 .env`, `sed -n p .env`, `cp .env /tmp/x` or `base64 .env`, then each is blocked. `.env.example` stays
  readable.
- **AC-12**: Given `sdlc init` in a fresh repo, when it finishes, then the repo has `.claude/settings.json` with the
  deny list, `ZOUJ_SDLC_REF: v<version>` in `aiops-gates.yml` and the Claude workflows, `allowed-signers` and
  `legacy-approvals` stubs, and `require_signed_approvals: true`. Existing files are still never overwritten.
- **AC-13**: Given a reviewed PASS on main, when `sdlc status` runs on any branch, then it reports state 6 DONE.
- **AC-14**: Given states 1-3, when the agent edits `CLAUDE.md`, `REVIEW.md`, `skills/x/SKILL.md` or
  `agents/x.md`, then it is blocked. `README.md`, `CHANGELOG.md` and `docs/x.md` remain writable.
- **AC-15**: Given this repo after the change, when `sdlc validate --all --ci --base origin/main` runs, then it passes
  (0001's and 0002's pre-signing approvals are in `legacy-approvals`). `make check` passes, and plugin.json says `0.2.0`.
- **AC-16**: Given `approval_key_policy: "human"` (the default), when `sdlc approve` or `sdlc doctor` runs, then:
  - an unencrypted key, or a key loaded in the reachable ssh-agent, is refused before stamping (doctor ✗), with the
    fix (`ssh-keygen -p`, `ssh-add -d`, or an `sk-` key)
  - an encrypted key that isn't in the agent, or an `sk-` key, passes the precheck
  - `"any"` restores the old behaviour
- **AC-17**: Given states 1-3, when a heredoc marker appears only inside quotes or a comment (`echo '<<EOF'` or
  `# <<EOF` followed by `echo 1 > src/app.py` on the next line), then the write on the next line is still blocked.
- **AC-18**: Given any state, when the agent runs `export -n CLAUDECODE`, `declare +x CLAUDECODE`, `env - sdlc …`,
  `f(){ sdlc "$@"; }; f approve 0001 intent`, `alias s=sdlc`, `sdlc $(echo approve) …`, `x=approve; sdlc $x …`,
  `echo … | xargs sdlc`, `cp bin/sdlc /tmp/s`, or a commit whose message builds `AIOps-Approval` from pieces, then each
  is blocked.
- **AC-19**: Given `--base REF` where REF doesn't resolve, or `--base` with an empty value, when
  `sdlc validate --ci` runs, then it fails. An allow-listed signature verified against a base that has the signer is
  accepted (positive test).
- **AC-20**: Given an initialized repo, when the agent runs `rm -rf .ai*`, `rm -rf $PWD/.aiops`,
  `rm -rf "$(pwd)/.aiops"`, `cd .aiops && rm -rf *`, `find . -name test-lock -delete`, `tar -xf x.tar -C .aiops` or
  `git apply x.patch` (a patch touching `.aiops/`), then each is blocked.
- **AC-21**: Given any repo, when the agent runs `cp .env /tmp/x; cat .env.example`, `cat ".env"`, `cat .e?v`, or
  Reads a symlink to `.env`, `~/.ssh/id_ed25519` or `sub/secrets/x`, then each is blocked.
- **AC-22**: Given `legacy-approvals` with a short sha, when the audit runs, then the entry doesn't match. When
  `sdlc legacy-approvals --write` runs, then it skips approval commits that fail the other audit checks. And
  `git push origin +main`, `git --work-tree=src checkout app.py` (locked) and `curl -o src/x …` (locked) are blocked.

## Data model
No database. File and config contract:

| Path | Format | Owner | Notes |
|---|---|---|---|
| `.aiops/config.json` | JSON | human (CODEOWNERS guard line) | new key `require_signed_approvals` (default **true**) |
| `.aiops/config/allowed-signers` | git `allowed_signers` (`<principal> namespaces="git" ssh-ed25519 AAAA…`) | human | read from `--base REF` in CI |
| `.aiops/config/legacy-approvals` | one commit sha per line, `#` comments | human | written by `sdlc legacy-approvals` |
| `defaults/secret-paths` | `<glob> <reason>` | plugin | split out of `protected-paths`; always on |
| `templates/scaffold/.claude/settings.json` | Claude settings | human | the old deny list |

## API contracts
- `sdlc validate [--all] [--ci] [--base REF]`: with `--base`, `allowed-signers`, `legacy-approvals` and
  `config.json` are read from `git show REF:…`.
- `sdlc approve <id> <kind>` (human only): checks the signing setup first, then stamps, then signs and commits. Exit 1
  with instructions if the setup is missing.
- `sdlc legacy-approvals [--write]` (human only): lists the unsigned approval commits of currently open gates.
  `--write` appends them to `.aiops/config/legacy-approvals`.
- `sdlc doctor`: adds signing checks (`user.signingkey`, `gpg.format=ssh`, key present in `allowed-signers`, and
  under `approval_key_policy: "human"` a key that needs the human for each signature).
- `.aiops/config.json` `approval_key_policy`: `"human"` (default) | `"any"`.
- `sdlc validate --ci --base REF` exits 1 when REF doesn't resolve or is empty.
- New hook `hooks/guard-read.sh` on `PreToolUse` `Read|Grep|Glob` (`file_path`, `path`, `pattern`). Exit 2 blocks.
- Unchanged: hook JSON in and out, and exit codes (0 allow, 2 block). Every block message keeps `Procedure:`.

## Security & data-leak flags
- ⚠️ **Signing-key access.** An agent running as the user can sign with an unprotected key. Mitigations: a passphrase
  or `ssh-add -c` confirmation (recommended in the docs and checked by `sdlc doctor`, see the open question), plus
  CODEOWNERS on `.aiops/config/allowed-signers`. (zoujagger)
- ⚠️ **Self-trust.** A PR must not be able to add its own signer. CI reads `allowed-signers` and `legacy-approvals`
  from the base ref (AC-9). (zoujagger)
- ⚠️ **Legacy list as a loophole.** `legacy-approvals` must stay append-only and human-owned: a protected path plus
  CODEOWNERS, and CI reads it from the base ref.
- ⚠️ **Secret reads** across Read, Grep and Glob, and shell readers (AC-11). The deny list goes back into the scaffold.
- ⚠️ **Supply chain.** The plugin is pinned in privileged CI jobs (R-7). A mutable tag is a residual risk, and the
  docs recommend a full sha.
- Residual, documented: interpreter writes (`python -c`) are not parsed. Signing makes them unable to open gates.

## Architecture
- `guards.py`:
  - a new `strip_heredocs()` that works line by line
  - write-target detection extended for `git -C`, `git commit` pathspecs, `cp/mv -t`, `find` actions and `awk -i inplace`
  - `.aiops` integrity check: `_is_aiops_protected(rel)`
  - env-var and dynamic-command checks on the unquoted tokens
- `machine.py`:
  - `initialized()` also checks `git ls-files .aiops`
  - `gate()` checks the id
  - state 6 no longer depends on the branch
  - `require_signed_approvals` defaults to True
- `approvals.py`: a signing precheck, `git commit -S`, an `audit(base=…)` that checks the signer through
  `gpg.ssh.allowedSignersFile` (a temporary file from the base ref), and the legacy list.
- `cli.py`: `--base`, the `legacy-approvals` command, and doctor signing checks.
- Hooks:
  - `engine.sh` keeps dormancy for the engine hooks only
  - guard-bash, guard-deploy and guard-files lose their `aiops_enabled` early exit for safety rules
  - new `guard-read.sh`
- Alternative considered: GitHub CODEOWNER-review mode. It's GitHub-only, needs a token, and a sole maintainer can't
  approve their own PR, so it was rejected (intent).

## Rollout & rollback
- **Release:** v0.2.0. Consumers then:
  1. set up SSH signing (`git config gpg.format ssh; git config user.signingkey ~/.ssh/id_ed25519.pub`)
  2. add their key to `.aiops/config/allowed-signers`
  3. run `sdlc legacy-approvals --write` once
  4. re-run `sdlc init` for the new scaffold files (it doesn't overwrite)
- **This repo:** the same steps (AC-15).
- **Rollback:** revert the merge, or pin consumers to `v0.1.0`. Setting `require_signed_approvals: false` in
  config.json is the documented emergency switch, and it's human-owned.

## Open questions
- [x] Should a protected key be *required* or only recommended? → **Required: a human for each signature** (a passphrase key not in ssh-agent, or an `sk-` key); approvals move to the terminal (zoujagger, 2026-11-02, after review 0002)
- [ ] Should the tech lead approve `risk: high` specs a second time? Carried over from 0001 (zoujagger)
