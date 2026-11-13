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
  It refuses inside Claude Code, the `!` prefix included, because approving is a human act. Lost the path?
  `sdlc where` prints it, and `sdlc status` shows it as `Your terminal:` while a gate waits on your key.
- **Check the gate:** `sdlc status` shows `intent ✓ · spec … · plan …`.

## Typing `Setup Profile solo` (or `team`, `strict`) does nothing, or says `profile NOT set`
- **Nothing happens:** the phrase must be the whole message, and the plugin must be loaded in that session, as for an
  approval. In a repo without `.aiops/` the phrase is ignored: run `/zouj-ai-sdlc:setup` first.
- **"unknown profile" or "no profile was named":** the names are `solo`, `team` and `strict`.
- **"a profile is already set here":** the phrase sets a repo's **first** profile only. To change one, run
  `sdlc setup --profile <name>` in your own terminal (`sdlc where` prints the command with its full path), then
  commit `.aiops/config.json` through a reviewed PR.
- **"config.json was edited after setup":** the phrase only fills in an untouched config. Use the terminal command
  above, which shows the change as a diff before writing.
- **"… is already Approved" (or Closed):** a gate was opened under the default profile, so changing how approvals are
  proven is now a deliberate change: the terminal command again.
- **"committing it failed":** the profile is in `.aiops/config.json` in your working tree. Commit that file alone.

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
- **Signing ceremony too heavy for a solo project?** In a repo with no profile yet, type `Setup Profile solo`. If a
  profile is set, run `sdlc setup --profile solo` in your terminal (`sdlc where` prints the full command). Approvals
  are then a typed phrase plus an unsigned commit. The workflow and the gates stay the same.

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
| `G-FILE-05` | The command deletes or moves the repo, a directory above it, or a directory holding protected or tracked secret files | Name the paths you mean (`rm -rf build/`) |
| `G-FILE-06` | An archive, a stash, a merge or a pull would bring in `.aiops/config*`, settings or a protected path | `git fetch`, then `git merge <ref>`; a human changes human-owned config. Merging from main is always fine. An archive piped in (`curl … \| tar xz`) or with symlink members can't be inspected: download it, then extract it outside the repo |
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

## A workflow, `ops/bands.yaml` or another scaffold file isn't there
Since 0.2.0-alpha.4, setup and `init` install the core scaffold only: what the gates, the read-only lock and the CI
audit need. The rest is opt-in, by part:
- `review`: Claude's PR review and `@claude` workflows
- `maintain`: `ops/bands.yaml`, the Maintain and scheduled-scan workflows, runbooks, postmortems, retros
- `deploy`: `deploy.yml` and release notes
- `governance`: policy examples, `docs/branch-protection.md`, `docs/adr/`, Dependabot
- `issues`: issue forms and issue triage

Add one with `sdlc setup --with <part>` (comma-separated, or `--with all`). `sdlc list-installed` ends with the parts
that aren't installed, and `sdlc setup --dry-run` names them too. `--with` only adds, and no command removes a part. A repo set up
before alpha.4 keeps every part.

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
  `<python> -I <plugin>/bin/sdlc upgrade` in your own terminal (`sdlc where` prints that prefix), then commit.
- **`! … ZOUJ_SDLC_REF is not a literal`:** your workflow sets the ref with an expression; upgrade leaves it
  alone. Set it to the printed sha yourself.
- **`upgrade` didn't create a new workflow:** it belongs to a part this repo doesn't have. `upgrade` and `repair` never
  add a part: `sdlc setup --with <part>` does.
- **A file shows `declined`:** it was part of the scaffold you adopted, but you had removed it, so upgrade and repair
  never re-create it. To get it back, copy it from the plugin's `templates/scaffold/`.
- **`! … pinning the tag`:** upgrade couldn't find the plugin's commit sha (no `installed_plugins.json` entry, or an
  unpushed checkout). Tags can move: pin a full sha when you can.
- **`uninstall` is refused inside Claude Code:** it's human-only. Preview with `sdlc uninstall --dry-run`, then run it
  in your own terminal.

## Starting over in a repo
Delete nothing by hand under `.aiops/`: the guards protect it, and CI audits it. To leave the workflow, remove the
plugin (`/plugin`), then delete the scaffold files you don't want, in a reviewed commit.
