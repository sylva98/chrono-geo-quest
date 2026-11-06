#!/bin/bash
# 重新构建并把 dist/ 的内容更新到 gh-pages 分支（不切换工作区，不影响 main 的未提交改动）
# 用法：./deploy.sh            仅更新本地 gh-pages 分支
#       ./deploy.sh --push     更新并推送到 origin
set -euo pipefail
cd "$(dirname "$0")"

python3 build.py

export GIT_INDEX_FILE="$(mktemp -u /tmp/ghpages-idx.XXXXXX)"
git --work-tree=dist add -A -- .
TREE=$(git write-tree)
COMMIT=$(git commit-tree "$TREE" -m "deploy: $(date '+%Y-%m-%d %H:%M:%S')")
git update-ref refs/heads/gh-pages "$COMMIT"
rm -f "$GIT_INDEX_FILE"
unset GIT_INDEX_FILE

git --no-pager log --oneline -1 gh-pages
echo "gh-pages 已更新（内容 = dist/ 根目录）"

if [ "${1:-}" = "--push" ]; then
  git push -f origin gh-pages
  echo "已推送，GitHub Pages 约 1 分钟后生效"
fi
