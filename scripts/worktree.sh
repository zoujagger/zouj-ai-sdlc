#!/usr/bin/env bash
# Create a git worktree for a parallel Claude Code session (playbook: 2-3 sessions max).
# Usage: scripts/worktree.sh <intent-id> <task-id>      e.g. scripts/worktree.sh 0001 T2
#        scripts/worktree.sh --list | --remove <path>
set -euo pipefail

root=$(git rev-parse --show-toplevel)
max=3

case "${1:-}" in
  --list)   git worktree list; exit 0 ;;
  --remove) git worktree remove "${2:?path required}"; exit 0 ;;
  ""|-h|--help) sed -n '2,4p' "$0"; exit 1 ;;
esac

id=$1; task=${2:?task id required}
count=$(( $(git worktree list | wc -l) - 1 ))
if (( count >= max )); then
  echo "Already $count parallel worktrees. The limit is $max: parallel work you can't review is the bottleneck." >&2
  exit 1
fi

name="$(basename "$root")-$id-$task"
path="$(dirname "$root")/$name"
branch="feat/$id-$(tr '[:upper:]' '[:lower:]' <<<"$task")"

git worktree add -b "$branch" "$path"
echo
echo "Worktree ready: $path (branch $branch)"
echo "Start the session:  cd \"$path\" && claude \"/implement $task $id\""
