# -*- coding: utf-8 -*-
"""Objective confusion test: how different is each candidate from the 4 amber-family stock icons?"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *
from PIL import Image
import colorsys

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = r"E:/我的世界/.minecraft/versions/1.20.1-Forge_47.4.10/tacz/tacz_default_gun/assets/tacz/textures/ammo/slot"
AMB = "#F5BF15"; BLK = "#000000"


def hist(im):
    """colour histogram over opaque pixels, weighted by area, in Lab-ish space."""
    px = im.load()
    acc = {}
    for y in range(32):
        for x in range(32):
            p = px[x, y]
            if p[3] == 0:
                continue
            # 4-bit per channel bucket
            k = (p[0] >> 4, p[1] >> 4, p[2] >> 4)
            acc[k] = acc.get(k, 0) + 1
    tot = sum(acc.values()) or 1
    return {k: v / tot for k, v in acc.items()}


def dist(a, b):
    keys = set(a) | set(b)
    return 0.5 * sum(abs(a.get(k, 0) - b.get(k, 0)) for k in keys)


def case_color(im):
    """dominant colour of the case body (rows 23..28), ignoring the band."""
    px = im.load()
    acc = {}
    for y in range(23, 29):
        for x in range(32):
            p = px[x, y]
            if p[3] == 0:
                continue
            k = p[:3]
            acc[k] = acc.get(k, 0) + 1
    return max(acc.items(), key=lambda kv: kv[1])[0]


stock = {}
for n in ["545x39", "556x45", "58x42", "762x39", "762x54", "308"]:
    stock[n] = Image.open(os.path.join(SRC, n + ".png")).convert("RGBA")

cands = {
    "A brass+greentip":  build("7X46", SIL_STOCK, "brass", AMB, BLK, B4, 1, "#3CC23C"),
    "B lacquer+green":   build("7X46", SIL_HEAVY, "lacquer", AMB, BLK, B4, 1, "#48D048"),
    "B3 lacquer+green3": build("7X46", SIL_HEAVY, "lacquer", AMB, BLK, B3, 5, "#48D048"),
    "C brass+blacktip":  build("7X46", SIL_HEAVY, "brass", AMB, BLK, B4, 1, "#20242C"),
    "C3 brass+black3":   build("7X46", SIL_HEAVY, "brass", AMB, BLK, B3, 5, "#20242C"),
    "D copper+green":    build("7X46", SIL_HEAVY, "copper", AMB, BLK, B4, 1, "#3CC23C"),
    "E bluesteel+red":   build("7X46", SIL_HEAVY, "bluesteel", AMB, BLK, B4, 1, "#E03A2A"),
    "F nickel+black":    build("7X46", SIL_HEAVY, "nickel", AMB, BLK, B4, 1, "#20242C"),
    "H brass plain":     build("7X46", SIL_HEAVY, "brass", AMB, BLK, B4, 1, None),
}

print("case-body dominant colour")
for n, im in stock.items():
    c = case_color(im)
    print("  stock %-9s #%02X%02X%02X" % (n, *c))
print()
for n, im in cands.items():
    c = case_color(im)
    h = hist(im)
    ds = sorted(((dist(h, hist(s)), sn) for sn, s in stock.items()))
    worst = ds[0]
    print("%-18s case=#%02X%02X%02X  nearest=%s d=%.3f   (%s)" % (
        n, *c, worst[1], worst[0],
        ", ".join("%s:%.2f" % (sn, d) for d, sn in ds)))
