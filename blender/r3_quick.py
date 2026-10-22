"""Quick visual check: build + viewport render of side/top/front + perspective."""
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r3_lib as L
import r3_parts as P
import r3_mat as MT
from r3_lib import S

L.wipe()
M = MT.build_materials()
P.build_muzzle(M['steel'])
P.build_barrel(M['steel'])
P.build_handguard(M['gray'], M['black'])
P.build_upper(M['black'], M['gray'])
P.build_lower(M['black'], M['gray'])
P.build_grip(M['poly'])
P.build_stock(M['poly'], M['gray'], M['rubber'])
P.build_mag(M['mag'], M['brass'])
P.build_optic(M['steel'], M['glass'])
P.build_sights(M['black'])

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rifle3.blend'))
print('SAVED')
