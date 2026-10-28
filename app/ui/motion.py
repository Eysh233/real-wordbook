"""动效基元：所有时长的唯一定义处。

设计原则（见 docs/05-动效规范.md）：

- 只用 `transform` 与 `opacity`（Qt 里对应自绘偏移与 setOpacity），不动布局；
- 时长按 Apple 的「响应感优先」压到 100–240ms，超过 300ms 只在揭晓/翻页这类少见的过渡里出现；
- 所有过渡都可被下一次操作打断：动画目标从**当前值**重新出发，而不是跳回起点；
- `set_reduced(True)`（设置页的“减少动效”）下自动把时长压到 0，只保留最终状态。
"""
from PyQt5.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QObject,
    QPointF,
    Qt,
    QTimer,
)
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QGraphicsEffect, QWidget

# ---- 时长（ms）------------------------------------------------------------
PRESS_MS = 110        # 按下缩到 0.97
RELEASE_MS = 170      # 回弹到 1.0（略慢于按下，手感更“实”）
HOVER_MS = 150        # 悬停底色/描边走完
POP_MS = 190          # 浮层、弹窗入场
POP_OUT_MS = 120      # 出场比入场快，取消操作不该等
PAGE_MS = 240
FRAME_MS = 6          # 自己驱帧：6ms 一拍 ≈ 165fps，Qt 默认 16ms 在 144Hz 屏上会显得卡
TURN_OUT_MS = 130         # 翻页位移 + 淡入
SHEET_MS = 240        # 抽背卡片入场
SWIPE_MS = 170        # 判定后卡片换下一张
TOAST_MS = 200        # 提示条上浮
STAGGER_MS = 40       # 列表入场错峰（最多 6 个）

# ---- 曲线 -----------------------------------------------------------------
EASE_OUT = QEasingCurve.OutCubic
EASE_IN = QEasingCurve.InCubic
EASE_STANDARD = QEasingCurve.InOutCubic
EASE_SETTLE = QEasingCurve(QEasingCurve.OutBack)   # 只用于入场；overshoot 越小越克制
EASE_SETTLE.setOvershoot(1.06)

_reduced = False


def set_reduced(value: bool) -> None:
    """减少动效：把时长压到 0，但保留最终状态（不是关掉逻辑）。"""
    global _reduced
    _reduced = bool(value)


def reduced() -> bool:
    return _reduced


def ms(value: int) -> int:
    return 0 if _reduced else value


