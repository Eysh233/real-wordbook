"""笔记本视图：纸页、装订脊、日期行、页脚、翻页。

行槽模型：日期行占一整行（1 槽），词行占一行（最多 5 词）。
"""
from typing import List, Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QPushButton, QWidget

from .. import config
from ..models import Word
from ..services import paging
from . import motion, painter_utils, theme
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
        # 翻页分层：纸面 / 行与日期与词 / 页脚，各自不同的位移与先后
        self._turn_mode = "idle"      # idle | out | in
        self._turn_dir = 1
        self._turn_p = 1.0
        self._cells_hidden = False
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
        """翻页：纸面、内容、页脚按不同幅度与先后错开，形成分层的方向感。

        Apple 的「hint in the direction of the gesture」在这里落到三处：
        要走的页内容先行、纸面随后；进来的页纸面先到、内容跟上来、页脚最后。
        位移/淡入只发生在纸页绘制里，控件本身不动，书桌背景不会跟着晃。
        """
        direction = 1 if target > self._index else -1
        if self._anim is not None:
            self._anim.stop()
        self._turn_dir = direction
        self._hide_cells(True)

        def animate(duration, curve, on_value, on_done=None):
            anim = QVariantAnimation(self)
            anim.setDuration(motion.ms(duration))
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(curve)
            anim.valueChanged.connect(lambda v: on_value(float(v)))
            if on_done is not None:
                anim.finished.connect(on_done)
            anim.start()
            self._anim = anim

        def on_out(value):
            self._turn_mode = "out"
            self._turn_p = value
            self.update()

        def switch():
            self._index = target
            self._rebuild_cells()
            self.pageChanged.emit(self.page_number(), len(self._pages))
            animate(motion.PAGE_MS, motion.EASE_OUT, on_in, self._clear_turn)

        def on_in(value):
            self._turn_mode = "in"
            self._turn_p = value
            self.update()

        animate(110, motion.EASE_IN, on_out, switch)

    # ------------------------------------------------------------ 分层进度
    @staticmethod
    def _clamp01(value: float) -> float:
        return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)

    def _layer_progress(self, layer: str) -> float:
        """返回某一层当前的完成度 0..1；idle 时恒为 1。"""
        if self._turn_mode == "idle":
            return 1.0
        p = self._turn_p
        if self._turn_mode == "out":
            # 内容先走，纸面与页脚后走
            delay = {"content": 0.0, "footer": 0.18, "paper": 0.3}.get(layer, 0.0)
        else:
            # 纸面先到，内容随后，页脚最后落定
            delay = {"paper": 0.0, "content": 0.16, "footer": 0.34}.get(layer, 0.0)
        span = max(0.001, 1.0 - delay)
        return self._clamp01((p - delay) / span)

    def _layer_tint(self, layer: str) -> tuple:
        """返回 (透明度, 水平位移)。

        出相：旧页从满透明度走到 0，并沿翻页方向移开；
        入相：新页从 0 走到满透明度，从翻页方向的反侧滑回原位。
        """
        if self._turn_mode == "idle":
            return 1.0, 0.0
        progress = self._layer_progress(layer)
        amplitude = {"paper": 4.0, "content": 22.0, "footer": 8.0}.get(layer, 12.0)
        # 纸面几乎不淡，只轻轻让位；真正动的是内容与页脚，避免整页化成一片糊
        floor = {"paper": 1.0, "content": 0.22, "footer": 0.45}.get(layer, 0.3)
        if self._turn_mode == "in":
            alpha = floor + (1.0 - floor) * progress
            return alpha, self._turn_dir * amplitude * (1.0 - progress)
        alpha = 1.0 - (1.0 - floor) * progress
        return alpha, -self._turn_dir * amplitude * progress

    def _hide_cells(self, hidden: bool) -> None:
        self._cells_hidden = hidden
        for cell in self._cells:
            cell.setVisible(not hidden)

    def _clear_turn(self) -> None:
        self._turn_mode = "idle"
        self._turn_p = 1.0
        self._hide_cells(False)
        self.update()

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

    def _slot_bands(self, page):
        """按行槽高度铺开：[(slot, y, height)]，日期行只有半行高。"""
        content, row_h, _col_w, _gap = self._metrics()
        bands = []
        y = content.top()
        for slot in page.slots:
            h = row_h * slot.rows
            bands.append((slot, y, h))
            y += h
        return bands

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
        # 翻页过渡期重建的词格必须保持隐藏，否则会和 _paint_words 叠成重影
        if self._cells_hidden:
            for cell in self._cells:
                cell.hide()
        self._layout_cells()
        self._sync_buttons()

    def _layout_cells(self) -> None:
        if not self._cells:
            return
        content, row_h, col_w, gap = self._metrics()
        page = self._pages[self._index] if self._pages else None
        if not page:
            return
        index = 0
        for slot, y0, h in self._slot_bands(page):
            if slot.kind != "words":
                continue
            cell_h = max(40, int(h - theme.scale(9)))
            for col, _word in enumerate(slot.words):
                if index >= len(self._cells):
                    break
                x = content.left() + col * (col_w + gap)
                y = y0 + theme.scale(3)
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
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.fillRect(self.rect(), theme.color("desk"))

        page = self._pages[self._index] if self._pages else None
        turning = self._turn_mode != "idle"

        # 翻页分三层走：纸面最先/最后、内容跟着、页脚收尾。
        # 每层单独 save/restore，透明度与位移互不影响，也不会让书桌背景抖动。
        alpha, dx = self._layer_tint("paper")
        painter.save()
        painter.setOpacity(alpha)
        painter.translate(int(round(dx)), 0)
        self._paint_sheet(painter)
        painter.restore()

        alpha, dx = self._layer_tint("content")
        painter.save()
        painter.setOpacity(alpha)
        painter.translate(int(round(dx)), 0)
        if page:
            self._paint_rows(painter, page)
            if turning:
                # 翻页期间词格控件被隐藏，这里直接画一遍，省掉 30 个控件的跟随动画
                self._paint_words(painter, page)
        else:
            self._paint_empty(painter)
        painter.restore()

        if page:
            alpha, dx = self._layer_tint("footer")
            painter.save()
            painter.setOpacity(alpha)
            painter.translate(int(round(dx)), 0)
            self._paint_footer(painter)
            painter.restore()

        painter.end()

    def _paint_sheet(self, painter: QPainter) -> None:
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

    def _paint_words(self, painter: QPainter, page: paging.Page) -> None:
        """翻页过渡期用的轻量词条绘制（与 WordCell 的排版对齐）。"""
        content, _row_h, col_w, gap = self._metrics()

        f_word = QFont(theme.SERIF)
        f_word.setPixelSize(theme.fs(17 if self._mode != config.DISPLAY_CN else 16))
        f_word.setWeight(QFont.DemiBold)
        f_word.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)

        f_mean = QFont(theme.SANS)
        f_mean.setPixelSize(theme.fs(11 if self._mode != config.DISPLAY_CN else 15))

        for slot, y0, h in self._slot_bands(page):
            if slot.kind != "words":
                continue
            cell_h = max(40, int(h - theme.scale(9)))
            for col, word in enumerate(slot.words):
                x = content.left() + col * (col_w + gap)
                box = QRectF(x + 4, y0 + theme.scale(3) + 1, col_w - 8, cell_h - 2)
                left = box.left() + 7
                text_width = max(20.0, box.width() - 14)
                seed = abs(hash(word.id or word.word)) % 100000

                painter.setFont(f_word)
                word_text = painter.fontMetrics().elidedText(word.word, Qt.ElideRight, int(text_width))
                word_h = painter.fontMetrics().height()
                word_rect = QRectF(left, box.top() + theme.scale(8), min(text_width, painter.fontMetrics().width(word_text) + 6), word_h)

                painter.setFont(f_mean)
                mean_text = painter.fontMetrics().elidedText(word.meaning_cn, Qt.ElideRight, int(text_width))
                mean_h = painter.fontMetrics().height()
                mean_rect = QRectF(left, box.top() + theme.scale(40), min(text_width, painter.fontMetrics().width(mean_text) + 6), mean_h)

                if word.highlight:
                    painter.setOpacity(0.86)
                    if self._mode != config.DISPLAY_CN:
                        painter_utils.draw_highlight(painter, word_rect.adjusted(-2, -2, 4, 2), theme.highlight_color(), seed)
                    if self._mode != config.DISPLAY_EN:
                        painter_utils.draw_highlight(painter, mean_rect.adjusted(-2, -1, 4, 1), theme.highlight_color(), seed + 3)
                    painter.setOpacity(1.0)

                if self._mode != config.DISPLAY_CN:
                    painter.setFont(f_word)
                    painter.setPen(theme.color("ink"))
                    painter.drawText(word_rect, Qt.AlignLeft | Qt.AlignVCenter, word_text)
                if self._mode != config.DISPLAY_EN:
                    painter.setFont(f_mean)
                    painter.setPen(theme.color("ink_soft"))
                    painter.drawText(mean_rect, Qt.AlignLeft | Qt.AlignVCenter, mean_text)

                if word.strike:
                    painter_utils.draw_strike(
                        painter, word_rect.left() - 2, word_rect.right() + 2,
                        (word_rect.center().y() if self._mode != config.DISPLAY_CN else mean_rect.center().y()),
                        theme.strike_color(), seed,
                    )

    def _paint_rows(self, painter: QPainter, page: paging.Page) -> None:
        content, _row_h, _col_w, _gap = self._metrics()
        bands = self._slot_bands(page)
        rule = QColor(theme.color("rule"))

        f_date = QFont(theme.SANS)
        f_date.setPixelSize(theme.fs(10))
        f_date.setWeight(QFont.DemiBold)
        f_date.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)

        for slot, y0, h in bands:
            bottom = y0 + h
            if slot.kind == "date":
                # 半行日期：文字在小圆点右侧，行线略淡
                rule.setAlpha(110)
                painter.setPen(QPen(rule, 1))
                painter.drawLine(int(content.left()), int(bottom), int(content.right()), int(bottom))
                painter.setFont(f_date)
                painter.setPen(theme.color("ink_soft"))
                label = paging.page_label(slot.date, slot.count, slot.continued)
                painter.drawText(
                    QRectF(content.left() + 12, y0, content.width() - 12, h),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    label,
                )
                dot = QColor(theme.color("accent"))
                dot.setAlpha(170)
                painter.setPen(Qt.NoPen)
                painter.setBrush(dot)
                painter.drawEllipse(QRectF(content.left(), y0 + h / 2 - 2.5, 5, 5))
            else:
                rule.setAlpha(170)
                painter.setPen(QPen(rule, 1))
                painter.drawLine(int(content.left()), int(bottom), int(content.right()), int(bottom))

    def _paint_footer(self, painter: QPainter) -> None:
        paper = self._paper_rect()
        f = QFont(theme.SANS)
        f.setPixelSize(theme.fs(10))
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
        f.setPixelSize(theme.fs(13))
        painter.setFont(f)
        painter.setPen(theme.color("ink_faint"))
        painter.drawText(
            QRectF(paper.left() + SPINE_W, paper.center().y() - 30, paper.width() - SPINE_W - 40, 24),
            Qt.AlignCenter,
            "这一页还是空白",
        )
        f2 = QFont(theme.SANS)
        f2.setPixelSize(theme.fs(11))
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
