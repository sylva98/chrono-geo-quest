#!/bin/bash
# 一键发布：构建 → 更新 gh-pages（网站）→ 推送源码到 main（备份）
# 用法：./release.sh "本次改动的说明"
#
# 自适应两种环境：
#   A) 存在 /root/.gh_token_chrono（手机端沙箱，git 直连不通）→ 走 GitHub API 推送
#      （push_api.py 更新 gh-pages；push_main.py 推 master 树到 main，要求已 commit）
#   B) 不存在 token 文件（本机 Mac，gh 已授权）→ 直接 git push
#
# 两种环境通用的前置：先把 git pull --ff-only 对齐远端（避免覆盖手机端的新提交）
set -euo pipefail
cd "$(dirname "$0")"

MSG="${1:-release: $(date '+%Y-%m-%d %H:%M')}"
TOKEN_FILE="/root/.gh_token_chrono"

echo "== 0/4 对齐远端 main（远端有新提交则先拉取）=="
if git fetch origin main 2>/dev/null && [ "$(git rev-list --count main...origin/main)" != "0" ]; then
  if [ "$(git rev-list --count origin/main..main)" = "0" ]; then
    echo "远端有新提交，快进合并："
    git merge --ff-only origin/main
  else
    echo "⚠ 本地与远端各有新提交，请先手动处理分叉后重试"; exit 1
  fi
else
  echo "远端无新提交，继续"
fi

echo "== 1/4 提交本地改动（如有）=="
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
  git add -A
  git commit -m "$MSG"
else
  echo "工作区干净，无需提交"
fi

echo "== 2/4 构建并更新本地 gh-pages =="
./deploy.sh

if [ -f "$TOKEN_FILE" ]; then
  echo "== 3/4 检测到 API token（$TOKEN_FILE），走 API 推送 =="
  python3 push_api.py
  echo "== 4/4 同步源码到 main（API）=="
  python3 push_main.py "$MSG"
else
  echo "== 3/4 无 API token，走 git 推送 gh-pages（网站生效）=="
  git push -f origin gh-pages
  echo "== 4/4 推送源码到 main（备份）=="
  git push origin main
fi

echo "== 完成：网站已更新（约 1 分钟生效），源码已备份到 main =="
