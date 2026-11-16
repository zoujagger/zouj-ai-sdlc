---
type: regex
pattern: "\\{\\s*\"lock_when_idle\":\\s*true,\\s*\"commit_approvals\":\\s*true,\\s*\"main_branch\":\\s*\"main\",\\s*\"require_signed_approvals\":\\s*true\\s*\\}"
target: { source: file, path: ".aiops/config.json" }
---
