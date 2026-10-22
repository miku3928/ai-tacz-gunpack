# -*- coding: utf-8 -*-
"""Silhouette diff: stock 5.56 vs new heavy, same colours, mask only."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = r"E:/我的世界/.minecraft/versions/1.20.1-Forge_47.4.10/tacz/tacz_default_gun/assets/tacz/textures/ammo/slot"

def font(sz):
    for p in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()
F = font(14)

a = Image.open(os.path.join(SRC, "556x45.png")).convert("RGBA")
b = build("7X46", SIL_HEAVY, "nickel", "#F5BF15", "#000000", B4, 1, "#20242C")

S = 9
sheet = Image.new("RGBA", (2 * (32 * S + 30) + 30, 32 * S + 60), (24, 24, 28, 255))
d = ImageDraw.Draw(sheet)
for i, (nm, im) in enumerate([("5.56x45  骨架", a), ("7x46  骨架", b)]):
    ox = 15 + i * (32 * S + 30)
    for gx in range(0, 32 * S + 1, S * 8):
        d.line([ox + gx, 15, ox + gx, 15 + 32 * S], fill=(52, 52, 60, 255))
    for gy in range(0, 32 * S + 1, S * 8):
        d.line([ox, 15 + gy, ox + 32 * S, 15 + gy], fill=(52, 52, 60, 255))
    sheet.alpha_composite(im.resize((32 * S, 32 * S), Image.NEAREST), (ox, 15))
    d.text((ox, 15 + 32 * S + 10), nm, font=F, fill=(220, 220, 220, 255))
sheet.save(os.path.join(OUT, "silhouette_diff.png"))

# numeric silhouette delta
pa, pb = a.load(), b.load()
only_a = only_b = 0
for y in range(32):
    for x in range(32):
        oa, ob = pa[x, y][3] > 0, pb[x, y][3] > 0
        if oa and not ob: only_a += 1
        if ob and not oa: only_b += 1
print("opaque px: stock=%d new=%d  only_stock=%d only_new=%d" % (
    sum(1 for y in range(32) for x in range(32) if pa[x, y][3] > 0),
    sum(1 for y in range(32) for x in range(32) if pb[x, y][3] > 0),
    only_a, only_b))
