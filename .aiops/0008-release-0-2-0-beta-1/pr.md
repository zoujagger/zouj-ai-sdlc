<!-- PR description for intent 0008, generated in state 5. `gh pr create --body-file` it. -->
## Release 0.2.0-beta.1

**Intent:** `.aiops/0008-release-0-2-0-beta-1/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 95/100 at `e07d019`

### What and why
`0.2.0-alpha.4` (intents 0005 and 0007) was never tagged. It ships as **0.2.0-beta.1**:
- `plugin.json` and the CHANGELOG (heading, beta banner, compare links)
- the scaffold-history key (same hashes)
- the README (beta status line, pins), TROUBLESHOOTING, `docs/adoption.md`, `docs/roadmap.md`
- one `lifecycle.py` docstring

No behaviour changes.

### Acceptance criteria
- [x] AC-1: the version and the newest CHANGELOG release with the compare link from alpha.3 (`tests/test_shell_hooks.py::test_version_matches_changelog`, `tests/test_cli.py::Docs::test_changelog_has_the_release`)
- [x] AC-2: no shipped file names the unreleased alpha (`tests/test_cli.py::Docs::test_no_shipped_file_names_alpha_4`)
- [x] AC-3: the history entry renamed with the same hashes (`tests/test_rules.py::History::test_current_scaffold_in_history`)
- [x] AC-4: every README pin is the version; no alpha banner (`tests/test_cli.py::Docs::test_release_banner_is_beta`)
- [x] AC-5: only the intended files change (`git diff --name-only`)
- [x] AC-6: `make check` (444), `claude plugin validate .`, and the `profile-by-setup-command` eval: 1.00 with the plugin, Δ +0.33

### Deviations from plan
S1 and S2 landed in one commit (a shared test). The proof tests build the rejected version string from parts. The
README pin pattern now takes any pre-release. All are logged in [plan.md](plan.md).

### Risks and rollback
- The pins name `v0.2.0-beta.1` before the tag exists: tag right after the merge.
- A repo scaffolded from untagged main may show stale files until `sdlc upgrade`.
- Rollback: revert the PR, and delete the tag if one was pushed.

### After the merge (the human)
```
git switch main && git pull --ff-only
git tag -a v0.2.0-beta.1 -m "zouj-ai-sdlc 0.2.0-beta.1" && git push origin v0.2.0-beta.1
```

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
