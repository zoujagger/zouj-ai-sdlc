---
id: 0019
title: Framework positioning and release 0.2.1
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-25
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-25T11:53:20Z
approved-via: cli
approved-sha256: 78350d2436cfe0f7ad79a9f3a3a57bb89f8d4638ad2720af8fca8e5cb7ef722b
---

# Spec: Framework positioning and release 0.2.1

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md. Release requirements modeled on 0018. The
     intent's one question (the date) was accepted with its approval as proposed: the day the PR opens, corrected
     before the merge if it lands later. -->

## Summary
The README now presents zouj-ai-sdlc as an AI-native software engineering framework, currently implemented as a
Claude Code plugin. This change states that identity in the other places that describe the project (the plugin and
marketplace manifests, `CLAUDE.md`), gives the README's engineering practices a reference section in `docs/sdlc.md`,
and releases it all, with the copyright and contribution-licensing docs already on main, as **0.2.1**. After the
merge, the merge commit is tagged `v0.2.1`, published as the latest GitHub release, and the repository description
is updated. Wording and version only (intent: Desired outcome, Constraints).

## Requirements
- **R-1: the manifest description.** `.claude-plugin/plugin.json` `description` becomes:
  "AI-native software engineering framework, implemented as a Claude Code plugin: a deterministic 5-state machine
  (intent → spec → read-only plan → TDD → review) over Git-versioned Markdown artifacts, with human approval gates
  and hook-enforced guardrails. Modeled on Anthropic's AI-Native SDLC Playbook."
- **R-2: the marketplace description.** `.claude-plugin/marketplace.json`'s plugin entry `description` becomes:
  "AI-native software engineering framework: a Git-backed SDLC state machine with human approval gates (intent →
  spec → plan → implement → review)." Its `metadata.description` ("zoujagger's Claude Code plugins") is unchanged.
- **R-3: `CLAUDE.md`.** The opening sentence becomes "This repo is **zouj-ai-sdlc**, an AI-native software
  engineering framework implemented as a Claude Code plugin, and it dogfoods itself: …"; the rest of the file is
  unchanged.
- **R-4: the practices section.** `docs/sdlc.md` gains `## Engineering practices` after `## Principles kept from the
  playbook`. It lists, each with the mechanism that implements it and its limit where there is one:
  - **Specification-driven development:** intent → spec (ACs) → plan before code; code read-only in states 1-3;
    plan and review cover every spec AC (`covers_spec_acs`).
  - **TDD workflows:** one plan step per implementer subagent: proof test, see it fail, minimal code, refactor while
    green; guard and engine changes test-first; `/zouj-ai-sdlc:fix` locks the approved failing test.
  - **Small planned steps:** file-by-file `## Steps` in `plan.md`; changing the Steps re-closes the plan gate; scope
    sizing keeps specs to 3-5 ACs.
  - **Continuous validation:** the post-edit hook validates artifacts against `schemas/`; the Stop hook requires
    `make check` green; CI (`aiops-gates`) audits every open gate.
  - **Fresh-context review:** `/zouj-ai-sdlc:review` runs the verifier, code-reviewer and security-reviewer in fresh
    contexts, given only the intent folder and the base branch. Nothing checks how a `review.md` was produced, so
    the human reviewing the PR still decides.
  - **A human at every gate:** only a human opens a gate (the typed phrase or `sdlc approve`) and merges.
  - **Limits:** local hooks are a deterrent, not a sandbox ([what is enforced](enforcement.md)); the practices
    borrow from XP (test-first, refactoring, small steps) without claiming all of it.
