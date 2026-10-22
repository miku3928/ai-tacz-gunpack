# -*- coding: utf-8 -*-
"""v2 icon in the amber-band rifle family, 32px, for hue/shape comparison."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = r"E:/我的世界/.minecraft/versions/1.20.1-Forge_47.4.10/tacz/tacz_default_gun/assets/tacz/textures/ammo/slot"

def font(sz, bold=False):
    ps = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"] if bold else [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]
    for p in ps:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()
F1, F2 = font(16, True), font(12)

items = [("5.45x39", "545x39.png"), ("5.56x45", "556x45.png"), ("5.8x42", "58x42.png"), ("7.62x39", "762x39.png")]
S = 6
pad, top = 18, 52
W = pad + (len(items) + 1) * (32 * S + pad)
H = top + 32 * S + 46
sheet = Image.new("RGBA", (W, H), (22, 22, 26, 255))
d = ImageDraw.Draw(sheet)
d.text((pad, 18), "琥珀缎带族 · 32px 并排（最后一个是 7x46）", font=F1, fill=(240, 240, 240, 255))

x = pad
for nm, fn in items + [("7x46", None)]:
    im = (Image.open(os.path.join(SRC, fn)).convert("RGBA") if fn
          else build("7X46", SIL_HEAVY, "nickel", "#F5BF15", "#000000", B4, 1, "#20242C"))
    sheet.alpha_composite(im.resize((32 * S, 32 * S), Image.NEAREST), (x, top))
    col = (255, 210, 110, 255) if nm == "7x46" else (150, 150, 150, 255)
    d.text((x, top + 32 * S + 10), nm, font=F2, fill=col)
    x += 32 * S + pad
sheet.save(os.path.join(OUT, "family_amber.png"))
print("ok")
