"""桌面迷你悬浮窗（F7）：常驻一角，随时瞄一眼单词。

外观：亚克力毛玻璃卡片（DWM 模糊）+ 纸色半透明底；打开时带弹簧感的缩放入场。
"""
import random
from typing import List, Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..models import Word
from . import acrylic, motion, theme

_ENTER_MS = 300
_EXIT_MS = 150


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
        self._pos: Optional[QPoint] = None
        self._target = QRect(self.pos(), self.size())
        self._geo_anim: Optional[QPropertyAnimation] = None
        self._fade_anim: Optional[QPropertyAnimation] = None
        self._glassy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(6)
        self._hint = QLabel("迷你单词")
        self._hint.setObjectName("faint")
        self._hint.setStyleSheet(
            "background: transparent; color: %s; font-size: %dpx;"
            % (theme.css("ink_faint"), theme.fs(10))
        )
        head.addWidget(self._hint)
        head.addStretch(1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { border: none; border-radius: 11px; background: transparent;"
            " color: %s; font-size: %dpx; }"
            "QPushButton:hover { background: rgba(127,110,88,60); }"
            % (theme.css("ink_soft"), theme.fs(15))
        )
        close_btn.clicked.connect(self.hide_window)
        head.addWidget(close_btn)
        root.addLayout(head)

        self._word = QLabel("")
        self._word.setStyleSheet(
            "background: transparent; color: %s; %s"
            % (theme.css("ink"), theme.font_css(23, theme.SERIF, 600))
        )
        root.addWidget(self._word)

        self._meaning = QLabel("")
        self._meaning.setWordWrap(True)
        self._meaning.setStyleSheet(
            "background: transparent; color: %s; font-size: %dpx;"
            % (theme.css("ink_soft"), theme.fs(11))
        )
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

    def toggle_window(self) -> None:
        if self.isVisible():
            self.hide_window()
        else:
            self.show_window()

    # ---------------------------------------------------------------- 显示
    def _default_pos(self) -> QPoint:
        screen = self.screen().availableGeometry() if self.screen() else None
        if not screen:
            return QPoint(200, 200)
        return QPoint(
            screen.right() - self.width() - 40,
            screen.bottom() - self.height() - 60,
        )

    def _scaled(self, factor: float) -> QRect:
        base = self._target
        w = max(1, int(base.width() * factor))
        h = max(1, int(base.height() * factor))
        return QRect(base.center().x() - w // 2, base.center().y() - h // 2, w, h)

    def _animate_geometry(self, start: QRect, end: QRect, ms: int, curve) -> None:
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(motion.ms(ms))
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        self._geo_anim = anim
        anim.finished.connect(self._geometry_settled)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def _geometry_settled(self) -> None:
        self._target = QRect(self._target.topLeft(), self.size())
        self._pos = self._target.topLeft()
        self._geo_anim = None

    def _animate_opacity(self, start: float, end: float, ms: int) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(motion.ms(ms))
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(motion.EASE_OUT)
        self._fade_anim = anim
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def show_window(self) -> None:
        if not self.isVisible():
            if self._pos is None:
                self._pos = self._default_pos()
            self._target = QRect(self._pos, self.size())
        self.show()
        self.raise_()
        self._apply_glass()
        if not motion.reduced():
            self._play_enter()
        if self._words:
            self._timer.start()

    def _play_enter(self) -> None:
        self._geo_anim = None
        self.setWindowOpacity(0.0)
        self.setGeometry(self._scaled(0.88))
        settle = QEasingCurve(QEasingCurve.OutBack)
        settle.setOvershoot(1.32)
        self._animate_geometry(self._scaled(0.88), self._target, _ENTER_MS, settle)
        self._animate_opacity(0.0, 1.0, int(_ENTER_MS * 0.55))

    def hide_window(self) -> None:
        self._timer.stop()
        if motion.reduced() or not self.isVisible():
            self._pos = self.pos()
            self.hide()
            return
        self._geo_anim = None
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(motion.ms(_EXIT_MS))
        anim.setStartValue(self.geometry())
        anim.setEndValue(self._scaled(0.93))
        anim.setEasingCurve(motion.EASE_IN)
        anim.finished.connect(self._after_hide)
        self._geo_anim = anim
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._animate_opacity(max(0.0, self.windowOpacity() or 1.0), 0.0, _EXIT_MS)

    def _after_hide(self) -> None:
        self._pos = self._target.topLeft()
        self._geo_anim = None
        self.hide()
        self.setGeometry(self._target)
        self.setWindowOpacity(1.0)

    def moveEvent(self, event):  # noqa: N802
        super().moveEvent(event)
        if self.isVisible() and self._geo_anim is None:
            self._pos = self.pos()
            self._target = QRect(self.pos(), self.size())

    def _apply_glass(self) -> None:
        if self._glassy:
            return
        self._glassy = acrylic.enable(int(self.winId()), tint=0x7AFFFFFF)

    # ---------------------------------------------------------------- 绘制
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        body = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -3.0)

        for i in range(3, 0, -1):
            layer = QColor(0, 0, 0, 46)
            layer.setAlpha(int(46 / (i + 1.2)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(layer)
            painter.drawRoundedRect(body.adjusted(-i, i, i, i + 2), 16, 16)

        glass = QColor(theme.color("paper"))
        glass.setAlpha(206)
        painter.setBrush(glass)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(body, 16, 16)

        highlight = QColor(255, 255, 255, 44)
        painter.setBrush(highlight)
        painter.drawRoundedRect(
            body.adjusted(0.5, 0.5, -0.5, -body.height() * 0.55), 16, 16
        )

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(theme.css("rule")), 1))
        painter.drawRoundedRect(body, 16, 16)
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
            self._geo_anim = None
            self.move(self._drag_origin + delta)
            self._pos = self.pos()
            self._target = QRect(self.pos(), self.size())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_from = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.openMain.emit()
        super().mouseDoubleClickEvent(event)
