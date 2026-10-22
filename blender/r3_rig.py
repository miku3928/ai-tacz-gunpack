"""Rig the rifle for animation.

WHY THIS SCRIPT EXISTS
-----------------------
The model was built to be looked at, not moved.  Two things block animation
straight out of the box:

  1. EVERY mesh has its origin at the world origin (0,0,0).  They were parented
     with matrix_parent_inverse, which pins matrix_world to identity, so
     `ob.rotation_euler = ...` on the Trigger swings it about the muzzle end of
     the gun rather than about its own pivot pin.  Measured: Trigger origin
     (0,0,0), Trigger centroid (382.8, 0, -45.2).

  2. The parts that a reload animation has to move were welded into larger
     meshes, or did not exist at all: no bolt, no charging handle, no bolt
     catch, no ejection port.  The magazine release button used to be part of
     LR_controls; it is now its own object.

WHAT THIS SCRIPT DOES
---------------------
  * moves each moveable part's origin onto its real pivot, WITHOUT moving any
    geometry, so a plain rotation/translation is already correct;
  * records every pivot in a JSON file (`out/anim/rig.json`) so the animator can
    key things from a script;
  * prints a table of what can move, on which axis, and by how much.

Run:  blender -b rifle3.blend --factory-startup -P r3_rig.py
"""
import bpy
import json
import os
from mathutils import Vector

ROOT = os.path.dirname(bpy.data.filepath) or \
    'C:/Users/miku/Documents/deepseek-harness/default-workspace/rifle3'
OUT = os.path.join(ROOT, 'out', 'anim')
os.makedirs(OUT, exist_ok=True)

D = bpy.data.objects
S = 0.001          # the model is in millimetres, Blender units are metres


def centroid(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    return Vector((sum(p.x for p in pts) / len(pts),
                   sum(p.y for p in pts) / len(pts),
                   sum(p.z for p in pts) / len(pts)))


def set_origin(o, pivot):
    """Move the object's origin to `pivot` (world, metres) without moving any
    geometry.

    bpy.ops.object.origin_set() is NOT usable here: these objects are parented
    with matrix_parent_inverse, so the operator's result gets undone the moment
    the world matrix is re-applied, and a first attempt left every origin at
    (0,0,0).  Doing it by hand is two lines and always correct:
      1. subtract the pivot's LOCAL coordinates from every vertex, which moves
         the geometry around the intended point;
      2. put the object's world translation on the pivot, which puts the origin
         there and leaves the geometry exactly where it was in the viewport.
    """
    mw = o.matrix_world.copy()
    delta = mw.inverted() @ pivot
    for v in o.data.vertices:
        v.co -= delta
    o.data.update()
    new = mw.copy()
    new.translation = pivot
    o.matrix_world = new


# ----------------------------------------------------------------- pivots
# Values measured off the geometry, not guessed:
#   TRIGGER   the shoe is x 379.2..390.6, z -38.2..-35.5, so the pin is at the
#             top of the blade near (384.9, 0, -36.2).
#   SELECTOR  a through-shaft: both flank levers share centre (407.0, -16.5),
#             and the shaft runs the full y -27.6..27.6, so the axis is the
#             X-... no: the shaft is along Y, the lever swings in the XZ plane.
#   MAGAZINE  insertion axis measured from the lofted spine: from the ring
#             centre at z -75 (x 311.10) to the one at z -145 (x 291.82), i.e.
#             direction (0.268, 0, 0.963) - 15.6 deg off vertical, out of the
#             well towards the butt.  The GRP_MAGAZINE empty already sits at the
#             centre of the assembly, so the magazine simply travels along it.
PIVOTS = {
    'Trigger': (384.9, 0.0, -36.2),
    'Selector': (407.0, 0.0, -16.5),
    'MagRelease': (355.0, 23.2, -34.0),
}

for name, (x, y, z) in PIVOTS.items():
    o = D.get(name)
    if not o:
        print('  MISSING', name)
        continue
    set_origin(o, Vector((x * S, y * S, z * S)))

# The magazine assembly is moved through its group empty; make sure that empty
# sits on the insertion axis rather than a bbox centre, so rotation about it is
# also sensible.
g = D.get('GRP_MAGAZINE')
if g:
    g.location = (302.07 * S, 0.0, -104.86 * S)

# ------------------------------------------------------------------ report
MOVEABLE = {
    # SIGN, measured rather than assumed: the pivot is at z -36.2 and the
    # trigger's hook is at z -58, i.e. 21.8 mm BELOW the pivot.  Rotating about
    # +Y by theta moves that hook by dz*sin(theta) in x, so a POSITIVE angle
    # swings it 6 mm towards the MUZZLE - backwards.  Real trigger pull swings
    # the hook 6 mm towards the BUTT, so the angle must be NEGATIVE.
    'Trigger': dict(axis='Y', kind='rotate', range_deg=(-6.0, -22.0),
                    note='NEGATIVE Y = proper pull (hook travels toward the butt); '
                         '-6 sear break, -22 full overtravel'),
    'Selector': dict(axis='Y', kind='rotate', range_deg=(0.0, -90.0),
                     note='0 = FIRE, -90 = SAFE (rotates about its own Y shaft)'),
    'MagRelease': dict(axis='Y', kind='translate', range_mm=(0.0, -3.2),
                       note='press inward along -Y to drop the magazine'),
    'GRP_MAGAZINE': dict(axis='XZ', kind='translate',
                         dir=(0.268, 0.0, 0.963), range_mm=(0.0, 165.0),
                         note='pull down along the insertion axis, then clear'),
    'GRP_STOCK': dict(axis='X', kind='translate', range_mm=(0.0, 240.0),
                      note='telescoping; buffer tube travel ~60 mm usable'),
}

rig = {}
for o in D:
    if o.type != 'MESH':
        continue
    rig[o.name] = {
        'grp': o.get('grp', ''),
        'origin_mm': [round(v / S, 3) for v in o.matrix_world.translation],
    }

data = {
    'units': 'model is built in millimetres; Blender units are metres (1 BU = 1000 mm)',
    'moveable': MOVEABLE,
    'pivots_mm': {k: list(v) for k, v in PIVOTS.items()},
    'objects': rig,
}
with open(os.path.join(OUT, 'rig.json'), 'w') as fh:
    json.dump(data, fh, indent=1, ensure_ascii=False)

print('=== PIVOTS SET ===')
for k, v in PIVOTS.items():
    o = D.get(k)
    if o:
        print('  %-11s origin (%.1f, %.1f, %.1f) mm'
              % (k, o.matrix_world.translation.x / S,
                 o.matrix_world.translation.y / S,
                 o.matrix_world.translation.z / S))

print('=== MOVEABLE ===')
for k, v in MOVEABLE.items():
    print('  %-13s %s %s %s' % (k, v['kind'], v['axis'], v.get('note', '')))

bpy.ops.wm.save_mainfile()
print('RIG saved ->', OUT)
