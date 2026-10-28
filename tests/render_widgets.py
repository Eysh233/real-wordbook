"""开发辅助：不显示窗口，直接把控件渲染成 PNG（字体正常，不打断桌面操作）。

用法：python tests/render_widgets.py [输出目录]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QRect, Qt  # noqa: E402
from PyQt5.QtGui import QPixmap  # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

from app import config  # noqa: E402
from app.repositories import BooksRepo, RecordsRepo, StatsRepo, WordsRepo  # noqa: E402
from app.services import quiz as quiz_service  # noqa: E402
from app.ui import theme  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "shots"


def grab(widget, name, size=None):
    if size:
        widget.resize(*size)
    widget.ensurePolished()
    if widget.layout() is not None:
        widget.layout().activate()
    widget.repaint()
    pix = QPixmap(widget.size())
    pix.fill(Qt.transparent)
    widget.render(pix)
    path = OUT / ("%s.png" % name)
    pix.save(str(path))
    print("saved", path, pix.width(), "x", pix.height())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    theme.set_theme(config.THEME_PAPER)
    app.setStyleSheet(theme.qss())

    from app.ui.action_popover import ActionPopover
    from app.ui.book_panel import BookPanel
    from app.ui.card_session import CardSession, SessionItem
    from app.ui.stats_page import StatsPage

    stage = QWidget()
    stage.resize(1240, 860)
    stage.setObjectName("root")
    stage.setStyleSheet("QWidget#root { background: %s; }" % theme.css("desk"))

    words_repo = WordsRepo()
    words = words_repo.sorted_words()
    book_words = [w for w in words if w.word.lower() == "resilient"] or words[:1]

    # 1. 抽背卡片：未揭晓 / 已揭晓
    items = [
        SessionItem(word=w.word, meaning_cn=w.meaning_cn, phonetic=w.phonetic, pos=w.pos, note=w.note, example="", no="", ref=w.id)
        for w in quiz_service.weighted_order(words)[:5]
    ]
    session = CardSession(items, stage, title="抽背 · 我的单词本", allow_register=False, reduced_motion=True)
    session.present()
    grab(session, "11-session-question")
    session.reveal()
    grab(session, "12-session-revealed")
    session.hide()

    # 2. 单词书卡片（背书模式，含登记按钮）
    book_items = [
        SessionItem(word=w.word, meaning_cn=w.meaning_cn, phonetic=w.phonetic, pos=w.pos, note=w.note,
                    example="The agreement is fragile.", no="0007", ref="0007")
        for w in words[:3]
    ]
    study = CardSession(book_items, stage, title="背书 · 基础 500 词（示例）", allow_register=True, reduced_motion=True)
    study.present()
    study.reveal()
    grab(study, "13-book-session")
    study.hide()

    # 3. 词条浮层（普通 / AI 报错态）
    if book_words:
        popover = ActionPopover(stage)
        popover.open_for(book_words[0], QRect(200, 200, 190, 66))
        grab(stage, "14-popover")
        popover.set_ai_error("还没有配置 DeepSeek API Key，点右上角 ⋯ → 设置。")
        grab(stage, "15-popover-ai")
        popover.close_popover()

    # 4. 统计页
    stats_page = StatsPage()
    stats_page.refresh(words, StatsRepo())
    grab(stats_page, "16-stats", (1240, 860))

    # 5. 单词书列表
    books = BooksRepo()
    records = RecordsRepo()
    panel = BookPanel(records)
    pairs = [(book, records.progress(book)) for book in books.list_books()]
    panel.set_books(pairs)
    grab(panel, "17-books", (1240, 860))

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
