"""dアニメストア 今期(秋)アニメ ラインナップ簡易スクレイパー

要件:
  * 今期放送予定(タブ1)の各曜日ブロックを取得
  * 取得項目: 曜日, 放送開始日(YYYY年なし・例: 10月6日～), タイトル, 画像URL(src優先/なければdata-src/alt), 画像
  * OUT/yyyymmdd/ に CSV と images/ 保存
  * "まだまだ配信中" タブ(タブ2)のリストは除外
  * 直接アクセス不可(ログイン画面/想定HTML未取得)の場合は例外を上位に伝え GUI 側でポップアップ表示

実装方針(シンプル/可読性重視):
  - HTTP取得は requests (静的で十分 / JS依存なし)
  - 失敗/403等 → LoginRequiredError
  - オフラインフォールバック: temp.html が存在すればパース
  - HTML構造は weekWrapper > .weekText と直後の .itemWrapper 内の .itemModule を列挙
  - 画像ファイル名は `序数_スラッグ化タイトル.png` 形式
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import requests
from version import __version__

try:
    from bs4 import BeautifulSoup, Tag  # type: ignore
except Exception as e:  # pragma: no cover
    print(
        "[ERROR] beautifulsoup4 がインストールされていません。'pip install beautifulsoup4 lxml' を実行してください.",
        file=sys.stderr,
    )
    raise


FALL_PAGE_URL = "https://animestore.docomo.ne.jp/animestore/CF/fall"
LIVE_HTML = Path(__file__).with_name("_live.html")  # 毎実行時に最新取得HTMLを上書き
OUT_DIR_NAME = "OUT"


class LoginRequiredError(RuntimeError):
    """Raised when the target page could not be accessed (likely login required)."""


@dataclass
class AnimeEntry:
    weekday: str  # 例: 月曜
    start_date: str  # 例: 10月6日～
    title: str
    image_url: str  # 最終的に採用した URL (CSV 出力用)
    image_filename: str  # 保存したローカルファイル名
    variants: list[str]  # 試行候補 URL (alt > data-src > src)


@dataclass
class ScrapeResult:
    csv_path: Path
    entries: List[AnimeEntry]
    used_local: bool  # 互換用（常に False）
    used_dynamic: bool  # 動的取得を使用した場合 True
    run_log_path: Path
    logs: List[str]


def slugify(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\s/\\]+", "_", text)
    text = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠_ー-]", "", text)
    return text[:60] if len(text) > 60 else text


def fetch_live_html(timeout: float = 15.0) -> tuple[str | None, str | None]:
    """ライブページを取得し (html, error_message) を返す。

    失敗時は (None, エラーメッセージ)。成功しても構造が期待と違う場合は html は返しつつ
    error_message に警告文字列を入れる。
    """
    try:
        resp = requests.get(
            FALL_PAGE_URL,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
            },
        )
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        html = resp.text
        warn: str | None = None
        if "weekText" not in html:
            warn = "期待するweekTextが見つからない (ログイン未済/構造変化の可能性)"
        return html, warn
    except Exception as e:  # ネットワーク異常
        return None, str(e)


def parse_entries(html: str) -> List[AnimeEntry]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one("#newContents")
    if not container:
        raise RuntimeError("新作コンテンツ領域(#newContents)が見つかりません")

    entries: List[AnimeEntry] = []

    week_wrappers = container.select("div.weekWrapper")
    for ww in week_wrappers:
        week_text_el = ww.select_one(".weekText")
        if not week_text_el:
            continue
        week_label = week_text_el.get_text(strip=True)
        # 例: "月曜配信" -> "月曜"
        weekday = week_label.replace("配信", "")
        # タブ2(まだまだ配信中)対策: 週見出しが曜日+配信 以外を除外
        if not weekday.endswith("曜"):
            continue

        item_wrapper = week_text_el.find_next_sibling(
            "div", class_=re.compile(r"itemWrapper")
        )
        if not item_wrapper:
            continue
        # プレースホルダ("配信作品はありません")のみの場合スキップ
        if not item_wrapper.select(
            "div.itemModule"
        ) and "配信作品はありません" in item_wrapper.get_text(strip=True):
            continue
        item_modules = item_wrapper.select("div.itemModule.list")
        for idx, module in enumerate(item_modules, start=1):
            # 放送開始日
            start_el = module.select_one("header .streamingDate")
            start_date = start_el.get_text(strip=True) if start_el else ""
            # タイトル
            title_el = module.select_one("p.newTVtitle span")
            title = title_el.get_text(strip=True) if title_el else ""
            # 画像 URL
            img_el: Optional[Tag] = module.select_one(".thumbnailArea img")
            variants: list[str] = []
            image_url = ""
            if img_el:
                # alt優先、その後 data-src, src の順
                for attr in ("alt", "data-src", "src"):
                    val = img_el.get(attr)
                    if val and val not in variants:
                        variants.append(val)
                if variants:
                    image_url = variants[0]
            base_name = f"{idx:02d}_{slugify(title) or 'no_title'}"
            ext_candidate = os.path.splitext(image_url)[1].split("?")[0]
            ext = ext_candidate if ext_candidate else ".png"
            image_filename = base_name + ext
            entries.append(
                AnimeEntry(
                    weekday=weekday,
                    start_date=start_date,
                    title=title,
                    image_url=image_url,
                    image_filename=image_filename,
                    variants=variants,
                )
            )
    return entries


def download_images(
    entries: Iterable[AnimeEntry], images_dir: Path, timeout: float = 15.0
) -> int:
    """画像をダウンロードし、成功件数を返す。

    各エントリで alt > data-src > src の順に試し、成功した時点で打ち切る。
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": FALL_PAGE_URL,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    saved = 0
    for e in entries:
        if not e.variants:
            continue
        target = images_dir / e.image_filename
        if target.exists():  # 既存なら成功扱いにしない(重複カウント回避)
            continue
        for url in e.variants:
            try:
                r = session.get(url, timeout=timeout, headers=headers)
                if r.status_code == 200 and r.content:
                    # 拡張子が異なる可能性があるので差し替え
                    ext = os.path.splitext(url)[1].split("?")[0]
                    if ext and ext.lower() not in (".php",):
                        new_target = target.with_suffix(ext)
                    else:
                        new_target = target
                    new_target.write_bytes(r.content)
                    saved += 1
                    break
            except Exception:
                continue
    return saved


