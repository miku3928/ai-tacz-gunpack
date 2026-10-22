# -*- coding: utf-8 -*-
import os, sys
from PIL import Image, ImageDraw
import uvlayout as U
HERE = os.path.dirname(os.path.abspath(__file__))
im = Image.open(os.path.join(HERE, "pack", "7x46_uv.png")).convert("RGBA")
Z = 6
big = Image.new("RGBA", (im.width * Z, im.height * Z), (26, 26, 30, 255))
# checker under
ck = Image.new("RGBA", big.size, (26, 26, 30, 255))
d = ImageDraw.Draw(ck)
for y in range(0, big.height, 8 * Z):
    for x in range(0, big.width, 8 * Z):
        if ((x // (8 * Z)) + (y // (8 * Z))) % 2 == 0:
            d.rectangle([x, y, x + 8 * Z - 1, y + 8 * Z - 1], fill=(40, 40, 46, 255))
ck.alpha_composite(im.resize((im.width * Z, im.height * Z), Image.NEAREST))
d = ImageDraw.Draw(ck)
for name, (u, v, w, h) in U.RECTS.items():
    x, y = u * U.K * Z, v * U.K * Z
    d.rectangle([x, y, x + w * U.K * Z - 1, y + h * U.K * Z - 1], outline=(255, 60, 60, 255))
ck.convert("RGB").save(os.path.join(HERE, "analysis", "atlas_zoom.png"))
print("ok")
