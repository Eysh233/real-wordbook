"""开发辅助：把主要界面离屏渲染成 PNG，便于检查排版。

用法：python tests/render_shots.py [输出目录]
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.ui import theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "shots"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    theme.set_theme(config.THEME_PAPER)
    app.setStyleSheet(theme.qss())
    win = MainWindow()
    win.resize(1240, 860)
    win.show()
    app.processEvents()

    def shot(widget, name):
        widget.repaint()
        app.processEvents()
        pix = widget.grab()
        path = OUT / ("%s.png" % name)
        pix.save(str(path))
        print("saved", path, pix.width(), "x", pix.height())

    shot(win, "01-notebook")

    word = win.words_repo.find("resilient") or (win._words[0] if win._words else None)
    if word is not None:
        win._open_word(word)
        app.processEvents()
        shot(win, "02-popover")

        win._explain_word(word)
        app.processEvents()
        shot(win, "03-popover-ai-error")
        win._close_popover()
        app.processEvents()

    if win._words:
        win.start_quiz()
        app.processEvents()
        session = win._session
        if session is not None:
            shot(win, "04-session-question")
            session.reveal()
            app.processEvents()
            shot(win, "05-session-revealed")
            session.close_session()
            app.processEvents()

    win._on_nav("study")
    app.processEvents()
    shot(win, "06-books")
    win._on_nav("stats")
    app.processEvents()
    shot(win, "07-stats")
    win._on_nav("book")
    app.processEvents()

    from app.ui.dialogs import AddWordDialog
    from app.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(win.settings, win.secret_repo, win)
    dialog.show()
    app.processEvents()
    shot(dialog, "08-settings")
    dialog.close()

    add = AddWordDialog(win)
    add.show()
    app.processEvents()
    shot(add, "09-add-word")
    add.close()

    for name in (config.THEME_GREEN, config.THEME_DARK):
        win.settings.theme = name
        win._apply_theme()
        app.processEvents()
        shot(win, "10-theme-%s" % name)
    win.settings.theme = config.THEME_PAPER
    win._apply_theme()
    app.processEvents()

    win.close()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
