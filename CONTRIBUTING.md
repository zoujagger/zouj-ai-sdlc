# Contributing to zouj-ai-sdlc

This repo dogfoods the plugin. Load it with `make dev` (`claude --plugin-dir .`) and follow the five states:

1. **Intent.** `/zouj-ai-sdlc:intent "<need>"` → `.aiops/NNNN-slug/intent.md`. A maintainer types `Intent Approved NNNN`.
2. **Spec.** `/zouj-ai-sdlc:spec`: requirements, ACs, contracts (CLI flags, hook JSON, schemas) and security flags → `Spec Approved NNNN`.
3. **Plan.** `/zouj-ai-sdlc:plan`, read-only → `Plan Approved NNNN`.
4. **Execute.** `/zouj-ai-sdlc:implement`. Guard and engine changes are test-first in `tests/`. `make check` must be green.
5. **Review.** `/zouj-ai-sdlc:review` → `review.md` + `pr.md`, then `/zouj-ai-sdlc:pr`. A CODEOWNER merges.

Exempt from the flow: typos and docs-only changes (`*.md`, `docs/`).

## Checks
- `make check`: bash syntax, shellcheck and ruff (if installed), JSON validity, byte-compile, and the unit and hook tests.
- `make validate`: `claude plugin validate .`.
- `make evals`: behavioural evals (`claude plugin eval`). Run them when you change skills, agents, hooks or schemas.
- `python3 scripts/scaffold-history.py [--check]`: regenerates (or checks) `defaults/scaffold-history.json`, the hash
  of every scaffold file in every release, which `sdlc upgrade`/`repair` use to adopt older repos. Run it when you
  change `templates/scaffold/` or `templates/stacks/`, and at each release.

## Using AI responsibly
You're accountable for every line you merge. Never bypass a hook: it says why it blocked you and what to do.

## Commit style
[Conventional Commits](https://www.conventionalcommits.org/), with footer `Refs: .aiops/NNNN-slug`.

## Licensing of contributions
- **Your contribution is licensed under AGPL-3.0-or-later.** By submitting a contribution (a pull request, patch or
  other material intended for inclusion), you license it under the GNU Affero General Public License v3.0 or later,
  the project's license (see [LICENSE](LICENSE)). Only submit work you have the right to license that way: if your
  employer may own it, get their permission first. Mark any third-party material and name its source and license.
- **You keep your copyright.** Contributing doesn't transfer ownership of your work to the maintainer or anyone
  else. A transfer would only happen through a separate written assignment that you sign.
- **A commercial edition needs your separate agreement.** The project may later also be offered under commercial
  (proprietary) terms. The AGPL alone doesn't allow the maintainer to include your contribution in a differently
  licensed edition: before doing so, the maintainer must obtain additional rights from you, in writing (for
  example a contributor license agreement). Without them, your contribution stays in the AGPL edition only.
- **Contributor License Agreement: planned, not in force.** A draft Individual CLA (a license, not an assignment;
  you keep your copyright) is in [`docs/legal/CLA.md`](docs/legal/CLA.md), with the reasoning in
  [`docs/legal/contribution-licensing.md`](docs/legal/contribution-licensing.md). It is under legal review and
  **must not be signed yet**. If it is adopted, it will be announced here and in the CHANGELOG, and it will apply
  only to contributions made after you accept it: you'd accept it once, by a comment on your first pull request,
  before that contribution is merged. It will never apply to earlier contributions without your explicit written
  consent.
