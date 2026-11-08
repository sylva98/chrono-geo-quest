#!/bin/bash
# 一键发布：构建 → 更新 gh-pages（网站）→ 同步源码到 main（备份）
# 用法：./release.sh "本次改动的说明"
# 前置：本地工作区已 commit（push_main.py 推的是 master 的树）
set -euo pipefail
cd "$(dirname "$0")"

MSG="${1:-release: $(date '+%Y-%m-%d %H:%M')}"

echo "== 1/3 构建并更新本地 gh-pages =="
./deploy.sh

echo "== 2/3 推送 gh-pages（网站生效）=="
python3 push_api.py

echo "== 3/3 同步源码到 main（备份）=="
python3 push_main.py "$MSG"

echo "== 完成：网站已更新，源码已备份到 main =="
