"""单词操作浮层：标注 / 划线 / 发音 / AI解释 / 编辑 / 删除。"""
from typing import Optional

from PyQt5.QtCore import QRect, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..models import Word
from . import motion, theme, widgets

WIDTH_IDLE = 396
WIDTH_AI = 476


class ActionPopover(QFrame):
    highlightToggled = pyqtSignal(object)
    strikeToggled = pyqtSignal(object)
    explainRequested = pyqtSignal(object)
    editRequested = pyqtSignal(object)
    deleteRequested = pyqtSignal(object)
    speakRequested = pyqtSignal(object)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("popover")
        self.setWindowFlag(Qt.NoDropShadowWindowHint, True)
        self.word: Optional[Word] = None
        self._anchor = QRect()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(20, 16, 12, 70))
        self.setGraphicsEffect(shadow)
        self.setFixedWidth(WIDTH_IDLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._title = QLabel("")
        font = QFont(theme.SERIF)
        font.setPixelSize(theme.fs(19))
        font.setWeight(QFont.DemiBold)
        self._title.setFont(font)
        self._title.setStyleSheet("color: %s;" % theme.css("ink"))
        header.addWidget(self._title)
        self._phonetic = QLabel("")
        self._phonetic.setObjectName("faint")
        header.addWidget(self._phonetic)
        header.addStretch(1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { border: none; border-radius: 12px; padding: 0px; color: %s; font-size: %dpx; }"
            "QPushButton:hover { background: rgba(127,110,88,30); }"
            % (theme.css("ink_soft"), theme.fs(16))
        )
        close_btn.clicked.connect(self.close_popover)
        header.addWidget(close_btn)
        root.addLayout(header)

        self._meaning = QLabel("")
        self._meaning.setWordWrap(True)
        self._meaning.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("ink_soft"), theme.fs(12)))
        root.addWidget(self._meaning)

        root.addWidget(widgets.divider())

        row = QHBoxLayout()
        row.setSpacing(6)
        self._btn_highlight = self._tool_button("标注", row)
        self._btn_strike = self._tool_button("划线", row)
        self._btn_speak = self._tool_button("发音", row)
        root.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self._btn_ai = self._tool_button("AI解释", row2)
        self._btn_edit = self._tool_button("编辑", row2)
        self._btn_delete = self._tool_button("删除", row2)
        self._btn_delete.setObjectName("danger")
        root.addLayout(row2)

        self._ai = QTextBrowser(self)
        self._ai.setOpenExternalLinks(True)
        self._ai.setFixedHeight(theme.scale(250))
        self._ai.setStyleSheet(
            "QTextBrowser { background: %s; border: 1px solid %s; border-radius: 10px; padding: 8px; }"
            % (theme.css("paper_alt"), theme.css("rule"))
        )
        self._ai.hide()
        root.addWidget(self._ai)

        self._footer = QLabel("")
        self._footer.setObjectName("faint")
        self._footer.setWordWrap(True)
        root.addWidget(self._footer)

        self._btn_highlight.clicked.connect(self._on_highlight)
        self._btn_strike.clicked.connect(self._on_strike)
        self._btn_speak.clicked.connect(lambda: self.word and self.speakRequested.emit(self.word))
        self._btn_ai.clicked.connect(self._on_ai)
        self._btn_edit.clicked.connect(lambda: self.word and self.editRequested.emit(self.word))
        self._btn_delete.clicked.connect(lambda: self.word and self.deleteRequested.emit(self.word))
        self.hide()

    # ---------------------------------------------------------------- 构建
    def _tool_button(self, label: str, layout: QHBoxLayout) -> QPushButton:
        """工具按钮必须有实体：1px 描边 + 淡纸底，悬停时描边转为 accent。"""
        button = QPushButton(label)
        button.setCursor(Qt.PointingHandCursor)
        button.setCheckable(False)
        button.setMinimumHeight(theme.scale(30))
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setStyleSheet(self._tool_qss(False))
        layout.addWidget(button, 1)
        return button

    @staticmethod
    def _tool_qss(active: bool) -> str:
        base = (
            "QPushButton { border: 1px solid %s; background: %s; border-radius: 9px;"
            " padding: 6px 10px; font-size: %dpx; color: %s; }"
            "QPushButton:hover { border-color: %s; background: %s; }"
            "QPushButton:pressed { background: %s; }"
            % (
                theme.css("rule"),
                theme.css("paper_alt"),
                theme.fs(13),
                theme.css("ink"),
                theme.css("accent"),
                theme.css("popover"),
                theme.css("accent_soft"),
            )
        )
        if active:
            base += (
                "QPushButton { background: %s; border-color: %s; font-weight: 600; }"
                % (theme.css("highlight"), theme.css("accent"))
            )
        return base

    def _set_active(self, button: QPushButton, label: str, active: bool) -> None:
        button.setText(("✓ " if active else "") + label)
        button.setStyleSheet(self._tool_qss(active))

    # ---------------------------------------------------------------- 打开
    def _bind_word(self, word: Word) -> None:
        self.word = word
        self._title.setText(word.word)
        self._phonetic.setText(word.phonetic or "")
        self._phonetic.setVisible(bool(word.phonetic))
        pos = ("%s " % word.pos) if word.pos else ""
        self._meaning.setText("%s%s" % (pos, word.meaning_cn))
        self._footer.setText(
            "权重 %d · %s 登记 · Esc 关闭%s"
            % (word.weight, word.date_added or "—", " · AI 结果已缓存" if word.ai else "")
        )
        self._refresh_state()

    def refresh_word(self, word: Word) -> None:
        """外部改动了单词（标注/划线/编辑）后同步浮层，不改变位置。"""
        if not self.isVisible():
            return
        self._bind_word(word)
        self.adjustSize()

    def open_for(self, word: Word, anchor: QRect) -> None:
        self._anchor = anchor
        self._bind_word(word)
        self._ai.hide()
        self.setFixedWidth(WIDTH_IDLE)
        self.adjustSize()
        self.show()
        self.raise_()
        self._place()
        # 从被点词格的位置“长出来”：锚点落在浮层上沿，符合空间一致性
        effect = motion.surface(self)
        anchor_local = self.mapFromGlobal(self._anchor.center())
        ox = 0.5 if not self.width() else max(0.0, min(1.0, anchor_local.x() / float(self.width())))
        below = anchor_local.y() <= 0
        motion.pop_in(self, origin=(ox, 0.0 if below else 1.0))
        effect.set_lift(0.0)

    def _refresh_state(self) -> None:
        if not self.word:
            return
        self._set_active(self._btn_highlight, "标注", self.word.highlight)
        self._set_active(self._btn_strike, "划线", self.word.strike)

    def _place(self) -> None:
        parent = self.parentWidget()
        if not parent or self._anchor.isNull():
            return
        top_left = parent.mapFromGlobal(self._anchor.topLeft())
        bottom_left = parent.mapFromGlobal(self._anchor.bottomLeft())
        size = self.sizeHint()
        width = self.width()
        height = size.height()
        x = top_left.x() - 8
        y = bottom_left.y() + 8
        if y + height > parent.height() - 12:
            y = max(12, top_left.y() - height - 8)
        x = max(12, min(x, parent.width() - width - 12))
        self.setGeometry(int(x), int(y), int(width), int(height))
        self.raise_()

    def close_popover(self) -> None:
        if not self.isVisible():
            self.word = None
            return
        self.word = None
        motion.pop_out(self, on_done=self.hide)

    # ---------------------------------------------------------------- AI
    def _on_ai(self) -> None:
        if not self.word:
            return
        if self.word.ai:
            self.show_ai(self.word.ai)
            return
        self.explainRequested.emit(self.word)

    def set_ai_loading(self) -> None:
        self._ai.show()
        self._ai.setHtml(
            "<div style='color:%s; font-size:11pt; padding:8px 2px;'>正在请 DeepSeek 拆解这个词……</div>"
            % theme.css("ink_soft")
        )
        self._fit_ai()

    def show_ai(self, data: dict) -> None:
        if not self.word:
            return
        self._ai.show()
        self._ai.setHtml(self._ai_html(data, self.word))
        self._fit_ai()

    def set_ai_error(self, message: str) -> None:
        self._ai.show()
        self._ai.setHtml(
            "<div style='color:%s; font-size:11pt; padding:6px 2px;'>AI 解释失败：%s<br><br>"
            "可在「设置」里检查 API Key 与网络。</div>" % (theme.css("danger"), message)
        )
        self._fit_ai()

    def _fit_ai(self) -> None:
        """按内容高度调整 AI 面板，避免大片留白。"""
        self.setFixedWidth(WIDTH_AI)
        self._ai.setFixedWidth(WIDTH_AI - 36)
        self._ai.ensurePolished()
        doc = self._ai.document()
        width = self._ai.viewport().width()
        if width <= 0:
            width = WIDTH_AI - 72
        doc.setTextWidth(width)
        height = int(doc.documentLayout().documentSize().height()) + 22
        self._ai.setFixedHeight(max(theme.scale(88), min(theme.scale(300), height)))
        self.adjustSize()
        self._place()

    def _ai_html(self, data: dict, word: Word) -> str:
        ink = theme.css("ink")
        soft = theme.css("ink_soft")
        accent = theme.css("accent")
        faint = theme.css("ink_faint")

        def section(title: str, body: str) -> str:
            if not body:
                return ""
            return (
                "<div style='margin-top:9px;'>"
                "<div style='color:%s; font-size:10pt; letter-spacing:1px;'>%s</div>"
                "<div style='color:%s; font-size:10.5pt; margin-top:2px;'>%s</div></div>"
                % (faint, title, ink, body)
            )

        parts = [
            "<div style='font-family:\"Microsoft YaHei UI\"; line-height:145%%;'>",
            "<div style='font-size:13pt; color:%s; font-weight:600;'>%s</div>"
            % (ink, data.get("translation_cn") or word.meaning_cn),
        ]
        if data.get("meaning_en"):
            parts.append("<div style='color:%s; font-size:10pt; font-style:italic;'>%s</div>" % (soft, data["meaning_en"]))
        if data.get("breakdown"):
            parts.append(section("构词", data["breakdown"]))
        collocations = data.get("collocations") or []
        if collocations:
            parts.append(section("搭配", " · ".join(collocations)))
        confusables = data.get("confusables") or []
        if confusables:
            parts.append(
                section("易混", " · ".join("<span style='color:%s'>%s</span>" % (accent, item) for item in confusables))
            )
        examples = data.get("examples") or []
        if examples:
            rows = []
            for item in examples[:2]:
                en = item.get("en", "")
                cn = item.get("cn", "")
                rows.append(
                    "<div style='margin:3px 0;'><span style='font-family:Segoe UI; font-size:10.5pt;'>%s</span>"
                    "<br><span style='color:%s; font-size:10pt;'>%s</span></div>" % (en, soft, cn)
                )
            parts.append(section("例句", "".join(rows)))
        if data.get("memory_tip"):
            parts.append(section("记忆", data["memory_tip"]))
        parts.append("</div>")
        return "".join(parts)

    # ---------------------------------------------------------------- 事件
    def _on_highlight(self) -> None:
        if self.word:
            self.highlightToggled.emit(self.word)

    def _on_strike(self) -> None:
        if self.word:
            self.strikeToggled.emit(self.word)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.close_popover()
        else:
            super().keyPressEvent(event)
