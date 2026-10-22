# -*- coding: utf-8 -*-
"""Confirm the shipped PNGs match what gen4.build produces, and print the v2 silhouette."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *
from PIL import Image

OUT = os.path.dirname(os.path.abspath(__file__))
spec = [("7x46.png","nickel","#20242C"),("7x46_lacquer.png","lacquer","#48D048"),
        ("7x46_bluesteel.png","bluesteel","#E03A2A"),("7x46_brass.png","brass",None)]
for fn, mat, tip in spec:
    a = Image.open(os.path.join(OUT, fn)).convert("RGBA")
    b = build("7X46", SIL_HEAVY, mat, "#F5BF15", "#000000", B4, 1, tip)
    pa, pb = a.load(), b.load()
    bad = sum(1 for y in range(32) for x in range(32) if pa[x,y] != pb[x,y])
    print("%-24s %s  mismatches=%d" % (fn, a.size, bad))

# print v2 silhouette
b = build("7X46", SIL_HEAVY, "nickel", "#F5BF15", "#000000", B4, 1, "#20242C")
p = b.load()
print("\n--- v2 silhouette (rows with content) ---")
for y in range(32):
    row = "".join("#" if p[x,y][3] > 0 else "." for x in range(32))
    if "#" in row:
        print("%2d %s" % (y, row))
