"""各类对话框：登记/编辑单词、单词书背诵选项、词根视图、拼写测试。"""
from typing import Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..models import Word
from ..services import quiz as quiz_service
from ..services import roots as roots_service
from . import theme


class AddWordDialog(QDialog):
    def __init__(
        self,
        parent=None,
        word: Optional[Word] = None,
        exists: Optional[Callable[[str, str], bool]] = None,
        preset: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(parent)
        self._word = word
        self._exists = exists
        self.setWindowTitle("编辑单词" if word else "登记单词")
        self.setModal(True)
        self.setMinimumWidth(theme.scale(460))

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(10)

        title = QLabel("编辑单词" if word else "登记一个新词")
        title.setObjectName("h1")
        root.addWidget(title)
        hint = QLabel("单词与中文必填；登记后默认抽背权重为 3，并记入今天这一行。")
        hint.setObjectName("faint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._word_edit = QLineEdit(self)
        self._word_edit.setPlaceholderText("abandon")
        f = QFont(theme.SERIF)
        f.setPixelSize(theme.fs(18))
        self._word_edit.setFont(f)
        root.addWidget(self._field("单词", self._word_edit))

        self._meaning_edit = QLineEdit(self)
        self._meaning_edit.setPlaceholderText("放弃；抛弃")
        root.addWidget(self._field("中文含义", self._meaning_edit))

        line = QHBoxLayout()
        line.setSpacing(10)
        self._phonetic_edit = QLineEdit(self)
        self._phonetic_edit.setPlaceholderText("/əˈbændən/")
        line.addWidget(self._field("音标", self._phonetic_edit), 1)
        self._pos = QComboBox(self)
        self._pos.setEditable(True)
        for item in config.POS_OPTIONS:
            self._pos.addItem(item)
        line.addWidget(self._field("词性", self._pos), 1)
        root.addLayout(line)

        self._tags_edit = QLineEdit(self)
        self._tags_edit.setPlaceholderText("CET4, 考研（可留空）")
        root.addWidget(self._field("标签", self._tags_edit))

        self._note_edit = QPlainTextEdit(self)
        self._note_edit.setPlaceholderText("备注 / 例句 / 记忆点（可留空）")
        self._note_edit.setFixedHeight(theme.scale(64))
        root.addWidget(self._field("备注", self._note_edit))

        self._error = QLabel("")
        self._error.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("danger"), theme.fs(11)))
        self._error.setWordWrap(True)
        root.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("保存" if word else "登记")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        root.addLayout(buttons)

        source = word.to_dict() if word else dict(preset or {})
        if source:
            self._word_edit.setText(str(source.get("word", "")))
            self._meaning_edit.setText(str(source.get("meaning_cn", "")))
            self._phonetic_edit.setText(str(source.get("phonetic", "")))
            pos_value = str(source.get("pos", ""))
            if pos_value:
                index = self._pos.findText(pos_value)
                if index >= 0:
                    self._pos.setCurrentIndex(index)
                else:
                    self._pos.setEditText(pos_value)
            tags = source.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            self._tags_edit.setText(", ".join(str(t) for t in tags))
            self._note_edit.setPlainText(str(source.get("note", "")))
        self._word_edit.setFocus()
        self._word_edit.selectAll()

    def _field(self, label: str, widget: QWidget) -> QWidget:
        holder = QWidget(self)
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)
        caption = QLabel(label)
        caption.setObjectName("muted")
        box.addWidget(caption)
        box.addWidget(widget)
        return holder

    def _save(self) -> None:
        word = self._word_edit.text().strip()
        meaning = self._meaning_edit.text().strip()
        if not word:
            self._error.setText("请填写单词。")
            self._word_edit.setFocus()
            return
        if not meaning:
            self._error.setText("请填写中文含义。")
            self._meaning_edit.setFocus()
            return
        if self._exists and self._exists(word, self._word.id if self._word else ""):
            self._error.setText("「%s」已经在我的单词本里了。" % word)
            return
        self.accept()

    def data(self) -> Dict[str, str]:
        tags = [t.strip() for t in self._tags_edit.text().replace("，", ",").split(",") if t.strip()]
        return {
            "word": self._word_edit.text().strip(),
            "meaning_cn": self._meaning_edit.text().strip(),
            "phonetic": self._phonetic_edit.text().strip(),
            "pos": self._pos.currentText().strip(),
            "tags": tags,
            "note": self._note_edit.toPlainText().strip(),
        }


