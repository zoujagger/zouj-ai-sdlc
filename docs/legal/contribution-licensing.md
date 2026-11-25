# Contribution licensing: options and recommendation

> **Status: working notes for the maintainer and their lawyer, not legal advice.** Nothing here has been reviewed by
> a lawyer. Before any contributor agreement is adopted, it must be reviewed by a qualified intellectual property
> lawyer practising in France.

The project is distributed under **AGPL-3.0-or-later** (from 0.2.0). The maintainer wants to keep the option of a
**dual-licensing model** later: the community edition under AGPL-3.0-or-later, and a commercial edition under
proprietary terms. This note explains what that needs from contributors, compares the usual mechanisms, and
recommends one.

## Where the project stands today (2026-11-25)
- **Contribution policy:** `CONTRIBUTING.md` described the workflow (the five states, checks, commit style) but said
  nothing about the license of contributions, copyright, or any agreement.
- **Contributors so far:** every human-authored commit and pull request is the maintainer's (git authors
  `zoujagger` / `Ulrich Jagger`). The only other PRs are five Dependabot bumps of GitHub Actions version pins in
  `.github/workflows/`. Many commits carry a `Co-Authored-By: Claude …` trailer for AI-assisted work.
- **So there are no third-party contributions to clear today**, and no retroactive question arises. Two points
  for the lawyer: whether the Dependabot version bumps need any treatment (they are mechanical pin changes), and
  how AI-assisted code affects the maintainer's ability to license the codebase commercially (who owns what, and
  whether any part is unprotected).

## What the AGPL gives, and what it doesn't
- **The AGPL grants every recipient**, the maintainer included, permission to use, modify and distribute the
  covered code **under the AGPL's conditions** (source availability, including to network users of a modified
  version; the same license for derivative works).
- **It does not give the maintainer exclusive commercial rights.** Anyone may sell or run the AGPL edition
  commercially, as long as they follow the AGPL. Being the maintainer adds nothing to that.
- **What lets the maintainer offer proprietary terms is ownership.** The maintainer can license **their own** code
  under any terms they choose, in addition to the AGPL. For code written by someone else, the maintainer holds only
  the AGPL permission, and the AGPL doesn't allow redistributing that code under proprietary terms.
- **So a commercial edition that includes a contributor's code needs additional rights from that contributor:** a
  license broad enough to cover proprietary relicensing, or an assignment. These are separate from, and in addition
  to, the AGPL.

## The mechanisms
| | DCO | ICLA | CCLA |
|---|---|---|---|
| **What it is** | A short certification (developercertificate.org) a contributor makes by adding `Signed-off-by:` to each commit | A contract between an individual contributor and the maintainer | The same, signed by a company for contributions its employees make |
| **What it proves** | Provenance: the contributor has the right to submit the code under the project's license | Provenance, plus the rights the agreement grants | Provenance and rights for work the employer owns |
| **Rights it grants the maintainer** | None beyond the project's license (here, the AGPL) | Whatever it states: typically a broad copyright and patent license, **including the right to sublicense and relicense under other terms** | Same as the ICLA, from the rights holder (the employer) |
| **Enough for a proprietary edition?** | **No.** A DCO doesn't grant relicensing rights | **Yes, if it says so explicitly** | Yes, for employer-owned work, if it says so |
| **Contributor keeps copyright?** | Yes | Yes, for a license-style CLA; no, for an assignment-style one | Yes (the company), for a license-style CLA |
| **Friction** | Low: one flag (`git commit -s`) | Medium: one acceptance before the first contribution | Higher: a company signatory |
| **Perception** | Friendly | Accepted, but some contributors refuse CLAs that permit proprietary relicensing | Expected by companies |

