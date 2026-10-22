# -*- coding: utf-8 -*-
"""7x46 ejected-casing (shell) model + texture + _n/_s maps.

The stock pack draws a casing with a 16x16 declared texture (png is 64x64), a
4-cube body and flat 1-texel faces per side. We keep that economy: no per-face
gradient, just a few flat tones that read as a lit cylinder once the game's
directional shading is applied. Orientation independence matters because the
casing tumbles in flight.
"""
import json, os, random
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pack")
os.makedirs(os.path.join(OUT, "geo_models", "shell"), exist_ok=True)
os.makedirs(os.path.join(OUT, "textures", "shell"), exist_ok=True)

TW = TH = 16
PNG = 64
K = PNG // TW

# flat tones, nickel flavour of the icon's casing
NICK_L = (238, 230, 212)
NICK_M = (196, 188, 168)
NICK_D = (128, 122, 106)
NICK_DD = (78, 74, 62)
BRASS = (206, 158, 66)
BRASS_D = (150, 104, 40)
SHADOW = (46, 44, 38)

# uv rects, one texel each in the 16-space
RECTS = {
    "lit":    (0, 0), "mid": (1, 0), "dark": (2, 0), "cap": (3, 0),
    "head":   (0, 1), "primer": (1, 1), "mouth": (2, 1), "flat": (3, 1),
}

def build_texture():
    im = Image.new('RGBA', (PNG, PNG), (0, 0, 0, 0))
    px = im.load()
    rnd = random.Random(11)
    cols = {'lit': NICK_L, 'mid': NICK_M, 'dark': NICK_D, 'cap': NICK_M,
            'head': NICK_DD, 'primer': BRASS, 'mouth': SHADOW, 'flat': NICK_D}
    for name, (u, v) in RECTS.items():
        c = cols[name]
        for yy in range(K):
            for xx in range(K):
                n = rnd.randint(-4, 4)
                px[u * K + xx, v * K + yy] = (max(0, min(255, c[0] + n)),
                                              max(0, min(255, c[1] + n)),
                                              max(0, min(255, c[2] + n)), 255)
    # the primer gets a punched centre so it does not read as a flat square
    u, v = RECTS['primer']
    for yy in range(1, K - 1):
        for xx in range(1, K - 1):
            px[u * K + xx, v * K + yy] = (BRASS_D[0], BRASS_D[1], BRASS_D[2], 255)
    return im

def flat_maps():
    n = Image.new('RGBA', (PNG, PNG), (127, 127, 255, 255))
    s = Image.new('RGBA', (PNG, PNG), (200, 0, 0, 255))   # rough, non metal
    return n, s

im = build_texture()
im.save(os.path.join(OUT, 'textures', 'shell', '7x46_shell.png'))
n, s = flat_maps()
n.save(os.path.join(OUT, 'textures', 'shell', '7x46_shell_n.png'))
s.save(os.path.join(OUT, 'textures', 'shell', '7x46_shell_s.png'))

# ---------------------------------------------------------------- geometry
def face(rect, flip=False):
    u, v = RECTS[rect]
    return {'uv': [u, v], 'uv_size': [1, -1 if flip else 1]}

def cube(o, sz, faces):
    return {'origin': [round(x, 5) for x in o],
            'size': [round(x, 5) for x in sz],
            'uv': faces}

# casing runs along +Z: primer at -Z, open mouth at +Z
BODY_L, BODY_D = 1.55, 0.42
NECK_L, NECK_D = 0.42, 0.30
RIM_L,  RIM_D = 0.09, 0.48
PRI_L,  PRI_D = 0.05, 0.28

def walls(lit, mid, dark):
    return {'up': face(lit), 'down': face(dark),
            'east': face(mid), 'west': face(mid)}

r0 = BODY_D / 2.0
z = -BODY_L / 2.0

cubes = [
    cube([-r0, -r0, z], [BODY_D, BODY_D, BODY_L],
         dict(walls('lit', 'mid', 'dark'), north=face('head'), south=face('flat'))),
    cube([-NECK_D / 2, -NECK_D / 2, z + BODY_L], [NECK_D, NECK_D, NECK_L],
         dict(walls('lit', 'mid', 'dark'), south=face('mouth'), north=face('flat'))),
    cube([-RIM_D / 2, -RIM_D / 2, z - RIM_L], [RIM_D, RIM_D, RIM_L],
         dict(walls('mid', 'mid', 'dark'), north=face('head'), south=face('flat'))),
    cube([-PRI_D / 2, -PRI_D / 2, z - RIM_L - PRI_L], [PRI_D, PRI_D, PRI_L],
         {'north': face('primer'), 'south': face('flat'),
          'up': face('primer'), 'down': face('flat'),
          'east': face('primer'), 'west': face('flat')}),
]

geo = {
    'format_version': '1.12.0',
    'minecraft:geometry': [{
        'description': {
            'identifier': 'geometry.7x46_shell',
            'texture_width': TW,
            'texture_height': TH,
            'visible_bounds_width': 2,
            'visible_bounds_height': 1.5,
            'visible_bounds_offset': [0, 0.25, 0],
        },
        'bones': [{'name': '7x46', 'pivot': [8, 0, -8], 'cubes': cubes}],
    }],
}

p = os.path.join(OUT, 'geo_models', 'shell', '7x46_shell.json')
with open(p, 'w', encoding='utf-8') as f:
    json.dump(geo, f, ensure_ascii=False, indent=2)
print('shell ok', sum(len(b['cubes']) for b in geo['minecraft:geometry'][0]['bones']))
