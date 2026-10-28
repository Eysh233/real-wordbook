"""翻页期间的绘制耗时基准（无头，不需要桌面窗口）。

用法：python tests/bench_paint.py
输出：静止 / 翻页中 两种状态下整窗重绘的平均毫秒数与等效帧率。
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402
from PyQt5.QtGui import QPixmap  # noqa: E402

from app import config  # noqa: E402
from app.models import Word  # noqa: E402
from app.ui import motion, theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def _isolate() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="rw-bench-"))
    config.DATA_DIR = tmp / "data"
    config.BOOKS_CACHE_DIR = config.DATA_DIR / "books"
    config.BACKUP_DIR = config.DATA_DIR / "backup"
    config.WORDS_FILE = config.DATA_DIR / "words.json"
    config.SETTINGS_FILE = config.DATA_DIR / "settings.json"
    config.AI_CACHE_FILE = config.DATA_DIR / "ai_cache.json"
    config.STATS_FILE = config.DATA_DIR / "stats.json"
    config.SECRET_FILE = tmp / "config.json"
    config.STUDYBOOK_DIR = tmp / "StudyBook"
    config.RECORD_DIR = tmp / "StudyRecord"
    config.ensure_dirs()


def _words(n: int):
    out = []
    for i in range(n):
        out.append(
            Word(
                id="w_%06d" % (i + 1),
                word="word%02d" % i,
                meaning_cn="释义 %d 号" % i,
                phonetic="/wɜːd/",
                pos="n.",
                weight=3,
                date_added="2026-10-28",
                created_at="2026-10-28T09:00:00",
            )
        )
    return out


def _time_render(win, frames: int = 40) -> float:
    pix = QPixmap(win.width(), win.height())
    win.render(pix)  # 预热
    start = time.perf_counter()
    for _ in range(frames):
        win.render(pix)
    return (time.perf_counter() - start) * 1000.0 / frames


def main() -> int:
    _isolate()
    app = QApplication(sys.argv)
    theme.set_theme("paper")
    app.setStyleSheet(theme.qss())
    motion.set_reduced(False)

    win = MainWindow()
    win.resize(1240, 860)
    win.show()
    app.processEvents()
    win.view.set_words(_words(60))
    app.processEvents()

    static_ms = _time_render(win)

    view = win.view
    view._turn_mode = "out"
    view._turn_p = 0.5
    view._take_cell_shots()
    app.processEvents()
    turning_ms = _time_render(win)

    view._clear_turn()
    win.close()
    print("静止   %.2f ms/帧  ≈ %d fps" % (static_ms, round(1000.0 / static_ms)))
    print("翻页中 %.2f ms/帧  ≈ %d fps" % (turning_ms, round(1000.0 / turning_ms)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
