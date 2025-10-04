## d アニメストア 今期アニメ一覧 スクレイピングツール

ブラウザで d アニメストアにログイン済みの状態で実行すると、今期放送予定ページから作品一覧を取得し、日付フォルダに CSV と画像を保存します。GUI 版はダブルクリックで実行～数秒後自動終了します。

### 特徴

- 曜日/放送開始日/タイトル/画像 URL/画像ファイル名 を CSV 出力 (UTF-8 BOM)
- 画像もローカル保存 (alt → data-src → src の順で取得)
- 日次フォルダ: `OUT/YYYYMMDD/`
- 最新取得 HTML を `_live.html` に保存
- GUI はシンプルなログ表示 (tkinter)
- Playwright はデフォルト非同梱（静的で 0 件になる場合のみ任意導入で精度向上）

### フォルダ構成 (主要ファイル)

| ファイル                         | 役割                                          |
| -------------------------------- | --------------------------------------------- |
| `gui_launcher.py`                | GUI ランチャ (エンドユーザーは主にこれを使う) |
| `scraper.py`                     | スクレイピング本体 (CLI / 内部呼び出し)       |
| `version.py`                     | バージョン定義                                |
| `requirements.txt`               | 最小依存 (静的スクレイプ用)                   |
| `build_exe.sh` / `build_exe.bat` | PyInstaller ビルドスクリプト                  |

### 最短利用手順 (exe 配布を受け取った場合)

1. ブラウザで d アニメストアにログインして作品一覧が表示できることを確認
2. `d_anime_scraper` (Windows は `.exe`) をダブルクリック
3. ログウィンドウが完了メッセージを表示 → 数秒後自動で閉じる
4. `OUT/今日の日付/` を確認 (CSV / images / run.log など)

### ソースから実行 (Python 環境)

```bash
pip install -r requirements.txt
python gui_launcher.py            # GUI 実行
# もしくは CLI で直接
python scraper.py                 # 静的取得のみ
python scraper.py --version       # バージョン表示
```

### 動的取得(任意機能)が必要なケース

静的結果が常に 0 件になる場合、ページ側が JavaScript でリスト挿入するタイミングに依存している可能性があります。以下を導入すると、CLI の `--dynamic` オプションや GUI の自動再試行で作品を取得できることがあります。

```bash
pip install playwright
playwright install chromium
python scraper.py --dynamic
```

GUI は静的 0 件時に自動で 1 回動的再試行を試みます (Playwright 未導入なら失敗ログを出して静的結果のまま続行)。

### 出力例

```
OUT/20251004/
  anime_list.csv      # UTF-8 (BOM) / Excel 可
  images/             # 作品画像
  _status.txt         # entries / saved_images / used_dynamic など
  run.log             # UTF-8 (BOM) ログ
_live.html            # 最新ページ HTML
```

### CSV カラム

`曜日, 放送開始日, タイトル, 画像URL, 画像ファイル名`

### よくある質問 (FAQ)

| 質問            | 回答                                                                              |
| --------------- | --------------------------------------------------------------------------------- |
| 0 件になる      | サイトの JS 挿入タイミング。Playwright 導入を検討。                               |
| 画像が一部ない  | 一時的 403 / ネット要因。再実行で補完されることあり。                             |
| 文字化けする    | BOM 付きなので Excel でそのまま開ける。改善しない場合はインポートウィザード使用。 |
| 動的導入は必須? | 多くのケースで静的のみでも可。0 件が続く時のみ任意導入。                          |

### ビルド (開発者向け)

```bash
pip install -r requirements.txt pyinstaller
bash build_exe.sh        # Linux / macOS
# Windows:
build_exe.bat
```

開発で `pip install -e .` を使うと `d_anime_scraper.egg-info/` が生成されますが、これはパッケージメタデータでありリポジトリにはコミットしません (`.gitignore` 済)。

生成物: `dist/d_anime_scraper` (Windows: `dist/d_anime_scraper.exe`)

### バージョン表示

```bash
python scraper.py --version
```

### 注意事項

- 過度な短時間連続アクセスを避けてください。
- HTML 構造変更で取得不能になった場合は `parse_entries` のセレクタ調整が必要です。
- 画像は著作権の対象です。個人/社内利用など適切な範囲で利用してください。

### ライセンス / 免責

本ツールは「現状有姿 (AS IS)」で提供されます。利用は自己責任で行ってください。対象サイトの利用規約と robots.txt を遵守してください。

---

改善要望や不具合があれば Issue / PR でお知らせください。
