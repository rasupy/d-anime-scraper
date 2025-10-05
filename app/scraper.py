import csv
import os
import sys
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import requests
from bs4 import (
    BeautifulSoup,
)  # 用途: 作品詳細ページから <div class="streamingDate"> を抽出

# 動的ロードのためページ HTML では作品一覧が存在しない。
# 公式 JS 解析より TV 連動ラインナップ API (WS000118) を利用。
# cours=YYYY + season code (01: winter, 02: spring, 03: summer, 04: fall)
PAGE_URL = "https://animestore.docomo.ne.jp/animestore/CF/fall"
API_URL = "https://animestore.docomo.ne.jp/animestore/rest/WS000118"
ADDDATA_BASE = "https://animestore.docomo.ne.jp/js/cms"


# 現在期 (例: 2025年秋 -> 2025 + 04)
def current_cours_code(dt: datetime) -> str:
    # 月からシーズン判定: 1-3=01, 4-6=02, 7-9=03, 10-12=04
    m = dt.month
    if 1 <= m <= 3:
        c = "01"
    elif 4 <= m <= 6:
        c = "02"
    elif 7 <= m <= 9:
        c = "03"
    else:
        c = "04"
    return f"{dt.year}{c}"


USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
TIMEOUT = 15

# 曜日 id と日本語表示対応（ページ内の weekText id 属性に合わせる）
WEEK_ID_TO_JP = {
    "monday": "月曜",
    "tuesday": "火曜",
    "wednesday": "水曜",
    "thursday": "木曜",
    "friday": "金曜",
    "saturday": "土曜",
    "sunday": "日曜",
}

HEADERS = {"User-Agent": USER_AGENT}


def fetch_json_lineup(cours: str) -> Dict:
    params = {
        "cours": cours,
        "includeOthersFlag": "1",
        "tvProgramFlag": "1",
        "vodTypeList": "svod_tvod",
    }
    resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def parse_api(json_data: Dict) -> List[Dict[str, str]]:
    """API JSON から必要項目を抽出して行リストを返す"""
    work_list = json_data.get("data", {}).get("workList", [])
    results: List[Dict[str, str]] = []
    week_map = {
        "mon": "月曜",
        "tue": "火曜",
        "wed": "水曜",
        "thu": "木曜",
        "fri": "金曜",
        "sat": "土曜",
        "sun": "日曜",
        "oth": "その他",
    }
    for w in work_list:
        info = w.get("workInfo", {})
        title = info.get("workTitle", "").strip()
        if not title:
            continue
        week_en = info.get("workWeek", "")
        weekday = week_map.get(week_en, week_en)

        # 2025-10 現在: WS000118 レスポンスから schedule が消滅 (過去は YYYY/MM/DD 形式)
        # → 放送開始日を取得できないため後段で追加 JSON / 詳細補完を行う。
        schedule = info.get("schedule") or ""
        broadcast_display = ""
        broadcast_jp = ""
        if schedule and re.match(r"\d{4}/\d{1,2}/\d{1,2}", schedule):
            _, m, d = schedule.split("/")
            m_i, d_i = int(m), int(d)
            broadcast_display = f"{m_i:02d}/{d_i:02d}"
            broadcast_jp = f"{m_i}月{d_i}日～"

        img = (info.get("mainKeyVisualPath") or "").split("?")[0]
        link = info.get("link") or ""

        results.append(
            {
                "weekday": weekday,
                "broadcast": broadcast_display,  # 旧スタイル (内部参照)
                "broadcast_jp": broadcast_jp,  # CSV 出力用
                "title": title,
                "image_url": img,
                "detail_link": link,
            }
        )
    return results


