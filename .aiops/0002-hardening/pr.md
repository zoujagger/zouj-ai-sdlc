<!-- PR description for intent 0002, generated in state 5. `gh pr create --body-file` it. -->
## Hardening release: zouj-ai-sdlc 0.2.0-alpha.1 (experimental)

**Intent:** `.aiops/0002-hardening/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 90/100, at `49487b2a987336d9fed0d3b5194123372854f6eb` (lint-only change after the reviews)

### What and why
This closes every finding from 0001's review and from review rounds 2-7 of this intent, and ships it as an
**alpha**, because the plugin is still experimental:
1. **Signed, allow-listed approval commits are the real gate.**
   - CI checks them against the target branch's signer list and fails closed.
   - The approval commit is built with git plumbing, by absolute git, ssh-keygen and python. No hook, fsmonitor or
     filter runs inside it.
   - Repo-local git config is limited to an allow-list.
2. **The shell guard parses much more:**
   - heredocs (including in arithmetic and `$'…'`)
   - braces, variables, patches, archives and `find`
   - disguised and wrapped engine calls
   - env-marker tampering
3. **Safety guards run in every repo:**
   - secret reads, in one Python pass covering globs, `$(…)`, `cd` and uploads
   - credential printers
   - force-push and production deploys
   - edits to the installed plugin and to the user's toolchain (global git config, shell startup files, PATH
     directories)
4. **The scaffold's CI pins the plugin.** Setup hints use `git config --global` and a dedicated signing key, and the
   approve command is `/usr/bin/python3 -I <plugin>/bin/sdlc approve …`.

### Acceptance criteria
- [x] AC-1 … AC-29: all met. The tests are cited per AC in [review.md](review.md); `make check` runs 115 tests.
- [x] AC-15: met as `0.2.0-alpha.1` instead of `v0.2.0`, by the human's decision (Deviation log).

### Deviations from plan
23 rows in the plan's Deviation log. The main ones:
- **Review fixes:** rounds 3-7 were fixed in state 5 as review-fix commits, without new plan steps, by human
  decision.
- **Engine changes:**
  - The approval commit moved to plumbing.
  - New modules `lib/sdlc_engine/shell.py` and `secret_scan.py`, and `defaults/toolchain-paths`.
  - R-12's ancestor rule covers one level, and for Grep/Glob only outside the repo.
- **This repo keeps `"approval_key_policy": "any"`** for the alpha (human decision). Parser bypasses can forge an
  approval here, but not under the default `"human"` policy.
- **Released as `0.2.0-alpha.1`.**

### Risks and rollback
- **Known issues:** listed in CHANGELOG, planned for 0.2.0-alpha.2. They are parser residuals, a few credential
  printers, and toolchain shell writes in uninitialized repos.
- **Behaviour may change between alphas:** consumers should pin `ZOUJ_SDLC_REF` to a full sha.
- **Bootstrap:** `origin/main` has no `allowed-signers` yet, so CI trusts this PR's list. It needs CODEOWNERS review
  of `.aiops/config/`.
- **Rollback:** revert the merge, or pin consumers to `v0.1.0`. `require_signed_approvals: false` is the
  human-owned emergency switch.

### After merge (human)
```bash
git checkout main && git pull
git tag -a v0.2.0-alpha.1 -m "zouj-ai-sdlc 0.2.0-alpha.1 (experimental)"
git push origin v0.2.0-alpha.1
gh release create v0.2.0-alpha.1 --prerelease --title "0.2.0-alpha.1 (experimental)" --notes-file <(sed -n '/^## \[0.2.0-alpha.1\]/,/^## \[0.1.0\]/p' CHANGELOG.md | sed '$d')
```

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
