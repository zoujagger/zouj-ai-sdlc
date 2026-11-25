---
id: 0019
title: Framework positioning and release 0.2.1
status: Approved
owner: zoujagger
initiator: zoujagger
source: request to reposition the project as an AI-native software engineering framework, apply the follow-up suggestions, then release a patch version, 2026-11-25
created: 2026-11-25
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-25T11:51:33Z
approved-via: cli
approved-sha256: fe01b086328a580af4afed0eb3b36c67bac39cb2e2ef76e8b6afd1f8b57ed24f
---

# Intent: Framework positioning and release 0.2.1

<!-- State 1 BRAINSTORMING. The README intro was rewritten first (docs only, zoujagger's wording, 2026-11-25); this
     intent carries the follow-ups that touch configuration or agent instructions, and the patch release. Scope
     check: one workflow (positioning) plus a version bump, 4 outcomes. Unknowns go in Open questions, never
     invented. approved-* fields are stamped by the human approval; agents never write them. -->

## Problem
The README now presents zouj-ai-sdlc as an **AI-native software engineering framework, currently implemented as a
Claude Code plugin**. The other places that state the project's identity still describe it the old way:

- `.claude-plugin/plugin.json` `description` ("Agentic SDLC orchestration modeled on …"), shown in plugin listings;
- `.claude-plugin/marketplace.json`'s plugin `description` ("AI-native SDLC state machine with human-only gates …");
- `CLAUDE.md` ("This repo is the zouj-ai-sdlc Claude Code plugin"), the agents' own description of the repo;
- the GitHub repository description ("An agentic workflow orchestration plugin …").

The README's list of engineering practices (SDD, test-first steps, continuous validation, fresh-context review, a
human at every gate) has no reference page: `docs/sdlc.md` maps the playbook but doesn't list them in one place.

The README positioning, the copyright section (PR #38) and the contribution-licensing policy (PR #39) are on main or
in this branch but in no release since `v0.2.0`.

## Desired outcome
- **One identity everywhere it is stated:** the manifest and marketplace descriptions and `CLAUDE.md` describe an
  AI-native software engineering framework implemented as a Claude Code plugin, without claiming support for any
  other environment, guaranteed agent behaviour, or sandbox-level enforcement.
- **The practices have a source:** `docs/sdlc.md` lists the engineering practices the README names, each tied to the
  mechanism that implements it, and the README links there.
- **A 0.2.1 release** whose tree describes itself (`plugin.json`, CHANGELOG, README pins, release tests, scaffold
  history), tagged and published as the latest GitHub release after the merge, at the human's request.
- **The GitHub repository description** matches, set after the release.

## Users & systems affected
- **Users:** people finding the project on GitHub or in a plugin listing; installers and repos pinned to a tag
  (`sdlc upgrade` moves them from 0.2.0).
- **Systems:** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CLAUDE.md`, `docs/sdlc.md`,
  `README.md`, `CHANGELOG.md`, `defaults/scaffold-history.json`, the release tests; the GitHub repository settings.

## Constraints
- **Wording and version only:** no change to the plugin id, command prefixes, skill names, hook ids, schemas,
  runtime behaviour, architecture, license or copyright notices.
- **Accurate claims:** Claude Code is the only supported environment; hooks are a deterrent, not a sandbox; not
  every review is necessarily by an independent agent; no claim of full XP.
- **Patch version** (0.2.1): nothing changes for existing installs beyond the pinned ref.
- **Tag, release and repository description after the merge only**, at zoujagger's request (2026-11-25).
- **Approval commits are never rebased:** merge main, don't rebase.

## Out of scope
- Renaming the project, the plugin id or the command prefix for other runtimes (a later architectural decision).
- Adopting the CLA (pending legal review).
- Intent 0006 and earlier review backlogs.

## Open questions
- [ ] **The release date:** the day the PR opens (2026-11-25), corrected before the merge if it lands later. (zoujagger)
