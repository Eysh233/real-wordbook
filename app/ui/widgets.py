"""通用小组件：分段控件、Toast、卡片标题行。"""
from typing import List, Sequence, Tuple

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import (
    QApplication,
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


class _TagRow(QWidget):
    """标签菜单的一行：名称、数量、当前项圆点。悬停用淡底而不是换色。"""

    def __init__(self, label: str, count: int, current: bool, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(theme.scale(30))
        self.setMinimumWidth(theme.scale(170))
        self._label = label
        self._count = count
        self._current = current
        self._hover = False

    def set_current(self, current: bool) -> None:
        if self._current != current:
            self._current = current
            self.update()

    def set_hover(self, hover: bool) -> None:
        if self._hover != hover:
            self._hover = hover
            self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        box = self.rect().adjusted(4, 2, -4, -2)

        if self._hover:
            tint = QColor(theme.color("accent"))
            tint.setAlpha(18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(tint)
            painter.drawRoundedRect(box, 7, 7)

        text_left = box.left() + theme.scale(9)
        if self._current:
            dot = QColor(theme.color("accent"))
            painter.setPen(Qt.NoPen)
            painter.setBrush(dot)
            painter.drawEllipse(box.left() + theme.scale(2), box.center().y() - 2, 4, 4)
            text_left += theme.scale(3)

        f = QFont(theme.SANS)
        f.setPixelSize(theme.fs(12))
        f.setWeight(QFont.DemiBold if self._current else QFont.Normal)
        painter.setFont(f)
        painter.setPen(theme.color("ink" if (self._current or self._hover) else "ink_soft"))
        text_rect = box.adjusted(int(text_left - box.left()), 0, -theme.scale(38), 0)
        painter.drawText(
            text_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            painter.fontMetrics().elidedText(self._label, Qt.ElideRight, text_rect.width()),
        )

        f2 = QFont(theme.SANS)
        f2.setPixelSize(theme.fs(11))
        painter.setFont(f2)
        painter.setPen(theme.color("ink_faint"))
        painter.drawText(
            box.adjusted(0, 0, -theme.scale(9), 0), Qt.AlignRight | Qt.AlignVCenter, str(self._count)
        )


class _TagPopup(QFrame):
    """菜单浮层：材质卡片 + 从按钮原点弹出 + 逐项错峰出现。"""

    picked = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._rows: List[_TagRow] = []
        self._index = 0

        self._panel = QFrame(self)
        self._panel.setObjectName("tagPanel")
        self._panel.setStyleSheet(
            "QFrame#tagPanel { background: %s; border: 1px solid %s; border-radius: 12px; }"
            % (theme.css("popover"), theme.css("rule"))
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.scale(8), theme.scale(8), theme.scale(8), theme.scale(8))
        outer.addWidget(self._panel)

        self._box = QVBoxLayout(self._panel)
        self._box.setContentsMargins(theme.scale(4), theme.scale(5), theme.scale(4), theme.scale(5))
        self._box.setSpacing(theme.scale(1))

    # ------------------------------------------------------------------ 内容
    def build(self, items: Sequence[Tuple[str, str, int]], current: str) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []

        for index, (value, label, count) in enumerate(items):
            row = _TagRow(label, count, value == current, self._panel)
            row.setProperty("tagValue", value)
            row.installEventFilter(self)
            self._box.addWidget(row)
            self._rows.append(row)
            if value == current and value:
                self._index = index

        self._mark()
        self.adjustSize()

    def _mark(self) -> None:
        for index, row in enumerate(self._rows):
            row.set_current(index == self._index)

    def play_in(self) -> None:
        end = self.pos()
        start = QPoint(end.x(), end.y() - theme.scale(6))
        if motion.reduced():
            self.setWindowOpacity(1.0)
            return
        self.move(start)
        self.setWindowOpacity(0.0)
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(motion.ms(motion.POP_MS))
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(motion.EASE_OUT)
        fade.start()
        slide = QPropertyAnimation(self, b"pos", self)
        slide.setDuration(motion.ms(motion.POP_MS))
        slide.setStartValue(start)
        slide.setEndValue(end)
        slide.setEasingCurve(motion.EASE_OUT)
        slide.start()
        self._anims = (fade, slide)

    def play_out(self, on_done) -> None:
        if motion.reduced():
            on_done()
            return
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(motion.ms(motion.POP_OUT_MS))
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(motion.EASE_IN)
        fade.finished.connect(on_done)
        fade.start()
        self._anims = (fade,)

    # ------------------------------------------------------------------ 交互
    def eventFilter(self, obj, event):  # noqa: N802
        if obj in self._rows:
            kind = event.type()
            if kind == event.Enter:
                obj.set_hover(True)
            elif kind == event.Leave:
                obj.set_hover(False)
            elif kind == event.MouseButtonRelease and event.button() == Qt.LeftButton:
                if obj.rect().contains(event.pos()):
                    self.picked.emit(str(obj.property("tagValue") or ""))
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):  # noqa: N802
        key = event.key()
        if key in (Qt.Key_Escape, Qt.Key_Tab):
            self.hide()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self._rows:
                self.picked.emit(str(self._rows[self._index].property("tagValue") or ""))
            return
        if key in (Qt.Key_Down, Qt.Key_Up) and self._rows:
            step = 1 if key == Qt.Key_Down else -1
            self._index = (self._index + step) % len(self._rows)
            self._mark()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event):  # noqa: N802
        super().hideEvent(event)
        self.closed.emit()


class TagMenu(QPushButton):
    """标签筛选：按钮 + 自绘菜单（替代 QComboBox）。菜单贴在按钮正下方。"""

    tagChanged = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("field")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(theme.scale(96))
        self.setMaximumWidth(theme.scale(168))
        self._items: List[Tuple[str, str, int]] = [("", "全部标签", 0)]
        self._value = ""
        self._popup = None
        self.setStyleSheet("font-size: %dpx;" % theme.fs(12))
        self._render_label()
        self.clicked.connect(self._toggle)

    # ------------------------------------------------------------------ 数据
    def set_items(self, items: Sequence[Tuple[str, str, int]], keep: bool = True) -> None:
        self._items = list(items) or [("", "全部标签", 0)]
        values = [value for value, _label, _count in self._items]
        if not keep or self._value not in values:
            self._value = ""
        self._render_label()

    def value(self) -> str:
        return self._value

    def set_value(self, value: str, emit: bool = False) -> None:
        values = [item[0] for item in self._items]
        self._value = value if value in values else ""
        self._render_label()
        if emit:
            self.tagChanged.emit(self._value)

    def _render_label(self) -> None:
        label = "全部标签"
        for value, text, _count in self._items:
            if value and value == self._value:
                label = text
                break
        self.setText("%s  \u25be" % label)

    # ------------------------------------------------------------------ 展开
    def _toggle(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._close()
            return
        self._open()

    def _open(self) -> None:
        popup = _TagPopup(self.window())
        popup.build(self._items, self._value)
        popup.picked.connect(self._apply)
        popup.closed.connect(self._on_closed)
        self._popup = popup

        popup.adjustSize()
        size = popup.size()
        anchor = self.mapToGlobal(QPoint(0, 0))
        screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
        area = screen.availableGeometry()

        x = anchor.x()
        y = anchor.y() + self.height() + theme.scale(6)
        if x + size.width() > area.right() - theme.scale(8):
            x = area.right() - theme.scale(8) - size.width()
        if y + size.height() > area.bottom() - theme.scale(8):
            y = anchor.y() - size.height() - theme.scale(6)
        x = max(area.left() + theme.scale(8), x)
        y = max(area.top() + theme.scale(8), y)

        popup.move(int(x), int(y))
        popup.show()
        popup.setFocus()
        popup.play_in()

    def _apply(self, value: str) -> None:
        self._close()
        value = value or ""
        if value != self._value:
            self._value = value
            self._render_label()
            self.tagChanged.emit(self._value)

    def _on_closed(self) -> None:
        self._popup = None

    def _close(self) -> None:
        popup = self._popup
        self._popup = None
        if popup is None:
            return
        popup.play_out(popup.close)
