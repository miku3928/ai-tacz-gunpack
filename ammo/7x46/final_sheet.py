# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = r"E:/我的世界/.minecraft/versions/1.20.1-Forge_47.4.10/tacz/tacz_default_gun/assets/tacz/textures/ammo/slot"

def font(sz, bold=False):
    paths = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"] if bold else [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()

F1, F2, F3 = font(20, True), font(13), font(12)

variants = [
    ("7x46.png",           "镀镍弹壳 + 黑弹尖", "nickel",    "#20242C"),
    ("7x46_lacquer.png",   "绿漆弹壳 + 绿弹尖", "lacquer",   "#48D048"),
    ("7x46_bluesteel.png", "蓝钢弹壳 + 红弹尖", "bluesteel", "#E03A2A"),
    ("7x46_brass.png",     "黄铜（原版，无标记）","brass",     None),
]

W, H = 1080, 486
sheet = Image.new("RGBA", (W, H), (22, 22, 26, 255))
d = ImageDraw.Draw(sheet)
d.text((28, 20), "7x46mm — 与 5.56 的区分方案", font=F1, fill=(245, 245, 245, 255))
d.text((28, 50), "骨架加高 2px（弹头更修长）+ 弹尖涂色标记 + 弹壳换材质", font=F2, fill=(150, 150, 150, 255))

# ---- before / after ----
S = 7
oy = 86
pairs = [("5.56x45 原版", Image.open(os.path.join(SRC, "556x45.png")).convert("RGBA"), (150,150,150)),
         ("7x46 旧版（像 5.56）", build("7X46", SIL_STOCK, "brass", "#F5BF15", "#000000"), (200,120,120)),
         ("7x46 新版", build("7X46", SIL_HEAVY, "nickel", "#F5BF15", "#000000", B4, 1, "#20242C"), (255,210,110))]
for i, (nm, im, col) in enumerate(pairs):
    ox = 28 + i * (32 * S + 30)
    for gx in range(0, 32 * S + 1, S * 8):
        d.line([ox + gx, oy, ox + gx, oy + 32 * S], fill=(50, 50, 58, 255))
    for gy in range(0, 32 * S + 1, S * 8):
        d.line([ox, oy + gy, ox + 32 * S, oy + gy], fill=(50, 50, 58, 255))
    sheet.alpha_composite(im.resize((32 * S, 32 * S), Image.NEAREST), (ox, oy))
    d.text((ox, oy + 32 * S + 10), nm, font=F3, fill=col + (255,))

# ---- variants column ----
vx = 28 + 3 * (32 * S + 30) + 20
d.text((vx, oy - 4), "可选的弹壳材质", font=F2, fill=(210, 210, 210, 255))
for i, (fn, label, mat, tip) in enumerate(variants):
    im = build("7X46", SIL_HEAVY, mat, "#F5BF15", "#000000", B4, 1, tip)
    yy = oy + 22 + i * 76
    sheet.alpha_composite(im.resize((64, 64), Image.NEAREST), (vx, yy))
    d.text((vx + 74, yy + 10), label, font=F3, fill=(235, 235, 235, 255))
    d.text((vx + 74, yy + 30), fn, font=F3, fill=(120, 120, 120, 255))

# ---- bottom: real-size lineup ----
by = oy + 32 * S + 44
d.text((28, by), "实际物品栏大小（16 px）", font=F2, fill=(200, 200, 200, 255))
line = [("5.45", Image.open(os.path.join(SRC, "545x39.png")).convert("RGBA")),
        ("5.56", Image.open(os.path.join(SRC, "556x45.png")).convert("RGBA")),
        ("5.8",  Image.open(os.path.join(SRC, "58x42.png")).convert("RGBA")),
        ("7.62x39", Image.open(os.path.join(SRC, "762x39.png")).convert("RGBA")),
        ("7x46", build("7X46", SIL_HEAVY, "nickel", "#F5BF15", "#000000", B4, 1, "#20242C"))]
lx = 28
for nm, im in line:
    small = im.resize((16, 16), Image.LANCZOS)
    sheet.alpha_composite(small.resize((64, 64), Image.NEAREST), (lx, by + 22))
    d.text((lx, by + 92), nm, font=F3, fill=(255, 210, 110, 255) if nm == "7x46" else (160, 160, 160, 255))
    lx += 78

sheet.save(os.path.join(OUT, "7x46_diff_spec.png"))
print("ok")
