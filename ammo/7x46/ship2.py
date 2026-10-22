# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen4 import *

OUT = os.path.dirname(os.path.abspath(__file__))
AMB = "#F5BF15"; BLK = "#000000"

variants = [
    ("7x46.png",          "nickel",    "#20242C"),   # default: nickel case + black tip
    ("7x46_lacquer.png",  "lacquer",   "#48D048"),   # military green lacquer + green tip
    ("7x46_bluesteel.png","bluesteel", "#E03A2A"),   # blue steel + red tip
    ("7x46_brass.png",    "brass",     None),        # original brass, no marking
]
for fn, mat, tip in variants:
    im = build("7X46", SIL_HEAVY, mat, AMB, BLK, B4, 1, tip)
    im.save(os.path.join(OUT, fn))
    print("wrote", fn)