### Why employer ownership matters (the CCLA)
In many jurisdictions, including France for most software written by an employee in the course of their duties,
the employer, not the employee, holds the economic rights to software an employee writes as part of their job. An
individual's ICLA can't grant rights the individual doesn't hold. A CCLA (or the employer's written permission) is
the standard way to cover that case. For a solo-maintained project with no corporate contributors today, a CCLA can
wait until the first company wants to contribute; the ICLA should require contributors to say when an employer may
own their work.

### Points the French lawyer should check
These are questions, not conclusions:
- **Formal requirements for transfers of rights** (Code de la propriété intellectuelle, notably article L131-3):
  whether a license-style CLA must list each right granted, its scope, purpose, territory and duration to be
  enforceable against a French contributor, and how the draft should be worded to meet them.
- **Moral rights** (droit moral), which under French law the author keeps and can't give away: how the draft should
  treat them (it shouldn't purport to transfer them).
- **Click-through or comment acceptance**: whether accepting by a pull-request comment from an authenticated GitHub
  account is enough evidence, or whether a signature in another form is needed.
- **Governing law and jurisdiction**, and the language of the agreement (French and/or English).
- **Patent license** scope, and the employer case (software written by employees).
- **AI-assisted contributions**: what the contributor should represent about them.

## Recommendation
For a solo maintainer who wants to keep a future commercial edition open:

1. **Adopt an Individual CLA that is a license, not an assignment.** Contributors keep their copyright and grant the
   maintainer a broad, perpetual, irrevocable license, including the right to sublicense and to distribute their
   contributions under other license terms, including proprietary ones. This is what makes dual licensing possible,
   and it is less demanding for contributors than an assignment (and avoids the heavier formalities of a transfer of
   ownership). Pair it with a **promise that the contribution will stay available under AGPL-3.0-or-later** (or
   another OSI-approved license), which addresses the usual objection to CLAs.
2. **Don't rely on a DCO for this.** A DCO sign-off is still worth keeping as a lightweight provenance record, but it
   grants nothing beyond the AGPL. It can complement the CLA, not replace it.
3. **Add a CCLA when the first contributor writes for an employer**, modelled on the ICLA.
4. **Until the CLA is adopted, accept outside contributions only under AGPL-3.0-or-later**, and don't put them in a
   commercial edition without obtaining the additional rights separately, in writing. `CONTRIBUTING.md` says so.
5. **Never apply the CLA retroactively.** Contributions made before it takes effect are covered by it only if their
   author agrees explicitly, in writing.

The draft ICLA is [`CLA.md`](CLA.md). It moves to the repository root only once the lawyer has reviewed it and
the maintainer adopts it.

## How contributors would accept the CLA (after adoption)
Proposed, deliberately without new automation:

1. **Before the first accepted contribution**, the contributor posts this comment on their pull request, from their
   own GitHub account:
   > I have read the zouj-ai-sdlc Individual Contributor License Agreement, version 1.0 (CLA.md at commit `<sha>`),
   > and I agree to it for my present and future contributions. Name: `<full legal name>` · Email: `<email>` ·
   > Country: `<country>` · My employer has no rights in my contributions / My employer's CCLA covers them.
2. **The maintainer records the acceptance** in `.github/cla-signatures.md` (GitHub login, name, CLA version, PR
   link, date) in the same pull request or a follow-up, and doesn't merge until it's recorded.
3. **The pull request template** gains one checkbox: "I have accepted the CLA (first contribution: see
   CONTRIBUTING.md)". The maintainer checks the signature list before merging.
4. **A new CLA version** needs a new acceptance for later contributions; earlier ones stay under the version that
   applied when they were made.

**Why no bot for now:** with one maintainer and no outside contributors yet, a manual check costs a minute per new
contributor. A CLA bot (for example CLA Assistant) adds a third-party service with write access to pull requests,
stores signatures outside the repository, and needs a workflow change under `.github/` (a protected path). Worth
revisiting if outside contributions become frequent.

Steps 2 and 3 change `.github/`, which is protected in this repo and goes through the five-state flow (an intent),
so they are made at adoption time, not in this draft.
