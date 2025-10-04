@echo off
set APP_NAME=d_anime_scraper
set SRC=gui_launcher.py

echo [INFO] Clean old dist/build
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist __pycache__ rmdir /s /q __pycache__

echo [INFO] PyInstaller build
pyinstaller --onefile --noconsole %SRC% -n %APP_NAME% --add-data version.py;.

echo [INFO] Build complete: dist\%APP_NAME%.exe
echo [HINT] 動的取得を利用するには実行環境で "pip install playwright" し、その後 "playwright install chromium" を実行してください。
