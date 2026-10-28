"""抽背 / 背书会话浮层：先看英文，点按后才揭晓中文。

键盘：空格揭晓 · ← 不认识 · → 认识 · Esc 退出。
"""
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import motion, theme, widgets


@dataclass
class SessionItem:
    word: str
    meaning_cn: str
    phonetic: str = ""
    pos: str = ""
    note: str = ""
    example: str = ""
    no: str = ""
    ref: Any = None
    registered: bool = False


class CardSession(QWidget):
    finished = pyqtSignal(dict)

    def __init__(
        self,
        items: List[SessionItem],
        parent: QWidget,
        title: str = "抽背",
        allow_register: bool = False,
        on_review: Optional[Callable[[SessionItem, bool], None]] = None,
        on_seen: Optional[Callable[[SessionItem], None]] = None,
        on_register: Optional[Callable[[SessionItem], bool]] = None,
        reduced_motion: bool = False,
    ) -> None:
        super().__init__(parent)
        self.items = list(items)
        self.title = title
        self.allow_register = allow_register
        self._on_review = on_review
        self._on_seen = on_seen
        self._on_register = on_register
        self._reduced = reduced_motion
        self._index = 0
        self._revealed = False
        self._known = 0
        self._answered = 0
        self._seen_sent = set()
        self._anim = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_StyledBackground, False)

        self._card = QFrame(self)
        self._card.setObjectName("sheet")
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 90))
        self._card.setGraphicsEffect(shadow)

        root = QVBoxLayout(self._card)
        root.setContentsMargins(38, 24, 38, 24)
        root.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(10)
        self._title = QLabel(title)
        self._title.setObjectName("faint")
        head.addWidget(self._title)
        head.addStretch(1)
        self._progress_text = QLabel("")
        self._progress_text.setObjectName("faint")
        head.addWidget(self._progress_text)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { border: none; border-radius: 13px; font-size: %dpx; color: %s; }"
            "QPushButton:hover { background: rgba(127,110,88,30); }"
            % (theme.fs(17), theme.css("ink_soft"))
        )
        close_btn.clicked.connect(self.close_session)
        head.addWidget(close_btn)
        root.addLayout(head)

        self._bar = QProgressBar(self._card)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        self._bar.setMaximum(max(1, len(self.items)))
        root.addWidget(self._bar)

        root.addStretch(3)

        self._word = QLabel("")
        word_font = QFont(theme.SERIF)
        word_font.setPixelSize(theme.fs(48))
        word_font.setWeight(QFont.DemiBold)
        self._word.setFont(word_font)
        self._word.setAlignment(Qt.AlignCenter)
        self._word.setWordWrap(True)
        self._word.setStyleSheet("color: %s;" % theme.css("ink"))
        root.addWidget(self._word)

        self._phonetic = QLabel("")
        phon_font = QFont(theme.SERIF)
        phon_font.setPixelSize(theme.fs(13))
        phon_font.setItalic(True)
        self._phonetic.setFont(phon_font)
        self._phonetic.setAlignment(Qt.AlignCenter)
        self._phonetic.setStyleSheet("color: %s;" % theme.css("ink_faint"))
        root.addWidget(self._phonetic)

        root.addSpacing(theme.scale(8))

        reveal_box = QWidget(self._card)
        reveal_box.setFixedHeight(theme.scale(116))
        reveal_layout = QVBoxLayout(reveal_box)
        reveal_layout.setContentsMargins(0, 0, 0, 0)
        reveal_layout.setSpacing(8)
        reveal_layout.addStretch(1)

        self._meaning = QLabel("")
        mean_font = QFont(theme.SANS)
        mean_font.setPixelSize(theme.fs(22))
        self._meaning.setFont(mean_font)
        self._meaning.setAlignment(Qt.AlignCenter)
        self._meaning.setWordWrap(True)
        self._meaning.setStyleSheet("color: %s;" % theme.css("ink"))
        self._meaning.hide()
        reveal_layout.addWidget(self._meaning)

        self._example = QLabel("")
        ex_font = QFont(theme.SERIF)
        ex_font.setPixelSize(theme.fs(13))
        ex_font.setItalic(True)
        self._example.setFont(ex_font)
        self._example.setAlignment(Qt.AlignCenter)
        self._example.setWordWrap(True)
        self._example.setStyleSheet("color: %s;" % theme.css("ink_soft"))
        self._example.hide()
        reveal_layout.addWidget(self._example)
        reveal_layout.addStretch(1)
        root.addWidget(reveal_box)

        root.addStretch(2)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch(1)
        self._btn_reveal = QPushButton("显示中文")
        self._btn_reveal.setObjectName("primary")
        self._btn_reveal.setCursor(Qt.PointingHandCursor)
        self._btn_reveal.clicked.connect(self.reveal)
        actions.addWidget(self._btn_reveal)

        self._btn_unknown = QPushButton("不认识")
        self._btn_unknown.setObjectName("ghost")
        self._btn_unknown.setCursor(Qt.PointingHandCursor)
        self._btn_unknown.clicked.connect(lambda: self._answer(False))
        self._btn_unknown.hide()
        actions.addWidget(self._btn_unknown)

        self._btn_known = QPushButton("认识")
        self._btn_known.setObjectName("primary")
        self._btn_known.setCursor(Qt.PointingHandCursor)
        self._btn_known.clicked.connect(lambda: self._answer(True))
        self._btn_known.hide()
        actions.addWidget(self._btn_known)

        self._btn_register = QPushButton("登记到我的单词本")
        self._btn_register.setObjectName("ghost")
        self._btn_register.setCursor(Qt.PointingHandCursor)
        self._btn_register.clicked.connect(self._register)
        self._btn_register.hide()
        actions.addWidget(self._btn_register)
        actions.addStretch(1)
        root.addLayout(actions)

        self._hint = QLabel("空格 显示中文 · ← 不认识 · → 认识 · Esc 退出")
        self._hint.setObjectName("faint")
        self._hint.setAlignment(Qt.AlignCenter)
        root.addWidget(self._hint)

        self._veil_t = 1.0
        self._base_w = 680
        self._base_h = 430
        self.hide()

    # ---------------------------------------------------------------- 展示
    def present(self) -> None:
        parent = self.parentWidget()
        if parent:
            self.setGeometry(parent.rect())
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self._enter()
        self._index = 0
        self._known = 0
        self._answered = 0
        self._seen_sent = set()
        self._render()

    def _enter(self) -> None:
        """入场：遮罩 160ms 淡入，卡片从 0.96 尺寸长到 1（OutBack 微弹）。"""
        self._fade_veil(1.0, 160, motion.EASE_OUT)
        if motion.reduced():
            self._card.setGeometry(self._rect_for(1.0))
            return
        self._card.setGeometry(self._rect_for(0.955))
        anim = QPropertyAnimation(self._card, b"geometry", self)
        anim.setDuration(motion.ms(motion.SHEET_MS))
        anim.setStartValue(self._card.geometry())
        anim.setEndValue(self._rect_for(1.0))
        anim.setEasingCurve(motion.EASE_SETTLE)
        anim.start()
        self._enter_anim = anim

    def _rect_for(self, factor: float) -> QRect:
        width = int(self._base_w * factor)
        height = int(self._base_h * factor)
        return QRect(
            int((self.width() - width) / 2),
            int((self.height() - height) / 2),
            width,
            height,
        )

    def _fade_veil(self, target: float, duration: int, curve, on_done=None) -> None:
        from PyQt5.QtCore import QVariantAnimation

        anim = QVariantAnimation(self)
        anim.setDuration(motion.ms(duration))
        anim.setStartValue(float(self._veil_t))
        anim.setEndValue(float(target))
        anim.setEasingCurve(curve)
        anim.valueChanged.connect(self._set_veil)
        if on_done is not None:
            anim.finished.connect(on_done)
        anim.start()
        self._veil_anim = anim

    def _set_veil(self, value) -> None:
        self._veil_t = float(value)
        self.update()

    def _slide(self, dx: int, duration: int, curve, on_done=None) -> None:
        base = self._card.pos()
        anim = QPropertyAnimation(self._card, b"pos", self)
        anim.setDuration(motion.ms(duration))
        anim.setStartValue(base)
        anim.setEndValue(base + QPoint(dx, 0))
        anim.setEasingCurve(curve)
        if on_done is not None:
            anim.finished.connect(on_done)
        anim.start()
        self._slide_anim = anim

    def _render(self) -> None:
        if not self.items or self._index >= len(self.items):
            self._show_summary()
            return
        item = self.items[self._index]
        self._revealed = False
        self._title.setText(self.title)
        self._progress_text.setText("%d / %d" % (self._index + 1, len(self.items)))
        self._bar.setValue(self._index + 1)
        self._word.setText(item.word)
        self._phonetic.setText(item.phonetic or "")
        self._meaning.setText(("%s %s" % (item.pos, item.meaning_cn)).strip())
        self._meaning.hide()
        self._example.setText(item.example or item.note or "")
        self._example.hide()
        self._btn_reveal.show()
        self._btn_reveal.setEnabled(True)
        self._btn_unknown.hide()
        self._btn_known.hide()
        self._btn_register.setVisible(bool(self.allow_register))
        self._btn_register.setEnabled(not item.registered)
        self._btn_register.setText("已在我的单词本" if item.registered else "登记到我的单词本")
        self._hint.setText("空格 显示中文 · ← 不认识 · → 认识 · Esc 退出")
        if self._index not in self._seen_sent and self._on_seen:
            self._seen_sent.add(self._index)
            try:
                self._on_seen(item)
            except Exception:  # noqa: BLE001 - 进度记录失败不应打断背诵
                pass

    def reveal(self) -> None:
        if self._revealed or not self.items:
            return
        self._revealed = True
        self._btn_reveal.hide()
        self._btn_unknown.show()
        self._btn_known.show()
        self._meaning.show()
        if self._example.text():
            self._example.show()
        self._hint.setText("← 不认识（明天再来） · → 认识（间隔拉长） · Esc 退出")
        if not self._reduced:
            effect = QGraphicsOpacityEffect(self._meaning)
            self._meaning.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(150)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda: self._meaning.setGraphicsEffect(None))
            self._anim = anim
            anim.start()

    def _answer(self, known: bool) -> None:
        if not self._revealed or not self.items:
            return
        item = self.items[self._index]
        self._answered += 1
        if known:
            self._known += 1
        if self._on_review:
            try:
                self._on_review(item, known)
            except Exception:  # noqa: BLE001
                pass
        if motion.reduced():
            self._index += 1
            self._render()
            return
        direction = -26 if known else 26
        base = self._card.pos()

        def advance() -> None:
            self._index += 1
            self._render()
            self._card.move(base - QPoint(int(direction * 0.7), 0))
            self._slide(int(direction * 0.7), motion.SWIPE_MS, motion.EASE_OUT)

        self._slide(direction, motion.SWIPE_MS, motion.EASE_IN, advance)

    def _register(self) -> None:
        if not self.items or not self._on_register:
            return
        item = self.items[self._index]
        if item.registered:
            return
        try:
            ok = self._on_register(item)
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            item.registered = True
            self._btn_register.setText("已在我的单词本")
            self._btn_register.setEnabled(False)

    def _show_summary(self) -> None:
        total = len(self.items)
        self._title.setText(self.title)
        self._progress_text.setText("完成")
        self._bar.setValue(total)
        self._word.setText("本轮结束")
        self._phonetic.setText("")
        self._meaning.setText("共 %d 词 · 认识 %d · 待复习 %d" % (total, self._known, max(0, total - self._known)))
        self._meaning.show()
        self._example.setText("")
        self._example.hide()
        self._btn_reveal.hide()
        self._btn_unknown.hide()
        self._btn_known.hide()
        self._btn_register.hide()
        self._hint.setText("按 Esc 或右上角关闭")
        self.finished.emit({"total": total, "known": self._known, "answered": self._answered})

    def close_session(self) -> None:
        self.finished.emit(
            {"total": len(self.items), "known": self._known, "answered": self._answered, "closed": True}
        )
        if motion.reduced():
            self.hide()
            return
        self._fade_veil(0.0, 140, motion.EASE_IN, self.hide)

    # ---------------------------------------------------------------- 事件
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        color = theme.veil_color()
        color.setAlphaF(max(0.0, min(1.0, color.alphaF() * self._veil_t)))
        painter.fillRect(self.rect(), color)
        painter.end()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._base_w = min(680, max(420, int(self.width() * 0.60)))
        self._base_h = min(430, max(340, int(self.height() * 0.52)))
        if not self.isVisible():
            self._card.setGeometry(self._rect_for(1.0))

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.setGeometry(self.parentWidget().rect())
        self.raise_()

    def keyPressEvent(self, event):  # noqa: N802
        key = event.key()
        if key == Qt.Key_Escape:
            self.close_session()
        elif key in (Qt.Key_Space, Qt.Key_Down):
            if not self._revealed:
                self.reveal()
            else:
                self._answer(True)
        elif key == Qt.Key_Right:
            self._answer(True)
        elif key == Qt.Key_Left:
            self._answer(False)
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        # 点浮层空白处不关闭，避免误触退出
        self.setFocus(Qt.OtherFocusReason)
        super().mousePressEvent(event)
