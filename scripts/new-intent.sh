#!/usr/bin/env bash
# Scaffold docs/intents/NNNN-slug/intent.md from the template (the SDLC trigger).
# Usage: scripts/new-intent.sh <kebab-slug>
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
slug=${1:-}
[[ -z "$slug" ]] && { echo "usage: $0 <kebab-slug>" >&2; exit 1; }
[[ "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "slug must be kebab-case" >&2; exit 1; }

last=$(find "$root/docs/intents" -mindepth 1 -maxdepth 1 -type d -name '[0-9][0-9][0-9][0-9]-*' -printf '%f\n' 2>/dev/null \
  | sort | tail -n1 | cut -c1-4)
next=$(printf '%04d' $((10#${last:-0} + 1)))
dir="$root/docs/intents/$next-$slug"
mkdir -p "$dir"

sed -e "s/NNNN/$next/g" -e "s/YYYY-MM-DD/$(date +%Y-%m-%d)/g" -e "s/<Intent title>/$(tr '-' ' ' <<<"$slug")/g" \
  "$root/docs/templates/intent.md" > "$dir/intent.md"

echo "Created ${dir#"$root"/}/intent.md"
echo "Next: fill it in (or run /intent in Claude Code), get it validated, then /spec $next"