def fetch_streaming_date(detail_url: str) -> Optional[str]:
    """作品詳細ページから <div class="streamingDate">10月6日～</div> を抽出して返す。

    Returns: '10月6日～' 形式の文字列 または None
    """
    if not detail_url:
        return None
    try:
        resp = requests.get(detail_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception:
        return None
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        el = soup.select_one("div.streamingDate")
        if not el:
            return None
        txt = el.get_text(strip=True)
        # 期待形: '10月6日～' / '10月??日～' 等。ざっくりバリデーション。
        if re.match(r"\d{1,2}月\d{1,2}日?～?", txt):
            # 統一して末尾に '～' を付ける (なければ)
            if not txt.endswith("～"):
                txt += "～"
            return txt
        return None
    except Exception:
        return None


def enrich_streaming_dates(rows: List[Dict[str, str]], sleep_sec: float = 0.3):
    """schedule が取れず broadcast_jp が空の行について、詳細ページを参照して補完する。

    - 重複する detail_link はキャッシュしてリクエストを抑制
    - SKIP_DETAIL=1 が環境変数にあればスキップ
    """
    if os.environ.get("SKIP_DETAIL") == "1":
        return
    cache: Dict[str, Optional[str]] = {}
    for r in rows:
        if r.get("broadcast_jp"):
            continue
        link = r.get("detail_link") or ""
        if not link:
            continue
        if link not in cache:
            date_txt = fetch_streaming_date(link)
            cache[link] = date_txt
            # 軽いクールダウン (過度な連続アクセスを避ける)
            time.sleep(sleep_sec)
        else:
            date_txt = cache[link]
        if date_txt:
            # '10月6日～' → broadcast_display も内部用に MM/DD へ派生させておく (ソート用)
            m_d = re.findall(r"(\d{1,2})月(\d{1,2})日", date_txt)
            if m_d:
                m_i, d_i = map(int, m_d[0])
                r["broadcast"] = f"{m_i:02d}/{d_i:02d}"
            r["broadcast_jp"] = date_txt


def enrich_adddata_schedules(rows: List[Dict[str, str]], cours_code: str):
    """追加 JSON (new_tv_adddata_<season>.json) から workId->workmaintxt を取得し放送日を補完。

    cours_code: 'YYYY0X' 形式。末尾 01..04 → winter/spring/summer/fall
    JSON 例: [{"workmaintxt":"2025年10月6日(月)18:00～","worklink":"#/animestore/ci?workId=28251", ... }]
    """
    if os.environ.get("SKIP_ADDDATA") == "1":
        return
    season_map = {"01": "winter", "02": "spring", "03": "summer", "04": "fall"}
    season_code = cours_code[-2:]
    season_slug = season_map.get(season_code)
    if not season_slug:
        return
    url = f"{ADDDATA_BASE}/new_tv_adddata_{season_slug}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return
    # workId -> (month, day)
    id_to_md: Dict[str, tuple] = {}
    pattern = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        wt = item.get("workmaintxt") or ""
        m = pattern.search(wt)
        if not m:
            continue
        month = int(m.group(2))
        day = int(m.group(3))
        link = item.get("worklink") or ""
        # worklink 例: '#/animestore/ci?workId=28251'
        wm = re.search(r"workId=(C?\d+)", link)
        if not wm:
            continue
        work_id = wm.group(1)
        id_to_md[work_id] = (month, day)
    if not id_to_md:
        return
    # 詳細リンクから workId を抽出し rows を更新
    updated = 0
    for r in rows:
        if r.get("broadcast_jp"):
            continue
        detail = r.get("detail_link") or ""
        m = re.search(r"workId=(C?\d+)", detail)
        if not m:
            continue
        wid = m.group(1)
        if wid in id_to_md:
            month, day = id_to_md[wid]
            r["broadcast"] = f"{month:02d}/{day:02d}"
            r["broadcast_jp"] = f"{month}月{day}日～"
            updated += 1
    if os.environ.get("DEBUG") == "1":
        print(f"[DEBUG] enrich_adddata_schedules updated={updated} (source={url})")


def ensure_output_dir(base: Path) -> Path:
    today = datetime.now().strftime("%Y%m%d")
    out_dir = base / today
    img_dir = out_dir / "image"
    img_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def save_csv(rows: List[Dict[str, str]], out_csv: Path):
    """曜日ごとにまとめた CSV を出力

    形式 (例):
    月曜,,
    放送日,タイトル,画像URL
    10月6日～,不滅のあなたへ Season3,https://...
    (空行)
    火曜,,
    放送日,タイトル,画像URL
    ...
    """
    # 曜日表示の並び順
    order = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜", "その他"]
    grouped: Dict[str, List[Dict[str, str]]] = {k: [] for k in order}
    for r in rows:
        grouped.setdefault(r["weekday"], []).append(r)

    # 各グループ内で開始日 + タイトルでソート（開始日が無いものは後ろ）
    for k, lst in grouped.items():

        def sort_key(x):
            # broadcast (MM/DD) が空なら大きな値で後ろへ
            b = x.get("broadcast") or "99/99"
            return b, x.get("title")

        lst.sort(key=sort_key)

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for weekday in order:
            lst = grouped.get(weekday) or []
            if not lst:
                continue
            # 見出し行 (曜日)
            writer.writerow([weekday, "", ""])
            # カラムヘッダ
            writer.writerow(["放送日", "タイトル", "画像URL"])
            for r in lst:
                writer.writerow(
                    [
                        r.get("broadcast_jp", ""),
                        r["title"],
                        r["image_url"],
                    ]
                )
            # グループ間の空行
            writer.writerow([])


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠_.-]", "_", name)[:80]


