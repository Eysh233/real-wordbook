"""临时探针：快速划过多词后，所有词格的悬停值应回落到 0。"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtWidgets import QApplication

from app.models import Word
from app.ui import theme
from app.ui.notebook_view import NotebookView


def pump(app, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.004)


def main() -> int:
    app = QApplication(sys.argv)
    theme.set_theme("paper")
    theme.set_scale(1.0)
    view = NotebookView()
    view.resize(1180, 800)
    words = [
        Word(id="w%03d" % i, word="word%d" % i, meaning_cn="释义%d" % i, weight=3)
        for i in range(30)
    ]
    view.set_words(words)
    view.show()
    app.processEvents()

    cells = view._cells
    print("cells:", len(cells))

    # 1) 快速来回划：enter/leave 连续打断，模拟鼠标高速掠过
    for cell in cells:
        for _ in range(3):
            cell.enterEvent(QEvent(QEvent.Enter))
            pump(app, 0.012)
            cell.leaveEvent(QEvent(QEvent.Leave))
            pump(app, 0.012)

    pump(app, 0.6)
    stuck = [(c.word.word, round(c._hover_t, 3)) for c in cells if c._hover_t > 0.01]
    print("stuck after sweep:", stuck)

    # 2) 单个词悬停应能到 1.0，离开后回 0
    first = cells[0]
    first.enterEvent(QEvent(QEvent.Enter))
    pump(app, 0.4)
    peak = first._hover_t
    first.leaveEvent(QEvent(QEvent.Leave))
    pump(app, 0.4)
    rest = first._hover_t
    print("peak:", round(peak, 3), "rest:", round(rest, 3))

    ok = not stuck and peak > 0.99 and rest < 0.01
    print("RESULT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
