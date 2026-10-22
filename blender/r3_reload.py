"""A working reload animation, as a reference for whoever animates this.

Run:
    blender -b rifle3.blend --factory-startup -P r3_reload.py
    blender -b rifle3.blend --factory-startup -P r3_reload.py -- --sheet

Writes the action onto the objects (and saves work/reload.blend), plus, with
--sheet, renders six frames into work/reload_*.png.

The point of this file is the TIMING and the AXES, both measured off the rig:

  mag insertion axis   (0.268, 0, 0.963), i.e. 15.6 deg off vertical, leaning
                       toward the butt.  The magazine is NOT pulled straight
                       down and it is NOT rocked out the front - it slides along
                       that one axis.  Travelling 165 mm clears the magwell.
  trigger pivot        (384.9, 0, -36.2) mm, rotate about Y, NEGATIVE = pull.
  selector pivot       (407.0, 0, -16.5) mm, rotate about Y.
  mag release          press along -Y by 3.2 mm.

Frame rate is 24 fps; the whole reload is 72 frames (3 s), which is the pace a
game reload typically plays at for a rifle.
"""
import bpy
import math
import os
import sys

ROOT = 'C:/Users/miku/Documents/deepseek-harness/default-workspace/rifle3'
D = bpy.data.objects
sc = bpy.context.scene
sc.render.fps = 24

AX = (0.268, 0.0, 0.963)          # insertion axis, unit vector, out of the well
TRAVEL = 0.165                    # metres needed to clear the magwell (165 mm)
g = D['GRP_MAGAZINE']
rest = g.location.copy()

KEY = [
    # frame, what
    (1, 'idle'),
    (6, 'press release'),
    (10, 'mag released'),
    (16, 'mag clears the well'),
    (24, 'mag fully out, hand takes it away'),
    (30, 'mag away'),
    (40, 'fresh mag arrives'),
    (46, 'mag mouth enters the well'),
    (54, 'mag seated'),
    (58, 'release button out'),
    (64, 'tap to seat'),
    (72, 'idle'),
]

# ---- magazine path -------------------------------------------------------
def mag_at(f):
    """(offset vector, is_visible) for frame f.

    Between 24 and 40 the magazine is 'in the hand': it is moved away along
    -X and down so it leaves frame, which is how a reload is usually cheated.
    """
    if f <= 6:
        return 0.0, True
    if f < 16:
        t = (f - 6) / 10.0
        return TRAVEL * (t * t), True          # accelerating drop, gravity-like
    if f < 24:
        t = (f - 16) / 8.0
        return TRAVEL + 0.05 * t, True          # hand catches it, keeps going
    if f < 40:
        return TRAVEL + 0.05, False             # away: exit frame below
    if f < 46:
        t = 1.0 - (f - 40) / 6.0
        return TRAVEL * max(0.0, t), True        # new mag coming up
    if f < 54:
        t = (54 - f) / 8.0
        return TRAVEL * (t * t * t), True        # decelerating into the well
    return 0.0, True

# ---- release button ------------------------------------------------------
def rel_at(f):
    if 6 <= f < 10:
        return -0.0032
    if 58 <= f < 62:
        return 0.0
    if f < 6:
        return 0.0
    if f < 58:
        return -0.0032 if f < 54 else -0.0032 * (58 - f) / 4.0
    return 0.0

# ---- trigger: fired once, before the reload -----------------------------
def trig_at(f):
    # Pull, hold through the shot, then RELEASE - a trigger left held through a
    # reload is the classic tell of a first-pass animation.
    if f < 4:
        return 0.0
    if f < 8:
        return math.radians(-18.0) * ((f - 4) / 4.0)
    if f < 12:
        return math.radians(-18.0)
    if f < 18:
        return math.radians(-18.0) * (1.0 - (f - 12) / 6.0)
    return 0.0

# ---- selector: on SAFE for the reload, back to FIRE at the end ----------
def sel_at(f):
    if f < 30:
        return 0.0
    if f < 36:
        return math.radians(-90.0) * (f - 30) / 6.0
    if f < 66:
        return math.radians(-90.0)
    return math.radians(-90.0) * (1.0 - (f - 66) / 6.0)


def key_all():
    for f, _ in KEY:
        off, vis = mag_at(f)
        g.location = (rest.x + AX[0] * off, rest.y, rest.z + AX[2] * off)
        g.keyframe_insert('location', frame=f)
        g.hide_render = not vis
        g.keyframe_insert('hide_render', frame=f)

        D['MagRelease'].location.y = 23.2 * 0.001 + rel_at(f)
        D['MagRelease'].keyframe_insert('location', frame=f)

        D['Trigger'].rotation_euler = (0.0, trig_at(f), 0.0)
        D['Trigger'].keyframe_insert('rotation_euler', frame=f)

        D['Selector'].rotation_euler = (0.0, sel_at(f), 0.0)
        D['Selector'].keyframe_insert('rotation_euler', frame=f)


key_all()
for ob in (g, D['MagRelease'], D['Trigger'], D['Selector']):
    if ob.animation_data and ob.animation_data.action:
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
sc.frame_start = 1
sc.frame_end = 72

bpy.ops.wm.save_as_mainfile(filepath=ROOT + '/out/anim/reload_reference.blend')
print('RELOAD action written, frames 1..72 @ 24 fps')

if '--sheet' in sys.argv:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.refresh_devices()
    for d in prefs.devices:
        d.use = (d.type == 'OPTIX')
    sc.cycles.device = 'GPU'
    sc.render.engine = 'CYCLES'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = 0.62
    sc.cycles.samples = 32

    from mathutils import Vector
    cd = bpy.data.cameras.new('c')
    cam = bpy.data.objects.new('c', cd)
    sc.collection.objects.link(cam)
    cam.location = (0.30, -0.42, -0.02)
    cam.rotation_euler = (Vector((0.31, 0, -0.06)) - cam.location)\
        .to_track_quat('-Z', 'Y').to_euler()
    cd.lens = 52
    sc.camera = cam
    sc.render.resolution_x = 620
    sc.render.resolution_y = 520
    for f in (4, 10, 20, 34, 50, 64):
        sc.frame_set(f)
        sc.render.filepath = '%s/work/reload_%02d.png' % (ROOT, f)
        bpy.ops.render.render(write_still=True)
    print('RELOAD sheet frames rendered')
