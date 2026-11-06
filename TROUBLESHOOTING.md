# Troubleshooting

Start with `sdlc doctor`. It checks the prerequisites, the profile, signing and every artifact, and each `✗` comes with
its fix. If you're stuck, `sdlc feedback` prints the issue links and a summary to paste (it sends nothing).

## Typing `Intent Approved NNNN` (or Spec/Plan) does nothing
- **The phrase must be the whole message:** `Plan Approved 0003`, nothing before or after it.
- **The plugin must be loaded in that Claude Code session.** Check with `/plugin list`. A session started before
  install, or one using another plugin directory, won't see the phrase.
- **The approval needs your key.** Under `team` (a passphrase key) the prompt can't ask for the passphrase. Claude
  then prints the exact command to run in **your own terminal**:
  `/usr/bin/python3 -I <plugin>/bin/sdlc approve NNNN intent|spec|plan`.
  It refuses inside Claude Code, the `!` prefix included, because approving is a human act.
- **Check the gate:** `sdlc status` shows `intent ✓ · spec … · plan …`.

## "approval signing: …" in doctor, or an approval is refused
- **"no passphrase" / "loaded in ssh-agent":** the `team` profile needs a human for every signature. Use a dedicated
  key with a passphrase, kept out of ssh-agent:
  ```bash
  ssh-keygen -t ed25519 -f ~/.ssh/aiops_signing      # set a passphrase
  git config --global gpg.format ssh
  git config --global user.signingkey ~/.ssh/aiops_signing.pub
  ssh-add -d ~/.ssh/aiops_signing 2>/dev/null
  ```
- **"strict … accepts only a FIDO sk- key":** create one with `ssh-keygen -t ed25519-sk -f ~/.ssh/aiops_signing_sk`.
  It must not be allow-listed with `no-touch-required`.
- **"repo-local git config sets …":** signing settings must come from your global config. Remove the local key with
  `git config --local --unset <key>`.
- **"not signed by an allow-listed signer" in CI:** add your public key to `.aiops/config/allowed-signers`, then land
  it through a reviewed PR. CI trusts the *target* branch's list.
- **Signing ceremony too heavy for a solo project?** Run `sdlc setup --profile solo` in your terminal. Approvals are
  then a typed phrase plus an unsigned commit. The workflow and the gates stay the same.

## `git push` fails
- **"could not read Username":** git has no credential helper. Run `gh auth setup-git`, or configure any helper.
- **"refusing to allow an OAuth App to create or update workflow … without `workflow` scope":** your `gh` token can't
  push changes to `.github/workflows/`. Run `gh auth refresh -h github.com -s workflow`.
- **"BLOCKED [G-MERGE-03] by guard-bash: direct push to main/master":** by design. Push a feature branch and open a PR
  (`/zouj-ai-sdlc:pr`); a human merges.

## A command is BLOCKED
Every block message reads `BLOCKED [<id>] by <hook>: <reason>`, followed by the procedure. Run `sdlc why <id>` to
see the reason, the playbook stage the rule protects and the safe alternative. The common ones:

| Id | Why | What to do |
|---|---|---|
| `G-LOCK-*` | States 1-3: code is read-only until `Plan Approved` | Finish the artifact; the human approves the plan |
| `G-GATE-*`, `G-MERGE-*`, `G-DEPLOY-*` | Only a human approves, merges or deploys to production | Ask the human; they run it themselves |
| `G-ART-*` | Shell writes to `.aiops/` bypass the gate guard | Edit artifacts with the Edit/Write tools |
| `G-FILE-*`, `G-TOOL-*` | Protected paths, your shell startup files, PATH, git config, the installed plugin | A human changes those |
| `G-SEC-*`, `G-ENV-01`, `G-ENV-04` | Secret files and tokens never enter the session | Use `.env.example` or the docs for names |