class SurfaceEffect(QGraphicsEffect):
    """同时做缩放与透明度：入场能从触发点“长出来”，而不是凭空出现。

    Qt 的 widget 没有 transform，QGraphicsEffect 是唯一不改布局还能做缩放的钩子。
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._widget = parent
        self._scale = 1.0
        self._opacity = 1.0
        self._origin = QPointF(0.5, 0.5)   # 0..1 的相对锚点
        self._lift = 0.0                   # 入场时的轻微垂直位移（px，正数向下）

    # -- 属性 ---------------------------------------------------------------
    @property
    def scale(self) -> float:
        return self._scale

    def set_scale(self, value: float) -> None:
        self._scale = float(value)
        self.update()

    @property
    def opacity(self) -> float:
        return self._opacity

    def set_opacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, float(value)))
        self.update()

    @property
    def lift(self) -> float:
        return self._lift

    def set_origin(self, x_ratio: float, y_ratio: float) -> None:
        self._origin = QPointF(x_ratio, y_ratio)
        self.update()

    def set_lift(self, value: float) -> None:
        self._lift = float(value)
        self.update()

    # -- 绘制 ---------------------------------------------------------------
    def draw(self, painter: QPainter) -> None:  # noqa: D102
        pixmap, offset = self.sourcePixmap(Qt.LogicalCoordinates, QGraphicsEffect.NoPad)
        if pixmap.isNull():
            return
        painter.save()
        painter.setOpacity(self._opacity)
        width = self._widget.width() if self._widget is not None else pixmap.width()
        height = self._widget.height() if self._widget is not None else pixmap.height()
        cx = offset.x() + width * self._origin.x()
        cy = offset.y() + height * self._origin.y()
        painter.translate(cx, cy)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy + self._lift)
        painter.drawPixmap(offset, pixmap)
        painter.restore()


_effects = {}
_animations = {}


def surface(widget: QWidget) -> SurfaceEffect:
    """取得（或挂上）widget 的动效表面。"""
    effect = _effects.get(widget)
    if effect is None:
        effect = SurfaceEffect(widget)
        _effects[widget] = effect
        widget.setGraphicsEffect(effect)
        widget.destroyed.connect(lambda *_: _effects.pop(widget, None))
    return effect


class Ticker(QObject):
    """用 6ms 精确定时器驱动 0→1 的进度（Qt 自带的统一动画定时器固定 16ms）。

    进度按真实经过时间换算，定时器偶尔迟到也不会改变节奏；`stop()` 后不再回调，
    因此可以直接被打断、从当前值续接。
    """

    def __init__(self, owner, duration: int, curve, on_value, on_done=None) -> None:
        super().__init__(owner)
        self._duration = max(1, int(duration))
        # 常量（如 QEasingCurve.OutCubic）是枚举而不是实例，必须先包一层
        self._curve = curve if isinstance(curve, QEasingCurve) else QEasingCurve(curve)
        self._on_value = on_value
        self._on_done = on_done
        self._elapsed = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._elapsed.start()
        self._tick()
        if self._duration > 0:
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._on_done = None
        self.deleteLater()

    def _tick(self) -> None:
        progress = min(1.0, self._elapsed.elapsed() / float(self._duration))
        self._on_value(self._curve.valueForProgress(progress))
        if progress >= 1.0:
            self._timer.stop()
            done = self._on_done
            self._on_done = None
            self.deleteLater()
            if done is not None:
                done()


def animate(owner, duration: int, curve, on_value, on_done=None) -> "Ticker":
    """统一的动画入口：返回的 Ticker 可由调用方 stop() 打断。"""
    ticker = Ticker(owner, duration, curve, on_value, on_done)
    ticker.start()
    return ticker


def _run(widget: QWidget, key: str, ms_value: int, curve, start: float, end: float, apply) -> None:
    previous = _animations.pop((widget, key), None)
    if previous is not None:
        previous.stop()
    if ms_value <= 0 or abs(start - end) < 1e-3:
        apply(end)
        return

    def on_value(progress: float) -> None:
        apply(start + (end - start) * progress)

    def on_done() -> None:
        _animations.pop((widget, key), None)

    _animations[(widget, key)] = animate(widget, ms_value, curve, on_value, on_done)


def scale_to(widget: QWidget, value: float, duration: int = PRESS_MS, curve=None) -> None:
    effect = surface(widget)
    _run(widget, "scale", ms(duration), curve or EASE_OUT, effect.scale, value, effect.set_scale)


def opacity_to(widget: QWidget, value: float, duration: int = POP_MS, curve=None) -> None:
    effect = surface(widget)
    _run(widget, "opacity", ms(duration), curve or EASE_OUT, effect.opacity, value, effect.set_opacity)


def pop_in(widget: QWidget, origin=(0.5, 0.5), start_scale: float = 0.96,
           lift: float = 6.0, duration: int = POP_MS) -> None:
    """浮层/卡片入场：从 origin 处 0.96 放大到 1，同时淡入并上移 6px。"""
    effect = surface(widget)
    effect.set_origin(*origin)
    if reduced():
        effect.set_opacity(1.0)
        effect.set_scale(1.0)
        effect.set_lift(0.0)
        return
    effect.set_opacity(0.0)
    effect.set_scale(start_scale)
    effect.set_lift(lift)
    opacity_to(widget, 1.0, duration, EASE_OUT)
    scale_to(widget, 1.0, duration, EASE_SETTLE)
    _run(widget, "lift", ms(duration), EASE_OUT, lift, 0.0, effect.set_lift)


def pop_out(widget: QWidget, on_done=None, duration: int = POP_OUT_MS) -> None:
    effect = surface(widget)
    if reduced():
        if on_done:
            on_done()
        return
    opacity_to(widget, 0.0, duration, EASE_IN)
    scale_to(widget, 0.98, duration, EASE_IN)
    if on_done is not None:
        # 与淡出同长再来一拍计时器，进度结束时收尾，避免依赖动画对象的信号
        animate(widget, ms(duration), EASE_IN, lambda _p: None, on_done)


def press_in(widget: QWidget) -> None:
    scale_to(widget, 0.97, PRESS_MS, EASE_OUT)


def press_out(widget: QWidget) -> None:
    scale_to(widget, 1.0, RELEASE_MS, EASE_OUT)


class PressFilter(QObject):
    """全局按下反馈：任何按钮一按就缩到 0.97，松开弹回。

    键盘触发（Enter/Space）不走这里——那类操作一天几十次，按 Apple 的原则
    「响应优先」，鼠标按下才给这一点点形变，且只有 110ms。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._down = set()

    def eventFilter(self, obj, event):  # noqa: N802
        if not isinstance(obj, QWidget):
            return False
        kind = event.type()
        if kind == event.MouseButtonPress:
            if getattr(obj, "_motion_press", True) and hasattr(obj, "click"):
                self._down.add(obj)
                press_in(obj)
        elif kind == event.MouseButtonRelease:
            for widget in list(self._down):
                self._down.discard(widget)
                try:
                    press_out(widget)
                except RuntimeError:  # 控件已销毁
                    pass
        elif kind == event.Leave and obj in self._down:
            pass
        return False


_filter = None


def install_press_feedback(app) -> None:
    """在 QApplication 上挂一次按下反馈，覆盖所有窗口（含对话框）。"""
    global _filter
    if _filter is None:
        _filter = PressFilter(app)
        app.installEventFilter(_filter)


__all__ = [
    "PRESS_MS", "RELEASE_MS", "HOVER_MS", "POP_MS", "POP_OUT_MS", "PAGE_MS",
    "SHEET_MS", "SWIPE_MS", "TOAST_MS", "STAGGER_MS",
    "EASE_OUT", "EASE_IN", "EASE_STANDARD", "EASE_SETTLE",
    "set_reduced", "reduced", "ms",
    "surface", "scale_to", "opacity_to", "pop_in", "pop_out",
    "press_in", "press_out", "PressFilter",
]