def download_images(rows: List[Dict[str, str]], img_dir: Path):
    for r in rows:
        url = r.get("image_url")
        if not url:
            continue
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
        except Exception:
            continue
        ext = ".png"
        if ".jpg" in url.lower() or ".jpeg" in url.lower():
            ext = ".jpg"
        filename = sanitize_filename(r["title"]) + ext
        path = img_dir / filename
        try:
            with path.open("wb") as f:
                f.write(resp.content)
        except Exception:
            pass


def main():
    base_out = Path(__file__).resolve().parent.parent / "OUT"
    base_out.mkdir(exist_ok=True)
    out_dir = ensure_output_dir(base_out)
    csv_path = out_dir / "anime_list.csv"
    img_dir = out_dir / "image"

    cours = current_cours_code(datetime.now())
    print(f"[INFO] Fetching lineup API cours={cours}")
    json_data = fetch_json_lineup(cours)
    if os.environ.get("DEBUG") == "1":
        (out_dir / "raw.json").write_text(str(json_data)[:20000], encoding="utf-8")
        print(f"[DEBUG] Saved raw JSON -> {out_dir / 'raw.json'}")

    print("[INFO] Parsing API JSON ...")
    rows = parse_api(json_data)
    if os.environ.get("DEBUG") == "1":
        print(f"[DEBUG] Sample rows: {rows[:2]}")

    if not rows:
        print("[WARN] No data parsed.")
    else:
        print(f"[INFO] Parsed {len(rows)} items.")

    # 放送開始日補完 (API 欠落時)
    before_missing = sum(1 for r in rows if not r.get("broadcast_jp"))
    if before_missing > 0:
        print(f"[INFO] Enriching broadcast dates (missing={before_missing}) ...")
        enrich_adddata_schedules(rows, cours)
        after_adddata = sum(1 for r in rows if not r.get("broadcast_jp"))
        print(f"[INFO] After adddata enrichment missing={after_adddata}")
        if after_adddata > 0:
            enrich_streaming_dates(rows)
        after_missing = sum(1 for r in rows if not r.get("broadcast_jp"))
        print(f"[INFO] Enrichment done. still_missing={after_missing}")
        if os.environ.get("DEBUG") == "1":
            sampled = [r for r in rows if r.get("broadcast_jp")][:5]
            print(f"[DEBUG] Enriched samples: {sampled}")

    print(f"[INFO] Saving CSV -> {csv_path}")
    save_csv(rows, csv_path)

    print(f"[INFO] Downloading images -> {img_dir}")
    download_images(rows, img_dir)

    print("[INFO] Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
