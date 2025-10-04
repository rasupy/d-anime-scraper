import sys
from pathlib import Path

# ルートディレクトリをパスに追加 (pytest 実行位置に依存しない)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from d_anime_scraper import scraper  # noqa: E402


def test_slugify_basic():
    assert scraper.slugify("タイトル/テスト 01")


def test_parse_no_weekcontents():
    # 最低限の HTML (空) で newContents 無し -> エラー
    html = "<html><body><div id='newContents'></div></body></html>"
    # newContents は存在するが中身に weekWrapper が無いので entries=0
    entries = scraper.parse_entries(html)
    assert entries == []


def test_fetch_live_function_signature():
    html, err = scraper.fetch_live_html()  # ネット環境に依存するので内容は緩く検査
    assert isinstance(html, (str, type(None)))
    assert isinstance(err, (str, type(None)))


def test_run_scrape_monkeypatch_requests(monkeypatch):
    # ネットに依存しないよう fetch_live_html を差し替え
    sample_html = """
    <div id='newContents'>
      <div class='weekWrapper'>
        <div class='weekText'>月曜配信</div>
        <div class='itemWrapper'>
          <div class='itemModule list'>
            <header><span class='streamingDate'>10月6日～</span></header>
            <p class='newTVtitle'><span>サンプル作品</span></p>
            <div class='thumbnailArea'><img alt='http://example.com/a.png'/></div>
          </div>
        </div>
      </div>
    </div>
    """

    def fake_fetch_live_html(timeout: float = 15.0):
        return sample_html, None

    monkeypatch.setattr(scraper, "fetch_live_html", fake_fetch_live_html)

    result = scraper.run_scrape()
    assert len(result.entries) == 1
    assert result.entries[0].weekday == "月曜"
    assert result.csv_path.exists()
    assert result.run_log_path.exists()
    # 画像は alt を URL として扱うがダウンロードは試行し失敗するかもしれない (HTTP 404) ので件数で判断しない
