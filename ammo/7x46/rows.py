# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *
from PIL import Image

SRC = r"E:/我的世界/.minecraft/versions/1.20.1-Forge_47.4.10/tacz/tacz_default_gun/assets/tacz/textures/ammo/slot"
a = Image.open(os.path.join(SRC, "556x45.png")).convert("RGBA").load()
b = build("7X46", SIL_HEAVY, "nickel", "#F5BF15", "#000000", B4, 1, "#20242C").load()

def widths(p):
    out = []
    for y in range(32):
        xs = [x for x in range(32) if p[x, y][3] > 0]
        out.append((y, (min(xs), max(xs)) if xs else None))
    return out

print("row | stock 5.56      | 7x46 v2")
for (y, wa), (_, wb) in zip(widths(a), widths(b)):
    fa = "%2d..%2d (w=%d)" % (wa[0], wa[1], wa[1]-wa[0]+1) if wa else "        -   "
    fb = "%2d..%2d (w=%d)" % (wb[0], wb[1], wb[1]-wb[0]+1) if wb else "        -   "
    print("%2d | %-15s | %s" % (y, fa, fb))
