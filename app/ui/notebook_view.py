"""笔记本视图：纸页、装订脊、日期行、页脚、翻页。

行槽模型：日期行占一整行（1 槽），词行占一行（最多 5 词）。
"""
from typing import List, Optional

from PyQt5.QtCore import QElapsedTimer, QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QPushButton, QWidget

from .. import config
from ..models import Word
from ..services import paging
from . import painter_utils, theme
from .word_cell import WordCell

SPINE_W = 54
PAD_OUTER = 20
PAD_LEFT = 36
PAD_RIGHT = 34
PAD_TOP = 28
PAD_BOTTOM = 50


class NotebookView(QWidget):
    wordClicked = pyqtSignal(object)
    pageChanged = pyqtSignal(int, int)
    backgroundClicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all_words: List[Word] = []
        self._pages: List[paging.Page] = []
        self._index = 0
        self._mode = config.DISPLAY_BOTH
        self._reduced = False
        self._cells: List[WordCell] = []
        self._anim: Optional[QPropertyAnimation] = None
        self._effect: Optional[QGraphicsOpacityEffect] = None
        self._wheel_clock = QElapsedTimer()
        self._wheel_clock.start()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self._prev_btn = QPushButton("‹", self)
        self._prev_btn.setObjectName("pageNav")
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setToolTip("上一页（←）")
        self._prev_btn.clicked.connect(self.prev_page)
        self._next_btn = QPushButton("›", self)
        self._next_btn.setObjectName("pageNav")
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setToolTip("下一页（→）")
        self._next_btn.clicked.connect(self.next_page)
        self._sync_buttons()

    # ---------------------------------------------------------------- 数据
    def set_words(self, words: List[Word]) -> None:
        self._all_words = list(words)
        self._pages = paging.paginate_words(self._all_words)
        if self._index >= len(self._pages):
            self._index = max(0, len(self._pages) - 1)
        self._rebuild_cells()
        self.update()
        self.pageChanged.emit(self.page_number(), len(self._pages))

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        for cell in self._cells:
            cell.set_mode(mode)
        self.update()

    def set_reduced_motion(self, reduced: bool) -> None:
        self._reduced = reduced

    def page_number(self) -> int:
        return self._index + 1 if self._pages else 0

    def total_pages(self) -> int:
        return len(self._pages)

    def refresh_word(self, word: Word) -> None:
        for cell in self._cells:
            if cell.word.id == word.id:
                cell.set_word(word)
        self.update()

    def set_selected(self, word_id: str) -> None:
        for cell in self._cells:
            cell.set_selected(bool(word_id) and cell.word.id == word_id)

    def cell_rect(self, word_id: str) -> "QRect":
        from PyQt5.QtCore import QPoint, QRect

        for cell in self._cells:
            if cell.word.id == word_id:
                origin = cell.mapToGlobal(QPoint(0, 0))
                return QRect(origin.x(), origin.y(), cell.width(), cell.height())
        return QRect()

    # ---------------------------------------------------------------- 翻页
    def goto(self, index: int, animate: bool = True) -> None:
        if not self._pages:
            return
        target = max(0, min(len(self._pages) - 1, index))
        if target == self._index:
            return
        if not animate or self._reduced:
            self._index = target
            self._rebuild_cells()
            self.update()
            self.pageChanged.emit(self.page_number(), len(self._pages))
            return
        self._fade_to(target)

    def next_page(self) -> None:
        self.goto(self._index + 1)

    def prev_page(self) -> None:
        self.goto(self._index - 1)

    def _fade_to(self, target: int) -> None:
        if self._anim is not None:
            self._anim.stop()
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(100)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def halfway() -> None:
            self._index = target
            self._rebuild_cells()
            back = QPropertyAnimation(effect, b"opacity", self)
            back.setDuration(170)
            back.setStartValue(0.0)
            back.setEndValue(1.0)
            back.setEasingCurve(QEasingCurve.OutCubic)
            back.finished.connect(self._clear_effect)
            self._anim = back
            back.start()

        anim.finished.connect(halfway)
        self._anim = anim
        anim.start()

    def _clear_effect(self) -> None:
        self.setGraphicsEffect(None)
        self._effect = None
        self._anim = None

    # ---------------------------------------------------------------- 布局
    def _paper_rect(self) -> QRectF:
        return QRectF(PAD_OUTER, PAD_OUTER, max(10, self.width() - PAD_OUTER * 2), max(10, self.height() - PAD_OUTER * 2))

    def _content_rect(self) -> QRectF:
        paper = self._paper_rect()
        return QRectF(
            paper.left() + SPINE_W + PAD_LEFT,
            paper.top() + PAD_TOP,
            max(40.0, paper.width() - SPINE_W - PAD_LEFT - PAD_RIGHT),
            max(40.0, paper.height() - PAD_TOP - PAD_BOTTOM),
        )

    def _metrics(self):
        content = self._content_rect()
        rows = config.ROWS_PER_PAGE
        row_h = content.height() / rows
        gap = theme.scale(11)
        col_w = (content.width() - gap * (config.WORDS_PER_ROW - 1)) / config.WORDS_PER_ROW
        return content, row_h, col_w, gap

    def _rebuild_cells(self) -> None:
        for cell in self._cells:
            cell.hide()
            cell.setParent(None)
            cell.deleteLater()
        self._cells = []
        page = self._pages[self._index] if self._pages else None
        if page:
            for slot in page.slots:
                if slot.kind != "words":
                    continue
                for word in slot.words:
                    cell = WordCell(word, self._mode, self)
                    cell.clicked.connect(self.wordClicked.emit)
                    cell.show()
                    self._cells.append(cell)
        self._layout_cells()
        self._sync_buttons()

    def _layout_cells(self) -> None:
        if not self._cells:
            return
        content, row_h, col_w, gap = self._metrics()
        page = self._pages[self._index] if self._pages else None
        if not page:
            return
        cell_h = max(40, int(row_h - theme.scale(9)))
        index = 0
        for row, slot in enumerate(page.slots):
            if slot.kind != "words":
                continue
            for col, _word in enumerate(slot.words):
                if index >= len(self._cells):
                    break
                x = content.left() + col * (col_w + gap)
                y = content.top() + row * row_h + theme.scale(3)
                self._cells[index].setGeometry(int(x), int(y), int(col_w), cell_h)
                index += 1

    def _nav_geometry(self) -> None:
        paper = self._paper_rect()
        size = theme.scale(28)
        y = int(paper.bottom() - PAD_BOTTOM / 2 - size / 2 + 2)
        self._next_btn.setGeometry(int(paper.right() - PAD_RIGHT - size), y, size, size)
        self._prev_btn.setGeometry(int(paper.right() - PAD_RIGHT - size * 2 - 8), y, size, size)

    def _sync_buttons(self) -> None:
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(self._index < len(self._pages) - 1)
        self._prev_btn.setVisible(bool(self._pages))
        self._next_btn.setVisible(bool(self._pages))

    # ---------------------------------------------------------------- 绘制
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        paper = self._paper_rect()

        # 投影 + 纸面
        painter_utils.rounded_rect_shadow(painter, paper, QColor(30, 24, 16, 70), spread=3)
        painter.setPen(QPen(theme.color("rule"), 1))
        painter.setBrush(theme.color("paper"))
        painter.drawRoundedRect(paper, 13, 13)

        # 纸纹
        painter_utils.paper_grain(painter, paper, theme.color("rule"), seed=11)

        # 装订脊
        painter.save()
        clip = QRectF(paper)
        painter.setClipRect(clip)
        spine = QRectF(paper.left(), paper.top(), SPINE_W, paper.height())
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.color("spine"))
        painter.drawRect(spine)
        # 脊右侧的柔和阴影
        grad = QLinearGradient(spine.right(), paper.top(), spine.right() + 18, paper.top())
        shadow = QColor(30, 24, 16)
        shadow.setAlpha(34)
        grad.setColorAt(0.0, shadow)
        transparent = QColor(30, 24, 16)
        transparent.setAlpha(0)
        grad.setColorAt(1.0, transparent)
        painter.setBrush(grad)
        painter.drawRect(QRectF(spine.right(), paper.top(), 18, paper.height()))
        # 装订孔
        painter.setBrush(theme.color("spine_hole"))
        holes = 8
        margin_y = 54.0
        span = paper.height() - margin_y * 2
        for i in range(holes):
            cy = paper.top() + margin_y + span * (i / float(holes - 1))
            painter.drawEllipse(QRectF(spine.center().x() - 4, cy - 7, 8, 14))
        painter.restore()

        # 内页左缘竖线（笔记本的红色边线）
        content = self._content_rect()
        margin_line = QColor(theme.color("accent"))
        margin_line.setAlpha(70)
        painter.setPen(QPen(margin_line, 1))
        painter.drawLine(
            QRectF(content.left() - 12, content.top() - 4, 1, content.height() + 4).topLeft(),
            QRectF(content.left() - 12, content.top() - 4, 1, content.height() + 4).bottomLeft(),
        )

        page = self._pages[self._index] if self._pages else None
        if page:
            self._paint_rows(painter, page)
            self._paint_footer(painter)
        else:
            self._paint_empty(painter)
        painter.end()

    def _paint_rows(self, painter: QPainter, page: paging.Page) -> None:
        content, row_h, _col_w, _gap = self._metrics()
        rule = QColor(theme.color("rule"))
        rule.setAlpha(170)
        for i in range(1, config.ROWS_PER_PAGE):
            y = content.top() + row_h * i
            painter.setPen(QPen(rule, 1))
            painter.drawLine(int(content.left()), int(y), int(content.right()), int(y))

        f_date = QFont(theme.SANS)
        f_date.setPixelSize(theme.scale(10))
        f_date.setWeight(QFont.DemiBold)
        f_date.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)

        for row, slot in enumerate(page.slots):
            if slot.kind != "date":
                continue
            y = content.top() + row * row_h
            painter.setFont(f_date)
            painter.setPen(theme.color("ink_soft"))
            label = paging.page_label(slot.date, slot.count, slot.continued)
            painter.drawText(
                QRectF(content.left(), y + theme.scale(4), content.width(), theme.scale(16)),
                Qt.AlignLeft | Qt.AlignVCenter,
                label,
            )
            # 日期行的小圆点
            dot = QColor(theme.color("accent"))
            dot.setAlpha(160)
            painter.setPen(Qt.NoPen)
            painter.setBrush(dot)
            painter.drawEllipse(QRectF(content.left() - 26, y + row_h / 2 - 2.5, 5, 5))

    def _paint_footer(self, painter: QPainter) -> None:
        paper = self._paper_rect()
        f = QFont(theme.SANS)
        f.setPixelSize(theme.scale(10))
        painter.setFont(f)
        painter.setPen(theme.color("ink_faint"))
        left = paper.left() + SPINE_W + PAD_LEFT
        painter.drawText(
            QRectF(left, paper.bottom() - PAD_BOTTOM + 10, 260, theme.scale(16)),
            Qt.AlignLeft | Qt.AlignVCenter,
            "共 %d 词 · 已登记 %d 天" % (len(self._all_words), len({w.date_added for w in self._all_words if w.date_added})),
        )
        text = "第 %d 页 / 共 %d 页" % (self.page_number(), len(self._pages))
        painter.drawText(
            QRectF(paper.center().x() - 90, paper.bottom() - PAD_BOTTOM + 10, 180, theme.scale(16)),
            Qt.AlignCenter,
            text,
        )

    def _paint_empty(self, painter: QPainter) -> None:
        paper = self._paper_rect()
        f = QFont(theme.SANS)
        f.setPixelSize(theme.scale(13))
        painter.setFont(f)
        painter.setPen(theme.color("ink_faint"))
        painter.drawText(
            QRectF(paper.left() + SPINE_W, paper.center().y() - 30, paper.width() - SPINE_W - 40, 24),
            Qt.AlignCenter,
            "这一页还是空白",
        )
        f2 = QFont(theme.SANS)
        f2.setPixelSize(theme.scale(11))
        painter.setFont(f2)
        painter.drawText(
            QRectF(paper.left() + SPINE_W, paper.center().y(), paper.width() - SPINE_W - 40, 22),
            Qt.AlignCenter,
            "点右上角「＋ 登记」写下第一个单词，或在「单词书」里导入一本词书",
        )

    # ---------------------------------------------------------------- 事件
    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._layout_cells()
        self._nav_geometry()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._nav_geometry()

    def mousePressEvent(self, event):  # noqa: N802
        self.backgroundClicked.emit()
        super().mousePressEvent(event)

    def wheelEvent(self, event):  # noqa: N802
        if not self._pages:
            return
        if self._wheel_clock.elapsed() < 220:
            return
        delta = event.angleDelta().y()
        if delta < 0:
            self.next_page()
        elif delta > 0:
            self.prev_page()
        self._wheel_clock.restart()

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key_Right, Qt.Key_PageDown):
            self.next_page()
        elif event.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self.prev_page()
        else:
            super().keyPressEvent(event)
