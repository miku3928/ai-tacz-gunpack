"""r3_build.py — assemble the rifle, save the .blend, render the sheet."""
import bpy, sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import r3_lib as L
import r3_parts as P
import r3_mat as MT
from r3_lib import Part, S

t0 = time.time()
L.wipe()
M = MT.build_materials()

objs = {}
def add(key, v):
    objs[key] = v if isinstance(v, list) else [v]

add('muzzle', P.build_muzzle(M['steel']))
add('barrel', P.build_barrel(M['steel']))
add('hg', P.build_handguard(M['gray'], M['black']))
add('upper', P.build_upper(M['black'], M['gray']))
add('lower', P.build_lower(M['black'], M['gray']))
P.build_side_detail(M['black'], M['gray'])
add('grip', P.build_grip(M['poly']))
add('stock', P.build_stock(M['poly'], M['gray'], M['rubber']))
add('mag', P.build_mag(M['mag'], M['brass']))
add('optic', P.build_optic(M['steel'], M['glass']))
add('sights', P.build_sights(M['black']))

print('BUILD time', round(time.time() - t0, 1), 's')
for k, v in objs.items():
    for o in v:
        if o: print(' ', k, o.name, len(o.data.polygons) if o.type == 'MESH' else '-')
