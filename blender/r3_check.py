"""r3_check.py — build, then render orthographic side/top/front + 3/4 with EEVEE for a quick look."""
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r3_lib as L
import r3_parts as P
import r3_mat as MT
from r3_lib import S
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = ROOT + '/work/'
os.makedirs(OUT, exist_ok=True)

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

sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.film_transparent = False
sc.eevee.taa_render_samples = 32
sc.view_settings.view_transform = 'AgX'
world = bpy.data.worlds.new('W')
sc.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.9, 0.9, 0.92, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = 1.0

def light(name, loc, size, energy):
    d = bpy.data.lights.new(name, 'AREA'); d.size = size; d.energy = energy
    o = bpy.data.objects.new(name, d); o.location = loc
    sc.collection.objects.link(o)
    o.rotation_euler = (Vector((0.345, 0, 0.0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
light('key', (0.2, -0.7, 0.55), 1.0, 55)
light('fill', (-0.5, -0.9, 0.05), 1.2, 18)
light('rim', (0.9, 0.7, 0.5), 1.0, 30)

cam_d = bpy.data.cameras.new('cam'); cam_d.type = 'ORTHO'; cam_d.ortho_scale = 0.76
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam

def shot(name, loc, look, ortho=None, res=(1500, 700)):
    cam.location = loc
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'; cam.data.lens = 70
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = OUT + name + '.png'
    bpy.ops.render.render(write_still=True)

shot('chk_side', (0.345, -1.2, 0.0), (0.345, 0, 0.0), ortho=0.78)
shot('chk_top', (0.345, 0.0, 1.4), (0.345, 0, 0.0), ortho=0.78)
shot('chk_front', (1.5, 0.0, 0.0), (0, 0, 0.0), ortho=0.60, res=(500, 900))
shot('chk_34', (0.10, -0.55, 0.22), (0.36, 0, 0.0), res=(1200, 900))
print('CHECK DONE')
