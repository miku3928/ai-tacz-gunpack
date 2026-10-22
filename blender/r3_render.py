"""r3_render.py — lighting, cameras, three-view sheet render, save file."""
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Vector
from r3_lib import S

OUT = os.path.dirname(os.path.abspath(__file__)) + '/out/'
os.makedirs(OUT, exist_ok=True)


def scene_setup(engine='CYCLES', samples=64):
    sc = bpy.context.scene
    sc.render.engine = engine
    if engine == 'CYCLES':
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 6
        sc.cycles.transmission_bounces = 8
        sc.cycles.device = 'GPU'
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Filmic' if 'Filmic' in [v.name for v in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'AgX'
    sc.view_settings.look = 'None'
    w = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 1.0


def add_lights():
    for n, loc, rot, size, power in [
        ('Key', (0.15, -1.1, 1.3), (0.9, 0, 0.5), 1.6, 260),
        ('Fill', (-0.7, -1.2, 0.2), (1.35, 0, -0.45), 2.2, 90),
        ('Rim', (0.9, 0.9, 0.8), (0.8, 0, 2.6), 1.4, 140),
        ('Top', (0.0, 0.0, 1.6), (0, 0, 0), 3.0, 60),
    ]:
        d = bpy.data.lights.new(n, 'AREA')
        d.energy = power
        d.size = size
        d.shape = 'RECTANGLE'
        ob = bpy.data.objects.new(n, d)
        ob.location = loc
        ob.rotation_mode = 'XYZ'
        ob.rotation_euler = rot
        bpy.context.scene.collection.objects.link(ob)


def make_cam(name, loc, look_at, ortho_scale=None, lens=85):
    cam = bpy.data.cameras.new(name)
    if ortho_scale:
        cam.type = 'ORTHO'
        cam.ortho_scale = ortho_scale
    else:
        cam.lens = lens
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(look_at) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


def render(path, cam, res=(1600, 700), samples=48):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    sc.render.image_settings.file_format = 'PNG'
    sc.cycles.samples = samples
    bpy.ops.render.render(write_still=True)
    print('rendered', path)
