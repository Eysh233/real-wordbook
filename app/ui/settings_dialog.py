"""设置：API Key、模型、推理等级、主题、默认显示、字号、动效。"""
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..models import Settings
from ..repositories import SecretRepo
from . import theme


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, secret: SecretRepo, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setMinimumWidth(theme.scale(520))
        self._settings = Settings.from_dict(settings.to_dict())
        self._secret = secret
        self._cleared = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("h1")
        root.addWidget(title)
        subtitle = QLabel("密钥只保存在本机 ~/.real_wordbook/config.json，不会写入仓库。")
        subtitle.setObjectName("faint")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self._key_input = QLineEdit(self)
        self._key_input.setEchoMode(QLineEdit.Password)
        self._key_input.setPlaceholderText("sk-…（留空表示沿用已保存的 Key）")
        existing = secret.api_key
        if existing:
            self._key_input.setPlaceholderText("已保存 %s，留空则不修改" % secret.mask())
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(self._key_input, 1)
        clear_btn = QPushButton("清除已保存")
        clear_btn.setObjectName("link")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setVisible(bool(existing))
        clear_btn.clicked.connect(self._clear_key)
        self._clear_btn = clear_btn
        key_row.addWidget(clear_btn)
        root.addWidget(self._labeled("DeepSeek API Key", key_row))

        self._model = QComboBox(self)
        self._model.setEditable(True)
        for item in ("deepseek-flash", "deepseek-chat", "deepseek-reasoner"):
            self._model.addItem(item)
        self._model.setCurrentText(settings.ai_model or config.AI_MODEL)
        root.addWidget(self._labeled("模型", self._model))

        self._effort = QComboBox(self)
        for key, label in (("low", "low · 快速作答（默认）"), ("high", "high · 多想一步"), ("max", "max · 最慢最深")):
            self._effort.addItem(label, key)
        index = self._effort.findData(settings.ai_effort or config.AI_EFFORT)
        self._effort.setCurrentIndex(max(0, index))
        root.addWidget(self._labeled("推理等级", self._effort))

        self._theme = QComboBox(self)
        for key in (config.THEME_PAPER, config.THEME_GREEN, config.THEME_DARK):
            self._theme.addItem(config.THEME_LABELS[key], key)
        self._theme.setCurrentIndex(max(0, self._theme.findData(settings.theme)))
        root.addWidget(self._labeled("纸张主题", self._theme))

        self._display = QComboBox(self)
        for key in (config.DISPLAY_BOTH, config.DISPLAY_EN, config.DISPLAY_CN):
            self._display.addItem(config.DISPLAY_LABELS[key], key)
        self._display.setCurrentIndex(max(0, self._display.findData(settings.display_mode)))
        root.addWidget(self._labeled("默认显示", self._display))

        scale_row = QHBoxLayout()
        scale_row.setSpacing(10)
        self._scale = QSlider(Qt.Horizontal, self)
        self._scale.setRange(85, 140)
        self._scale.setValue(int(round(settings.font_scale * 100)))
        self._scale_label = QLabel("%d%%" % self._scale.value())
        self._scale_label.setObjectName("faint")
        self._scale.valueChanged.connect(lambda value: self._scale_label.setText("%d%%" % value))
        scale_row.addWidget(self._scale, 1)
        scale_row.addWidget(self._scale_label)
        root.addWidget(self._labeled("字号", scale_row))

        self._reduced = QCheckBox("减少动效（关闭翻页淡入与卡片过渡）", self)
        self._reduced.setChecked(settings.reduced_motion)
        root.addWidget(self._reduced)

        note = QLabel(
            "提示：AI 解释会把单词与已填中文发送给 DeepSeek；同一单词 + 同一模型的解释会缓存，避免重复计费。"
        )
        note.setObjectName("faint")
        note.setWordWrap(True)
        root.addWidget(note)

        root.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("保存")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _labeled(self, text: str, field) -> QWidget:
        holder = QWidget(self)
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        label = QLabel(text)
        label.setObjectName("muted")
        box.addWidget(label)
        if isinstance(field, QHBoxLayout):
            box.addLayout(field)
        else:
            box.addWidget(field)
        return holder

    def _clear_key(self) -> None:
        self._cleared = True
        self._key_input.clear()
        self._key_input.setPlaceholderText("已标记清除，保存后生效")

    def _save(self) -> None:
        self._settings.ai_model = self._model.currentText().strip() or config.AI_MODEL
        self._settings.ai_effort = self._effort.currentData() or config.AI_EFFORT
        self._settings.theme = self._theme.currentData() or config.THEME_PAPER
        self._settings.display_mode = self._display.currentData() or config.DISPLAY_BOTH
        self._settings.font_scale = self._scale.value() / 100.0
        self._settings.reduced_motion = self._reduced.isChecked()
        self.accept()

    def result_settings(self) -> Settings:
        return self._settings

    def key_to_save(self) -> Optional[str]:
        text = self._key_input.text().strip()
        return text or None

    def key_cleared(self) -> bool:
        return self._cleared
