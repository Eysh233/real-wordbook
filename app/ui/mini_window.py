"""桌面迷你悬浮窗（F7）：常驻一角，随时瞄一眼单词。"""
import random
from typing import List

from PyQt5.QtCore import QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..models import Word
from . import theme


class MiniWindow(QWidget):
    openMain = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(theme.scale(330), theme.scale(148))
        self._words: List[Word] = []
        self._index = 0
        self._revealed = False
        self._drag_from = None
        self._drag_origin = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(6)
        self._hint = QLabel("迷你单词")
        self._hint.setObjectName("faint")
        head.addWidget(self._hint)
        head.addStretch(1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { border: none; border-radius: 11px; color: %s; font-size: 15px; }"
            "QPushButton:hover { background: rgba(127,110,88,30); }" % theme.css("ink_soft")
        )
        close_btn.clicked.connect(self.hide_window)
        head.addWidget(close_btn)
        root.addLayout(head)

        self._word = QLabel("")
        word_font = QFont(theme.SERIF)
        word_font.setPixelSize(theme.scale(23))
        word_font.setWeight(QFont.DemiBold)
        self._word.setFont(word_font)
        self._word.setStyleSheet("color: %s;" % theme.css("ink"))
        root.addWidget(self._word)

        self._meaning = QLabel("")
        self._meaning.setWordWrap(True)
        self._meaning.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("ink_soft"), theme.scale(11)))
        self._meaning.hide()
        root.addWidget(self._meaning)
        root.addStretch(1)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._btn_reveal = QPushButton("显示中文")
        self._btn_reveal.setObjectName("link")
        self._btn_reveal.setCursor(Qt.PointingHandCursor)
        self._btn_reveal.clicked.connect(self.toggle)
        row.addWidget(self._btn_reveal)
        row.addStretch(1)
        next_btn = QPushButton("换一个")
        next_btn.setObjectName("link")
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.clicked.connect(self.next_word)
        row.addWidget(next_btn)
        root.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setInterval(14000)
        self._timer.timeout.connect(self.next_word)
        self.hide()

    # ---------------------------------------------------------------- 数据
    def set_words(self, words: List[Word]) -> None:
        self._words = list(words)
        random.shuffle(self._words)
        self._index = 0
        self._revealed = False
        self._render()
        if self._words:
            self._timer.start()

    def next_word(self) -> None:
        if not self._words:
            return
        self._index = (self._index + 1) % len(self._words)
        self._revealed = False
        self._render()

    def toggle(self) -> None:
        self._revealed = not self._revealed
        self._render()

    def _render(self) -> None:
        if not self._words:
            self._word.setText("单词本是空的")
            self._meaning.setText("先登记几个单词吧")
            self._meaning.show()
            self._btn_reveal.setText("显示中文")
            return
        word = self._words[self._index]
        self._word.setText(word.word)
        self._meaning.setText(("%s %s" % (word.pos, word.meaning_cn)).strip())
        self._meaning.setVisible(self._revealed)
        self._btn_reveal.setText("隐藏中文" if self._revealed else "显示中文")
        self._hint.setText("迷你单词 · %d/%d" % (self._index + 1, len(self._words)))

    def show_window(self) -> None:
        if not self.isVisible():
            screen = self.screen().availableGeometry() if self.screen() else None
            if screen:
                self.move(screen.right() - self.width() - 40, screen.bottom() - self.height() - 60)
        self.show()
        self.raise_()
        if self._words:
            self._timer.start()

    def hide_window(self) -> None:
        self._timer.stop()
        self.hide()

    # ---------------------------------------------------------------- 绘制
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        shadow = QColor(0, 0, 0, 60)
        for i in range(3, 0, -1):
            layer = QColor(shadow)
            layer.setAlpha(int(60 / (i + 1.2)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(layer)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(-i, i, i, i + 2), 16, 16)
        painter.setBrush(theme.color("paper"))
        painter.setPen(QColor(theme.css("rule")))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -3), 16, 16)
        painter.end()

    # ---------------------------------------------------------------- 事件
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_from = event.globalPos()
            self._drag_origin = self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_from is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPos() - self._drag_from
            self.move(self._drag_origin + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_from = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.openMain.emit()
        super().mouseDoubleClickEvent(event)
