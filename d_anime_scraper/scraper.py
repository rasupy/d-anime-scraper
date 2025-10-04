"""Core scraping logic for d-anime current season list.

Enhancements in 0.6.0:
 - Switched to standard logging (module logger name: d_anime_scraper.scraper)
 - Parallel image downloads (ThreadPoolExecutor) with limited concurrency
 - Structure change detection (warn when zero entries & weekWrapper present / or signature missing)
 - Package layout (d_anime_scraper.*)
"""

from __future__ import annotations

import contextlib
import csv
import datetime as dt
import logging
import os
import re
import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import requests

from .version import __version__

try:  # Third-party optional
    from bs4 import BeautifulSoup, Tag  # type: ignore
except Exception:  # pragma: no cover
    print(
        "[ERROR] beautifulsoup4 がインストールされていません。'pip install beautifulsoup4 lxml' を実行してください.",
        file=sys.stderr,
    )
    raise

LOGGER = logging.getLogger(__name__)

FALL_PAGE_URL = "https://animestore.docomo.ne.jp/animestore/CF/fall"
LIVE_HTML = Path(__file__).with_name("_live.html")  # 毎実行時に最新取得HTMLを上書き
OUT_DIR_NAME = "OUT"


class LoginRequiredError(RuntimeError):
    """Raised when the target page could not be accessed (likely login required)."""


@dataclass
class AnimeEntry:
    weekday: str
    start_date: str
    title: str
    image_url: str
    image_filename: str
    variants: list[str]


@dataclass
class ScrapeResult:
    csv_path: Path
    entries: list[AnimeEntry]
    used_local: bool
    used_dynamic: bool
    run_log_path: Path
    logs: list[str]
    structure_warning: str | None = None


def slugify(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\s/\\]+", "_", text)
    text = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠_ー-]", "", text)
    return text[:60] if len(text) > 60 else text


def fetch_live_html(timeout: float = 15.0) -> tuple[str | None, str | None]:
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


def parse_entries(html: str) -> list[AnimeEntry]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one("#newContents")
    if not container:
        raise RuntimeError("新作コンテンツ領域(#newContents)が見つかりません")

    entries: list[AnimeEntry] = []
    week_wrappers = container.select("div.weekWrapper")
    for ww in week_wrappers:
        week_text_el = ww.select_one(".weekText")
        if not week_text_el:
            continue
        week_label = week_text_el.get_text(strip=True)
        weekday = week_label.replace("配信", "")
        if not weekday.endswith("曜"):
            continue
        item_wrapper = week_text_el.find_next_sibling(
            "div", class_=re.compile(r"itemWrapper")
        )
        if not item_wrapper:
            continue
        if not item_wrapper.select(
            "div.itemModule"
        ) and "配信作品はありません" in item_wrapper.get_text(strip=True):
            continue
        item_modules = item_wrapper.select("div.itemModule.list")
        for idx, module in enumerate(item_modules, start=1):
            start_el = module.select_one("header .streamingDate")
            start_date = start_el.get_text(strip=True) if start_el else ""
            title_el = module.select_one("p.newTVtitle span")
            title = title_el.get_text(strip=True) if title_el else ""
            img_el: Tag | None = module.select_one(".thumbnailArea img")
            variants: list[str] = []
            image_url = ""
            if img_el:
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


def _download_one(
    session: requests.Session, e: AnimeEntry, images_dir: Path, timeout: float
) -> bool:
    if not e.variants:
        return False
    target = images_dir / e.image_filename
    if target.exists():
        return False
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": FALL_PAGE_URL,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    for url in e.variants:
        try:
            r = session.get(url, timeout=timeout, headers=headers)
            if r.status_code == 200 and r.content:
                ext = os.path.splitext(url)[1].split("?")[0]
                if ext and ext.lower() not in (".php",):
                    new_target = target.with_suffix(ext)
                else:
                    new_target = target
                new_target.write_bytes(r.content)
                return True
        except Exception:
            continue
    return False


def download_images(
    entries: Iterable[AnimeEntry],
    images_dir: Path,
    timeout: float = 15.0,
    max_workers: int = 6,
) -> int:
    images_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    saved = 0
    # 並列数は過度な負荷を避け控えめ
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(_download_one, session, e, images_dir, timeout): e
            for e in entries
        }
        for fut in as_completed(futures):
            try:
                if fut.result():
                    saved += 1
            except Exception:
                continue
    return saved


