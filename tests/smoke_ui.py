"""离屏冒烟测试：不弹任何对话框，验证主链路可构建、可交互。

用法：python tests/smoke_ui.py
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.models import Word  # noqa: E402
from app.ui import theme  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="rw-smoke-"))
config.DATA_DIR = TMP / "data"
config.BOOKS_CACHE_DIR = config.DATA_DIR / "books"
config.BACKUP_DIR = config.DATA_DIR / "backup"
config.WORDS_FILE = config.DATA_DIR / "words.json"
config.SETTINGS_FILE = config.DATA_DIR / "settings.json"
config.AI_CACHE_FILE = config.DATA_DIR / "ai_cache.json"
config.STATS_FILE = config.DATA_DIR / "stats.json"
config.RECORD_DIR = TMP / "StudyRecord"
config.STUDYBOOK_DIR = TMP / "StudyBook"
config.SECRET_FILE = TMP / "config.json"
config.ensure_dirs()

from app.repositories import BooksRepo, RecordsRepo  # noqa: E402
from app.services import book_parser  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def check(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print("  ok  %s" % message)


def main() -> int:
    app = QApplication(sys.argv[:1])
    theme.set_theme(config.THEME_PAPER)
    app.setStyleSheet(theme.qss())

    print("[1] 构建主窗口")
    win = MainWindow()
    win.resize(1180, 840)
    win.show()
    app.processEvents()
    check(win.view.total_pages() == 0, "空单词本 0 页（显示空态）")
    check(win.stack.currentIndex() == 0, "默认在我的单词本")

    print("[2] 登记三个单词")
    for word, meaning, pos in (
        ("serendipity", "意外发现珍奇事物的能力", "n."),
        ("resilient", "有韧性的；能恢复的", "adj."),
        ("abandon", "放弃；抛弃", "v."),
    ):
        win.words_repo.add(Word(id="", word=word, meaning_cn=meaning, pos=pos, tags=["smoke"]))
    win.reload_all()
    app.processEvents()
    check(len(win._words) == 3, "仓库存到 3 个词")
    check(win.view.total_pages() >= 1, "分页完成：%d 页" % win.view.total_pages())

    target = win.words_repo.find("resilient")
    rect = win.view.cell_rect(target.id)
    check(not rect.isNull(), "能定位词格矩形 %s" % (rect.getRect(),))

    print("[3] 打开浮层并标注 / 划线")
    win._open_word(target)
    app.processEvents()
    check(win._popover.isVisible(), "浮层已显示")
    win._toggle_highlight(target)
    app.processEvents()
    fresh = win.words_repo.get(target.id)
    check(fresh.highlight and fresh.weight == config.HIGHLIGHT_WEIGHT, "标注后权重 = 6")
    win._toggle_highlight(fresh)
    app.processEvents()
    fresh = win.words_repo.get(target.id)
    check(not fresh.highlight and fresh.weight == config.DEFAULT_WEIGHT, "取消标注后权重回到 3")
    win._toggle_strike(fresh)
    app.processEvents()
    fresh = win.words_repo.get(target.id)
    check(fresh.strike and fresh.weight == config.STRIKE_WEIGHT, "划线后权重 = 1")
    win._toggle_strike(fresh)
    app.processEvents()
    fresh = win.words_repo.get(target.id)
    check(not fresh.strike and fresh.weight == config.DEFAULT_WEIGHT, "取消划线与标注后权重回到 3")
    win._close_popover()
    app.processEvents()

    print("[4] 显示模式切换与搜索")
    win._on_mode(config.DISPLAY_EN)
    app.processEvents()
    win.search.setText("res")
    win._refresh_words()
    app.processEvents()
    check(len(win._filtered()) == 1, "搜索 “res” 命中 1 词")
    win.search.clear()
    win._on_mode(config.DISPLAY_BOTH)
    win._refresh_words()
    app.processEvents()

    print("[5] 抽背会话")
    win.start_quiz()
    app.processEvents()
    session = win._session
    check(session is not None and session.isVisible(), "抽背卡片已弹出")
    session.reveal()
    app.processEvents()
    session._answer(True)
    app.processEvents()
    check(win.stats_repo.data["quiz"]["total"] >= 1, "抽背计入统计")
    session.close_session()
    app.processEvents()
    check(win._session is None, "会话关闭后清理")

    print("[6] 导入单词书并背书")
    source = ROOT / "StudyBook" / "demo-basic-001.md"
    result = book_parser.parse_file(source)
    check(len(result.words) == 15, "示例书解析 15 词")
    book = book_parser.build_book(source, result, "2026-10-28T18:00:00")
    books = BooksRepo()
    records = RecordsRepo()
    books.save(book)
    records.ensure(book)
    win.reload_all()
    app.processEvents()
    win._on_nav("study")
    app.processEvents()
    check(win.stack.currentIndex() == 1, "切到单词书页")
    progress = records.progress(book)
    check(progress["total"] == 15, "记录文件预建 15 条")

    item = book.words[0]
    session_items = []
    from app.ui.card_session import CardSession, SessionItem

    for word in book.words[:5]:
        session_items.append(
            SessionItem(
                word=word.word,
                meaning_cn=word.meaning_cn,
                phonetic=word.phonetic,
                pos=word.pos,
                no=word.no,
                ref=word,
            )
        )
    book_session = CardSession(
        session_items,
        win._root,
        title="背书 · %s" % book.title,
        allow_register=True,
        on_seen=lambda it: records.mark_seen(book.book_id, it.no),
        on_register=lambda it: win._register_book_word(book, it),
        reduced_motion=True,
    )
    win._open_session(book_session)
    app.processEvents()
    book_session.reveal()
    app.processEvents()
    book_session._answer(True)
    book_session._register()
    app.processEvents()
    after = records.progress(book)
    check(after["seen"] >= 1, "已显示记录 +%d" % after["seen"])
    check(after["registered"] >= 1, "已登记记录 +%d" % after["registered"])
    book_session.close_session()
    app.processEvents()

    print("[7] 统计页与主题")
    win._on_nav("stats")
    app.processEvents()
    for name in (config.THEME_GREEN, config.THEME_DARK, config.THEME_PAPER):
        win.settings.theme = name
        win._apply_theme()
        app.processEvents()
        check(True, "主题 %s 渲染" % name)
    win._refresh_stats()
    app.processEvents()

    print("[8] 迷你窗")
    win.toggle_mini()
    app.processEvents()
    check(win._mini is not None and win._mini.isVisible(), "迷你窗已显示")
    win._mini.next_word()
    win._mini.toggle()
    app.processEvents()
    win.toggle_mini()
    app.processEvents()
    check(not win._mini.isVisible(), "迷你窗已隐藏")

    print("[9] 搜索过滤与标签")
    win._on_nav("book")
    app.processEvents()
    win.tag_combo.set_value("smoke", emit=True)
    win._refresh_words()
    app.processEvents()
    check(len(win._filtered()) == 3, "标签过滤到 3 词")
    win.tag_combo.set_value("", emit=True)
    win._refresh_words()
    app.processEvents()

    print("[10] 清空我的单词本")
    before = len(win.words_repo.all())
    removed = win._clear_wordbook()
    app.processEvents()
    check(removed == before and before > 0, "清空返回删除数 %d" % removed)
    check(not win.words_repo.all(), "单词本已空")
    check(win.stats_repo.accuracy() == 0.0, "抽背统计已重置")
    check(win.view.total_pages() == 0, "笔记本回到空状态")

    print("[11] 关闭窗口")
    win.close()
    app.processEvents()
    print("\nSMOKE OK · 临时目录 %s" % TMP)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        traceback.print_exc()
        code = 1
    sys.exit(code)
