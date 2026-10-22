---
name: pr
description: Opens a pull request that links intent.md, spec.md, and plan.md and attaches the mechanical evidence, so reviewers can focus on intent and risk.
argument-hint: "[base-branch]"
disable-model-invocation: true
---

# /pr: open a pull request

Base: `$ARGUMENTS` (default `main`)

1. Pre-flight: `make check` is green, `/verify` returned VERIFIED (run it if you're unsure), the tree is clean, and the branch isn't `main`.
2. Collect the commits, the diff stat, and the intent folder.
3. Write the body from `.github/pull_request_template.md`: links to intent, spec, and plan, the ACs covered, whether deviations were logged, the evidence (check output, verifier verdict, screenshots), the risk and rollback command, and the AI disclosure.
4. Ask for confirmation, then run `git push -u origin HEAD` and `gh pr create --base <base> --title "<conventional title>" --body-file -`.
5. Print the URL. Claude reviews in CI and only comments. **A CODEOWNER approves. The authoring agent never approves its own PR.**
