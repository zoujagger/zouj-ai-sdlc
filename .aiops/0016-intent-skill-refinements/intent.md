---
id: 0016
title: Intent skill: PRD source, domain vocabulary, clean branch start
status: Approved
owner: zoujagger
initiator: zoujagger
source: request to refine State 1's Gather, Locate and Create steps (2026-11-21)
created: 2026-11-21
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-21T11:38:05Z
approved-via: cli
approved-sha256: e044f599a2712afd267d5651b56e1d65d79fc69c8f758822ccf5ab3f22115747
---

# Intent: Intent skill: PRD source, domain vocabulary, clean branch start

<!-- State 1 BRAINSTORMING. Written from zoujagger's request on 2026-11-21, which named exactly three outcomes.
     The scope check passed: 3 outcomes, one workflow (how State 1 starts an intent). No interview round was
     needed; the two open questions were answered by zoujagger before approval. Unknowns go in Open
     questions, never invented. approved-* fields are stamped by
     the human approval; agents never write them. -->

## Problem
`skills/intent/SKILL.md` starts every intent from the prompt alone, so three things go wrong today:

- **Settled questions are asked again.** When a team already wrote a PRD or ticket for the need, Step 2 doesn't
  look for it, and the Step 3 interview asks the human what the document already answers.
- **The intent's vocabulary drifts from the domain model.** In repos where the `dsl` part is active
  (`domain/*.dsl.json`, intent 0012), Step 1 never looks at the model, so the intent can name an entity
  differently from the model the spec must later follow.
- **The branch can start from the wrong place.** Step 4 runs `git switch -c feat/NNNN-<slug>` from whatever is
  checked out: a stale `main`, another intent's branch, or a tree with uncommitted changes. Those changes then
  land in the diff, and a review written later can go stale (review stale = files outside `.aiops/` changed
  after `commit:`).

## Desired outcome
- **PRD or ticket as the source of truth (Step 2).** When `docs/prd/` holds a PRD or ticket file matching the need,
  or `$ARGUMENTS` names `prd:<slug>` or a local ticket path, the agent reads that file first, treats it as the
  source of truth, and in Step 3 asks only what the file leaves unsettled.
- **Domain vocabulary (Step 1).** When `domain/*.dsl.json` files exist, the agent quickly scans their filenames and
  entity/model names, so the intent uses the existing domain model's terms.
- **Clean branch start (Step 4).** Before `git switch -c feat/NNNN-<slug>`, the agent checks that the branch will
  start from an up-to-date `main` (unless the human explicitly asks to chain intents), and warns when uncommitted
  changes exist that could make the future review stale.

## Users & systems affected
- Users: the human who starts an intent (fewer repeated questions, a clean branch); the agent in State 1; the
  product-analyst, which writes intent.md from the gathered source.
- Systems: `skills/intent/SKILL.md` (Steps 1, 2 and 4), and `tests/` where they check the skill's text.

## Constraints
- **Guidance only:** no engine, hook or schema change; `sdlc new` and the gates behave as today.
- **Read-only state:** the new steps only read files and git state; nothing in them writes code in State 1.
- **Optional inputs:** a repo without `docs/prd/` or `domain/` behaves exactly as today, and neither is added to
  the scaffold.
- **Warn, don't block:** the uncommitted-changes check warns and lets the human decide; the agent never stashes,
  resets or discards changes on its own.
- **A PRD doesn't lift the gates:** it is input to intent.md, never an approval, and its unknowns still go to
  Open questions.

## Out of scope
- Scaffolding `docs/prd/` or a PRD template.
- Parsing or validating PRDs, or fetching tickets from remote trackers (`#N` via `gh` stays as is).
- Changing the DSL part or its checks (0012, 0013).
- Any other step of the intent skill, and the other states' skills.

## Open questions
- [x] **How is a PRD "matching"?** The file named by `prd:<slug>`, an explicit local path in `docs/prd/`, or a
  file in `docs/prd/` whose name matches the slug or the issue number. When several match, the agent asks the
  human which one. (zoujagger, 2026-11-21)
- [x] **What does "up-to-date main" mean?** Checked against `origin/main` when a remote is available; offline or
  with no remote, the agent warns and continues. When local `main` is behind, the agent warns and asks the human
  before fast-forwarding; it never switches branches or pulls on its own. (zoujagger, 2026-11-21)
