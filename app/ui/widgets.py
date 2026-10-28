"""通用小组件：分段控件、Toast、卡片标题行。"""
from typing import List, Sequence, Tuple

from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import motion, theme


class _Pill(QWidget):
    """分段控件里滑动的白色药丸：位置在按钮之间以 220ms 连续过渡。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._radius = 8

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.color("paper")))
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)


class Segmented(QFrame):
    """iOS 风格分段控件：选中态由滑动的药丸表达，而不是硬切背景色。"""

    changed = pyqtSignal(str)

    def __init__(self, options: Sequence[Tuple[str, str]], current: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("segmented")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._buttons = []  # type: List[QPushButton]
        self._current = current or (options[0][0] if options else "")
        self._placed = False
        self._pill = _Pill(self)
        shadow = QGraphicsDropShadowEffect(self._pill)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 34))
        self._pill.setGraphicsEffect(shadow)
        self._slide = QPropertyAnimation(self._pill, b"geometry", self)
        self._slide.setDuration(motion.ms(motion.PAGE_MS))
        self._slide.setEasingCurve(QEasingCurve.OutCubic)

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

    # -- 药丸 ---------------------------------------------------------------
    def _pill_rect(self, index: int) -> QRect:
        if index < 0 or index >= len(self._buttons):
            return QRect(3, 3, 0, self.height() - 6)
        return self._buttons[index].geometry()

    def _move_pill(self, animate: bool) -> None:
        index = self._index_of(self._current)
        target = self._pill_rect(index)
        if target.width() <= 0:
            return
        self._pill.raise_()
        if not animate or motion.reduced() or not self._placed:
            self._slide.stop()
            self._pill.setGeometry(target)
        else:
            self._slide.stop()
            self._slide.setStartValue(self._pill.geometry())
            self._slide.setEndValue(target)
            self._slide.start()
        for button in self._buttons:
            button.raise_()
        self._placed = True

    def _index_of(self, key: str) -> int:
        for index, button in enumerate(self._buttons):
            if button.property("segKey") == key:
                return index
        return -1

    # -- 对外 ---------------------------------------------------------------
    def value(self) -> str:
        return self._current

    def set_value(self, key: str, emit: bool = True) -> None:
        if key == self._current and emit:
            self._move_pill(animate=True)
        self._current = key
        for button in self._buttons:
            button.setChecked(button.property("segKey") == key)
        self._move_pill(animate=self._placed)
        if emit:
            self.changed.emit(key)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._move_pill(animate=False)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._move_pill(animate=False)


class Toast(QLabel):
    """轻量提示：自下方上浮 8px 淡入 → 停留 → 下沉淡出，不打断操作。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()
        self._full_text = ""
        self._effect = motion.surface(self)
        self._effect.set_opacity(0.0)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.setStyleSheet(
            "QLabel#toast { background: rgba(30,26,22,235); color: #FBF7EF;"
            " border-radius: 11px; padding: 9px 16px; font-size: %dpx; }" % theme.fs(13)
        )

    def show_message(self, text: str, msec: int = 2200) -> None:
        self._full_text = text
        self.setText(text)
        self._reposition()
        self.show()
        self.raise_()
        self._effect.set_opacity(0.0)
        self._effect.set_lift(8.0)
        motion.opacity_to(self, 1.0, motion.TOAST_MS, motion.EASE_OUT)
        effect = self._effect
        lift = QVariantAnimation(self)
        lift.setDuration(motion.ms(motion.TOAST_MS))
        lift.setStartValue(8.0)
        lift.setEndValue(0.0)
        lift.setEasingCurve(motion.EASE_OUT)
        lift.valueChanged.connect(lambda v: effect.set_lift(float(v)))
        lift.start()
        self._lift_anim = lift
        self._timer.start(msec)

    def _fade_out(self) -> None:
        motion.opacity_to(self, 0.0, 160, motion.EASE_IN)
        previous = getattr(self, "_lift_anim", None)
        if previous is not None:
            previous.stop()
        effect = self._effect
        lift = QVariantAnimation(self)
        lift.setDuration(motion.ms(160))
        lift.setStartValue(self._effect.lift)
        lift.setEndValue(-4.0)
        lift.setEasingCurve(motion.EASE_IN)
        lift.valueChanged.connect(lambda v: effect.set_lift(float(v)))
        lift.finished.connect(self.hide)
        lift.start()
        self._lift_anim = lift

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
            " padding: 2px 8px; font-size: %dpx; }" % (theme.css("ink_soft"), theme.fs(11))
        )
