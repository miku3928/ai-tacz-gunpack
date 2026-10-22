# -*- coding: utf-8 -*-
"""7x46 icon generator v2: silhouette + material + optional painted bullet tip."""
from PIL import Image, ImageDraw
import os

OUT = os.path.dirname(os.path.abspath(__file__))

GLYPHS = {
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": ["#", "#", "#", "#", "#"],
    "2": ["###", "..#", "###", "#..", "###"], "3": ["###", "..#", "###", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"], "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "###"],
    ".": [".", ".", ".", ".", "#"], "X": ["...", "...", "#.#", ".#.", "#.#"],
}

SIL_STOCK = {
    3:  "...F...", 4:  "..FNF..", 5:  "..FOF..",
    6:  ".FLOMF.", 7:  ".FLOMF.", 8:  ".KLNMK.", 9:  ".KLNMK.",
    10: ".CKCCC.", 11: ".CGBBC.", 12: "CIGBBEC.", 13: "CIGBBEC.",
    14: "BGHBBJC.", 15: "BGHBBJB.",
    16: "BGHEEJB.", 17: "BGHEEJB.", 18: "BGHEEJB.", 19: "BGHEEJB.",
    20: "BGHEEJB.", 21: "BGHEEJB.", 22: "BGHEEJB.",
    23: "BGHEEJB.", 24: "BGHEEJB.", 25: "BIHBBJC.", 26: "BIHBBEC.",
    27: "CIGBBEC.", 28: "CIGBBEC.", 29: ".CBCCC.", 30: "CCBBCCC.",
}

# taller spitzer bullet (starts at y=1), longer neck, shorter body
SIL_HEAVY = {
    1:  "...F...", 2:  "..FNF..", 3:  "..FOF..",
    4:  ".FLOMF.", 5:  ".FLOMF.", 6:  ".FLOMF.", 7:  ".KLNMK.", 8:  ".KLNMK.",
    9:  ".CKCCC.", 10: ".CGBBC.", 11: ".CGBBC.", 12: "CIGBBEC.", 13: "CIGBBEC.",
    14: "BGHBBJC.", 15: "BGHBBJB.",
    16: "BGHEEJB.", 17: "BGHEEJB.", 18: "BGHEEJB.", 19: "BGHEEJB.",
    20: "BGHEEJB.", 21: "BGHEEJB.", 22: "BGHEEJB.",
    23: "BGHEEJB.", 24: "BGHEEJB.", 25: "BGHEEJB.", 26: "BIHBBJC.",
    27: "CIGBBEC.", 28: ".CBCCC.", 29: "CCBBCCC.",
}

BAND_RIGHT = [31, 30, 29, 28, 27, 26, 25]
TEXT_TOP = 17
B4 = [0, 8, 16, 24]
B3 = [5, 13, 21]


def hx(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def shade(h, f):
    r, g, b = hx(h)
    if f >= 0:
        r = int(r + (255 - r) * f); g = int(g + (255 - g) * f); b = int(b + (255 - b) * f)
    else:
        r = int(r * (1 + f)); g = int(g * (1 + f)); b = int(b * (1 + f))
    return (r, g, b)


CU = dict(F="#54002F", N="#C67A4E", O="#DEA46A", L="#94533D", M="#944235", K="#702F3A")

RAMP = {
    "brass":     dict(C="#49041B", B="#8D3723", G="#F8D383", H="#FEEDBC", I="#DE9754", E="#A1542E", J="#C9793F"),
    "nickel":    dict(C="#2E2A22", B="#6E6858", G="#C8C0AC", H="#F0E8D6", I="#A89E88", E="#4A4436", J="#D8D0BC"),
    "bluesteel": dict(C="#10141C", B="#2A3240", G="#7C8CA4", H="#C4D2E4", I="#556275", E="#3A4454", J="#8C9AB0"),
    "lacquer":   dict(C="#0E1408", B="#22300E", G="#66822C", H="#A8C460", I="#48581E", E="#2E3C14", J="#54682A"),
    "copper":    dict(C="#3A1A10", B="#7A3E22", G="#D08A50", H="#F2C090", I="#A86438", E="#5A2C18", J="#C07640"),
    "burnt":     dict(C="#2A1008", B="#5E2410", G="#B4542A", H="#DC8048", I="#8A3C1C", E="#4A1C0C", J="#A84820"),
}

TIP_ROWS = (3, 4, 5)
TIP_ROLES = ("F", "N", "O")


def build(text, sil, mat_key, band_hex, text_hex, bullets=B4, text_x=1,
          tip=None, tip_rows=TIP_ROWS, band_line=None):
    ramp = dict(CU)
    ramp.update(RAMP[mat_key])
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    px = img.load()

    for bx in bullets:
        for y, row in sil.items():
            for i, ch in enumerate(row):
                if ch == ".":
                    continue
                x = bx + i
                if not (0 <= x < 32):
                    continue
                if tip and y in tip_rows and ch in TIP_ROLES:
                    # F = tip outline (dark), N = tip mid, O = tip light
                    f = {"F": -0.45, "N": 0.0, "O": 0.30}[ch]
                    px[x, y] = shade(tip, f) + (255,)
                else:
                    px[x, y] = hx(ramp[ch]) + (255,)

    bc = hx(band_hex) + (255,)
    for j, y in enumerate(range(16, 23)):
        for x in range(0, BAND_RIGHT[j] + 1):
            px[x, y] = bc

    if band_line:
        lc = hx(band_line) + (255,)
        for j, y in enumerate([21, 22]):
            for x in range(0, BAND_RIGHT[j] + 1):
                px[x, y] = lc

    tc = hx(text_hex) + (255,)
    x = text_x
    for ch in text:
        g = GLYPHS[ch]
        for yy, r in enumerate(g):
            for xx, c in enumerate(r):
                if c == "#" and 0 <= x + xx < 32:
                    px[x + xx, TEXT_TOP + yy] = tc
        x += len(g[0]) + 1
    return img


def preview(img, scale, label=None):
    w, h = img.size
    pad = 14 if label else 0
    p = Image.new("RGBA", (w * scale, h * scale + pad), (26, 26, 30, 255))
    d = ImageDraw.Draw(p)
    for a in range(0, w * scale, 8):
        for b in range(0, h * scale, 8):
            if ((a // 8) + (b // 8)) % 2 == 0:
                d.rectangle([a, b, a + 7, b + 7], fill=(40, 40, 46, 255))
    p.alpha_composite(img.resize((w * scale, h * scale), Image.NEAREST), (0, 0))
    if label:
        d.text((3, h * scale + 2), label, fill=(215, 215, 215, 255))
    return p