def write_csv(entries: List[AnimeEntry], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    # 曜日毎にまとめて並べる
    by_day: dict[str, List[AnimeEntry]] = {}
    for e in entries:
        by_day.setdefault(e.weekday, []).append(e)
    # 安定した順序: 月火水木金土日 の順 / 見つかったもののみ
    order = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]
    # Excel で日本語カラム/文字化けを避けるため BOM 付き UTF-8 (utf-8-sig)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["曜日", "放送開始日", "タイトル", "画像URL", "画像ファイル名"])
        for day in order:
            if day not in by_day:
                continue
            for e in by_day[day]:
                w.writerow(
                    [e.weekday, e.start_date, e.title, e.image_url, e.image_filename]
                )


async def _fetch_dynamic_html(timeout_sec: int = 15) -> str:
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Playwright 未インストールです。'pip install playwright' 後 'playwright install chromium' を実行してください"
        ) from e
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(FALL_PAGE_URL, timeout=timeout_sec * 1000)
        try:
            await page.wait_for_selector("div.itemModule.list", timeout=8000)
        except Exception:
            pass
        html = await page.content()
        await browser.close()
        return html


def run_scrape(dynamic: bool = False) -> ScrapeResult:
    """ライブページをスクレイピング。

    Parameters
    ----------
    dynamic: bool, default False
        True の場合、静的(単純 HTTP)パース結果が 0 件だったとき Playwright を用いた
        動的 DOM 取得を 1 回試みる。GUI では自動的に静的 0 件時に再試行するため、
        CLI で明示的に挙動を確認したい場合のみ --dynamic を指定する。
    """
    used_local = False
    used_dynamic = False
    logs: List[str] = []

    def _log(msg: str):  # 内部ロガー
        ts = dt.datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{ts}] {msg}")

    _log(f"run_scrape start mode={'dynamic' if dynamic else 'static'}")
    live_html, live_err = fetch_live_html()
    if live_html:
        _log(f"live fetch ok size={len(live_html)}")
        try:
            LIVE_HTML.write_text(live_html, encoding="utf-8")
        except Exception:
            pass
        parse_html = live_html
    else:
        _log(f"live fetch failed: {live_err}")
        raise LoginRequiredError(f"ライブページ取得失敗: {live_err}")

    entries: List[AnimeEntry] = []
    entries = parse_entries(parse_html)
    _log(f"parsed entries={len(entries)} (static)")
    if dynamic and len(entries) == 0:
        _log("static 0 -> dynamic 再取得開始")
        try:
            import asyncio

            dyn_html = asyncio.run(_fetch_dynamic_html())
            _log(f"dynamic fetch size={len(dyn_html)}")
            dyn_entries = parse_entries(dyn_html)
            _log(f"dynamic parsed entries={len(dyn_entries)}")
            if dyn_entries:
                entries = dyn_entries
                used_dynamic = True
                try:
                    LIVE_HTML.write_text(dyn_html, encoding="utf-8")
                except Exception:
                    pass
        except Exception as e:
            _log(f"dynamic fetch failed: {e}")

    # 3. 空ならフォールバック
    # フォールバック廃止: entries が 0 の場合でもそのまま出力

    today = dt.datetime.now().strftime("%Y%m%d")
    base_out = Path(__file__).parent / OUT_DIR_NAME / today
    images_dir = base_out / "images"
    csv_path = base_out / "anime_list.csv"
    saved = download_images(entries, images_dir)
    _log(f"download images saved={saved}")
    write_csv(entries, csv_path)
    _log("csv written")
    # ステータス行を簡易的に追記 (再実行確認しやすいように)
    status_path = base_out / "_status.txt"
    status_lines = [
        f"entries={len(entries)}",
        f"saved_images={saved}",
        f"used_local={used_local}",
    ]
    if live_err:
        status_lines.append(f"live_warn={live_err}")
    if used_dynamic:
        status_lines.append("used_dynamic=1")
    status_path.write_text(" ".join(status_lines) + "\n", encoding="utf-8")
    # run.log へ書き出し
    run_log_path = base_out / "run.log"  # ログも Excel で開きやすいよう BOM 付き
    try:
        run_log_path.write_text("\n".join(logs) + "\n", encoding="utf-8-sig")
    except Exception:
        pass
    return ScrapeResult(
        csv_path=csv_path,
        entries=entries,
        used_local=used_local,
        used_dynamic=used_dynamic,
        run_log_path=run_log_path,
        logs=logs,
    )


def _cli():  # 簡易CLI (開発/デバッグ用)
    import argparse

    parser = argparse.ArgumentParser(
        description="dアニメ 今期アニメリスト スクレイパー (version %s)" % __version__
    )
    parser.add_argument(
        "--dynamic",
        action="store_true",
        help="静的取得が 0 件だった場合に Playwright で動的 DOM を再取得する",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="バージョンを表示して終了",
    )
    args = parser.parse_args()

    try:
        if args.version:
            print(__version__)
            return
        result = run_scrape(dynamic=args.dynamic)
        print(
            f"CSV 出力: {result.csv_path} (件数: {len(result.entries)} | used_local={result.used_local})"
        )
        if result.used_dynamic:
            print("(dynamic fetch used)")
        print(f"run.log: {result.run_log_path}")
    except LoginRequiredError as e:
        print(f"ログインが必要かもしれません: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:  # noqa
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
