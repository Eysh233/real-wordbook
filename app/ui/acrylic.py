"""Windows 亚克力（毛玻璃）背景，走未公开的 SetWindowCompositionAttribute。

只在 Windows 10/11 上有效；调用失败时静默返回 False，调用方退回半透明绘制。
"""
import ctypes
import sys
from ctypes import wintypes

ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
WCA_ACCENT_POLICY = 19


class _AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WindowCompositionAttributeData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _apply(hwnd: int, state: int, tint: int) -> bool:
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        policy = _AccentPolicy(state, 2, tint, 0)
        data = _WindowCompositionAttributeData()
        data.Attribute = WCA_ACCENT_POLICY
        data.SizeOfData = ctypes.sizeof(policy)
        data.Data = ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p)
        return bool(user32.SetWindowCompositionAttribute(int(hwnd), ctypes.byref(data)))
    except Exception:  # noqa: BLE001 - 系统接口失败不该影响界面
        return False


def enable(hwnd: int, tint: int = 0x99FFFFFF) -> bool:
    """打开亚克力模糊。tint 是 AABBGGRR（默认半透明白）。"""
    if _apply(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND, tint):
        return True
    # 老系统（Win10 早期）没有亚克力，退到高斯模糊
    return _apply(hwnd, ACCENT_ENABLE_BLURBEHIND, tint)


def disable(hwnd: int) -> bool:
    return _apply(hwnd, ACCENT_DISABLED, 0)
