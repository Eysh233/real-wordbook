"""视觉主题：三套 token（米白纸 / 护眼绿 / 深色）+ 全局 QSS。

所有绘制都从这里取色，切换主题时只需 set_theme + 重新 setStyleSheet。
"""
from typing import Dict

from PyQt5.QtGui import QColor

from .. import config

# 英文一律用无衬线（黑体观感）；中文用雅黑
SERIF = "Segoe UI"
SANS = "Microsoft YaHei UI"

# 字号整体放大一档：所有字号都过 fs()，与间距用的 scale() 分开
FONT_BOOST = 1.12

THEMES: Dict[str, Dict[str, str]] = {
    config.THEME_PAPER: {
        "desk": "#E5DAC6",
        "desk_deep": "#D2C5AC",
        "paper": "#FBF7EE",
        "paper_alt": "#F5EFE1",
        "spine": "#EFE5D0",
        "spine_hole": "#CDBE9F",
        "ink": "#2B2722",
        "ink_soft": "#6B6459",
        "ink_faint": "#A2988A",
        "rule": "#E4DAC6",
        "accent": "#C4703C",
        "accent_soft": "#E8D2C0",
        "highlight": "#FFE26E",
        "highlight_alpha": "184",
        "strike": "#6B6459",
        "danger": "#B4483C",
        "good": "#4E7A4A",
        "popover": "#FFFCF5",
        "shadow": "rgba(43, 39, 34, 34)",
        "veil": "rgba(43, 39, 34, 120)",
    },
    config.THEME_GREEN: {
        "desk": "#DCE3D2",
        "desk_deep": "#C9D2BD",
        "paper": "#F1F4E6",
        "paper_alt": "#E9EEDA",
        "spine": "#DCE4CC",
        "spine_hole": "#C3CFB0",
        "ink": "#232E20",
        "ink_soft": "#5B6754",
        "ink_faint": "#8E9A84",
        "rule": "#D8E0C7",
        "accent": "#5F7F4A",
        "accent_soft": "#D6E1C6",
        "highlight": "#E8E27A",
        "highlight_alpha": "170",
        "strike": "#5B6754",
        "danger": "#A64B3F",
        "good": "#4C7241",
        "popover": "#F7F9EE",
        "shadow": "rgba(35, 46, 32, 32)",
        "veil": "rgba(35, 46, 32, 120)",
    },
    config.THEME_DARK: {
        "desk": "#12100E",
        "desk_deep": "#0C0B0A",
        "paper": "#211E1A",
        "paper_alt": "#27231F",
        "spine": "#1A1714",
        "spine_hole": "#302A24",
        "ink": "#EDE5D7",
        "ink_soft": "#B6A996",
        "ink_faint": "#7C7264",
        "rule": "#3B342B",
        "accent": "#E0915B",
        "accent_soft": "#3A2C22",
        "highlight": "#FFD65C",
        "highlight_alpha": "26",
        "strike": "#D8CCB8",
        "danger": "#E07A6C",
        "good": "#8FBF83",
        "popover": "#26221D",
        "shadow": "rgba(0, 0, 0, 120)",
        "veil": "rgba(8, 7, 6, 170)",
    },
}

_current = config.THEME_PAPER
_scale = 1.0


def set_theme(name: str) -> None:
    global _current
    _current = name if name in THEMES else config.THEME_PAPER


def current_theme() -> str:
    return _current


def set_scale(value: float) -> None:
    global _scale
    try:
        _scale = max(0.85, min(1.4, float(value)))
    except (TypeError, ValueError):
        _scale = 1.0


def scale(px: float) -> int:
    return max(1, int(round(px * _scale)))


def fs(px: float) -> int:
    """字号：在 scale 基础上再放大 FONT_BOOST（只用于 font-size / setPixelSize）。"""
    return max(1, int(round(px * _scale * FONT_BOOST)))


def font_css(px: float, family: str = None, weight: int = None, italic: bool = False) -> str:
    """控件内联样式里的字体声明。

    QSS 的 `QLabel { font-size: ... }` 会盖掉 setFont()/setPixelSize()，
    所以凡是要和全局字号不同的标签，必须把 font-size 写进它自己的 stylesheet。
    """
    parts = ["font-size: %dpx;" % fs(px)]
    if family:
        parts.append("font-family: '%s';" % family)
    if weight:
        parts.append("font-weight: %d;" % weight)
    if italic:
        parts.append("font-style: italic;")
    return " ".join(parts)


def tokens() -> Dict[str, str]:
    return THEMES[_current]


def css(key: str) -> str:
    return THEMES[_current].get(key, "#000000")


def color(key: str) -> QColor:
    return QColor(THEMES[_current].get(key, "#000000"))


