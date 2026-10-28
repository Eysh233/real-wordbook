"""单词格：纸页上的一个可点击词条，负责标注/划线的绘制。"""
from PyQt5.QtCore import QRectF, Qt, QVariantAnimation, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget

from .. import config
from ..models import Word
from ..services import quiz as quiz_service
from . import motion, painter_utils, theme


class WordCell(QWidget):
    clicked = pyqtSignal(object)

    def __init__(self, word: Word, mode: str = config.DISPLAY_BOTH, parent=None) -> None:
        super().__init__(parent)
        self.word = word
        self.mode = mode
        self._hover = False
        self._hover_t = 0.0
        self._hover_target = 0.0
        self._pressed = False
        self._selected = False
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setEasingCurve(motion.EASE_OUT)
        self._hover_anim.valueChanged.connect(self._set_hover)
        self._hover_anim.finished.connect(self._snap_hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setToolTip(self._tooltip())

    # ---------------------------------------------------------------- 数据
    def set_word(self, word: Word) -> None:
        self.word = word
        self.setToolTip(self._tooltip())
        self.update()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def _tooltip(self) -> str:
        parts = [self.word.word, self.word.meaning_cn]
        if self.word.pos:
            parts.insert(1, self.word.pos)
        parts.append("权重 %d" % self.word.weight)
        return " · ".join([p for p in parts if p])

    def sizeHint(self):
        from PyQt5.QtCore import QSize

        return QSize(theme.scale(150), theme.scale(72))

    # ---------------------------------------------------------------- 交互
    def enterEvent(self, event):  # noqa: N802
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._pressed = False
        self.set_hovered(False)
        super().leaveEvent(event)

    def set_hovered(self, hovered: bool) -> None:
        """显式的悬停状态：鼠标进出、翻页重建、窗口失焦都走这里。

        只保留一条动画并复用，避免快速划过时「旧动画还在跑、新动画又启动」
        把 `_hover_t` 停在 1.0，让词格一直亮着。
        """
        self._hover = hovered
        self._animate_hover(1.0 if hovered else 0.0)

    def _animate_hover(self, target: float) -> None:
        self._hover_target = target
        anim = self._hover_anim
        anim.stop()
        if motion.reduced() or abs(self._hover_t - target) < 0.01:
            self._set_hover(target)
            return
        anim.setDuration(motion.ms(motion.HOVER_MS))
        anim.setStartValue(float(self._hover_t))
        anim.setEndValue(float(target))
        anim.start()

    def _snap_hover(self) -> None:
        # 动画结束时精确落位，避免缓动尾巴留下 0.02 之类的残值
        self._set_hover(self._hover_target)

    def _set_hover(self, value) -> None:
        self._hover_t = float(value)
        self.update()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        was = self._pressed
        self._pressed = False
        self.update()
        if was and event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self.word)
        super().mouseReleaseEvent(event)

    # ---------------------------------------------------------------- 绘制
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        box = QRectF(self.rect()).adjusted(4, 1, -4, -1)
        tint = theme.color("accent")
        if self._pressed:
            tint.setAlpha(30)
            painter.setPen(Qt.NoPen)
            painter.setBrush(tint)
            painter.drawRoundedRect(box, 8, 8)
        elif self._hover_t > 0.01:
            # 悬停底色随动画长大，不是突然出现
            tint.setAlpha(int(16 * self._hover_t))
            painter.setPen(Qt.NoPen)
            painter.setBrush(tint)
            painter.drawRoundedRect(box, 8, 8)

        if self._selected:
            ring = QColor(theme.color("accent"))
            ring.setAlpha(150)
            painter.setPen(QPen(ring, 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(box, 8, 8)

        word = self.word
        seed = abs(hash(word.id or word.word)) % 100000

        # 字体
        f_word = QFont(theme.SERIF)
        f_word.setPixelSize(theme.fs(17 if self.mode != config.DISPLAY_CN else 16))
        f_word.setWeight(QFont.DemiBold)
        f_word.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)

        f_phon = QFont(theme.SANS)
        f_phon.setPixelSize(theme.fs(9))
        f_phon.setItalic(True)

        f_mean = QFont(theme.SANS)
        f_mean.setPixelSize(theme.fs(11 if self.mode != config.DISPLAY_CN else 15))

        left = box.left() + 7
        width = box.width() - 14
        text_width = max(20.0, width)

        painter.setFont(f_word)
        word_text = painter.fontMetrics().elidedText(word.word, Qt.ElideRight, int(text_width))
        word_h = painter.fontMetrics().height()
        word_top = box.top() + theme.scale(8)
        word_rect = QRectF(left, word_top, min(text_width, painter.fontMetrics().width(word_text) + 6), word_h)

        painter.setFont(f_mean)
        mean_text = painter.fontMetrics().elidedText(word.meaning_cn, Qt.ElideRight, int(text_width))
        mean_h = painter.fontMetrics().height()
        mean_top = box.top() + theme.scale(40)
        mean_rect = QRectF(left, mean_top, min(text_width, painter.fontMetrics().width(mean_text) + 6), mean_h)

        # 荧光笔底色
        if word.highlight:
            painter.setOpacity(0.95 if self._hover else 0.86)
            if self.mode != config.DISPLAY_CN:
                painter_utils.draw_highlight(painter, word_rect.adjusted(-2, -2, 4, 2), theme.highlight_color(), seed)
            if self.mode != config.DISPLAY_EN:
                painter_utils.draw_highlight(painter, mean_rect.adjusted(-2, -1, 4, 1), theme.highlight_color(), seed + 3)
            painter.setOpacity(1.0)

        # 英文
        if self.mode != config.DISPLAY_CN:
            painter.setFont(f_word)
            painter.setPen(theme.color("ink"))
            painter.drawText(QRectF(left, word_top, text_width, word_h), Qt.AlignLeft | Qt.AlignVCenter, word_text)
            painter.setFont(f_phon)
            painter.setPen(theme.color("ink_faint"))
            phon = word.phonetic or ""
            painter.drawText(
                QRectF(left, word_top + word_h - theme.scale(3), text_width, theme.scale(12)),
                Qt.AlignLeft | Qt.AlignVCenter,
                painter.fontMetrics().elidedText(phon, Qt.ElideRight, int(text_width)),
            )

        # 中文
        if self.mode != config.DISPLAY_EN:
            painter.setFont(f_mean)
            painter.setPen(theme.color("ink_soft"))
            painter.drawText(QRectF(left, mean_top, text_width, mean_h), Qt.AlignLeft | Qt.AlignVCenter, mean_text)

        # 划线压字
        if word.strike:
            painter.setOpacity(0.9)
            if self.mode != config.DISPLAY_CN:
                painter_utils.draw_strike(
                    painter, left, left + painter.fontMetrics().width(word_text) + 2,
                    word_top + word_h / 2.0 + 1, theme.strike_color(), seed,
                )
            if self.mode != config.DISPLAY_EN:
                painter.setFont(f_mean)
                painter_utils.draw_strike(
                    painter, left, left + painter.fontMetrics().width(mean_text) + 2,
                    mean_top + mean_h / 2.0 + 1, theme.strike_color(), seed + 5,
                )
            painter.setOpacity(1.0)

        # 到期标记 / 权重提示
        mark = quiz_service.difficulty_marks(word)
        if mark:
            painter.setFont(f_phon)
            painter.setPen(theme.color("accent"))
            painter.drawText(
                QRectF(box.right() - theme.scale(16), box.top(), theme.scale(14), theme.scale(16)),
                Qt.AlignRight | Qt.AlignTop, mark,
            )
        if self._hover:
            painter.setFont(f_phon)
            painter.setPen(theme.color("ink_faint"))
            painter.drawText(
                QRectF(box.right() - theme.scale(48), box.bottom() - theme.scale(15), theme.scale(46), theme.scale(14)),
                Qt.AlignRight | Qt.AlignVCenter, "w%d" % word.weight,
            )
        painter.end()
