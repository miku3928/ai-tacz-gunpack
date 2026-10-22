# -*- coding: utf-8 -*-
"""Does the differentiation survive at real inventory size (16 px)?"""
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
F = font(13)

items = [
    ("5.56x45", Image.open(os.path.join(SRC, "556x45.png")).convert("RGBA")),
    ("7.62x39", Image.open(os.path.join(SRC, "762x39.png")).convert("RGBA")),
    ("5.45x39", Image.open(os.path.join(SRC, "545x39.png")).convert("RGBA")),
    ("B 绿漆",  build("7X46", SIL_HEAVY, "lacquer", AMB, BLK, B4, 1, "#48D048")),
    ("D 紫铜",  build("7X46", SIL_HEAVY, "copper", AMB, BLK, B4, 1, "#3CC23C")),
    ("E 蓝钢",  build("7X46", SIL_HEAVY, "bluesteel", AMB, BLK, B4, 1, "#E03A2A")),
    ("F 镀镍",  build("7X46", SIL_HEAVY, "nickel", AMB, BLK, B4, 1, "#20242C")),
]

# render at 16 px (true in-game item size) then blow up 4x to inspect what survives
cell = 16 * 4
W = len(items) * (cell + 16) + 16
sheet = Image.new("RGBA", (W, cell + 60), (198, 198, 198, 255))
d = ImageDraw.Draw(sheet)
for i, (name, im) in enumerate(items):
    small = im.resize((16, 16), Image.LANCZOS)
    ox = 16 + i * (cell + 16)
    sheet.alpha_composite(small.resize((cell, cell), Image.NEAREST), (ox, 16))
    d.text((ox, cell + 26), name, font=F, fill=(30, 30, 30, 255))
sheet.save(os.path.join(OUT, "tiny16.png"))
print("ok")
