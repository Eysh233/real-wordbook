"""统计页（F4）：总量、连续天数、正确率 + 12 周热力图。"""
from typing import Any, Dict, List

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..services import stats as stats_service
from . import theme

CELL = 17
GAP = 5


class HeatmapWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._grid: List[List[Dict[str, Any]]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(150)

    def set_data(self, grid: List[List[Dict[str, Any]]]) -> None:
        self._grid = grid
        self.update()

    def _origin(self):
        cols = len(self._grid) or 12
        grid_w = cols * CELL + (cols - 1) * GAP
        left = max(40, int((self.width() - grid_w) / 2))
        top = 26
        return left, top

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        left, top = self._origin()
        f = QFont(theme.SANS)
        f.setPixelSize(theme.fs(9))
        painter.setFont(f)

        if not self._grid:
            painter.setPen(theme.color("ink_faint"))
            painter.drawText(self.rect(), Qt.AlignCenter, "还没有学习记录")
            painter.end()
            return

        # 月标签
        last_month = ""
        cols = len(self._grid)
        painter.setPen(theme.color("ink_faint"))
        for col, week in enumerate(self._grid):
            first = week[0]["date"]
            month = first[5:7]
            if month != last_month:
                painter.drawText(
                    QRectF(left + col * (CELL + GAP), 2, CELL * 4, 14),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    "%s月" % int(month),
                )
                last_month = month

        # 周标签
        labels = {0: "一", 2: "三", 4: "五", 6: "日"}
        painter.setPen(theme.color("ink_faint"))
        for row, text in labels.items():
            painter.drawText(
                QRectF(left - 34, top + row * (CELL + GAP), 28, CELL),
                Qt.AlignRight | Qt.AlignVCenter,
                text,
            )

        # 方块
        painter.setPen(Qt.NoPen)
        for col, week in enumerate(self._grid):
            for row, day in enumerate(week):
                total = int(day.get("added", 0)) + int(day.get("quiz", 0))
                rect = QRectF(left + col * (CELL + GAP), top + row * (CELL + GAP), CELL, CELL)
                if day.get("future"):
                    colr = QColor(theme.css("rule"))
                    colr.setAlpha(90)
                elif total == 0:
                    colr = QColor(theme.css("rule"))
                    colr.setAlpha(150)
                else:
                    base = QColor(theme.css("accent"))
                    if total <= 2:
                        base.setAlpha(80)
                    elif total <= 5:
                        base.setAlpha(125)
                    elif total <= 9:
                        base.setAlpha(175)
                    else:
                        base.setAlpha(235)
                    colr = base
                painter.setBrush(colr)
                painter.drawRoundedRect(rect, 3, 3)

        painter.setPen(theme.color("ink_faint"))
        painter.setFont(f)
        painter.drawText(
            QRectF(left, top + 7 * (CELL + GAP) + 8, 300, 16),
            Qt.AlignLeft | Qt.AlignVCenter,
            "每天登记 + 抽背的次数",
        )

        # 图例：少 → 多
        legend_y = top + 7 * (CELL + GAP) + 7
        legend_x = int(left + cols * (CELL + GAP) - 5 * (CELL + GAP) - 34)
        painter.drawText(QRectF(legend_x, legend_y, 30, 16), Qt.AlignRight | Qt.AlignVCenter, "少")
        for i in range(4):
            base = QColor(theme.css("accent"))
            base.setAlpha((80, 125, 175, 235)[i])
            painter.setPen(Qt.NoPen)
            painter.setBrush(base)
            rect = QRectF(legend_x + 34 + i * (CELL + GAP), legend_y + 1, CELL, CELL)
            painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(theme.color("ink_faint"))
        painter.drawText(
            QRectF(legend_x + 40 + 4 * (CELL + GAP), legend_y, 30, 16),
            Qt.AlignLeft | Qt.AlignVCenter,
            "多",
        )
        painter.end()

    def mouseMoveEvent(self, event):  # noqa: N802
        left, top = self._origin()
        x = event.pos().x() - left
        y = event.pos().y() - top
        col = int(x // (CELL + GAP))
        row = int(y // (CELL + GAP))
        if 0 <= col < len(self._grid) and 0 <= row < 7:
            day = self._grid[col][row]
            self.setToolTip(
                "%s · 登记 %d · 抽背 %d" % (day.get("date", ""), day.get("added", 0), day.get("quiz", 0))
            )
        else:
            self.setToolTip("")
        super().mouseMoveEvent(event)


class StatsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 18, 26, 18)
        root.setSpacing(14)

        title = QLabel("统计")
        title.setObjectName("h1")
        root.addWidget(title)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self._values = {}
        for key, label in (
            ("total", "总词数"),
            ("today_added", "今日新增"),
            ("streak", "连续登记"),
            ("accuracy", "抽背正确率"),
        ):
            frame = QWidget()
            frame.setObjectName("statCard")
            frame.setStyleSheet(
                "#statCard { background: %s; border: 1px solid %s; border-radius: 14px; }"
                % (theme.css("paper"), theme.css("rule"))
            )
            box = QVBoxLayout(frame)
            box.setContentsMargins(16, 14, 16, 14)
            box.setSpacing(2)
            value = QLabel("0")
            value.setObjectName("statValue")
            box.addWidget(value)
            caption = QLabel(label)
            caption.setObjectName("statLabel")
            box.addWidget(caption)
            self._values[key] = value
            cards.addWidget(frame, 1)
        root.addLayout(cards)

        heat_card = QWidget()
        heat_card.setStyleSheet(
            "#statCard { background: %s; border: 1px solid %s; border-radius: 14px; }"
            % (theme.css("paper"), theme.css("rule"))
        )
        heat_card.setObjectName("statCard")
        heat_card.setFixedHeight(theme.scale(292))
        heat_box = QVBoxLayout(heat_card)
        heat_box.setContentsMargins(18, 14, 18, 14)
        heat_box.setSpacing(4)
        heat_title = QLabel("最近 12 周")
        heat_title.setObjectName("muted")
        heat_box.addWidget(heat_title)
        self._heat = HeatmapWidget(heat_card)
        heat_box.addWidget(self._heat, 1)
        root.addWidget(heat_card)

        extra = QHBoxLayout()
        extra.setSpacing(12)
        self._review_card, self._review_box = self._make_card("复习节奏")
        self._tag_card, self._tag_box = self._make_card("标签")
        extra.addWidget(self._review_card, 1)
        extra.addWidget(self._tag_card, 1)
        root.addLayout(extra)
        root.addStretch(1)

        foot = QHBoxLayout()
        self._detail = QLabel("")
        self._detail.setObjectName("faint")
        self._detail.setWordWrap(True)
        foot.addWidget(self._detail, 1)
        root.addLayout(foot)

        self._stats_repo = None
        self._words = []

    def _make_card(self, title: str):
        card = QWidget()
        card.setObjectName("statCard")
        card.setStyleSheet(
            "#statCard { background: %s; border: 1px solid %s; border-radius: 14px; }"
            % (theme.css("paper"), theme.css("rule"))
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("muted")
        outer.addWidget(label)
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        outer.addLayout(box)
        outer.addStretch(1)
        return card, box

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _line(self, text: str, faint: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setObjectName("faint" if faint else "muted")
        if not faint:
            label.setStyleSheet("color: %s; font-size: %dpx;" % (theme.css("ink"), theme.fs(12)))
        return label

    def refresh(self, words, stats_repo) -> None:
        self._words = list(words)
        self._stats_repo = stats_repo
        summary = stats_service.summary(self._words, stats_repo)
        self._values["total"].setText(str(summary["total"]))
        self._values["today_added"].setText(str(summary["today_added"]))
        self._values["streak"].setText("%d 天" % summary["streak"])
        self._values["accuracy"].setText("%d%%" % int(round(summary["accuracy"] * 100)))
        grid = stats_service.heatmap_weeks(self._words, stats_repo, weeks=12)
        self._heat.set_data(grid)
        self._detail.setText("热力图按周一到周日排列，鼠标悬停可看单日登记与抽背次数。")
        self._fill_extra(summary)

    def _fill_extra(self, summary: dict) -> None:
        from datetime import date

        today = date.today().isoformat()
        overdue = 0
        due_today = 0
        for word in self._words:
            due = (word.due or "")[:10]
            if not due:
                continue
            if due < today:
                overdue += 1
            elif due == today:
                due_today += 1

        self._clear(self._review_box)
        self._review_box.addWidget(self._line("今天到期 %d 词" % due_today))
        self._review_box.addWidget(self._line("已超期 %d 词" % overdue, faint=True))
        self._review_box.addWidget(self._line("累计抽背 %d 次" % summary["quiz_total"], faint=True))
        self._review_box.addWidget(
            self._line("标注 %d · 划线 %d" % (summary["highlight"], summary["strike"]), faint=True)
        )

        counts = {}
        for word in self._words:
            for tag in word.tags or []:
                counts[tag] = counts.get(tag, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
        self._clear(self._tag_box)
        if not ranked:
            self._tag_box.addWidget(self._line("还没有标签。登记时填「CET4, 考研」之类即可。", faint=True))
        else:
            for tag, count in ranked:
                self._tag_box.addWidget(self._line("%s · %d 词" % (tag, count)))