**A false positive** (a safe command that's blocked): the static parser is strict on purpose. Run `sdlc why <id>`.
If the rule is one of the two `heuristic` rules (`G-ENV-03`, `G-BASH-07`), a human can allow that exact command: add
the line `<id> <exact command>` to `.aiops/config/allowed-commands` (human-owned, reviewed through CODEOWNERS). Only
that rule is lifted, only for that command, and `sdlc doctor` and CI reject entries for any other rule. Otherwise
rephrase the command, for example without a variable as the command word, or run it yourself. Please report it with
`sdlc feedback`.
A known one: a line that mentions `sdlc init` or `sdlc setup` next to a directory or git-location change (`cd`,
`pushd`, `-C`, `--chdir`, `-execdir`, `GIT_*=`, `HOME=`, `CLAUDE_PROJECT_DIR=`; a commit message, `grep -C3`), or run
from another repo, is refused on purpose; run it as two commands.

## The Stop hook keeps saying "definition of done not met" (`G-STOP-01`)
`make check` must pass before a turn can end, whenever the working tree changed. Run `make check` and fix what fails.
If a Makefile target still prints `not configured`, wire it: edit the
Makefile's recipes (the plugin ships presets in `templates/stacks/`).

## Setup says `✗` and "nothing was written"
Setup stops before writing anything when:
- **git, make, or Python ≥ 3.9 is missing.** Install it and rerun `sdlc setup`.
- **`.aiops/config.json` or `.claude/settings.json` isn't valid JSON, isn't a JSON object**, or has a marketplace key
  that isn't an object. Fix the file by hand (it's human-owned).
- **A scaffold file, or a folder above it, is a symlink** (`init` too). Setup never writes through links: remove the
  link.
- **`config.json` names an unknown `profile`.** Set it to `solo`, `team` or `strict`, or pass `--profile`.
- **The folder isn't the top of a git repository**, or it is your home directory, `~/.claude` or a folder on PATH,
  or git's `GIT_DIR`/`GIT_WORK_TREE` variables are set, or `CLAUDE_PROJECT_DIR` names another repo (`init` too).
  Run `git init` in a project folder and set up from inside it.

`!` rows (claude, gh, credential helper, signing) are warnings: setup continues and lists the fix.

## Setup shows `!` rows in its plan and "Review before committing"
A human-owned file (such as `.aiops/config/allowed-signers` or `.claude/settings.json`) exists, no commit has it,
and it holds something setup doesn't write, or its staged version isn't what's on disk. Setup didn't write it and
leaves it out of the commit command it prints. Read the diff it shows: an `allowed-signers` key you don't recognise
must not be committed, because CI would then trust approvals signed with it. Fix or delete the file, then commit it
yourself. If the file on disk looks fine, look at what is staged too:
`git --no-pager diff --cached --no-textconv --no-ext-diff HEAD -- <file>`, and unstage it with
`git restore --staged -- <file>`.

An agent running as you controls `.git`: staged content, skip-worktree flags, repo-local filters, diff drivers, the
pager and hooks. Setup's checks, and any git command you run in that checkout, can be bent by them. So:
1. Before setting up a new repo, and before committing, look at `.git` itself: `git config --local --list` should
   have no `filter.*`, `diff.*`, `core.pager`, `core.hooksPath` or `core.fsmonitor`; `.git/info/attributes` should be
   missing or empty; `ls .git/hooks` should show only `*.sample` files. Remove anything you didn't put there.
2. If a staged key won't unstage, run `git update-index --no-skip-worktree --no-assume-unchanged -- <file>` first.
3. After committing, read every commit you are about to push:
   `git --no-pager log --stat --patch --no-textconv --no-ext-diff origin/main..HEAD` (`--root` instead of the range in a repo with no remote yet). Check the profile in
   `.aiops/config.json` and every key in `allowed-signers`.
4. Before merging, read the adoption PR's full "Files changed" on GitHub, every file, ideally with a second person.
   CODEOWNERS doesn't cover this PR: GitHub reads it from the base branch, and the adoption PR is the one that adds
   it.

## Upgrading, repairing, removing
- **What did the plugin install here?** `sdlc list-installed`. A repo set up before 0.2.0-alpha.3 shows a preview of
  what adoption would record.
- **`upgrade` says a file is kept (modified):** you changed it, so upgrade only rewrote its CI ref and printed the
  diff against the new template. Merge what you want by hand.
- **`upgrade` run by Claude left files for you:** human-owned files (workflows, `.claude/settings.json`,
  `.aiops/config*`, CODEOWNERS) and code under the read-only lock are yours. Run the printed
  `<python> -I <plugin>/bin/sdlc upgrade` in your own terminal, then commit.
- **`! … pinning the tag`:** upgrade couldn't find the plugin's commit sha (no `installed_plugins.json` entry, or an
  unpushed checkout). Tags can move: pin a full sha when you can.
- **`uninstall` is refused inside Claude Code:** it's human-only. Preview with `sdlc uninstall --dry-run`, then run it
  in your own terminal.

## Starting over in a repo
Delete nothing by hand under `.aiops/`: the guards protect it, and CI audits it. To leave the workflow, remove the
plugin (`/plugin`), then delete the scaffold files you don't want, in a reviewed commit.
