"""通用小组件：分段控件、Toast、卡片标题行。"""
from typing import List, Sequence, Tuple

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme


class Segmented(QFrame):
    """iOS 风格分段控件：单选、即时反馈。"""

    changed = pyqtSignal(str)

    def __init__(self, options: Sequence[Tuple[str, str]], current: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("segmented")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._buttons = []  # type: List[QPushButton]
        self._current = current or (options[0][0] if options else "")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        for key, label in options:
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setChecked(key == self._current)
            button.setFlat(True)
            button.clicked.connect(lambda _checked=False, k=key: self.set_value(k))
            layout.addWidget(button)
            self._buttons.append(button)
            button.setProperty("segKey", key)
        self.set_value(self._current, emit=False)

    def value(self) -> str:
        return self._current

    def set_value(self, key: str, emit: bool = True) -> None:
        self._current = key
        for button in self._buttons:
            button.setChecked(button.property("segKey") == key)
        if emit:
            self.changed.emit(key)


class Toast(QLabel):
    """轻量提示：出现 → 停留 → 淡出，不打断操作。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()
        self._full_text = ""
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.setStyleSheet(
            "QLabel#toast { background: rgba(30,26,22,235); color: #FBF7EF;"
            " border-radius: 11px; padding: 9px 16px; font-size: 13px; }"
        )

    def show_message(self, text: str, msec: int = 2200) -> None:
        self._full_text = text
        self.setText(text)
        self._reposition()
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(msec)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        try:
            self._anim.finished.disconnect()
        except TypeError:
            pass
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        metrics = self.fontMetrics()
        text = self._full_text or self.text()
        limit = max(160, parent.width() - 72)
        width = metrics.horizontalAdvance(text) + 34
        if width > limit:
            width = limit
            text = metrics.elidedText(text, Qt.ElideRight, limit - 34)
        self.setText(text)
        self.setFixedWidth(int(width))
        self.setFixedHeight(metrics.height() + 18)
        self.move(int((parent.width() - self.width()) / 2), parent.height() - self.height() - 30)


class Card(QFrame):
    """带标题的纸卡容器。"""

    def __init__(self, title: str = "", subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(8)
        if title:
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(title)
            label.setObjectName("muted")
            row.addWidget(label)
            row.addStretch(1)
            self.header = row
            self.body.addLayout(row)
        if subtitle:
            hint = QLabel(subtitle)
            hint.setObjectName("faint")
            hint.setWordWrap(True)
            self.body.addWidget(hint)


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFrameShape(QFrame.HLine)
    return line


class Chip(QLabel):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("chipText")
        self.setMargin(0)
        self.setStyleSheet(
            "QLabel { background: rgba(127,110,88,26); color: %s; border-radius: 7px;"
            " padding: 2px 8px; font-size: 11px; }" % theme.css("ink_soft")
        )
