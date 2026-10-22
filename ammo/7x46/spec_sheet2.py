# -*- coding: utf-8 -*-
"""Annotated design sheet for the v2 (differentiated) 7x46 icon."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))

def font(sz, bold=False):
    ps = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"] if bold else [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]
    for p in ps:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()
F1, F2, F3 = font(20, True), font(13), font(12)

icon = build("7X46", SIL_HEAVY, "nickel", "#F5BF15", "#000000", B4, 1, "#20242C")

W, H = 780, 600
sheet = Image.new("RGBA", (W, H), (22, 22, 26, 255))
d = ImageDraw.Draw(sheet)

S = 12
ox, oy = 40, 74
# grid
for gx in range(0, 32 * S + 1, S * 8):
    d.line([ox + gx, oy, ox + gx, oy + 32 * S], fill=(48, 48, 56, 255))
for gy in range(0, 32 * S + 1, S * 8):
    d.line([ox, oy + gy, ox + 32 * S, oy + gy], fill=(48, 48, 56, 255))
sheet.alpha_composite(icon.resize((32 * S, 32 * S), Image.NEAREST), (ox, oy))

d.text((40, 24), "7x46mm 物品图标 · 32x32 RGBA", font=F1, fill=(245, 245, 245, 255))
d.text((40, 50), "镀镍弹壳 + 黑弹尖 + 琥珀缎带（中间威力步枪弹）", font=F2, fill=(150, 150, 150, 255))

# annotations
ann = [
    (1, "弹尖标记 #20242C", "y=1-5，标示特殊弹种"),
    (7, "铜被甲弹头 #C67A4E", "y=1-11，11 行（原版 9 行）"),
    (12, "弹壳肩部", "y=12-15，收至全宽"),
    (16, "缎带 #F5BF15", "y=16-22，右端斜切"),
    (23, "镀镍弹壳", "y=23-27，5 行壳体"),
    (28, "抽壳沟 y=28 / 底缘 y=29", "底部收口"),
]
lx = ox + 32 * S + 34
for yrow, t1, t2 in ann:
    yy = oy + yrow * S
    d.line([ox + 32 * S + 6, yy, lx - 6, yy], fill=(120, 120, 130, 255))
    d.text((lx, yy - 8), t1, font=F3, fill=(235, 235, 235, 255))
    d.text((lx, yy + 8), t2, font=F3, fill=(125, 125, 135, 255))

# palette strip
py = oy + 32 * S + 20
d.text((40, py), "配色", font=F2, fill=(200, 200, 200, 255))
pal = [("#54002F","弹头描边"),("#C67A4E","被甲中间"),("#DEA46A","被甲亮部"),
       ("#2E2A22","壳描边"),("#A89E88","壳中间"),("#F0E8D6","壳高光"),
       ("#F5BF15","缎带"),("#000000","缎带字"),("#20242C","弹尖")]
px = 40
for hexv, nm in pal:
    d.rectangle([px, py + 22, px + 46, py + 52], fill=hexv + "FF", outline=(80, 80, 90, 255))
    d.text((px, py + 56), nm, font=F3, fill=(170, 170, 170, 255))
    d.text((px, py + 70), hexv, font=F3, fill=(110, 110, 120, 255))
    px += 56

sheet.save(os.path.join(OUT, "7x46_spec.png"))
print("ok")
