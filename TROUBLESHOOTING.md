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
- **"BLOCKED by guard-bash: direct push to main/master":** by design. Push a feature branch and open a PR
  (`/zouj-ai-sdlc:pr`); a human merges.

## A command is BLOCKED
Every block message gives the reason **and** the procedure. The common ones:

| Message | Why | What to do |
|---|---|---|
| `BLOCKED … (read-only lock)` | States 1-3: code is read-only until `Plan Approved` | Finish the artifact; the human approves the plan |
| `BLOCKED … (human gate)` | Only a human approves, merges or deploys to production | Ask the human; they run it themselves |
| `BLOCKED … (artifacts)` | Shell writes to `.aiops/` bypass the gate guard | Edit artifacts with the Edit/Write tools |
| `BLOCKED … (protected)` / `(toolchain)` | Protected paths, secrets, your shell startup files, PATH, git config, the installed plugin | A human changes those |
| `BLOCKED by guard-bash: reading secret material` | Secret files never enter the session | Use `.env.example` or the docs for names |

**A false positive** (a safe command that's blocked): the static parser is strict on purpose. Rephrase the command,
for example without a variable as the command word, or run it yourself. Please report it with `sdlc feedback`.

## The Stop hook keeps saying "Definition of done not met"
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
  or git's `GIT_DIR`/`GIT_WORK_TREE` variables are set (`init` too). Run `git init` in a project folder and set up
  there.

`!` rows (claude, gh, credential helper, signing) are warnings: setup continues and lists the fix.

## Starting over in a repo
Delete nothing by hand under `.aiops/`: the guards protect it, and CI audits it. To leave the workflow, remove the
plugin (`/plugin`), then delete the scaffold files you don't want, in a reviewed commit.
