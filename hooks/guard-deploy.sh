#!/usr/bin/env bash
# PreToolUse(Bash | mcp__.*deploy.*): the production gate.
# "The agent does everything up to the production gate and nothing past it."
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

input=$(cat)
aiops_enabled "${CLAUDE_PROJECT_DIR:-$PWD}" || exit 0
tool=$(json_get tool_name <<<"$input") || fail_closed guard-deploy

block() {
  {
    echo "BLOCKED by guard-deploy: $1 targets production."
    echo "Reason: production is a human gate. The agent stops at staging."
    echo "Procedure: run /zouj-ai-sdlc:deploy to produce the handoff note; a named approver then approves the 'production'"
    echo "environment in the GitHub 'deploy' workflow, or runs 'make deploy ENV=prod' themselves."
  } >&2
  exit 2
}

P='(prod|production|prd|live)([^a-z]|$)'

if [[ "$tool" == "Bash" ]]; then
  c=$(json_get tool_input.command <<<"$input" | tr -s '[:space:]' ' ')
  re_make="make [^;&|]*(deploy|rollback|release|promote)[^;&|]*ENV=$P"
  re_wf="gh workflow run [^;&|]*deploy[^;&|]*(environment|env)=$P"
  re_tools="(kubectl|helm|terraform|pulumi|serverless|vercel|flyctl|fly|gcloud|aws|az|eb|cdk)[^;&|]*(apply|deploy|up|upgrade|install|--prod)[^;&|]*$P"
  re_tools2="(kubectl|helm|terraform|pulumi|vercel|flyctl|fly)[^;&|]*$P[^;&|]*(apply|deploy|up|upgrade|install)"
  re_vercel="vercel[^;&|]*--prod"
  for re in "$re_make" "$re_wf" "$re_tools" "$re_tools2" "$re_vercel"; do
    [[ "$c" =~ $re ]] && block "'$c'"
  done
  exit 0
fi

# MCP deploy tools: block when any argument mentions production.
if [[ "$tool" == mcp__* ]]; then
  args=$(json_get tool_input <<<"$input" | tr '[:upper:]' '[:lower:]')
  [[ "$args" =~ $P ]] && block "MCP tool $tool"
fi
exit 0
