"""r3_preview.py — 1-3 second Cycles/OptiX preview for iteration.

Usage:  blender -b -P r3_preview.py -- <view> [width] [samples]
view: hero | side | detail | stock
"""
import bpy, sys, os, time
ROOT = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
view = argv[0] if argv else 'hero'
W = int(argv[1]) if len(argv) > 1 else 900
SMP = int(argv[2]) if len(argv) > 2 else 24

t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=ROOT + '/rifle3.blend')
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.refresh_devices()
for d in prefs.devices:
    d.use = (d.type == 'OPTIX')
sc.cycles.device = 'GPU' if any(d.use for d in prefs.devices) else 'CPU'
sc.cycles.samples = SMP
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'

CAM = {'hero': 'CAM_Hero', 'side': 'CAM_Side', 'detail': 'CAM_Detail',
       'stock': 'CAM_Stock', 'front': 'CAM_Front', 'top': 'CAM_Top'}[view]
sc.camera = bpy.data.objects[CAM]
aspect = 1350 / 2400 if view == 'hero' else 1080 / 2400
sc.render.resolution_x = W
sc.render.resolution_y = int(W * aspect)
sc.render.filepath = ROOT + '/work/prev_' + view + '.png'
bpy.ops.render.render(write_still=True)
print('PREVIEW %s %dx%d in %.1fs' % (view, sc.render.resolution_x,
                                    sc.render.resolution_y, time.time() - t0))
