"""GUI ログウィンドウ付きランチャー

PyInstaller で exe 化を想定。--noconsole でもログを見える化するため
シンプルな tkinter Text を使う。
完了後 2 秒で自動終了。
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox
import os
import sys
import subprocess

from d_anime_scraper.scraper import LoginRequiredError, run_scrape, ScrapeResult
from d_anime_scraper.version import __version__


class LogWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"dアニメ 今期アニメ スクレイピング v{__version__}")
        self.text = tk.Text(self.root, width=90, height=24, state="disabled")
        self.text.pack(fill=tk.BOTH, expand=True)
        # Python 3.8 でも動くようコメント化 (型は参考)
        self.queue = queue.Queue()  # type: ignore[assignment]
        self._poll()

    def log(self, msg: str):
        self.queue.put(msg)

    def _poll(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                self.text.configure(state="normal")
                self.text.insert(tk.END, msg + "\n")
                self.text.see(tk.END)
                self.text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    def run(self):
        self.root.mainloop()

    def close_after(self, sec: float):
        def _delayed():
            time.sleep(sec)
            self.root.quit()

        threading.Thread(target=_delayed, daemon=True).start()


def main():
    win = LogWindow()

    def worker():
        win.log("[INFO] スクレイピング開始")
        try:
            result: ScrapeResult = run_scrape()
            win.log(
                f"[INFO] 完了 CSV: {result.csv_path} 件数={len(result.entries)} local={result.used_local}"
            )
            # _status.txt から画像保存数を読む
            try:
                status_file = result.csv_path.parent / "_status.txt"
                if status_file.exists():
                    status_text = status_file.read_text(encoding="utf-8").strip()
                    win.log("[INFO] " + status_text)
            except Exception:
                pass
            # run.log 末尾数行を表示
            if result.logs:
                tail = result.logs[-5:]
                for line in tail:
                    win.log(f"[LOG] {line}")
            if result.structure_warning:
                win.log(f"[WARN] {result.structure_warning}")
            if not result.entries:
                win.log("[INFO] 静的取得で 0 件 → 動的取得(dyanmic)を試行します")
                try:
                    dyn = run_scrape(dynamic=True)
                    win.log(
                        f"[INFO] dynamic 再取得 件数={len(dyn.entries)} used_dynamic={dyn.used_dynamic}"
                    )
                    if dyn.entries:
                        result = dyn
                    else:
                        win.log("[WARN] 動的取得でも 0 件でした")
                except Exception as e:  # noqa
                    win.log(f"[ERROR] dynamic fetch failed: {e}")
            # 出力フォルダ自動オープン
            try:
                out_dir = result.csv_path.parent
                if out_dir.exists():
                    win.log(f"[INFO] 出力フォルダを開きます: {out_dir}")
                    _open_folder(out_dir)
            except Exception as e:  # noqa
                win.log(f"[WARN] フォルダ自動オープン失敗: {e}")
            win.log("[INFO] ウィンドウは数秒後に閉じます...")
            win.close_after(4.0)
        except LoginRequiredError:
            messagebox.showwarning(
                "ログインしてください",
                "ページにアクセスできません。ブラウザでログイン済みか確認してください。",
            )
            win.log("[WARN] ログインが必要と思われるため中断")
        except Exception as e:  # noqa
            win.log(f"[ERROR] {e}")
            messagebox.showerror("エラー", str(e))

    threading.Thread(target=worker, daemon=True).start()
    win.run()


if __name__ == "__main__":
    main()


def _open_folder(path):  # 定義を末尾に配置して import 時 accidental 実行を避ける
    """OSごとにフォルダを開く。失敗は例外送出せず握りつぶす。"""
    try:
        p = str(path)
        if sys.platform.startswith("win"):
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
    except Exception:
        pass
