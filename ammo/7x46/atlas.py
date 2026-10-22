# -*- coding: utf-8 -*-
"""7x46 UV atlas generator -> pack/7x46_uv.png (128x128 RGBA).
Layout comes from uvlayout.RECTS so the geo model and the texture never drift apart.
"""
import os, math, random
from PIL import Image, ImageDraw
import uvlayout as U

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pack")
os.makedirs(OUT, exist_ok=True)

W = U.PNG  # 128

# ---------------- 3x5 pixel font (matches the stock pack glyph style) -------------
FONT = {
 "0": ["###","#.#","#.#","#.#","###"],
 "1": [".#.","##.",".#.",".#.","###"],
 "2": ["###","..#","###","#..","###"],
 "3": ["###","..#","###","..#","###"],
 "4": ["#.#","#.#","###","..#","..#"],
 "5": ["###","#..","###","..#","###"],
 "6": ["###","#..","###","#.#","###"],
 "7": ["###","..#","..#","..#","..#"],
 "8": ["###","#.#","###","#.#","###"],
 "9": ["###","#.#","###","..#","###"],
 "A": ["###","#.#","###","#.#","#.#"],
 "B": ["##.","#.#","##.","#.#","##."],
 "C": ["###","#..","#..","#..","###"],
 "D": ["##.","#.#","#.#","#.#","##."],
 "E": ["###","#..","##.","#..","###"],
 "F": ["###","#..","##.","#..","#.."],
 "G": ["###","#..","#.#","#.#","###"],
 "H": ["#.#","#.#","###","#.#","#.#"],
 "I": ["###",".#.",".#.",".#.","###"],
 "J": ["..#","..#","..#","#.#","###"],
 "K": ["#.#","#.#","##.","#.#","#.#"],
 "L": ["#..","#..","#..","#..","###"],
 "M": ["#.#","###","###","#.#","#.#"],
 "N": ["##.","#.#","#.#","#.#","#.#"],
 "O": ["###","#.#","#.#","#.#","###"],
 "P": ["###","#.#","###","#..","#.."],
 "Q": ["###","#.#","#.#","###","..#"],
 "R": ["###","#.#","##.","#.#","#.#"],
 "S": ["###","#..","###","..#","###"],
 "T": ["###",".#.",".#.",".#.",".#."],
 "U": ["#.#","#.#","#.#","#.#","###"],
 "V": ["#.#","#.#","#.#","#.#",".#."],
 "W": ["#.#","#.#","###","###","#.#"],
 "X": ["#.#","#.#",".#.","#.#","#.#"],
 "Y": ["#.#","#.#",".#.",".#.",".#."],
 "Z": ["###","..#",".#.","#..","###"],
 " ": ["...","...","...","...","..."],
 "-": ["...","...","###","...","..."],
 ".": ["...","...","...","...",".#."],
 "x": ["...","#.#",".#.","#.#","..."],
}

def text_w(s, scale=1, sp=1):
    return len(s) * (3 * scale + sp) - sp

def draw_text(px, x, y, s, col, scale=1, sp=1):
    cx = x
    for ch in s:
        g = FONT.get(ch.upper(), FONT[" "])
        for gy, row in enumerate(g):
            for gx, c in enumerate(row):
                if c == "#":
                    for dy in range(scale):
                        for dx in range(scale):
                            px(cx + gx * scale + dx, y + gy * scale + dy, col)
        cx += 3 * scale + sp

# ---------------- canvas --------------------------------------------------------
class Canvas:
    def __init__(self, w, h):
        self.im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        self.w, self.h = w, h

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.im.putpixel((int(x), int(y)), tuple(c) if len(c) == 4 else tuple(c) + (255,))

    def rect(self, x, y, w, h, c):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                self.px(xx, yy, c)

    def frame(self, x, y, w, h, c):
        for xx in range(int(x), int(x + w)):
            self.px(xx, y, c); self.px(xx, y + h - 1, c)
        for yy in range(int(y), int(y + h)):
            self.px(x, yy, c); self.px(x + w - 1, yy, c)

    def hgrad(self, x, y, w, h, stops):
        """stops = [(pos0..1, color), ...] left->right"""
        for xx in range(int(w)):
            t = xx / max(1, w - 1)
            c = sample(stops, t)
            for yy in range(int(h)):
                self.px(x + xx, y + yy, c)

    def vgrad(self, x, y, w, h, stops):
        for yy in range(int(h)):
            t = yy / max(1, h - 1)
            c = sample(stops, t)
            for xx in range(int(w)):
                self.px(x + xx, y + yy, c)

