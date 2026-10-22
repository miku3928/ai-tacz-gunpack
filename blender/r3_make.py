"""r3_make.py — assemble the full scene (materials, lights, cameras), save .blend."""
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r3_lib as L
import r3_parts as P
import r3_mat as MT
from r3_lib import S
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))


def build_geo():
    M = MT.build_materials()
    parts = {}
    parts['muzzle'] = P.build_muzzle(M['steel'])
    parts['barrel'] = P.build_barrel(M['steel'])
    parts['hg'] = P.build_handguard(M['gray'], M['black'])
    parts['upper'] = P.build_upper(M['black'], M['gray'])
    parts['lower'] = P.build_lower(M['black'], M['gray'])
    P.build_side_detail(M['black'], M['gray'])
    parts['grip'] = P.build_grip(M['grip'])
    parts['stock'] = P.build_stock(M['poly'], M['gray'], M['rubber'])
    parts['mag'] = P.build_mag(M['mag'], M['brass'])
    parts['magbig'] = P.build_mag_big(M['mag'], M['brass'])
    parts['optic'] = P.build_optic(M['optic'], M['glass'])
    parts['sights'] = P.build_sights(M['black'])
    return M, parts


def enable_gpu():
    """Actually enable the OptiX device - just setting device='GPU' falls back to CPU."""
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.refresh_devices()
    got = False
    for d in prefs.devices:
        d.use = (d.type == 'OPTIX')
        got = got or d.use
    bpy.context.scene.cycles.device = 'GPU' if got else 'CPU'
    print('GPU backend:', prefs.compute_device_type, 'enabled:', got)
    return got


def setup_world():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles.transparent_max_bounces = 12
    sc.cycles.transmission_bounces = 12
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.resolution_percentage = 100
    enable_gpu()

    w = bpy.data.worlds.new('Studio')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    # Blender 4.2 does not index the world's default node as 'Background';
    # look it up by type or this raises KeyError and kills the whole build.
    bg = [n for n in nt.nodes if n.type == 'BACKGROUND'][0]
    bg.inputs[0].default_value = (0.055, 0.06, 0.07, 1)
    bg.inputs[1].default_value = 0.55
    sc.view_settings.exposure = 0.62
    sc.view_settings.look = 'None'


