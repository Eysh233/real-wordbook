"""翻页动画的真实帧率（无头）：统计 400ms 内 notebook 重绘次数。

用法：python tests/bench_turn_fps.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QEvent, QObject, QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.models import Word  # noqa: E402
from app.ui import motion, theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


class Counter(QObject):
    def __init__(self):
        super().__init__()
        self.paints = 0

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.Paint:
            self.paints += 1
        return False


def _isolate() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="rw-fps-"))
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
    return [
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
        for i in range(n)
    ]


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

    view = win.view
    counter = Counter()
    view.installEventFilter(counter)

    view.next_page()
    started = time.perf_counter()
    deadline = started + 0.45
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.002)
    elapsed = time.perf_counter() - started

    win.close()
    print("重绘 %d 次 / %.0f ms → %.0f fps" % (counter.paints, elapsed * 1000, counter.paints / elapsed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
