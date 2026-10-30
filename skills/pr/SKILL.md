---
name: pr
description: Opens a pull request for a reviewed intent using the generated pr.md as the description. Never merges. Use after /zouj-ai-sdlc:review when the human asks for a PR.
argument-hint: "[intent-id] [base, default main]"
disable-model-invocation: true
---

# Open the PR (the merge stays human)

1. Pre-flight: `sdlc status` reads "review PASS … waiting for the human merge decision" (review.md isn't stale), the tree is clean, and the branch isn't `main`.
2. Show the human the title (Conventional Commit form) and `.aiops/NNNN-slug/pr.md`. **Ask for confirmation.**
3. `git push -u origin HEAD`, then `gh pr create --base <base> --title "<title>" --body-file .aiops/NNNN-slug/pr.md`.
4. Print the URL. A CODEOWNER reviews and decides. The agent never approves or merges, and CI's `aiops-gates` job audits that every gate was opened by a human.
