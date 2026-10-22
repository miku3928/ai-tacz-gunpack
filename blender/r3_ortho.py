"""r3_ortho.py — exact-scale orthographic silhouette render (used for IoU checks).

Framing: the frame is centred on the bore axis (z=0) and spans exactly 690 mm
horizontally, matching the reference sheet's content box 1:1.
"""
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r3_lib as L
import r3_parts as P
import r3_mat as MT
from r3_lib import S
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = ROOT + '/work/'
# MATCH THE REFERENCE FRAME EXACTLY.
# ref_side.png is 1490x677 px at SC = 690/1481 mm/px, with the bore axis on
# row YC=257 and the muzzle at column X0=1. Rendering at the same size and
# offset means regions.py can compare pixels 1:1 with no resampling.
W, H = 1490, 677
SC = 690.0 / 1481.0
MMW = W * SC                       # 694.2 mm across the frame
CAMX = (W * 0.5 - 1.0) * SC        # frame centre in model mm
CAMZ = (257.0 - H * 0.5) * SC      # ditto, so row 257 is z = 0

L.wipe()
M = MT.build_materials()
P.build_muzzle(M['steel'])
P.build_barrel(M['steel'])
P.build_handguard(M['gray'], M['black'])
P.build_upper(M['black'], M['gray'])
P.build_lower(M['black'], M['gray'])
P.build_side_detail(M['black'], M['gray'])
P.build_grip(M['poly'])
P.build_stock(M['poly'], M['gray'], M['rubber'])
P.build_mag(M['mag'], M['brass'])
P.build_optic(M['optic'], M['glass'])
P.build_sights(M['black'])

sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.film_transparent = False
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('W'); sc.world = w
w.use_nodes = True
_bg = [n for n in w.node_tree.nodes if n.type == 'BACKGROUND'][0]
_bg.inputs[0].default_value = (1, 1, 1, 1)
_bg.inputs[1].default_value = 1.0
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'

# flat emission override: silhouette only, clean anti-aliasing, no shading
em = bpy.data.materials.new('SIL')
em.use_nodes = True
nt = em.node_tree
for n in list(nt.nodes):
    if n.type != 'OUTPUT_MATERIAL':
        nt.nodes.remove(n)
out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
e = nt.nodes.new('ShaderNodeEmission')
e.inputs[0].default_value = (0, 0, 0, 1)
e.inputs[1].default_value = 1.0
nt.links.new(e.outputs[0], out.inputs['Surface'])
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.data.materials.clear()
        o.data.materials.append(em)

cam_d = bpy.data.cameras.new('c'); cam_d.type = 'ORTHO'
cam_d.ortho_scale = MMW * S
cam = bpy.data.objects.new('c', cam_d); sc.collection.objects.link(cam); sc.camera = cam
# camera looks along +Y. The model spans x 0..690, so the frame centre must be
# x = 345 mm and z = 0 (bore axis) for a 1:1 match with the reference crop.
cam.location = (CAMX * S, -2.0, CAMZ * S)
cam.rotation_euler = (math.pi / 2, 0, 0)
sc.render.filepath = OUT + 'ortho_side.png'
bpy.ops.render.render(write_still=True)

# top view: same scale, frame centred laterally
cam.location = (CAMX * S, 0, 2.0)
cam.rotation_euler = (0, 0, 0)
sc.render.filepath = OUT + 'ortho_top.png'
bpy.ops.render.render(write_still=True)
print('ORTHO DONE', MMW, MMW * H / W)
