"""主窗口：把笔记本、单词书、统计、抽背、设置串起来。"""
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import QPoint, QRect, Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config, storage
from ..models import Book, BookWord, Word
from ..repositories import BooksRepo, RecordsRepo, SecretRepo, SettingsRepo, StatsRepo, WordsRepo
from ..services import ai_client, book_parser, csv_io, quiz as quiz_service, tts
from . import motion, theme
from .action_popover import ActionPopover
from .ai_worker import AIWorker
from .book_panel import BookPanel
from .card_session import CardSession, SessionItem
from .dialogs import AddWordDialog, RootsDialog, SpellingDialog, StudyOptionsDialog
from .mini_window import MiniWindow
from .notebook_view import NotebookView
from .settings_dialog import SettingsDialog
from .stats_page import StatsPage
from .widgets import Segmented, Toast

PAGE_BOOK = 0
PAGE_STUDY = 1
PAGE_STATS = 2


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", (text or "").strip().lower()).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned[:64]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        config.ensure_dirs()

        self.words_repo = WordsRepo()
        self.settings_repo = SettingsRepo()
        self.secret_repo = SecretRepo()
        self.books_repo = BooksRepo()
        self.records_repo = RecordsRepo()
        self.stats_repo = StatsRepo()
        self.settings = self.settings_repo.settings

        self._words: List[Word] = []
        self._workers: List[AIWorker] = []
        self._session: Optional[CardSession] = None
        self._mini: Optional[MiniWindow] = None
        self._toast: Optional[Toast] = None

        self.setWindowTitle("%s · %s" % (config.APP_TITLE, config.APP_NAME))
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        if available is not None:
            width = min(1240, max(960, available.width() - 60))
            height = min(860, max(620, available.height() - 60))
            self.setMinimumSize(min(940, width), min(620, height))
        else:
            width, height = 1180, 820
            self.setMinimumSize(940, 620)
        self.resize(width, height)

        theme.set_theme(self.settings.theme)
        theme.set_scale(self.settings.font_scale)

        self._build_ui()
        self._apply_theme()
        self.reload_all()
        self._center()

    # ------------------------------------------------------------------ 构建
    def _build_ui(self) -> None:
        self._root = QWidget(self)
        self._root.setObjectName("root")
        self.setCentralWidget(self._root)

        outer = QVBoxLayout(self._root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        topbar = QFrame(self._root)
        topbar.setObjectName("topbar")
        bar = QHBoxLayout(topbar)
        bar.setContentsMargins(20, 12, 20, 10)
        bar.setSpacing(10)

        brand = QWidget(topbar)
        brand_box = QVBoxLayout(brand)
        brand_box.setContentsMargins(0, 0, 0, 0)
        brand_box.setSpacing(0)
        brand_title = QLabel("真实单词本")
        brand_title.setStyleSheet(
            "font-size: %dpx; font-weight: 600; letter-spacing: 0.3px;" % theme.fs(15)
        )
        brand_sub = QLabel("REAL WORDBOOK")
        brand_sub.setObjectName("faint")
        brand_sub.setStyleSheet("font-size: %dpx; letter-spacing: 1.4px;" % theme.fs(9))
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_sub)
        bar.addWidget(brand)
        bar.addSpacing(16)

        self.nav = Segmented([("book", "我的单词本"), ("study", "单词书"), ("stats", "统计")], "book", topbar)
        bar.addWidget(self.nav)
        bar.addStretch(1)

        self.search = QLineEdit(topbar)
        self.search.setPlaceholderText("搜索单词或中文")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(theme.scale(118))
        self.search.setMaximumWidth(theme.scale(210))
        self.search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bar.addWidget(self.search)

        self.tag_combo = QComboBox(topbar)
        self.tag_combo.setMinimumWidth(theme.scale(84))
        self.tag_combo.setMaximumWidth(theme.scale(112))
        self.tag_combo.addItem("全部标签", "")
        bar.addWidget(self.tag_combo)

        self.mode = Segmented(
            [
                (config.DISPLAY_BOTH, config.DISPLAY_LABELS[config.DISPLAY_BOTH]),
                (config.DISPLAY_EN, config.DISPLAY_LABELS[config.DISPLAY_EN]),
                (config.DISPLAY_CN, config.DISPLAY_LABELS[config.DISPLAY_CN]),
            ],
            self.settings.display_mode,
            topbar,
        )
        bar.addWidget(self.mode)

        add_btn = QPushButton("＋ 登记", topbar)
        add_btn.setObjectName("ghost")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.add_word)
        bar.addWidget(add_btn)

        self.quiz_btn = QPushButton("抽背", topbar)
        self.quiz_btn.setObjectName("primary")
        self.quiz_btn.setCursor(Qt.PointingHandCursor)
        self.quiz_btn.clicked.connect(self.start_quiz)
        bar.addWidget(self.quiz_btn)

        more_btn = QPushButton("⋯", topbar)
        more_btn.setObjectName("ghost")
        more_btn.setFixedWidth(theme.scale(38))
        more_btn.setCursor(Qt.PointingHandCursor)
        more_btn.setToolTip("更多")
        bar.addWidget(more_btn)
        self._build_menu(more_btn)

        outer.addWidget(topbar)

        self.stack = QStackedWidget(self._root)
        outer.addWidget(self.stack, 1)

        self.view = NotebookView(self.stack)
        self.stack.addWidget(self.view)

        self.book_panel = BookPanel(self.records_repo, self.stack)
        self.stack.addWidget(self.book_panel)

        self.stats_page = StatsPage(self.stack)
        self.stack.addWidget(self.stats_page)

        self._toast = Toast(self._root)
        self._popover: Optional[ActionPopover] = ActionPopover(self._root)
        self._popover.highlightToggled.connect(self._toggle_highlight)
        self._popover.strikeToggled.connect(self._toggle_strike)
        self._popover.explainRequested.connect(self._explain_word)
        self._popover.editRequested.connect(self._edit_word)
        self._popover.deleteRequested.connect(self._delete_word)
        self._popover.speakRequested.connect(self._speak_word)

        self._wire()

    def _build_menu(self, button: QPushButton) -> None:
        menu = QMenu(self)
        menu.addAction("拼写测试", self.spelling_test)
        menu.addAction("词根视图", self.open_roots)
        menu.addSeparator()
        menu.addAction("导入 CSV", self.import_csv)
        menu.addAction("导出 CSV", self.export_csv)
        menu.addSeparator()
        menu.addAction("桌面迷你窗", self.toggle_mini)
        menu.addAction("设置", self.open_settings)
        menu.addSeparator()
        menu.addAction("关于", self.show_about)
        button.setMenu(menu)

    def _wire(self) -> None:
        self.view.wordClicked.connect(self._open_word)
        self.view.backgroundClicked.connect(self._close_popover)
        self.view.pageChanged.connect(lambda *_: self._close_popover())
        self.nav.changed.connect(self._on_nav)
        self.mode.changed.connect(self._on_mode)
        self.search.textChanged.connect(lambda _t: self._search_timer.start())
        self.tag_combo.currentIndexChanged.connect(lambda _i: self._refresh_words())

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._refresh_words)

        self.book_panel.importRequested.connect(self.import_book)
        self.book_panel.openFolderRequested.connect(self.open_book_folder)
        self.book_panel.startStudy.connect(self.start_book)
        self.book_panel.exportBook.connect(self.export_book)
        self.book_panel.removeBook.connect(self.remove_book)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_word)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.search.setFocus())
        QShortcut(QKeySequence("Ctrl+Shift+M"), self, activated=self.toggle_mini)
        QShortcut(QKeySequence("Escape"), self, activated=self._escape)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)

    def _center(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        self.move(available.center().x() - self.width() // 2, max(available.top(), available.center().y() - self.height() // 2))

    # ------------------------------------------------------------------ 主题
    def _apply_theme(self) -> None:
        motion.set_reduced(bool(getattr(self.settings, "reduced_motion", False)))
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme.qss())
            font = QFont(theme.SANS)
            font.setPixelSize(int(theme.fs(13)))
            app.setFont(font)

    def _rebuild_ui(self) -> None:
        """主题/字号一变就整体重建：控件的颜色和字号都是在构造时从 token 取的。"""
        page = self.stack.currentIndex()
        query = self.search.text()
        tag = self.tag_combo.currentData()
        mode = self.mode.value()

        self._close_popover()
        old = self.takeCentralWidget()
        if old is not None:
            old.deleteLater()
        self._toast = None
        self._popover = None

        theme.set_theme(self.settings.theme)
        theme.set_scale(self.settings.font_scale)
        self._build_ui()
        self._apply_theme()
        self.reload_all()

        self.mode.set_value(mode, emit=False)
        self.view.set_mode(mode)
        self.search.setText(query)
        index = self.tag_combo.findData(tag)
        if index > 0:
            self.tag_combo.setCurrentIndex(index)
        self.stack.setCurrentIndex(page)
        self._on_nav(("book", "study", "stats")[page])

    # ------------------------------------------------------------------ 数据
    def reload_all(self) -> None:
        self._words = self.words_repo.all()
        self._refresh_tags()
        self._refresh_words()
        self._refresh_books()
        self._refresh_stats()

    def _refresh_tags(self) -> None:
        current = self.tag_combo.currentData()
        self.tag_combo.blockSignals(True)
        self.tag_combo.clear()
        self.tag_combo.addItem("全部标签", "")
        for tag in self.words_repo.tags():
            self.tag_combo.addItem(tag, tag)
        index = self.tag_combo.findData(current)
        self.tag_combo.setCurrentIndex(index if index >= 0 else 0)
        self.tag_combo.blockSignals(False)

    def _filtered(self) -> List[Word]:
        keyword = self.search.text().strip().lower()
        tag = self.tag_combo.currentData()
        result: List[Word] = []
        for word in self.words_repo.sorted_words():
            if tag and tag not in word.tags:
                continue
            if keyword:
                haystack = " ".join(
                    [word.word, word.meaning_cn, word.phonetic, word.note, " ".join(word.tags)]
                ).lower()
                if keyword not in haystack:
                    continue
            result.append(word)
        return result

    def _refresh_words(self) -> None:
        self._words = self.words_repo.all()
        words = self._filtered()
        self.view.set_mode(self.settings.display_mode)
        self.view.set_reduced_motion(self.settings.reduced_motion)
        self.view.set_words(words)
        self.view.update()

    def _refresh_books(self) -> None:
        pairs = []
        for book in self.books_repo.list_books():
            if not self.records_repo.path(book.book_id).exists():
                self.records_repo.ensure(book)
            pairs.append((book, self.records_repo.progress(book)))
        self.book_panel.set_books(pairs)

    def _refresh_stats(self) -> None:
        self.stats_page.refresh(self._words, self.stats_repo)

    def _toast_message(self, text: str, msec: int = 2200) -> None:
        if self._toast is not None:
            self._toast.show_message(text, msec)

    # ------------------------------------------------------------------ 顶栏交互
    def _on_nav(self, key: str) -> None:
        index = {"book": PAGE_BOOK, "study": PAGE_STUDY, "stats": PAGE_STATS}.get(key, PAGE_BOOK)
        self.stack.setCurrentIndex(index)
        self._close_popover()
        if index == PAGE_BOOK:
            self._refresh_words()
        elif index == PAGE_STUDY:
            self._refresh_books()
        elif index == PAGE_STATS:
            self._refresh_stats()

    def _on_mode(self, key: str) -> None:
        self.settings.display_mode = key
        self.settings_repo.settings = self.settings
        self.settings_repo.save()
        self.view.set_mode(key)

    def _escape(self) -> None:
        if self._session is not None and self._session.isVisible():
            self._session.close_session()
            return
        self._close_popover()

    # ------------------------------------------------------------------ 单词操作
    def _open_word(self, word: Word) -> None:
        fresh = self.words_repo.get(word.id) or word
        anchor = self.view.cell_rect(fresh.id)
        if anchor.isNull():
            anchor = QRect(self.view.mapToGlobal(QPoint(40, 80)), QRect(0, 0, 160, 60).size())
        self._popover.open_for(fresh, anchor)
        self.view.set_selected(fresh.id)

    def _close_popover(self) -> None:
        if self._popover is not None and self._popover.isVisible():
            self._popover.close_popover()
        self.view.set_selected("")

    def _reweight(self, word: Word) -> None:
        if word.highlight:
            word.weight = config.HIGHLIGHT_WEIGHT
        elif word.strike:
            word.weight = config.STRIKE_WEIGHT
        else:
            word.weight = config.DEFAULT_WEIGHT

    def _after_change(self, word: Word, message: str = "") -> None:
        self.words_repo.update(word)
        self.view.refresh_word(word)
        if self._popover is not None and self._popover.isVisible():
            self._popover.refresh_word(word)
        self._refresh_stats()
        if message:
            self._toast_message(message)

    def _toggle_highlight(self, word: Word) -> None:
        fresh = self.words_repo.get(word.id) or word
        fresh.highlight = not fresh.highlight
        self._reweight(fresh)
        self._after_change(fresh, "已标注（权重 6）" if fresh.highlight else "已取消标注（权重 3）")

    def _toggle_strike(self, word: Word) -> None:
        fresh = self.words_repo.get(word.id) or word
        fresh.strike = not fresh.strike
        self._reweight(fresh)
        self._after_change(fresh, "已划线（权重 1）" if fresh.strike else "已取消划线（权重 3）")

    def _speak_word(self, word: Word) -> None:
        fresh = self.words_repo.get(word.id) or word
        if not tts.available():
            self._toast_message("系统朗读不可用")
            return
        tts.speak(fresh.word, on_error=lambda message: self._toast_message(message))

    def _duplicate(self, text: str, exclude_id: str = "") -> bool:
        found = self.words_repo.find(text)
        return bool(found and found.id != exclude_id)

    def add_word(self) -> None:
        dialog = AddWordDialog(self, exists=self._duplicate)
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.data()
        word = Word(
            id="",
            word=data["word"],
            meaning_cn=data["meaning_cn"],
            phonetic=data["phonetic"],
            pos=data["pos"],
            tags=data["tags"],
            note=data["note"],
            weight=config.DEFAULT_WEIGHT,
        )
        self.words_repo.add(word)
        self.reload_all()
        self.nav.set_value("book", emit=False)
        self.stack.setCurrentIndex(PAGE_BOOK)
        self.view.goto(max(0, self.view.total_pages() - 1), animate=False)
        self._toast_message("已登记「%s」" % word.word)

    def _edit_word(self, word: Word) -> None:
        fresh = self.words_repo.get(word.id) or word
        dialog = AddWordDialog(self, word=fresh, exists=self._duplicate)
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.data()
        fresh.word = data["word"]
        fresh.meaning_cn = data["meaning_cn"]
        fresh.phonetic = data["phonetic"]
        fresh.pos = data["pos"]
        fresh.tags = data["tags"]
        fresh.note = data["note"]
        self._after_change(fresh, "已更新")
        self._refresh_tags()

    def _delete_word(self, word: Word) -> None:
        fresh = self.words_repo.get(word.id) or word
        answer = QMessageBox.question(
            self,
            "删除单词",
            "确定从「我的单词本」删除 %s 吗？此操作不可撤销。" % fresh.word,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._close_popover()
        self.words_repo.delete(fresh.id)
        self.reload_all()
        self._toast_message("已删除「%s」" % fresh.word)

    def _explain_word(self, word: Word) -> None:
        fresh = self.words_repo.get(word.id) or word
        model = self.settings.ai_model
        cache = ai_client.AICache()
        cached = fresh.ai or cache.get(fresh.word, model)
        if cached:
            if not fresh.ai:
                fresh.ai = cached
                self.words_repo.update(fresh)
            self._popover.show_ai(cached)
            return
        api_key = self.secret_repo.api_key
        if not api_key:
            self._popover.set_ai_error("还没有配置 DeepSeek API Key，点右上角 ⋯ → 设置。")
            return
        self._popover.set_ai_loading()
        worker = AIWorker(fresh, api_key, model, self.settings.ai_effort, self)
        worker.done.connect(self._on_ai_done)
        worker.failed.connect(self._on_ai_failed)
        worker.finished.connect(lambda w=worker: self._drop_worker(w))
        self._workers.append(worker)
        worker.start()

    def _drop_worker(self, worker: AIWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def _on_ai_done(self, word_id: str, data: Dict) -> None:
        fresh = self.words_repo.get(word_id)
        if fresh is None:
            return
        fresh.ai = data
        if not fresh.phonetic and data.get("phonetic"):
            fresh.phonetic = data["phonetic"]
        if not fresh.pos and data.get("pos"):
            fresh.pos = data["pos"]
        self.words_repo.update(fresh)
        try:
            ai_client.AICache().put(fresh.word, self.settings.ai_model, data)
        except OSError:
            pass
        self.view.refresh_word(fresh)
        if self._popover is not None and self._popover.isVisible() and self._popover.word is not None:
            if self._popover.word.id == word_id:
                self._popover.refresh_word(fresh)
                self._popover.show_ai(data)

    def _on_ai_failed(self, word_id: str, message: str) -> None:
        if self._popover is not None and self._popover.isVisible():
            self._popover.set_ai_error(message)

    # ------------------------------------------------------------------ 抽背
    def start_quiz(self) -> None:
        pool = self._filtered() or self.words_repo.all()
        if not pool:
            self._toast_message("单词本还是空的，先登记几个词吧")
            return
        queue = quiz_service.build_queue(pool)
        items = [
            SessionItem(
                word=item.word,
                meaning_cn=item.meaning_cn,
                phonetic=item.phonetic,
                pos=item.pos,
                note=item.note,
                example=(item.note.split("\n")[0] if item.note else ""),
                ref=item,
            )
            for item in queue
        ]
        session = CardSession(
            items,
            self._root,
            title="抽背 · 我的单词本",
            allow_register=False,
            on_review=self._on_quiz_review,
            reduced_motion=self.settings.reduced_motion,
        )
        self._open_session(session)

    def _on_quiz_review(self, item: SessionItem, known: bool) -> None:
        word = self.words_repo.get(item.ref.id)
        if word is None:
            return
        quiz_service.apply_review(word, known)
        word.seen_count += 1
        word.last_quiz_at = datetime.now().replace(microsecond=0).isoformat()
        self.words_repo.update(word)
        self.stats_repo.record_quiz(known)

    def _open_session(self, session: CardSession) -> None:
        if self._session is not None:
            self._session.deleteLater()
        self._session = session
        session.finished.connect(self._on_session_finished)
        session.present()

    def _on_session_finished(self, summary: Dict) -> None:
        if self._session is not None:
            self._session.deleteLater()
            self._session = None
        if summary and not summary.get("closed"):
            self._toast_message(
                "本轮 %d 词 · 认识 %d · 不认识 %d"
                % (summary.get("total", 0), summary.get("known", 0), summary.get("total", 0) - summary.get("known", 0)),
                2800,
            )
        self.reload_all()

    # ------------------------------------------------------------------ 单词书
    def import_book(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self, "导入单词书", str(config.STUDYBOOK_DIR), "Markdown (*.md)"
        )
        if not path_text:
            return
        path = Path(path_text)
        result = book_parser.parse_file(path)
        if not result.words:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except OSError as exc:
                QMessageBox.warning(self, "导入失败", "读取文件失败：%s" % exc)
                return
            result = book_parser.parse_markdown(text, fallback_title=path.stem)
        if not result.words:
            details = "\n".join(item.get("msg", "") for item in result.errors[:8]) or "没有解析到任何单词。"
            QMessageBox.warning(self, "导入失败", details)
            return
        problems = [item for item in result.errors if not item.get("fatal")]
        if problems:
            details = "\n".join(
                "第 %s 行：%s" % (item.get("line", "?"), item.get("msg", "")) for item in problems[:10]
            )
            answer = QMessageBox.question(
                self,
                "发现 %d 处问题" % len(problems),
                details + "\n\n仍然导入其余 %d 个单词？" % len(result.words),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return

        book = book_parser.build_book(path, result, datetime.now().replace(microsecond=0).isoformat())
        base_id = _slug(book.book_id) or _slug(path.stem) or "book-%s" % datetime.now().strftime("%H%M%S")
        book_id = base_id
        suffix = 2
        while self.books_repo.get(book_id) is not None:
            book_id = "%s-%d" % (base_id, suffix)
            suffix += 1
        book.book_id = book_id
        target = config.STUDYBOOK_DIR / ("%s.md" % book_id)
        try:
            if path.resolve() != target.resolve():
                storage.write_text(target, storage.read_text(path) or "")
        except OSError as exc:
            QMessageBox.warning(self, "导入失败", "复制到 StudyBook 失败：%s" % exc)
            return
        book.file = target.name
        self.books_repo.save(book)
        self.records_repo.ensure(book)
        self.reload_all()
        self.nav.set_value("study", emit=False)
        self._on_nav("study")
        self._toast_message("已导入《%s》· %d 词" % (book.title, len(book.words)), 2800)

    def open_book_folder(self) -> None:
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.STUDYBOOK_DIR)))

    def export_book(self, book: Book) -> None:
        default = str(Path.home() / ("%s.md" % book.book_id))
        path_text, _ = QFileDialog.getSaveFileName(self, "导出单词书", default, "Markdown (*.md)")
        if not path_text:
            return
        storage.write_text(Path(path_text), book_parser.to_markdown(book))
        self._toast_message("已导出到 %s" % Path(path_text).name)

    def remove_book(self, book: Book) -> None:
        answer = QMessageBox.question(
            self,
            "移除单词书",
            "移除《%s》？\nStudyBook/%s.md 与背诵记录会一起删除，已登记到单词本的词不受影响。"
            % (book.title, book.book_id),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.books_repo.delete(book.book_id)
        self.records_repo.delete(book.book_id)
        source = config.STUDYBOOK_DIR / ("%s.md" % book.book_id)
        if source.exists():
            try:
                source.unlink()
            except OSError:
                pass
        self._refresh_books()
        self._toast_message("已移除《%s》" % book.title)

    def start_book(self, book: Book) -> None:
        self.records_repo.ensure(book)
        progress = self.records_repo.progress(book)
        dialog = StudyOptionsDialog(book.title, len(book.words), progress, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        order = dialog.order()
        scope = dialog.scope()
        data = self.records_repo.load(book.book_id)
        picked: List[BookWord] = []
        for item in book.words:
            entry = data["words"].get(item.no, {})
            if scope == "unseen" and entry.get("seen"):
                continue
            if scope == "registered" and not entry.get("registered"):
                continue
            picked.append(item)
        if not picked:
            self._toast_message("这个范围里没有可背诵的单词")
            return
        if order == "random":
            random.shuffle(picked)
        else:
            picked.sort(key=lambda w: w.no)
        self.records_repo.save_session(book.book_id, order, 0)

        items = []
        for item in picked:
            example = ""
            if item.examples:
                first = item.examples[0]
                example = (first.get("en", "") + " " + first.get("cn", "")).strip()
            items.append(
                SessionItem(
                    word=item.word,
                    meaning_cn=item.meaning_cn,
                    phonetic=item.phonetic,
                    pos=item.pos,
                    note=item.note,
                    example=example,
                    no=item.no,
                    ref=item,
                    registered=bool(data["words"].get(item.no, {}).get("registered")),
                )
            )
        session = CardSession(
            items,
            self._root,
            title="背书 · %s" % book.title,
            allow_register=True,
            on_seen=lambda item, b=book: self.records_repo.mark_seen(b.book_id, item.no),
            on_register=lambda item, b=book: self._register_book_word(b, item),
            reduced_motion=self.settings.reduced_motion,
        )
        self._open_session(session)

    def _register_book_word(self, book: Book, item: SessionItem) -> bool:
        existing = self.words_repo.find(item.word)
        if existing is not None:
            self.records_repo.mark_registered(book.book_id, item.no, existing.id)
            self._toast_message("「%s」已在单词本里，已记为已登记" % item.word)
            return True
        word = Word(
            id="",
            word=item.word,
            meaning_cn=item.meaning_cn,
            phonetic=item.phonetic,
            pos=item.pos,
            note=item.note or item.example,
            source="book:%s#%s" % (book.book_id, item.no),
            weight=config.DEFAULT_WEIGHT,
        )
        self.words_repo.add(word)
        self.records_repo.mark_registered(book.book_id, item.no, word.id)
        self._refresh_words()
        self._refresh_books()
        self._refresh_stats()
        self._toast_message("已登记「%s」到我的单词本" % word.word)
        return True

    # ------------------------------------------------------------------ 其它功能
    def spelling_test(self) -> None:
        if not self._words:
            self._toast_message("单词本还是空的")
            return
        dialog = SpellingDialog(self._words, self)
        dialog.answered.connect(self._on_spell_answer)
        dialog.exec_()
        self.reload_all()

    def _on_spell_answer(self, word: Word, correct: bool) -> None:
        fresh = self.words_repo.get(word.id)
        if fresh is None:
            return
        quiz_service.apply_review(fresh, correct)
        fresh.seen_count += 1
        fresh.last_quiz_at = datetime.now().replace(microsecond=0).isoformat()
        self.words_repo.update(fresh)
        self.stats_repo.record_quiz(correct)

    def open_roots(self) -> None:
        if not self._words:
            self._toast_message("单词本还是空的")
            return
        RootsDialog(self._words, self).exec_()

    def import_csv(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(self, "导入 CSV", "", "CSV / 文本 (*.csv *.txt)")
        if not path_text:
            return
        rows, errors = csv_io.import_csv(Path(path_text))
        added = 0
        for row in rows:
            if self.words_repo.find(row.get("word", "")) is not None:
                continue
            self.words_repo.add(
                Word(
                    id="",
                    word=row.get("word", ""),
                    meaning_cn=row.get("meaning_cn", ""),
                    phonetic=row.get("phonetic", ""),
                    pos=row.get("pos", ""),
                    tags=row.get("tags") or [],
                    note=row.get("note", ""),
                    weight=config.DEFAULT_WEIGHT,
                ),
                save=False,
            )
            added += 1
        self.words_repo.save()
        self.reload_all()
        message = "导入 %d 词" % added
        if errors:
            message += "，%d 行有问题" % len(errors)
        self._toast_message(message, 2800)

    def export_csv(self) -> None:
        if not self._words:
            self._toast_message("还没有可导出的单词")
            return
        default = str(Path.home() / ("我的单词本-%s.csv" % datetime.now().strftime("%Y%m%d")))
        path_text, _ = QFileDialog.getSaveFileName(self, "导出 CSV", default, "CSV (*.csv)")
        if not path_text:
            return
        count = csv_io.export_csv(self._words, Path(path_text))
        self._toast_message("已导出 %d 词" % count)

    def toggle_mini(self) -> None:
        if self._mini is None:
            self._mini = MiniWindow(self)
            self._mini.openMain.connect(self._restore_from_mini)
        if self._mini.isVisible():
            self._mini.hide_window()
            return
        self._mini.set_words([w for w in self._words if w.word])
        self._mini.show_window()

    def _restore_from_mini(self) -> None:
        if self._mini is not None:
            self._mini.hide_window()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.secret_repo, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        new_settings = dialog.result_settings()
        key = dialog.key_to_save()
        if key:
            self.secret_repo.save_key(key)
        elif dialog.key_cleared():
            self.secret_repo.save_key("")
        self.settings = new_settings
        self.settings_repo.settings = new_settings
        self.settings_repo.save()
        self.mode.set_value(new_settings.display_mode, emit=False)
        self.view.set_mode(new_settings.display_mode)
        self._rebuild_ui()
        self._toast_message("设置已保存")

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "关于",
            "%s %s\n\n"
            "本地优先的英文单词本：登记、标注、抽背、单词书背诵与统计。\n"
            "数据目录：%s\n"
            "密钥文件：%s" % (config.APP_TITLE, config.APP_VERSION, config.DATA_DIR, config.SECRET_FILE),
        )

    # ------------------------------------------------------------------ 关闭
    def closeEvent(self, event):  # noqa: N802
        for worker in list(self._workers):
            worker.requestInterruption()
            worker.wait(400)
        if self._mini is not None:
            self._mini.hide_window()
        self.settings_repo.settings = self.settings
        self.settings_repo.save()
        event.accept()
