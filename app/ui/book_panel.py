"""单词书面板：导入的词汇书列表、进度、开始背书入口。"""
from typing import Callable, List, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import Book
from ..repositories import RecordsRepo
from . import theme


class BookCard(QFrame):
    startRequested = pyqtSignal(object)
    exportRequested = pyqtSignal(object)
    removeRequested = pyqtSignal(object)
    revealRequested = pyqtSignal(object)

    def __init__(self, book: Book, progress: dict, parent=None) -> None:
        super().__init__(parent)
        self.book = book
        self.setObjectName("bookCard")
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 14)
        layout.setSpacing(7)

        head = QHBoxLayout()
        head.setSpacing(10)
        title = QLabel(book.title)
        title.setStyleSheet("font-size: %dpx; font-weight: 600; color: %s;" % (theme.scale(15), theme.css("ink")))
        head.addWidget(title)
        if book.level:
            level = QLabel(book.level)
            level.setStyleSheet(
                "background: rgba(127,110,88,26); color: %s; border-radius: 6px; padding: 1px 7px; font-size: %dpx;"
                % (theme.css("ink_soft"), theme.scale(10))
            )
            head.addWidget(level)
        head.addStretch(1)
        total = progress.get("total", len(book.words))
        meta = QLabel("共 %d 词 · 已显示 %d · 已登记 %d" % (total, progress.get("seen", 0), progress.get("registered", 0)))
        meta.setObjectName("faint")
        head.addWidget(meta)
        layout.addLayout(head)

        desc = book.description or "（未填写简介）"
        detail = QLabel(desc)
        detail.setWordWrap(True)
        detail.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("ink_soft"), theme.scale(11)))
        layout.addWidget(detail)

        bar = QProgressBar(self)
        bar.setTextVisible(False)
        bar.setFixedHeight(4)
        bar.setMaximum(max(1, total))
        bar.setValue(progress.get("seen", 0))
        layout.addWidget(bar)

        foot = QHBoxLayout()
        foot.setSpacing(6)
        file_label = QLabel(book.file)
        file_label.setObjectName("faint")
        foot.addWidget(file_label)
        foot.addStretch(1)
        start = QPushButton("开始背书")
        start.setObjectName("primary")
        start.setCursor(Qt.PointingHandCursor)
        start.clicked.connect(lambda: self.startRequested.emit(self.book))
        foot.addWidget(start)
        export = QPushButton("导出")
        export.setObjectName("link")
        export.setCursor(Qt.PointingHandCursor)
        export.setToolTip("另存为标准格式 Markdown")
        export.clicked.connect(lambda: self.exportRequested.emit(self.book))
        foot.addWidget(export)
        remove = QPushButton("移除")
        remove.setObjectName("link")
        remove.setCursor(Qt.PointingHandCursor)
        remove.clicked.connect(lambda: self.removeRequested.emit(self.book))
        foot.addWidget(remove)
        layout.addLayout(foot)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.revealRequested.emit(self.book)
        super().mouseDoubleClickEvent(event)


class BookPanel(QWidget):
    importRequested = pyqtSignal()
    openFolderRequested = pyqtSignal()
    startStudy = pyqtSignal(object)
    exportBook = pyqtSignal(object)
    removeBook = pyqtSignal(object)

    def __init__(self, records: RecordsRepo, parent=None) -> None:
        super().__init__(parent)
        self.records = records
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 18, 26, 18)
        root.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("单词书")
        title.setObjectName("h1")
        head.addWidget(title)
        self._count = QLabel("")
        self._count.setObjectName("faint")
        head.addSpacing(8)
        head.addWidget(self._count)
        head.addStretch(1)
        folder = QPushButton("打开文件夹")
        folder.setObjectName("link")
        folder.setCursor(Qt.PointingHandCursor)
        folder.clicked.connect(self.openFolderRequested.emit)
        head.addWidget(folder)
        import_btn = QPushButton("导入单词书")
        import_btn.setObjectName("ghost")
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.clicked.connect(self.importRequested.emit)
        head.addWidget(import_btn)
        root.addLayout(head)

        hint = QLabel(
            "导入的单词书只读保存在 StudyBook/，不会自动进入「我的单词本」；背到需要记的词，再点「登记到我的单词本」。"
        )
        hint.setObjectName("faint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._holder = QWidget()
        self._holder.setStyleSheet("background: transparent;")
        self._list = QVBoxLayout(self._holder)
        self._list.setContentsMargins(0, 4, 8, 12)
        self._list.setSpacing(12)
        self._list.addStretch(1)
        self._scroll.setWidget(self._holder)
        root.addWidget(self._scroll, 1)

    def set_books(self, books: List[Tuple[Book, dict]]) -> None:
        while self._list.count():
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._count.setText("· %d 本" % len(books) if books else "")
        if not books:
            empty = QLabel(
                "还没有导入单词书。\n\n把符合格式的 .md 文件放进 StudyBook/ 后点「导入单词书」，\n"
                "或直接导入任意位置的词书文件。格式见 docs/02-单词书文件格式规范.md。"
            )
            empty.setObjectName("faint")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: %s; font-size: %dpx; line-height: 170%%;" % (theme.css("ink_faint"), theme.scale(12)))
            self._list.addWidget(empty)
        else:
            for book, progress in books:
                card = BookCard(book, progress, self._holder)
                card.startRequested.connect(self.startStudy.emit)
                card.revealRequested.connect(self.startStudy.emit)
                card.exportRequested.connect(self.exportBook.emit)
                card.removeRequested.connect(self.removeBook.emit)
                self._list.addWidget(card)
        self._list.addStretch(1)