def highlight_color() -> QColor:
    col = QColor(css("highlight"))
    col.setAlpha(int(css("highlight_alpha")))
    return col


def strike_color() -> QColor:
    col = QColor(css("strike"))
    col.setAlpha(200)
    return col


def veil_color() -> QColor:
    """浮层遮罩：浅色主题用暖黑半透明，深色主题更重。"""
    col = QColor(24, 20, 16)
    col.setAlpha(190 if _current == config.THEME_DARK else 132)
    return col


def qss() -> str:
    t = THEMES[_current]
    base = fs(13)
    small = fs(12)
    return """
    QWidget#root { background: %(desk)s; }
    QStackedWidget { background: transparent; }
    QStackedWidget > QWidget { background: transparent; }
    QLabel { color: %(ink)s; font-family: "%(sans)s"; font-size: %(base)dpx; background: transparent; }
    QLabel#brand { color: %(ink_soft)s; font-size: %(small)dpx; letter-spacing: 2px; }
    QLabel#h1 { color: %(ink)s; font-size: %(h1)dpx; font-weight: 600; }
    QLabel#muted { color: %(ink_soft)s; }
    QLabel#faint { color: %(ink_faint)s; font-size: %(small)dpx; }
    QLabel#statValue { color: %(ink)s; font-size: %(stat)dpx; font-family: "%(serif)s"; }
    QLabel#statLabel { color: %(ink_faint)s; font-size: %(small)dpx; }
    QFrame#topbar { background: %(desk)s; border: none; }
    QFrame#divider { background: %(rule)s; max-height: 1px; border: none; }

    QPushButton {
        color: %(ink)s; background: transparent; border: 1px solid transparent;
        border-radius: 9px; padding: 7px 13px; font-size: %(base)dpx;
    }
    QPushButton:hover { background: rgba(127, 110, 88, 22); }
    QPushButton:pressed { background: rgba(127, 110, 88, 36); }
    QPushButton:disabled { color: %(ink_faint)s; }
    QPushButton#primary { background: %(accent)s; color: #FFF8EF; font-weight: 600; padding: 8px 16px; }
    QPushButton#primary:hover { background: %(accent)s; }
    QPushButton#ghost { border: 1px solid %(rule)s; padding: 6px 12px; }
    QPushButton#ghost:hover { background: %(paper_alt)s; }
    QPushButton#danger {
        color: %(danger)s; background: transparent; border: 1px solid %(danger)s;
        border-radius: 9px; padding: 6px 14px; font-weight: 600;
    }
    QPushButton#danger:hover { background: rgba(178, 74, 60, 26); }
    QPushButton#danger:disabled { color: %(ink_faint)s; border-color: %(rule)s; }
    QPushButton#danger { color: %(danger)s; }
    /* 文字型按钮也必须有按钮实体：淡底 + 1px 描边，悬停加深，按下压暗 */
    QPushButton#link {
        color: %(accent)s; background: %(paper_alt)s; border: 1px solid %(rule)s;
        border-radius: 9px; padding: 5px 11px;
    }
    QPushButton#link:hover { background: %(popover)s; border-color: %(accent)s; }
    QPushButton#link:pressed { background: %(accent_soft)s; }
    QPushButton#soft {
        color: %(accent)s; background: %(accent_soft)s; border: 1px solid %(accent_soft)s;
        border-radius: 9px; padding: 6px 13px; font-weight: 600;
    }
    QPushButton#soft:hover { border-color: %(accent)s; }
    QPushButton#soft:pressed { background: %(paper_alt)s; }
    QPushButton#pageNav {
        background: %(paper_alt)s; color: %(ink_soft)s; border-radius: 14px;
        min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
        font-size: %(navFont)dpx; padding: 0px;
    }
    QPushButton#pageNav:hover { background: %(accent_soft)s; color: %(ink)s; }
    QPushButton#pageNav:disabled { color: %(rule)s; background: transparent; }

    QFrame#segmented { background: rgba(127, 110, 88, 26); border-radius: 10px; }
    QFrame#segmented QPushButton {
        border: none; border-radius: 8px; padding: 5px 11px; font-size: %(small)dpx;
        color: %(ink_soft)s; background: transparent;
    }
    QFrame#segmented QPushButton:hover { color: %(ink)s; background: transparent; }
    QFrame#segmented QPushButton:pressed { background: transparent; }
    QFrame#segmented QPushButton:checked { background: transparent; color: %(ink)s; font-weight: 600; }

    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
        background: %(popover)s; color: %(ink)s; border: 1px solid %(rule)s;
        border-radius: 9px; padding: 7px 10px; selection-background-color: %(accent_soft)s;
        font-size: %(base)dpx;
    }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1px solid %(accent)s; }
    QComboBox::drop-down { border: none; width: 18px; }
    QComboBox QAbstractItemView {
        background: %(popover)s; color: %(ink)s; border: 1px solid %(rule)s;
        selection-background-color: %(accent_soft)s; outline: none;
    }
    QCheckBox { color: %(ink)s; font-size: %(base)dpx; spacing: 8px; }
    QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid %(rule)s; background: %(popover)s; }
    QCheckBox::indicator:checked { background: %(accent)s; border: 1px solid %(accent)s; }
    QRadioButton { color: %(ink)s; font-size: %(base)dpx; spacing: 8px; padding: 2px 0px; }
    QRadioButton::indicator {
        width: 15px; height: 15px; border-radius: 8px;
        border: 1px solid %(rule)s; background: %(popover)s;
    }
    QRadioButton::indicator:hover { border: 1px solid %(accent)s; }
    QRadioButton::indicator:checked { border: 5px solid %(accent)s; background: %(popover)s; }
    QRadioButton:disabled { color: %(ink_faint)s; }
    QGroupBox { color: %(ink)s; font-size: %(base)dpx; border: 1px solid %(rule)s; border-radius: 10px; margin-top: 10px; padding-top: 6px; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: %(ink_soft)s; }
    QListWidget, QListView {
        background: %(paper)s; color: %(ink)s; border: 1px solid %(rule)s; border-radius: 10px;
        font-size: %(base)dpx; outline: none;
    }
    QListWidget::item { padding: 5px 7px; border-radius: 6px; }
    QListWidget::item:selected { background: %(accent_soft)s; color: %(ink)s; }
    QScrollArea > QWidget > QWidget { background: transparent; }

    QFrame#popover { background: %(popover)s; border: 1px solid %(rule)s; border-radius: 16px; }
    QFrame#bookCard { background: %(popover)s; border: 1px solid %(rule)s; border-radius: 14px; }
    QFrame#statCard { background: %(popover)s; border: 1px solid %(rule)s; border-radius: 14px; }
    QFrame#sheet { background: %(paper)s; border: 1px solid %(rule)s; border-radius: 18px; }
    QFrame#chip { background: %(paper_alt)s; border-radius: 8px; }
    QLabel#chipText { color: %(ink_soft)s; font-size: %(small)dpx; }
    QLabel#quote { color: %(ink_soft)s; font-size: %(base)dpx; }
    QTextBrowser { background: transparent; border: none; color: %(ink)s; font-size: %(base)dpx; }

    QMenu { background: %(popover)s; color: %(ink)s; border: 1px solid %(rule)s; border-radius: 10px; padding: 6px; }
    QMenu::item { padding: 7px 22px 7px 14px; border-radius: 7px; font-size: %(base)dpx; }
    QMenu::item:selected { background: %(accent_soft)s; }
    QMenu::separator { height: 1px; background: %(rule)s; margin: 5px 8px; }

    QToolTip { background: %(ink)s; color: %(paper)s; border: none; border-radius: 6px; padding: 5px 8px; font-size: %(small)dpx; }
    QScrollArea { background: transparent; border: none; }
    QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
    QScrollBar::handle:vertical { background: rgba(127, 110, 88, 70); border-radius: 4px; min-height: 30px; }
    QScrollBar::handle:vertical:hover { background: rgba(127, 110, 88, 110); }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
    QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
    QScrollBar::handle:horizontal { background: rgba(127, 110, 88, 70); border-radius: 4px; min-width: 30px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

    QDialog { background: %(paper)s; }
    QDialog QLabel { color: %(ink)s; }
    QSlider::groove:horizontal { height: 4px; background: %(rule)s; border-radius: 2px; }
    QSlider::handle:horizontal { width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; background: %(accent)s; }
    QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 2px; }
    QProgressBar { background: %(rule)s; border: none; border-radius: 3px; max-height: 6px; text-align: center; color: transparent; }
    QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
    QTreeWidget { background: %(paper)s; color: %(ink)s; border: 1px solid %(rule)s; border-radius: 10px; }
    QTreeWidget::item { padding: 5px; }
    QTreeWidget::item:selected { background: %(accent_soft)s; color: %(ink)s; }
    QHeaderView::section { background: %(paper_alt)s; color: %(ink_soft)s; border: none; padding: 6px; }
    """ % {
        "desk": t["desk"],
        "paper": t["paper"],
        "paper_alt": t["paper_alt"],
        "ink": t["ink"],
        "ink_soft": t["ink_soft"],
        "ink_faint": t["ink_faint"],
        "rule": t["rule"],
        "accent": t["accent"],
        "accent_soft": t["accent_soft"],
        "popover": t["popover"],
        "danger": t["danger"],
        "sans": SANS,
        "serif": SERIF,
        "base": base,
        "small": small,
        "h1": fs(21),
        "stat": fs(27),
        "navFont": fs(15),
    }