def write_csv(entries: list[AnimeEntry], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    by_day: dict[str, list[AnimeEntry]] = {}
    for e in entries:
        by_day.setdefault(e.weekday, []).append(e)
    order = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]
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
        # 多少時間が掛かる可能性があるため待機。失敗は致命ではないので握りつぶす。
        with contextlib.suppress(Exception):
            await page.wait_for_selector("div.itemModule.list", timeout=8000)
        html = await page.content()
        await browser.close()
        return html


def run_scrape(dynamic: bool = False) -> ScrapeResult:
    used_local = False
    used_dynamic = False
    logs: list[str] = []
    structure_warning: str | None = None

    def _log(msg: str, level: int = logging.INFO):
        ts = dt.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        logs.append(line)
        LOGGER.log(level, msg)

    _log(f"run_scrape start mode={'dynamic' if dynamic else 'static'}")
    live_html, live_err = fetch_live_html()
    if live_html:
        _log(f"live fetch ok size={len(live_html)}")
        with contextlib.suppress(Exception):
            LIVE_HTML.write_text(live_html, encoding="utf-8")
        parse_html = live_html
    else:
        _log(f"live fetch failed: {live_err}", logging.ERROR)
        raise LoginRequiredError(f"ライブページ取得失敗: {live_err}")

    entries: list[AnimeEntry] = parse_entries(parse_html)
    _log(f"parsed entries={len(entries)} (static)")

    if not entries:
        # 構造変化簡易検出: weekWrapper が存在するのに itemModule が 0 など
        if "weekWrapper" in live_html and "itemModule" not in live_html:
            structure_warning = "構造変化の可能性 (weekWrapper あるが itemModule 無)"
        elif "weekText" not in live_html:
            structure_warning = "weekText 不在 (ログイン/構造変化)"
        if structure_warning:
            _log(structure_warning, logging.WARNING)

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
                with contextlib.suppress(Exception):
                    LIVE_HTML.write_text(dyn_html, encoding="utf-8")
        except Exception as e:
            _log(f"dynamic fetch failed: {e}", logging.WARNING)

    today = dt.datetime.now().strftime("%Y%m%d")

    def _determine_base_dir() -> Path:
        # 1) 明示指定 (環境変数) 優先
        env = os.environ.get("D_ANIME_SCRAPER_OUT_DIR")
        if env:
            try:
                return Path(env).expanduser().resolve()
            except Exception:
                pass  # フォールバック
        # 2) PyInstaller onefile 実行時: 展開先(_MEIPASS)ではなく exe 位置を基準にする
        if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
            return Path(sys.executable).resolve().parent
        # 3) 通常: プロジェクトルート (scraper.py の 2 つ上: repo ルート想定)
        return Path(__file__).resolve().parent.parent

    base_root = _determine_base_dir()
    base_out = base_root / OUT_DIR_NAME / today
    images_dir = base_out / "images"
    csv_path = base_out / "anime_list.csv"
    saved = download_images(entries, images_dir)
    _log(f"download images saved={saved}")
    write_csv(entries, csv_path)
    _log("csv written")
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
    if structure_warning:
        status_lines.append(f"structure_warning={structure_warning}")
    status_path.write_text(" ".join(status_lines) + "\n", encoding="utf-8")
    run_log_path = base_out / "run.log"
    with contextlib.suppress(Exception):
        run_log_path.write_text("\n".join(logs) + "\n", encoding="utf-8-sig")
    return ScrapeResult(
        csv_path=csv_path,
        entries=entries,
        used_local=used_local,
        used_dynamic=used_dynamic,
        run_log_path=run_log_path,
        logs=logs,
        structure_warning=structure_warning,
    )


def _cli():
    import argparse

    parser = argparse.ArgumentParser(
        description=f"dアニメ 今期アニメリスト スクレイパー (version {__version__})"
    )
    parser.add_argument(
        "--dynamic",
        action="store_true",
        help="静的取得が 0 件だった場合に Playwright で動的 DOM を再取得する",
    )
    parser.add_argument(
        "--out-dir",
        help="OUT フォルダの親ディレクトリを明示指定 (未指定時: exe 位置 or プロジェクトルート)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="バージョンを表示して終了",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        if args.version:
            print(__version__)
            return
        if args.out_dir:
            os.environ["D_ANIME_SCRAPER_OUT_DIR"] = args.out_dir
        result = run_scrape(dynamic=args.dynamic)
        print(
            f"CSV 出力: {result.csv_path} (件数: {len(result.entries)} | used_local={result.used_local})"
        )
        if result.used_dynamic:
            print("(dynamic fetch used)")
        if result.structure_warning:
            print(f"[WARN] {result.structure_warning}")
        print(f"run.log: {result.run_log_path}")
    except LoginRequiredError as e:
        print(f"ログインが必要かもしれません: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:  # noqa
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    _cli()
