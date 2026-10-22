# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen2 import build, BRASS
from PIL import Image

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = r"E:/我的世界/.minecraft/versions/1.20.1-Forge_47.4.10/tacz/tacz_default_gun/assets/tacz/textures/ammo/slot"

def diff(text, fname, mat=BRASS, band="#F5BF15", tc="#000000", show=50):
    a = Image.open(os.path.join(SRC, fname)).convert("RGBA")
    b = build(text, mat, band, tc)
    pa, pb = a.load(), b.load()
    bad = []
    for y in range(32):
        for x in range(32):
            p, q = pa[x, y], pb[x, y]
            if p[3] == 0 and q[3] == 0:
                continue
            if p != q:
                bad.append((x, y, p, q))
    print("== %s  '%s'  mismatches=%d" % (fname, text, len(bad)))
    for x, y, p, q in bad[:show]:
        print("   (%2d,%2d) stock=#%02X%02X%02X/%d mine=#%02X%02X%02X/%d" % (x, y, *p, *q))
    return len(bad)

diff("5.56X45", "556x45.png")
diff("7.62X39", "762x39.png")
