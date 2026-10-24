#!/bin/bash
# Push the in-progress deepseek-v4-pro-0813.jsonl to a remote data-backup
# branch. Motivation: 2026-10-23 sandbox rollback destroyed 1269 collected
# cells (~5.5h); remote pushes are the only storage that survives rollbacks.
# Usage: bash scripts/backup_data.sh
set -e
cd /home/z/my-project/github_repo
SRC=/home/z/my-project/results/expand/deepseek-v4-pro-0813.jsonl
[ -f "$SRC" ] || { echo "no jsonl yet, skip"; exit 0; }

# data-backup branch: reuse if exists, else create from origin/main
if git show-ref --verify --quiet refs/heads/data-backup; then
  git checkout -q data-backup
else
  git checkout -q -b data-backup origin/main
fi
cp "$SRC" results/expand/
git add results/expand/deepseek-v4-pro-0813.jsonl
N=$(grep -c '"answer":' results/expand/deepseek-v4-pro-0813.jsonl || true)
git commit -qm "v4-pro data backup: ${N} answer-records @ $(date '+%F %T')"
timeout 60 git push origin data-backup 2>&1 | tail -1 || echo "push failed (will retry next cycle)"
git checkout -q main
echo "backup done: ${N} records pushed to data-backup"
