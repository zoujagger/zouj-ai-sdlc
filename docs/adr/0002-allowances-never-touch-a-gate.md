# ADR 0002: Allowances never touch a gate

- Status: Accepted
- Date: 2026-11-06
- Deciders: zoujagger (intent 0004 spec gate; PR 1 review)

## Context
The guards match command text, so they sometimes block safe commands. For example, `ls env` trips the env-dump rule.
Users had two choices: rephrase the command, or weaken the guards. ECC offers per-hook disable switches
(`ECC_DISABLED_HOOKS`). Here, though, the hooks *are* the playbook's gates (`docs/roadmap.md`, Non-negotiable), so a
switch that turns a rule off would also turn off a gate.

## Decision
- Every rule has a stable id and a class in `defaults/rules`: `gate`, `secret`, `toolchain`, `safety` or
  `heuristic`.
- Only `heuristic` rules accept an allowance: `G-ENV-03` (env/printenv) and `G-BASH-07` (sudo, mkfs, dd if=,
  chmod -R 777). For `G-ENV-03`, a command that prints the whole environment (`env`, `printenv` with no variable)
  is never allowed: it would put every token in the session (PR 2 security review).
- An allowance is one line in the human-owned `.aiops/config/allowed-commands`: `<rule id> <exact command>`. It lifts
  that rule for that byte-equal, single-line command, and every other rule still runs on it.
- Gate, secret, toolchain and safety rules call `block` directly; the allowance code is unreachable from them.
  `sdlc doctor` and `sdlc validate --ci` (head and base) reject entries for them.
- There is no per-rule disable switch, no pattern allowance and no environment variable.

The PR 1 review moved `G-BASH-01` (nested shells), `G-BASH-02` (`rm -rf .`) and `G-BASH-06` (`curl | sh`) from
heuristic to safety. Each one stands in front of every other check, so allowing it would lift them all. The
credential-echo branch of the env rule became `G-ENV-04` (secret).

## Consequences
- A false positive on a gate rule is fixed in the guard, by a new intent, never in configuration.
- An allowed `sudo` command can still write root-owned PATH directories that approvals run. `sdlc why G-BASH-07`
  warns about this.
- Adding a rule means adding a registry line, a `rules.md` section and a test that emits its id
  (`tests/test_rules.py::Coverage`).
