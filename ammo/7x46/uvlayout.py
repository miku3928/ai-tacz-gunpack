# -*- coding: utf-8 -*-
"""Shared UV rect table for the 7x46 pack.

uv units live in a 64x64 grid; the png is 2x that (128px), K=2.
Rects are sized so 1 model unit == 2 uv units on the crate faces, which keeps
the cardboard pixel density even on every side.
"""

UVW = 64
K = 2
PNG = UVW * K

RECTS = {
    # ---- crate: 7 x 7 x 3.5 model units (2 uv per model unit on every face) ----
    "cart_front":  (0.0,  0.0, 14.0, 14.0),
    "cart_plain":  (15.0, 0.0, 14.0, 14.0),
    "cart_side":   (30.0, 0.0,  7.0, 14.0),
    "cart_side2":  (38.0, 0.0,  7.0, 14.0),
    "cart_top":    (46.0, 0.0, 14.0,  7.0),
    "cart_inner":  (46.0, 8.0, 14.0,  7.0),
    "cart_bottom": (46.0,16.0, 14.0,  7.0),

    # ---- cartridge case + bullet ----
    "case_side":      (0.0, 20.0, 6.0, 14.0),
    "rim_side":       (7.0, 20.0, 6.0,  2.0),
    "groove_side":    (7.0, 23.0, 6.0,  2.0),
    "shoulder_side":  (7.0, 26.0, 6.0,  5.0),
    "neck_side":      (7.0, 32.0, 6.0,  3.0),
    "bullet_side":    (14.0, 20.0, 6.0, 10.0),
    "ogive":          (14.0, 31.0, 6.0,  5.0),
    "tip_cap":        (21.0, 20.0, 3.0,  3.0),
    "primer":         (21.0, 24.0, 3.0,  3.0),

    # ---- flat shade patches for 1-2 px faces ----
    "s_nick":    (21.0, 28.0, 2.0, 2.0),
    "s_nick_d":  (21.0, 31.0, 2.0, 2.0),
    "s_cu":      (24.0, 28.0, 2.0, 2.0),
    "s_cu_d":    (24.0, 31.0, 2.0, 2.0),
    "s_black":   (27.0, 28.0, 2.0, 2.0),
    "s_kraft":   (27.0, 31.0, 2.0, 2.0),
    "s_kraft_d": (30.0, 28.0, 2.0, 2.0),
}