# -*- coding: utf-8 -*-
"""Derive 7x46_uv_n.png / _s.png from the base atlas.

The stock pack ships _n maps that are pure flat (127,127,255) copies of the
atlas alpha, and _s maps where G = metalness and R = roughness. tacz only
needs the alpha silhouette from _n, so a flat normal map is exactly right.
"""
import os
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'pack', '7x46_uv.png')

# per-uv-rect metalness / roughness, keyed by the rect name
METAL = {
    'case_side': 230, 'rim_side': 230, 'groove_side': 230, 'shoulder_side': 230,
    'neck_side': 230, 'bullet_side': 200, 'ogive': 200, 'tip_cap': 210,
    'primer': 235,
    'cart_front': 0, 'cart_plain': 0, 'cart_side': 0, 'cart_side2': 0,
    'cart_top': 0, 'cart_inner': 0, 'cart_bottom': 0,
}
ROUGH = {
    'case_side': 70, 'rim_side': 60, 'groove_side': 95, 'shoulder_side': 66,
    'neck_side': 62, 'bullet_side': 52, 'ogive': 50, 'tip_cap': 90,
    'primer': 88,
    'cart_front': 215, 'cart_plain': 215, 'cart_side': 215, 'cart_side2': 215,
    'cart_top': 215, 'cart_inner': 225, 'cart_bottom': 225,
}
DEFAULTS = {'metal': 60, 'rough': 200}

import uvlayout as U

src = Image.open(SRC).convert('RGBA')
W, H = src.size
nm = Image.new('RGBA', (W, H), (127, 127, 255, 0))
sm = Image.new('RGBA', (W, H), (DEFAULTS['rough'], DEFAULTS['metal'], 0, 0))
np_, sp_ = nm.load(), sm.load()
sa = src.load()

# paint spec into each rect, then re-apply the atlas alpha on both maps
for name, (u, v, w, h) in U.RECTS.items():
    r = int(round(v * U.K)); c0 = int(round(u * U.K))
    n_r = len(range(int(round(w * U.K))))
    for yy in range(r, r + int(round(h * U.K))):
        for xx in range(c0, c0 + int(round(w * U.K))):
            if 0 <= xx < W and 0 <= yy < H:
                sp_[xx, yy] = (ROUGH.get(name, DEFAULTS['rough']),
                               METAL.get(name, DEFAULTS['metal']), 0, 255)

for y in range(H):
    for x in range(W):
        a = sa[x, y][3]
        if a:
            np_[x, y] = (127, 127, 255, 255)
            r, g = sp_[x, y][0], sp_[x, y][1]
            sp_[x, y] = (r, g, 0, 255)
        else:
            np_[x, y] = (127, 127, 255, 0)
            sp_[x, y] = (0, 0, 0, 0)

nm.save(os.path.join(HERE, 'pack', '7x46_uv_n.png'))
sm.save(os.path.join(HERE, 'pack', '7x46_uv_s.png'))
print('wrote _n / _s', W, H)