def sample(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        p0, c0 = stops[i - 1]
        p1, c1 = stops[i]
        if t <= p1:
            k = (t - p0) / max(1e-6, (p1 - p0))
            return tuple(int(round(c0[j] + (c1[j] - c0[j]) * k)) for j in range(len(c0)))
    return stops[-1][1]

def R(name):
    u, v, w, h = U.RECTS[name]
    return int(u * U.K), int(v * U.K), int(w * U.K), int(h * U.K)

# ---------------- palette -------------------------------------------------------
KRAFT      = (196, 154, 96)
KRAFT_L    = (214, 174, 116)
KRAFT_D    = (162, 122, 72)
KRAFT_DD   = (128, 94, 54)
AMBER      = (245, 191, 21)
AMBER_D    = (196, 148, 12)
INK        = (32, 26, 16)
NICK       = [(46,42,34),(110,104,88),(168,158,136),(200,192,172),(240,232,214)]
COPPER     = [(112,52,26),(168,88,46),(206,124,68),(228,158,96),(248,196,140)]
BLACKTIP   = [(18,20,26),(38,42,52),(64,70,84),(92,98,112)]

c = Canvas(W, W)

# =============================== CARTON FRONT ===================================
x0, y0, w0, h0 = R("cart_front")
c.rect(x0, y0, w0, h0, KRAFT)
# paper grain
rnd = random.Random(7)
for yy in range(h0):
    for xx in range(w0):
        n = rnd.randint(-8, 8)
        r, g, b = KRAFT
        c.px(x0 + xx, y0 + yy, (max(0,min(255,r+n)), max(0,min(255,g+n)), max(0,min(255,b+n))))
# folded edge shading
for xx in range(w0):
    c.px(x0 + xx, y0, KRAFT_DD)
    c.px(x0 + xx, y0 + 1, KRAFT_D)
    c.px(x0 + xx, y0 + h0 - 1, KRAFT_DD)
for yy in range(h0):
    c.px(x0, y0 + yy, KRAFT_DD)
    c.px(x0 + 1, y0 + yy, KRAFT_D)
    c.px(x0 + w0 - 1, y0 + yy, KRAFT_DD)
    c.px(x0 + w0 - 2, y0 + yy, KRAFT_D)

# amber label band
bx, by, bw, bh = x0 + 2, y0 + 3, w0 - 4, 10
c.rect(bx, by, bw, bh, AMBER)
c.rect(bx, by, bw, 1, (255, 220, 110))
c.rect(bx, by + bh - 1, bw, 1, AMBER_D)
c.rect(bx, by + bh - 2, bw, 1, (226, 172, 18))
# centred caliber text: 4 glyphs * (3+1) - 1 = 15px inside a 20px band
tw = text_w("7X46", 1, 1)
draw_text(c.px, bx + (bw - tw) // 2, by + (bh - 5) // 2, "7X46", INK, scale=1, sp=1)

# stencil rule + pictogram row under the band
rule_y = by + bh + 2
for xx in range(x0 + 3, x0 + w0 - 3):
    c.px(xx, rule_y, KRAFT_DD)
py = rule_y + 2
for i in range(4):
    px = x0 + 3 + i * 4
    for yy in range(py, py + 5):
        c.px(px, yy, KRAFT_DD)
    c.px(px, py - 1, KRAFT_DD)          # tip
    c.px(px + 1, py - 1, KRAFT_DD)

# bottom-left: count mark, bottom-right: a short rule
draw_text(c.px, x0 + 3, y0 + h0 - 7, "60", KRAFT_DD, scale=1, sp=1)
for xx in range(x0 + w0 - 10, x0 + w0 - 3):
    c.px(xx, y0 + h0 - 3, KRAFT_DD)

# =============================== CARTON PLAIN ===================================
x0, y0, w0, h0 = R("cart_plain")
c.rect(x0, y0, w0, h0, KRAFT)
for yy in range(h0):
    for xx in range(w0):
        n = rnd.randint(-7, 7)
        r, g, b = KRAFT
        c.px(x0 + xx, y0 + yy, (max(0,min(255,r+n)), max(0,min(255,g+n)), max(0,min(255,b+n))))
for xx in range(w0):
    c.px(x0 + xx, y0, KRAFT_DD); c.px(x0 + xx, y0 + 1, KRAFT_D)
    c.px(x0 + xx, y0 + h0 - 1, KRAFT_DD)
for yy in range(h0):
    c.px(x0, y0 + yy, KRAFT_DD); c.px(x0 + 1, y0 + yy, KRAFT_D)
    c.px(x0 + w0 - 1, y0 + yy, KRAFT_DD); c.px(x0 + w0 - 2, y0 + yy, KRAFT_D)
# stencil mark
c.rect(x0 + 4, y0 + 6, w0 - 8, 1, KRAFT_D)
c.rect(x0 + 4, y0 + 8, w0 - 12, 1, KRAFT_D)

# =============================== CARTON SIDES ===================================
for nm, col in (("cart_side", KRAFT), ("cart_side2", KRAFT_D)):
    x0, y0, w0, h0 = R(nm)
    c.rect(x0, y0, w0, h0, col)
    for yy in range(h0):
        for xx in range(w0):
            n = rnd.randint(-6, 6)
            r, g, b = col
            c.px(x0 + xx, y0 + yy, (max(0,min(255,r+n)), max(0,min(255,g+n)), max(0,min(255,b+n))))
    for xx in range(w0):
        c.px(x0 + xx, y0, KRAFT_DD); c.px(x0 + xx, y0 + h0 - 1, KRAFT_DD)
    for yy in range(h0):
        c.px(x0, y0 + yy, KRAFT_DD); c.px(x0 + w0 - 1, y0 + yy, KRAFT_DD)
    # corrugation ridges
    for yy in range(y0 + 3, y0 + h0 - 3, 4):
        for xx in range(x0 + 1, x0 + w0 - 1):
            c.px(xx, yy, KRAFT_D)

# =============================== CARTON TOP / INNER / BOTTOM ====================
x0, y0, w0, h0 = R("cart_top")
c.rect(x0, y0, w0, h0, KRAFT_L)
for xx in range(w0):
    c.px(x0 + xx, y0 + h0 - 1, KRAFT_DD)

x0, y0, w0, h0 = R("cart_inner")
c.rect(x0, y0, w0, h0, KRAFT_DD)
for yy in range(h0):
    for xx in range(w0):
        n = rnd.randint(-5, 5)
        r, g, b = KRAFT_DD
        c.px(x0 + xx, y0 + yy, (max(0,min(255,r+n)), max(0,min(255,g+n)), max(0,min(255,b+n))))

x0, y0, w0, h0 = R("cart_bottom")
c.rect(x0, y0, w0, h0, KRAFT_D)
for i in range(0, w0, 2):
    c.rect(x0 + i, y0 + 1, 1, h0 - 2, KRAFT_DD)

# =============================== CASE / BULLET BANDS ============================
# every band uses a horizontal dark->light->dark ramp so a 4-sided box reads as a cylinder
def band(name, ramp, dark_edges=True):
    x0, y0, w0, h0 = R(name)
    n = len(ramp)
    for xx in range(w0):
        t = xx / max(1, w0 - 1)
        # symmetric ramp: edges dark, centre bright
        k = 1.0 - abs(t - 0.5) * 2.0
        c0 = ramp[0]; c1 = ramp[-1]
        col = tuple(int(round(c0[j] + (c1[j] - c0[j]) * k)) for j in range(3))
        for yy in range(h0):
            c.px(x0 + xx, y0 + yy, col)

band("case_side", [(70,64,52), (226,218,198)])
band("rim_side", [(80,74,60), (232,224,204)])
band("groove_side", [(48,44,36), (120,114,98)])
band("shoulder_side", [(74,68,56), (222,214,194)])
band("neck_side", [(80,74,60), (232,224,204)])
band("bullet_side", [(96,44,22), (238,182,120)])
band("ogive", [(104,48,24), (244,190,128)])

# ---- black tip cap (our design marker) ----
x0, y0, w0, h0 = R("tip_cap")
for xx in range(w0):
    t = xx / max(1, w0 - 1)
    k = 1.0 - abs(t - 0.5) * 2.0
    col = tuple(int(round(BLACKTIP[0][j] + (BLACKTIP[-1][j] - BLACKTIP[0][j]) * k)) for j in range(3))
    for yy in range(h0):
        c.px(x0 + xx, y0 + yy, col)

# ---- primer (brass disc in the case head) ----
x0, y0, w0, h0 = R("primer")
c.rect(x0, y0, w0, h0, (58, 54, 44))
c.rect(x0 + 1, y0 + 1, w0 - 2, h0 - 2, (186, 148, 62))
c.rect(x0 + 2, y0 + 2, w0 - 4, h0 - 4, (218, 186, 96))
c.px(x0 + 1, y0 + 1, (120, 92, 36))

# ---- flat patches ----
def flat(name, col):
    x0, y0, w0, h0 = R(name)
    c.rect(x0, y0, w0, h0, col)

flat("s_nick",   (206, 198, 178))
flat("s_nick_d", (128, 122, 106))
flat("s_cu",     (214, 146, 88))
flat("s_cu_d",   (138, 70, 36))
flat("s_black",  (34, 38, 48))
flat("s_kraft",  (196, 154, 96))
flat("s_kraft_d",(150, 112, 64))

path = os.path.join(OUT, "7x46_uv.png")
c.im.save(path)
print("wrote", path, c.im.size)