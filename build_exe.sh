#!/usr/bin/env bash
set -euo pipefail

# 簡易 PyInstaller ビルドスクリプト (Linux / macOS 用)
# 使い方:
#   bash build_exe.sh            # 通常ビルド (静的スクレイプ + 動的は Playwright 在庫あれば)
#   bash build_exe.sh --dynamic  # 実質同じ (Playwright が無ければ警告)

APP_NAME="d_anime_scraper"
SRC="gui_launcher.py"

echo "[INFO] Clean old dist/build"
rm -rf dist build __pycache__ || true

echo "[INFO] PyInstaller build"
pyinstaller --onefile --noconsole "$SRC" -n "$APP_NAME" \
  --add-data "d_anime_scraper/version.py:d_anime_scraper" \
  --add-data "d_anime_scraper/scraper.py:d_anime_scraper"

echo "[INFO] Build complete: dist/$APP_NAME"
echo "[HINT] 動的取得を利用するには配布先で 'pip install playwright && playwright install chromium' を実行してください。"
