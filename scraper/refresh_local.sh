#!/bin/sh
# Weekly local refresh: fetch Murachh data and push it to GitHub if it changed.
# Run by ~/Library/LaunchAgents/com.letsgrowmp.refresh.plist
set -e
export PATH="/Users/spike/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
cd "$(dirname "$0")/.."
echo "== $(date)"
git pull --ff-only -q
python3 -I scraper/fetch_murachh.py
git add data/murachh.json
if git diff --cached --quiet; then
  echo "no changes"
else
  git commit -q -m "Refresh Murachh data $(date +%F)"
  git push -q
  echo "pushed"
fi
