"""生成程序图标：粗体「Re」压在一条荧光笔色带上的纸色圆角方块。

用法：python tools/make_icon.py
产物：assets/app.ico（内含 16/24/32/48/64/128/256 七个尺寸）、assets/app.png（256px 预览）
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets"

PAPER = (251, 247, 238, 255)
BORDER = (232, 221, 201, 255)
INK = (43, 39, 34, 255)
MARKER = (255, 214, 92, 168)
MARKER_EDGE = (255, 205, 70, 210)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("找不到可用的粗体字体，请检查 C:\\Windows\\Fonts")


def render(size: int) -> Image.Image:
    scale = 8 if size >= 128 else 4  # 先放大再缩小，边缘更干净
    work = size * scale
    img = Image.new("RGBA", (work, work), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(work * 0.22)
    draw.rounded_rectangle((0, 0, work - 1, work - 1), radius=radius, fill=PAPER)
    draw.rounded_rectangle(
        (1, 1, work - 2, work - 2), radius=radius - 1, outline=BORDER, width=max(1, work // 128)
    )

    # 荧光笔色带：小尺寸下省略，避免糊成一团
    if size >= 32:
        band_h = int(work * 0.30)
        band_y = int(work * 0.46)
        pad = int(work * 0.13)
        draw.rounded_rectangle(
            (pad, band_y, work - pad, band_y + band_h),
            radius=int(band_h * 0.34),
            fill=MARKER,
            outline=MARKER_EDGE,
            width=max(1, work // 160),
        )

    font_size = int(work * 0.60)
    font = _font(font_size)
    text = "Re"
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    x = (work - tw) / 2 - box[0]
    y = work * 0.50 - th / 2 - box[1]
    draw.text((x, y), text, font=font, fill=INK)

    return img.resize((size, size), Image.LANCZOS)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [render(s) for s in sizes]
    ico_path = OUT_DIR / "app.ico"
    images[-1].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
    images[-1].save(OUT_DIR / "app.png", format="PNG")
    print("saved %s (%d sizes)" % (ico_path, len(sizes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