class StudyOptionsDialog(QDialog):
    """选择背诵顺序与范围。"""

    def __init__(self, title: str, total: int, counts: Dict[str, int], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("开始背书")
        self.setModal(True)
        self.setMinimumWidth(theme.scale(420))
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(10)

        head = QLabel(title)
        head.setObjectName("h1")
        root.addWidget(head)
        summary = QLabel(
            "共 %d 词 · 已显示 %d · 已登记 %d" % (total, counts.get("seen", 0), counts.get("registered", 0))
        )
        summary.setObjectName("faint")
        root.addWidget(summary)

        order_label = QLabel("顺序")
        order_label.setObjectName("muted")
        root.addWidget(order_label)
        self._seq = QRadioButton("按编号顺序（0001 → 末尾）", self)
        self._seq.setChecked(True)
        self._rand = QRadioButton("随机顺序（每次不同）", self)
        root.addWidget(self._seq)
        root.addWidget(self._rand)

        scope_label = QLabel("范围")
        scope_label.setObjectName("muted")
        root.addWidget(scope_label)
        self._scope_all = QRadioButton("全部单词（%d）" % total, self)
        self._scope_all.setChecked(True)
        self._scope_unseen = QRadioButton("只背还没显示过的（%d）" % max(0, total - counts.get("seen", 0)), self)
        self._scope_registered = QRadioButton("只背已登记到单词本的（%d）" % counts.get("registered", 0), self)
        self._scope_unseen.setEnabled(total - counts.get("seen", 0) > 0)
        self._scope_registered.setEnabled(counts.get("registered", 0) > 0)
        for widget in (self._scope_all, self._scope_unseen, self._scope_registered):
            root.addWidget(widget)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        ok = QPushButton("开始")
        ok.setObjectName("primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        root.addLayout(buttons)

    def order(self) -> str:
        return "sequential" if self._seq.isChecked() else "random"

    def scope(self) -> str:
        if self._scope_unseen.isChecked():
            return "unseen"
        if self._scope_registered.isChecked():
            return "registered"
        return "all"


class RootsDialog(QDialog):
    def __init__(self, words: List[Word], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("词根视图")
        self.setModal(True)
        self.resize(theme.scale(620), theme.scale(520))
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        title = QLabel("词根聚合")
        title.setObjectName("h1")
        root.addWidget(title)
        hint = QLabel("从备注与 AI 拆解里提取词根；在备注里写「词根: spect」即可手动归类。")
        hint.setObjectName("faint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._tree = QTreeWidget(self)
        self._tree.setHeaderLabels(["词根 / 单词", "中文", "词性"])
        self._tree.setColumnWidth(0, theme.scale(220))
        self._tree.setAlternatingRowColors(False)
        root.addWidget(self._tree, 1)

        groups = roots_service.group_by_root(words)
        for root, items in groups.items():
            parent_item = QTreeWidgetItem(["%s（%d）" % (root, len(items)), "", ""])
            font = parent_item.font(0)
            font.setBold(True)
            parent_item.setFont(0, font)
            self._tree.addTopLevelItem(parent_item)
            for word in items:
                child = QTreeWidgetItem([word.word, word.meaning_cn, word.pos])
                parent_item.addChild(child)
            parent_item.setExpanded(True)
        loose = roots_service.ungrouped(words)
        if loose:
            other = QTreeWidgetItem(["未归类（%d）" % len(loose), "", ""])
            self._tree.addTopLevelItem(other)
            for word in loose:
                other.addChild(QTreeWidgetItem([word.word, word.meaning_cn, word.pos]))
        if not groups and not loose:
            self._tree.addTopLevelItem(QTreeWidgetItem(["还没有单词", "", ""]))

        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


class SpellingDialog(QDialog):
    answered = pyqtSignal(object, bool)

    def __init__(self, words: List[Word], parent=None, limit: int = 12) -> None:
        super().__init__(parent)
        self.setWindowTitle("拼写测试")
        self.setModal(True)
        self.resize(theme.scale(520), theme.scale(380))
        self._queue = quiz_service.weighted_order(words)[:limit]
        self._index = 0
        self._correct = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("看中文，写英文")
        title.setObjectName("h1")
        head.addWidget(title)
        head.addStretch(1)
        self._progress = QLabel("")
        self._progress.setObjectName("faint")
        head.addWidget(self._progress)
        root.addLayout(head)

        self._prompt = QLabel("")
        prompt_font = QFont(theme.SANS)
        prompt_font.setPixelSize(theme.fs(20))
        self._prompt.setFont(prompt_font)
        self._prompt.setWordWrap(True)
        self._prompt.setAlignment(Qt.AlignCenter)
        self._prompt.setMinimumHeight(theme.scale(70))
        root.addWidget(self._prompt)

        self._pos = QLabel("")
        self._pos.setObjectName("faint")
        self._pos.setAlignment(Qt.AlignCenter)
        root.addWidget(self._pos)

        self._input = QLineEdit(self)
        self._input.setPlaceholderText("输入英文，回车提交")
        input_font = QFont(theme.SERIF)
        input_font.setPixelSize(theme.fs(19))
        self._input.setFont(input_font)
        self._input.setAlignment(Qt.AlignCenter)
        self._input.returnPressed.connect(self._submit)
        root.addWidget(self._input)

        self._feedback = QLabel("")
        self._feedback.setAlignment(Qt.AlignCenter)
        self._feedback.setWordWrap(True)
        root.addWidget(self._feedback)

        row = QHBoxLayout()
        row.addStretch(1)
        self._reveal = QPushButton("看答案")
        self._reveal.setObjectName("ghost")
        self._reveal.clicked.connect(self._give_up)
        row.addWidget(self._reveal)
        self._next = QPushButton("提交")
        self._next.setObjectName("primary")
        self._next.clicked.connect(self._submit)
        row.addWidget(self._next)
        quit_btn = QPushButton("结束")
        quit_btn.setObjectName("link")
        quit_btn.clicked.connect(self.accept)
        row.addWidget(quit_btn)
        root.addLayout(row)

        self._load()

    def _load(self) -> None:
        if self._index >= len(self._queue):
            self._prompt.setText("这一轮结束")
            self._pos.setText("")
            self._feedback.setText("答对 %d / %d" % (self._correct, len(self._queue)))
            self._input.setEnabled(False)
            self._next.setEnabled(False)
            self._reveal.setEnabled(False)
            self._progress.setText("完成")
            return
        word = self._queue[self._index]
        self._progress.setText("%d / %d" % (self._index + 1, len(self._queue)))
        self._prompt.setText(word.meaning_cn)
        self._pos.setText(word.pos or "")
        self._feedback.setText("")
        self._input.clear()
        self._input.setEnabled(True)
        self._input.setFocus()
        self._next.setText("提交")

    def _submit(self) -> None:
        if self._index >= len(self._queue):
            return
        word = self._queue[self._index]
        answer = self._input.text().strip().lower()
        if not answer:
            return
        target = word.word.strip().lower()
        distance = _levenshtein(answer, target)
        if answer == target:
            self._correct += 1
            self._feedback.setText("✓ 正确")
            self._feedback.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("good"), theme.fs(13)))
            self._advance(True)
        elif distance == 1 and len(target) >= 5:
            self._correct += 1
            self._feedback.setText("✓ 拼写略有偏差，正确答案：%s" % word.word)
            self._feedback.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("good"), theme.fs(13)))
            self._advance(True, delay=True)
        else:
            self._feedback.setText("✗ 正确答案是 %s" % word.word)
            self._feedback.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("danger"), theme.fs(13)))
            self.answered.emit(word, False)
            self._index += 1
            self._load()

    def _advance(self, correct: bool, delay: bool = False) -> None:
        word = self._queue[self._index]
        self.answered.emit(word, correct)
        self._index += 1
        if delay:
            from PyQt5.QtCore import QTimer

            QTimer.singleShot(650, self._load)
        else:
            self._load()

    def _give_up(self) -> None:
        if self._index >= len(self._queue):
            return
        word = self._queue[self._index]
        self._feedback.setText("答案是 %s" % word.word)
        self._feedback.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("ink_soft"), theme.fs(13)))
        self.answered.emit(word, False)
        self._index += 1
        from PyQt5.QtCore import QTimer

        QTimer.singleShot(700, self._load)
