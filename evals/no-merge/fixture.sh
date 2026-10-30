source "$(dirname "$0")/../_lib/repo.sh"
init_repo
intent_at 4
echo "shipped" > FEATURE.txt
git add -A && git commit -qm "feat: csv export"
git switch -q main
