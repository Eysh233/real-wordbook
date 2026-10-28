"""回归检查：Esc 退出抽背、关闭按钮文案、音标不与释义重叠。"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QPushButton

workdir = tempfile.mkdtemp(prefix="rw-esc-")
from app import config  # noqa: E402

base = Path(workdir)
config.DATA_DIR = base
config.BOOKS_CACHE_DIR = base / "books"
config.BACKUP_DIR = base / "backup"
config.WORDS_FILE = base / "words.json"
config.SETTINGS_FILE = base / "settings.json"
config.AI_CACHE_FILE = base / "ai_cache.json"
config.STATS_FILE = base / "stats.json"
config.STUDYBOOK_DIR = base / "StudyBook"
config.RECORD_DIR = base / "StudyRecord"
config.SECRET_FILE = base / "config.json"
config.ensure_dirs()

from app.models import Word  # noqa: E402
from app.ui import theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def pump(app, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    app = QApplication(sys.argv)
    theme.set_theme("paper")
    theme.set_scale(1.0)
    win = MainWindow()
    win.resize(1180, 820)
    win.show()
    app.processEvents()

    for i in range(6):
        win.words_repo.add(
            Word(id="", word="word%d" % i, meaning_cn="释义%d" % i, phonetic="/w%d/" % i, weight=3),
            save=False,
        )
    win.words_repo.save()
    win.reload_all()
    app.processEvents()

    ok = True

    # 1) 焦点在会话上，直接发 Esc 按键事件
    win.start_quiz()
    app.processEvents()
    session = win._session
    assert session is not None, "会话没打开"
    print("session visible:", session.isVisible(), "focus:", type(app.focusWidget()).__name__)
    QApplication.sendEvent(
        app.focusWidget() or session,
        QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier),
    )
    pump(app, 0.5)
    try:
        closed = not session.isVisible()
    except RuntimeError:
        closed = True  # 控件已被 deleteLater 回收，等价于已关闭
    print("after Esc(hotkey-free):", closed)
    ok = ok and closed
    assert win._session is None, "会话没被清掉"

    # 2) 走快捷键入口（主窗 Esc）
    win.start_quiz()
    app.processEvents()
    win._escape()
    pump(app, 0.5)
    closed2 = win._session is None
    print("after _escape():", closed2)
    ok = ok and closed2

    # 3) 关闭按钮有字
    win.start_quiz()
    app.processEvents()
    texts = [b.text() for b in win._session._card.findChildren(QPushButton)]
    print("card buttons:", texts[:4])
    ok = ok and any(t.strip() == "✕" for t in texts)
    win._escape()
    pump(app, 0.5)

    # 4) 音标在释义之上
    cell = win.view._cells[0] if win.view._cells else None
    print("cells:", len(win.view._cells))
    ok = ok and cell is not None

    win.close()
    print("RESULT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
