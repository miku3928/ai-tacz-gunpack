"""r3_shots.py — render deliverable stills from rifle3.blend."""
import bpy, sys, os, math
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = ROOT + '/out/'
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=ROOT + '/rifle3.blend')
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
# real GPU enable - device='GPU' alone silently falls back to CPU
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.refresh_devices()
for d in prefs.devices:
    d.use = (d.type == 'OPTIX')
sc.cycles.device = 'GPU' if any(d.use for d in prefs.devices) else 'CPU'
print('CYCLES DEVICE:', sc.cycles.device)
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
BD = bpy.data.objects.get('Backdrop')

jobs = [
    ('hero', 'CAM_Hero', (2400, 1350), 128, False),
    ('hero_front', 'CAM_Hero2', (1800, 1200), 96, False),
    ('side', 'CAM_Side', (2400, 1080), 96, False),
    ('top', 'CAM_Top', (2400, 1080), 96, False),
    ('front', 'CAM_Front', (900, 1600), 96, False),
    ('detail', 'CAM_Detail', (1800, 1200), 96, False),
    ('stock', 'CAM_Stock', (1800, 1200), 96, False),
    # cut-out versions for the three-view sheet
    ('side_t', 'CAM_Side', (2400, 1080), 96, True),
    ('top_t', 'CAM_Top', (2400, 1080), 96, True),
    ('front_t', 'CAM_Front', (900, 1600), 96, True),
]
for name, cam, res, smp, transparent in jobs:
    sc.camera = bpy.data.objects[cam]
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.cycles.samples = smp
    sc.render.film_transparent = transparent
    sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    if BD:
        BD.hide_render = transparent
    sc.render.filepath = OUT + name + '.png'
    bpy.ops.render.render(write_still=True)
    print('OK', name)
if BD:
    BD.hide_render = False