- **R-5: the README link.** The README's "Engineering practices" bullet links to
  `docs/sdlc.md#engineering-practices`. The README intro and list written before this intent (zoujagger's wording)
  are otherwise kept.
- **R-6: the release.**
  - `plugin.json` `version` `0.2.1`.
  - CHANGELOG: `## [0.2.1] - 2026-11-25` above `## [0.2.0]`, no banner, a lead line naming
    `.aiops/0019-framework-positioning-0-2-1/` and saying the gates, guards and what CI audits are unchanged;
    `### Changed`: the positioning (README intro, manifest and marketplace descriptions, `CLAUDE.md`, the new
    practices section); `### Added`: the two entries under `[Unreleased]` today (copyright notice, licensing of
    contributions), moved unchanged. `[Unreleased]` empty; links `[Unreleased]: …/compare/v0.2.1...HEAD` and
    `[0.2.1]: …/compare/v0.2.0...v0.2.1`.
  - The README status line `**Status: 0.2.1.**` and the four pins (`@v0.2.1` twice, `checkout v0.2.1`, the settings
    `"ref"`); the License section's "From 0.2.0" is history and stays.
  - `defaults/scaffold-history.json` gains `0.2.1`, equal to `0.2.0`'s entry (no scaffold file changes).
  - Date: the day the PR opens, corrected before the merge if it lands later (a logged deviation).
- **R-7: the tests.**
  - `test_version_matches_changelog` and `test_changelog_has_the_release` expect `0.2.1`; the newest section names
    `AI-native software engineering framework`, `Copyright` and `CLA`; the 0.2.0 checks (`AGPL-3.0-or-later`, `MIT`,
    `Quick start`) move to an explicit `## [0.2.0]` slice; the other checks are kept.
  - A new `Docs` test pins the positioning: both manifest descriptions contain `AI-native software engineering
    framework` and neither `orchestration`, `guarantee` nor `sandbox`; `CLAUDE.md` names the framework and the Claude
    Code plugin; `docs/sdlc.md` has `## Engineering practices` naming the six practices; the README links
    `docs/sdlc.md#engineering-practices`.
- **R-8: nothing else changes:** plugin id, command prefix, skill names, hook ids, schemas, behaviour, license and
  copyright notices.
- **R-9: after the merge** (at zoujagger's request): an unsigned annotated tag `v0.2.1` (`zouj-ai-sdlc 0.2.1`) on
  the merge commit, pushed; a GitHub release `0.2.1`, not a pre-release, marked latest, notes = the CHANGELOG
  section; then the repository description set to "AI-native software engineering framework, implemented as a
  Claude Code plugin: a Git-backed state machine over Markdown artifacts, with human approval gates and
  hook-enforced guardrails."
- **Non-functional:** `make check`, `claude plugin validate .` and `scripts/scaffold-history.py --check` pass.

## Acceptance criteria
- **AC-1**: Given the manifests, then `plugin.json` and the marketplace plugin entry describe an AI-native software
  engineering framework (R-1, R-2), with no `orchestration`, `guarantee` or `sandbox`, and `CLAUDE.md` opens with
  R-3's sentence.
- **AC-2**: Given `docs/sdlc.md`, then `## Engineering practices` lists the six practices of R-4 with their
  mechanisms and the limits, and the README's practices bullet links to it.
- **AC-3**: Given the release, then `plugin.json` `version` is `0.2.1`, the newest CHANGELOG release is
  `[0.2.1] - <date>` with the compare link from `v0.2.0`, holding the positioning change and the two moved entries,
  and `[Unreleased]` is empty.
- **AC-4**: Given the README, then the status line and every pin name `0.2.1`, and no pre-release version appears
  above `## Lifecycle`.
- **AC-5**: Given the change, then `defaults/scaffold-history.json` has a `0.2.1` entry equal to `0.2.0`'s with the
  released entries unchanged; only R-1 to R-7's files and `.aiops/0019-*` changed; `make check`,
  `claude plugin validate .` and `scaffold-history.py --check` pass.

## Data model
None (no changes)

## API contracts
None (no changes)

## Security & data-leak flags
- ⚠️ **Overclaiming:** positioning text could suggest guarantees the hooks don't give. Mitigation: R-4's Limits
  bullet, the README's "deterrent, not a sandbox", and AC-1's test that bans `guarantee`/`sandbox` from the
  manifest descriptions. (zoujagger)
- ⚠️ **`CLAUDE.md` is agent instruction:** only its opening sentence changes, so no rule moves. (zoujagger)
- ⚠️ **Pins to a tag that doesn't exist until after the merge:** installs fail closed until R-9. (zoujagger)
- No secret, approval, lock or audit path changes (R-8).

## Architecture
- **Where identity is stated:** the README (done), `plugin.json` `description` (plugin listings and
  `claude plugin validate`), `marketplace.json` (the marketplace view), `CLAUDE.md` (agent context), the GitHub
  repository description (a setting, outside the tree). Category B/C mentions (installation, runtime, identifiers)
  stay, as reviewed with zoujagger on 2026-11-25.
- **Release mechanics** as in 0018: `cli.plugin_version()` reads `plugin.json` for the scaffold's CI ref, and
  `lifecycle.history_key()` finds the running version in the scaffold history.
- **Not taken:** renaming the plugin id or command prefix (intent: Out of scope).

## Rollout & rollback
- **Rollout:** one PR; after the human merges it, R-9. R-9 has no AC: it can only hold after the merge. Its check:
  `git rev-parse v0.2.1^{commit}` equals the merge commit, `gh release view v0.2.1` is a non-pre-release marked
  latest, and `gh repo view --json description` shows R-9's text.
- **Upgrades:** repos on 0.2.0 move with `sdlc upgrade`; only the pinned ref changes.
- **Rollback:** revert the PR; delete the tag and release; restore the previous repository description.

## Open questions
None. The intent's question (the date) was accepted with its approval.
