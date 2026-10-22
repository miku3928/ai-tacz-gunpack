"""r3_magvar.py — switch between the two magazines.

The model ships with two interchangeable magazines:

    std  the standard 30-round magazine that matches the reference sheet
    big  the quad-stack (四排) extended magazine - 1.6x the thickness,
         ~225 mm long instead of 157 mm, so roughly twice the capacity

Both exist in rifle3.blend at all times; only one is visible.  Switching is
just a visibility toggle, so anything that reads the scene (renders, exports,
group isolation) picks up whichever one is showing.

Run:
    blender -b rifle3.blend -P r3_magvar.py -- std
    blender -b rifle3.blend -P r3_magvar.py -- big

Add --save to write the change back into rifle3.blend.
"""
import bpy, sys, os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from r3_make import set_mag_variant, MAG_STD, MAG_BIG

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
which = 'std'
for a in argv:
    if a in ('std', 'big'):
        which = a

set_mag_variant(which)

if '--save' in argv:
    bpy.ops.wm.save_mainfile(filepath=ROOT + '/rifle3.blend')
    print('MAGVAR saved', which)

for n in MAG_STD + MAG_BIG:
    o = bpy.data.objects.get(n)
    if o:
        print('  %-12s visible=%s' % (n, not o.hide_render))
