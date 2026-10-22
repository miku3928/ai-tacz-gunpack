# -*- coding: utf-8 -*-
"""7x46 ammo geo model -> pack/geo_models/ammo/7x46.json

Bedrock quirks encoded here:
  * a bone pivot only spins its cubes, it never translates them, so each round
    bakes its offset into the cube origins and the pivot sits on that offset;
  * uv coords are in texture_width/height space, while the png is 2x that;
  * uv_size may be negative to flip a face.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uvlayout as U

OUT = os.path.join(HERE, "pack")
os.makedirs(os.path.join(OUT, "geo_models", "ammo"), exist_ok=True)

def R(name):
    return U.RECTS[name]

def uvof(rect, flip_v=False):
    u, v, w, h = R(rect)
    return {"uv": [u, v], "uv_size": [w, -h if flip_v else h]}

def side_faces(rect, top=None, bottom=None):
    f = {k: uvof(rect) for k in ("north", "south", "east", "west")}
    if top:
        f["up"] = uvof(top)
    if bottom:
        f["down"] = uvof(bottom, flip_v=True)
    return f

def cube(origin, size, faces, rotation=None, pivot=None):
    c = {"origin": [round(x, 5) for x in origin],
         "size": [round(x, 5) for x in size],
         "uv": faces}
    if rotation:
        c["rotation"] = rotation
    if pivot:
        c["pivot"] = [round(x, 5) for x in pivot]
    return c

# ---------------------------------------------------------------- cartridge
# the taller silhouette we locked in for the icon: long ogive, short case
STACK = [
    ("rim_side",      0.30, 1.00),
    ("groove_side",   0.22, 0.82),
    ("case_side",     4.10, 0.98),
    ("shoulder_side", 0.55, 0.86),
    ("shoulder_side", 0.45, 0.74),
    ("neck_side",     0.80, 0.66),
    ("bullet_side",   2.60, 0.66),
    ("ogive",         0.70, 0.56),
    ("ogive",         0.55, 0.42),
    ("tip_cap",       0.42, 0.30),
]
CART_H = sum(h for _, h, _ in STACK)

def cartridge(base):
    bx, by, bz = base
    cubes, y = [], 0.0
    for i, (rect, h, dia) in enumerate(STACK):
        r = dia * 0.5
        f = side_faces(rect, top=("s_nick" if i == len(STACK) - 1 else None))
        if i == 0:
            f["down"] = uvof("primer", flip_v=True)
        cubes.append(cube([bx - r, by + y, bz - r], [dia, h, dia], f))
        y += h
    return cubes

# ---------------------------------------------------------------- crate
BOX_O = [-7.0, 0.0, -2.0]
BOX_S = [7.0, 7.0, 3.5]
BOX_TOP = BOX_O[1] + BOX_S[1]

box_cubes = [
    cube(BOX_O, BOX_S, {
        "north": uvof("cart_front"),
        "south": uvof("cart_plain"),
        "east":  uvof("cart_side"),
        "west":  uvof("cart_side2"),
        "up":    uvof("cart_top"),
        "down":  uvof("cart_bottom", flip_v=True),
    }),
    # dark interior floor seen through the open top
    cube([BOX_O[0] + 0.20, BOX_TOP - 0.45, BOX_O[2] + 0.20],
         [BOX_S[0] - 0.40, 0.05, BOX_S[2] - 0.40],
         {k: uvof("cart_inner") for k in ("north", "south", "east", "west", "up")}),
]

# ---------------------------------------------------------------- rounds
# four standing in the crate, fanned so the silhouettes separate
ROUND_SPOTS = [
    ([-5.90, 0.0, -0.30], [0, 0, 0]),
    ([-4.60, 0.0, -0.55], [0, 14, 0]),
    ([-3.30, 0.0, -0.15], [0, -12, 0]),
    ([-2.00, 0.0, -0.60], [0, 18, 0]),
]
# one loose round on the ground in front of the crate, pointing +X
LOOSE = ([0.30, 0.50, 2.70], [0, 0, -90])

bones = [{"name": "root", "pivot": [-4, 0, 0]},
         {"name": "box", "parent": "root", "pivot": [-7, 3.5, 0], "rotation": [0, -10, 0],
          "cubes": box_cubes}]

for i, (base, rot) in enumerate(ROUND_SPOTS):
    bones.append({"name": "round%d" % (i + 1), "parent": "root",
                  "pivot": base, "rotation": rot, "cubes": cartridge(base)})
bones.append({"name": "round5", "parent": "root",
              "pivot": LOOSE[0], "rotation": LOOSE[1], "cubes": cartridge(LOOSE[0])})

bones += [
    {"name": "positioning", "pivot": [-7.025, -3.5, -11.225]},
    {"name": "ground", "parent": "positioning", "pivot": [0, 3.5, 0]},
    {"name": "fixed", "parent": "positioning", "pivot": [0, 9.25, 2.875], "rotation": [0, -10, 0]},
    {"name": "thirdperson_hand", "parent": "positioning", "pivot": [-2, 3.5, 2]},
]

geo = {
    "format_version": "1.12.0",
    "minecraft:geometry": [{
        "description": {
            "identifier": "geometry.7x46",
            "texture_width": U.UVW,
            "texture_height": U.UVW,
            "visible_bounds_width": 3,
            "visible_bounds_height": 2.5,
            "visible_bounds_offset": [0, 1.0, 0],
        },
        "bones": bones,
    }],
}

p = os.path.join(OUT, "geo_models", "ammo", "7x46.json")
with open(p, "w", encoding="utf-8") as f:
    json.dump(geo, f, ensure_ascii=False, indent=2)
print("cart_h", CART_H, "cubes", sum(len(b.get("cubes", [])) for b in bones))