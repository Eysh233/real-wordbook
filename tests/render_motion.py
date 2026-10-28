"""渲染动效关键帧（不显示窗口，走真实字体平台）。

用法：python tests/render_motion.py
产物：docs/shots/21-turn-mid.png、22-tag-menu.png、23-notebook.png
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtGui import QPixmap  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="rw-motion-"))
    from app import config

    config.DATA_DIR = tmp / "data"
    config.BOOKS_CACHE_DIR = config.DATA_DIR / "books"
    config.BACKUP_DIR = config.DATA_DIR / "backup"
    config.STUDYBOOK_DIR = tmp / "StudyBook"
    config.RECORD_DIR = tmp / "StudyRecord"
    config.USER_DIR = tmp / "user"
    config.WORDS_FILE = config.DATA_DIR / "words.json"
    config.SETTINGS_FILE = config.DATA_DIR / "settings.json"
    config.AI_CACHE_FILE = config.DATA_DIR / "ai_cache.json"
    config.STATS_FILE = config.DATA_DIR / "stats.json"
    config.SECRET_FILE = config.USER_DIR / "config.json"
    config.ensure_dirs()

    from app import models
    from app.repositories import SettingsRepo, WordsRepo
    from app.ui import theme

    settings = SettingsRepo()
    settings.settings.theme = config.THEME_PAPER
    settings.save()
    repo = WordsRepo()
    samples = [
        ("abandon", "放弃；抛弃", "动词"),
        ("brief", "简短的；短暂的", "adj."),
        ("resilient", "有韧性的；能恢复的", "adj."),
        ("attain", "达到；获得", "v."),
        ("deliberate", "深思熟虑的；故意的", "adj."),
        ("fragile", "易碎的；脆弱的", "adj."),
        ("genuine", "真正的；真诚的", "adj."),
        ("hesitate", "犹豫；踌躇", "v."),
        ("inevitable", "不可避免的", "adj."),
        ("justify", "证明…正当", "v."),
        ("modest", "谦虚的；适度的", "adj."),
        ("persuade", "说服；劝说", "v."),
        ("reluctant", "不情愿的；勉强的", "adj."),
        ("sustain", "维持；支撑", "v."),
        ("vivid", "生动的；鲜明的", "adj."),
        ("wander", "漫游；走神", "v."),
        ("zeal", "热情；热忱", "n."),
        ("absorb", "吸收；使全神贯注", "v."),
    ]
    for index, (word, meaning, pos) in enumerate(samples):
        repo.add(
            models.Word(
                id="",
                word=word,
                meaning_cn=meaning,
                pos=pos,
                phonetic="/%s/" % word[:3],
                tags=["CET4"] if index % 3 == 0 else (["考研"] if index % 3 == 1 else []),
                highlight=index in (1, 8),
                strike=index in (5, 17),
            )
        )
        if index == 1:
            stored = repo.all()[-1]
            stored.weight = config.HIGHLIGHT_WEIGHT
            repo.update(stored)

    from app.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.resize(1240, 860)
    win.reload_all()
    win.ensurePolished()
    win.layout().activate()
    theme.set_theme(config.THEME_PAPER)
    app.setStyleSheet(theme.qss())
    win.view.set_words(win._filtered())
    win.ensurePolished()
    win.view.ensurePolished()
    win.layout().activate()

    out = ROOT / "docs" / "shots"
    out.mkdir(parents=True, exist_ok=True)

    def save(widget, name: str) -> None:
        widget.ensurePolished()
        if widget.layout() is not None:
            widget.layout().activate()
        pix = QPixmap(widget.size())
        pix.fill(Qt.transparent)
        widget.render(pix)
        path = out / name
        pix.save(str(path), "PNG")
        print("saved", path, pix.width(), "x", pix.height())

    save(win, "23-notebook.png")

    # 翻页中间帧：强制停在 out 相 50%
    win.view._turn_mode = "out"
    win.view._turn_dir = 1
    win.view._turn_p = 0.5
    win.view._hide_cells(True)
    save(win, "21-turn-mid.png")
    win.view._clear_turn()

    # 标签菜单：直接把浮层抓下来
    if len(win.tag_combo._items) > 1:
        win.tag_combo._open()
        popup = win.tag_combo._popup
        if popup is not None:
            popup.adjustSize()
            panel = popup._panel
            panel.setGraphicsEffect(None)
            panel.adjustSize()
            save(panel, "22-tag-menu.png")
            win.tag_combo._close()

    win.close()
    print("done · 临时目录", tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
