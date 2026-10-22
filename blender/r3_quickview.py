"""Fast iteration renders (EEVEE, seconds) - for checking shape/colour while working.
Final deliverables still come from r3_shots.py (Cycles).
"""
import bpy, sys, os, math, time
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = ROOT + '/work/'
os.makedirs(OUT, exist_ok=True)
t0 = time.time()

bpy.ops.wm.open_mainfile(filepath=ROOT + '/rifle3.blend')
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.eevee.taa_render_samples = 12
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_percentage = 100

jobs = [
    ('q_hero', 'CAM_Hero', (1100, 620)),
    ('q_side', 'CAM_Side', (1500, 640)),
]
for name, cam, res in jobs:
    sc.camera = bpy.data.objects[cam]
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = OUT + name + '.png'
    bpy.ops.render.render(write_still=True)
    print('OK', name, '%.1fs' % (time.time() - t0))
print('TOTAL %.1fs' % (time.time() - t0))
