"""手绘质感绘制工具：荧光笔色块、划线、纸张微纹理。

所有随机都带种子，保证同一单词在每次重绘时形状稳定（不闪烁）。
"""
import random

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen


def _rng(seed: int) -> random.Random:
    return random.Random(seed & 0x7FFFFFFF)


def highlight_path(rect: QRectF, seed: int) -> QPainterPath:
    """返回一条略带波动的粗荧光笔路径（覆盖 rect）。"""
    rng = _rng(seed)
    top = rect.top() + rng.uniform(-1.0, 1.2)
    bottom = rect.bottom() + rng.uniform(-1.2, 1.0)
    left = rect.left() - rng.uniform(3.0, 6.0)
    right = rect.right() + rng.uniform(2.0, 5.0)
    path = QPainterPath()
    path.moveTo(left, top + rect.height() * 0.18)
    step = (right - left) / 3.0
    path.cubicTo(
        QPointF(left + step, top - rng.uniform(0.4, 1.6)),
        QPointF(left + step * 2, top + rng.uniform(0.2, 1.4)),
        QPointF(right, top + rng.uniform(0.0, 1.8)),
    )
    path.lineTo(right, bottom - rect.height() * 0.14)
    path.cubicTo(
        QPointF(right - step, bottom + rng.uniform(0.2, 1.6)),
        QPointF(left + step, bottom - rng.uniform(0.2, 1.4)),
        QPointF(left, bottom - rng.uniform(0.2, 1.2)),
    )
    path.closeSubpath()
    return path


def draw_highlight(painter: QPainter, rect: QRectF, color: QColor, seed: int) -> None:
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawPath(highlight_path(rect.adjusted(0, -2, 0, 2), seed))
    painter.restore()


def draw_strike(painter: QPainter, left: float, right: float, y: float, color: QColor, seed: int) -> None:
    """两条几乎重合的细线，模拟笔尖压过文字。"""
    rng = _rng(seed + 17)
    painter.save()
    painter.setBrush(Qt.NoBrush)
    for index, alpha in enumerate((200, 120)):
        layer = QColor(color)
        layer.setAlpha(alpha)
        pen = QPen(layer, 1.05 if index == 0 else 0.8)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        offset = rng.uniform(-0.8, 0.8)
        painter.drawLine(
            QPointF(left - 2, y + offset),
            QPointF(right + 2, y + offset + rng.uniform(-0.9, 0.9)),
        )
    painter.restore()


def paper_grain(painter: QPainter, rect: QRectF, color: QColor, seed: int = 7) -> None:
    """极淡的纸纹横线，避免大面积纯色显得塑料。"""
    rng = _rng(seed)
    painter.save()
    painter.setPen(QPen(color, 1))
    y = rect.top() + 16
    while y < rect.bottom() - 10:
        if rng.random() < 0.4:
            painter.setOpacity(rng.uniform(0.04, 0.10))
            painter.drawLine(QPointF(rect.left() + 14, y), QPointF(rect.right() - 14, y))
        y += 8
    painter.restore()


def rounded_rect_shadow(painter: QPainter, rect: QRectF, color: QColor, spread: int = 3) -> None:
    """用几层半透明圆角矩形伪造柔和投影（比 QGraphicsDropShadow 便宜）。"""
    painter.save()
    painter.setPen(Qt.NoPen)
    for index in range(spread, 0, -1):
        layer = QColor(color)
        layer.setAlpha(max(4, int(color.alpha() / (index + 1.4))))
        painter.setBrush(layer)
        offset = index * 1.6
        painter.drawRoundedRect(rect.adjusted(-offset, offset * 0.4, offset, offset), 16, 16)
    painter.restore()
