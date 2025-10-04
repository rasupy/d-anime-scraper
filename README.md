### バージョン

現在のバージョンは `d_anime_scraper/version.py` を参照してください (タグ: vX.Y.Z)。

## d アニメストア 今期アニメ一覧 スクレイピングツール

ブラウザで d アニメストアにログイン済みの状態で実行すると、今期放送予定ページ ("今期(秋)アニメ") から作品一覧を取得し、日付フォルダに **CSV + 画像** を保存します。GUI 版は「ダブルクリック → 待つ → 出力フォルダが自動で開く → 数秒後ウィンドウ自動終了」というワンステップ利用を想定しています。

---

### ✅ 特徴 (ユーザー向け)

- CSV 出力 (BOM 付 UTF-8): 曜日 / 放送開始日 / タイトル / 画像 URL / 画像ファイル名
- 画像自動保存 (候補: `alt` → `data-src` → `src` の順で最初の有効 URL 採用)
- 日付ごとフォルダ: `OUT/YYYYMMDD/`
- 最新 HTML を `_live.html` に保存 (不具合調査用)
- ログ & ステータス: `run.log`, `_status.txt` で取得件数や動的判定・警告確認
- 静的 0 件時のみ Playwright (動的) 再取得をオプション実行
- 完了後に出力フォルダを OS のファイルマネージャで自動オープン

### 📦 構成 (主要)

| パス                             | 役割                                        |
| -------------------------------- | ------------------------------------------- |
| `gui_launcher.py`                | GUI ランチャ (exe 化対象)                   |
| `d_anime_scraper/`               | コアパッケージ (`scraper.py`, `version.py`) |
| `pyproject.toml`                 | パッケージ / CLI エントリ / ツール設定      |
| `requirements.txt`               | 最小依存 (静的スクレイピング)               |
| `build_exe.sh` / `build_exe.bat` | PyInstaller ビルドスクリプト                |
| `.github/workflows/`             | リリース自動ビルド CI                       |

旧ルート `scraper.py`, `version.py` は互換用スタブになっている場合があります。公式 API は `d_anime_scraper` パッケージ配下を参照してください。

---

## 🔰 クイックスタート (配布バイナリ)

1. ブラウザで d アニメストアにログインし対象ページが見られることを確認
2. ダウンロードした `d_anime_scraper` (Windows: `d_anime_scraper.exe`) をダブルクリック
3. ログ表示 → 完了後フォルダ自動オープン (`OUT/YYYYMMDD/`)
4. 数秒後ウィンドウ自動終了

再実行で既存画像はスキップされ、新規のみ追加保存されます。

---

## 🐍 ソース実行 (Python)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python gui_launcher.py      # GUI 利用 (推奨)
```

### CLI 利用

```bash
pip install .
d-anime-scraper            # 静的取得
d-anime-scraper --version  # バージョン表示
```

### (任意) 動的再取得を試す

```bash
pip install .[dynamic]
playwright install chromium
d-anime-scraper --dynamic
```

GUI は静的 0 件時に自動で 1 回 Playwright を試行します。

---

## 📂 出力例

```
OUT/20251004/
  anime_list.csv      # UTF-8 (BOM)
  images/             # 作品画像
  _status.txt         # entries / saved_images / used_dynamic / structure_warning
  run.log             # 実行ログ (BOM 付)
_live.html            # 最新ページ HTML
```

### 出力先ディレクトリの決定ルール

優先順位:

1. 環境変数 `D_ANIME_SCRAPER_OUT_DIR` が設定されていればそのパス
2. PyInstaller onefile 版: 実行した exe があるフォルダ直下
3. ソース実行: プロジェクトルート直下

その下に `OUT/<YYYYMMDD>/` が生成されます。CLI で `--out-dir /path/to/base` を指定すれば (1) と同様に上書き可能です。

例:

```bash
d-anime-scraper --out-dir "D:/data/danime"
```

→ `D:/data/danime/OUT/20251004/anime_list.csv` などが生成。

CSV カラム: `曜日, 放送開始日, タイトル, 画像URL, 画像ファイル名`

---

## ⚠️ structure_warning

静的 HTML に `weekWrapper` があるのに `itemModule` が無い / 想定シグネチャ欠落時など DOM 構造変化を示唆する警告。表示された場合は `d_anime_scraper/scraper.py` の `parse_entries` セレクタ調整を検討してください。

---

## ❓ FAQ

| 質問                   | 回答                                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| 0 件になる             | JS 後挿入の可能性。`pip install .[dynamic]` → `playwright install chromium` → `--dynamic`。 |
| 画像が一部無い         | 一時的エラー。再実行で補完されるケースあり。                                                |
| Excel 文字化け         | BOM 付き UTF-8。改善しない場合は「データの取得」で UTF-8 指定。                             |
| Playwright は必須?     | いいえ。静的で取得できていれば不要。0 件時のみ導入。                                        |
| フォルダ自動で開かない | Linux で `xdg-open` 無い等。手動で `OUT` を参照。                                           |
| 再実行時の画像重複     | 既存ファイルはスキップし新規のみ保存。                                                      |

---

## 🛠 開発者向け

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
ruff check .
mypy .
```

### PyInstaller ビルド

```bash
pip install pyinstaller
bash build_exe.sh        # Linux / macOS
build_exe.bat            # Windows
```

生成物: `dist/d_anime_scraper` (Windows: `.exe`)

### バージョン

`d_anime_scraper/version.py` と `pyproject.toml` を更新 → `git tag vX.Y.Z` → push で CI がリリース作成。

### Editable

`pip install -e .` が生成する `*.egg-info/` はコミット不要。

---

## 🔒 注意 / 免責

- サイト規約・robots.txt を遵守
- 画像は著作権対象。適切な範囲で利用
- 本ツールは "AS IS" 提供。自己責任で利用

---

## 📬 フィードバック

Issue / PR 歓迎。`_status.txt` や `run.log` の抜粋を添付すると解析が早くなります。

Enjoy scraping!
