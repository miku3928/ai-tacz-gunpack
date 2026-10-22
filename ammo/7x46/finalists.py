# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = r"E:/我的世界/.minecraft/versions/1.20.1-Forge_47.4.10/tacz/tacz_default_gun/assets/tacz/textures/ammo/slot"
AMB = "#F5BF15"; BLK = "#000000"

def font(sz):
    for p in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()
F = font(14); F2 = font(13)

items = [
    ("5.45x39", Image.open(os.path.join(SRC, "545x39.png")).convert("RGBA"), False),
    ("5.56x45", Image.open(os.path.join(SRC, "556x45.png")).convert("RGBA"), False),
    ("5.8x42",  Image.open(os.path.join(SRC, "58x42.png")).convert("RGBA"), False),
    ("7.62x39", Image.open(os.path.join(SRC, "762x39.png")).convert("RGBA"), False),
    ("B 绿漆+绿弹尖", build("7X46", SIL_HEAVY, "lacquer", AMB, BLK, B4, 1, "#48D048"), True),
    ("D 紫铜+绿弹尖", build("7X46", SIL_HEAVY, "copper", AMB, BLK, B4, 1, "#3CC23C"), True),
    ("E 蓝钢+红弹尖", build("7X46", SIL_HEAVY, "bluesteel", AMB, BLK, B4, 1, "#E03A2A"), True),
    ("F 镀镍+黑弹尖", build("7X46", SIL_HEAVY, "nickel", AMB, BLK, B4, 1, "#20242C"), True),
]

S = 5
cw = 32 * S + 20
rows_n, cols_n = 2, 4
grid_h = rows_n * (32 * S + 30)
strip_h = 32 * 2 + 44
W = cols_n * cw + 24
H = grid_h + strip_h + 60

sheet = Image.new("RGBA", (W, H), (24, 24, 28, 255))
d = ImageDraw.Draw(sheet)

for i, (name, im, new) in enumerate(items):
    r, c = divmod(i, cols_n)
    ox = 12 + c * cw
    oy = 16 + r * (32 * S + 30)
    for gx in range(0, 32 * S + 1, S * 8):
        d.line([ox + gx, oy, ox + gx, oy + 32 * S], fill=(52, 52, 60, 255))
    for gy in range(0, 32 * S + 1, S * 8):
        d.line([ox, oy + gy, ox + 32 * S, oy + gy], fill=(52, 52, 60, 255))
    sheet.alpha_composite(im.resize((32 * S, 32 * S), Image.NEAREST), (ox, oy))
    d.text((ox, oy + 32 * S + 8), name, font=F2, fill=(255, 210, 110, 255) if new else (160, 160, 160, 255))

# ---- actual-size strip ----
sy = grid_h + 34
d.text((12, sy - 20), "实际大小", font=F2, fill=(200, 200, 200, 255))
x = 12
for name, im, new in items:
    sheet.alpha_composite(im.resize((32, 32), Image.NEAREST), (x, sy))
    sheet.alpha_composite(im.resize((64, 64), Image.NEAREST), (x + 40, sy))
    x += 116
sheet.save(os.path.join(OUT, "finalists.png"))
print("ok")
