# d-anime-scraper

d-アニメストアの今期の作品一覧から作品情報を取得し、
曜日ごとにまとめた CSV とサムネイル画像を保存します。

## できること

- 作品一覧取得
- CSV 出力 (放送日 / タイトル / 画像 URL)
- タイトル画像を `OUT/＜日付＞/image/` に保存
- Docker でワンコマンド実行

## 最速利用手順 (Docker)

```bash
git clone <url>
cd d-anime-scraper
cp .env.example .env   # 任意
docker compose build
docker compose up --remove-orphans
```

出力: `OUT/YYYYMMDD/anime_list.csv` と `image/` ディレクトリ

## CSV 例

```
月曜,,
放送日,タイトル,画像URL
10月6日～,作品タイトルA,https://.../A.png

火曜,,
放送日,タイトル,画像URL
 ,放送日未確定タイトル,https://.../B.png
```

※ 放送日が空欄の作品は初回日が API/追加データで未取得または未定。

## 環境変数 (必要なら `.env` に設定)

| 変数     | 説明                                     | 例   |
| -------- | ---------------------------------------- | ---- |
| HOST_UID | ホスト UID を合わせて OUT の権限問題回避 | 1000 |
| HOST_GID | ホスト GID                               | 1000 |
| DEBUG    | 1 で `raw.json` などデバッグ出力         | 1    |

## ローカル実行 (任意)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app/scraper.py
```

## 注意

- 利用規約を守り一括取得のみを想定 (大量・高頻度アクセスはしない)
- API / サイト構造変更で動かなくなる可能性があります

## ライセンス / 更新履歴

ライセンス: `LICENSE` を参照。詳細な変更点は `CHANGELOG.md` または `リリースノート.txt` を参照してください。