def add_backdrop():
    """Large cyclorama: back wall + floor, so the gun sits in a light studio."""
    sc = bpy.context.scene
    import bmesh
    me = bpy.data.meshes.new('Backdrop')
    bm = bmesh.new()
    cy = 3.2           # wall distance
    zb = -0.30         # floor height
    fy = 1.0           # floor radius behind the camera
    r = 0.55           # cove radius
    pts = []
    # floor from front to the cove
    pts.append((-2.6, -3.0, zb))
    pts.append((4.0, -3.0, zb))
    pts.append((4.0, cy - r, zb))
    pts.append((-2.6, cy - r, zb))
    # wall
    pts2 = [(-2.6, cy, zb + r), (4.0, cy, zb + r), (4.0, cy, 2.4), (-2.6, cy, 2.4)]
    vs = [bm.verts.new(p) for p in pts]
    bm.faces.new(vs)
    vs2 = [bm.verts.new(p) for p in pts2]
    bm.faces.new(vs2)
    # cove: strip between floor and wall
    import math
    n = 8
    prev = None
    for i in range(n + 1):
        a = math.radians(90.0 * i / n)
        y = (cy - r) + r * math.sin(a)
        z = zb + r - r * math.cos(a)
        row = [bm.verts.new((-2.6, y, z)), bm.verts.new((4.0, y, z))]
        if prev:
            bm.faces.new((prev[0], prev[1], row[1], row[0]))
        prev = row
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('Backdrop', me)
    sc.collection.objects.link(ob)
    mat = bpy.data.materials.new('M_Backdrop')
    mat.use_nodes = True
    b = [n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    b.inputs['Base Color'].default_value = (0.78, 0.79, 0.81, 1)
    b.inputs['Roughness'].default_value = 0.80
    b.inputs['Specular IOR Level'].default_value = 0.15
    me.materials.append(mat)
    return ob


def add_lights():
    sc = bpy.context.scene

    def area(name, loc, rot, size, size_y, power, color=(1, 1, 1)):
        d = bpy.data.lights.new(name, 'AREA')
        d.energy = power
        d.shape = 'RECTANGLE'
        d.size = size
        d.size_y = size_y
        d.color = color
        ob = bpy.data.objects.new(name, d)
        ob.location = loc
        ob.rotation_euler = rot
        sc.collection.objects.link(ob)
        return ob

    # Calibrated studio rig (work/lframe.py + work/lscale.py, scored on the
    # EXACT reference pixel frame by work/lscore.py). Target was the sheet's
    # flat catalogue lighting; the previous rig blew every frontal face out to
    # ~1.5x because the rim kickers were 32/18 W and the key sat high.
    def aim(ob, loc, tgt=(0.345, 0.0, -0.02)):
        from mathutils import Vector
        ob.location = loc
        ob.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

    # big soft frontal key, slightly above the bore
    k = area('Key', (0.10, -0.95, 0.45), (0, 0, 0), 0.9, 0.55, 10.4)
    aim(k, (0.10, -0.95, 0.45))
    # gentle top for rail highlights (was 14 W and painted the whole upper)
    t = area('Top', (0.34, -0.15, 1.05), (0, 0, 0), 1.3, 0.30, 2.0)
    aim(t, (0.34, -0.15, 1.05))
    # broad frontal fill from the other side, cool
    f = area('Fill', (-0.55, -0.90, 0.10), (0, 0, 0), 1.2, 0.7, 5.6, (0.90, 0.94, 1.0))
    aim(f, (-0.55, -0.90, 0.10))
    # very weak rims: they exist only to separate the silhouette from the cove
    r = area('Rim', (0.60, 0.85, 0.45), (0, 0, 0), 0.6, 0.35, 2.0)
    aim(r, (0.60, 0.85, 0.45))
    r2 = area('Rim2', (0.10, 0.90, 0.25), (0, 0, 0), 0.8, 0.30, 1.2)
    aim(r2, (0.10, 0.90, 0.25))
    # low kicker for the underside of the magwell and handguard
    u = area('Under', (0.30, -0.60, -0.55), (0, 0, 0), 0.8, 0.4, 1.6)
    aim(u, (0.30, -0.60, -0.55))
    # FRONT fill: every other lamp sits beside the gun, so CAM_Front (which
    # looks along +X at the muzzle end) was rendering almost pure black - the
    # front of the model received no light at all.  This one sits in front of
    # the muzzle and fires back down the bore axis.
    fr = area('Front', (-0.70, -0.28, 0.13), (0, 0, 0), 1.1, 0.9, 7.5,
              (0.96, 0.97, 1.0))
    aim(fr, (-0.70, -0.28, 0.13), (0.30, 0.0, 0.0))
    # second, lower front lamp: the underside of the handguard and the
    # magazine's front face receive almost nothing from the rig above.
    fr2 = area('Front2', (-0.55, -0.10, -0.28), (0, 0, 0), 0.9, 0.7, 3.6,
               (0.95, 0.96, 1.0))
    aim(fr2, (-0.55, -0.10, -0.28), (0.30, 0.0, -0.05))


def add_cameras():
    sc = bpy.context.scene
    cams = {}

    def cam(name, loc, look, lens=85, ortho=None):
        cd = bpy.data.cameras.new(name)
        if ortho:
            cd.type = 'ORTHO'
            cd.ortho_scale = ortho
        else:
            cd.lens = lens
        ob = bpy.data.objects.new(name, cd)
        sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        cams[name] = ob
        return ob

    cam('CAM_Side', (0.345, -2.4, 0.0), (0.345, 0, 0.0), ortho=0.75)
    cam('CAM_Top', (0.345, 0.0, 2.4), (0.345, 0, 0.0), ortho=0.75)
    # NOTE: the front view must stand IN FRONT OF THE MUZZLE (x<0) and look
    # back along +X.  At x=+2.2 it was looking at the butt pad, which is why
    # the front elevation in every sheet render showed the stock end-on.
    cam('CAM_Front', (-0.62, 0.0, 0.0), (0.30, 0, 0.0), ortho=0.32)
    cam('CAM_Hero', (0.92, -1.45, 0.36), (0.345, 0.0, -0.02), lens=72)
    cam('CAM_Hero2', (-0.28, -1.48, 0.28), (0.345, 0.0, -0.01), lens=72)
    cam('CAM_Detail', (0.30, -0.36, 0.16), (0.40, 0.0, 0.05), lens=105)
    cam('CAM_Stock', (0.98, -0.62, -0.08), (0.68, 0.0, -0.03), lens=105)
    sc.camera = cams['CAM_Hero']
    return cams


MAG_STD = ('Magazine', 'MagFloor', 'MagSlot', 'MagNeck')
MAG_BIG = ('MagazineBig', 'MagBigFloor', 'MagBigSlot', 'MagBigNeck')


def set_mag_variant(which='std'):
    """Show one magazine, hide the other.

    Both magazines are built into the scene so the model ships with a standard
    30-round magazine AND a quad-stack extended one.  They occupy the same
    space, so exactly one has to be visible at a time - otherwise the two
    shells interpenetrate and the result is an unreadable mess.

    'std'  -> the 30-round magazine from the reference sheet (default)
    'big'  -> the quad-stack extended magazine
    """
    show = MAG_STD if which == 'std' else MAG_BIG
    hide = MAG_BIG if which == 'std' else MAG_STD
    for n in show:
        o = bpy.data.objects.get(n)
        if o:
            o.hide_render = False
            o.hide_viewport = False
    for n in hide:
        o = bpy.data.objects.get(n)
        if o:
            o.hide_render = True
            o.hide_viewport = True
    print('MAGVARIANT', which)


if __name__ == '__main__':
    L.wipe()
    M, parts = build_geo()
    setup_world()
    add_backdrop()
    add_lights()
    cams = add_cameras()
    set_mag_variant('std')
    bpy.ops.wm.save_as_mainfile(filepath=ROOT + '/rifle3.blend')
    n = sum(len(p.data.polygons) for p in bpy.data.objects if p.type == 'MESH')
    print('SAVED objects', len(bpy.data.objects), 'faces', n)
