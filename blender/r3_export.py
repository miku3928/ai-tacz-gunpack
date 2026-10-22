"""Export the finished model.

Run with:
  blender -b rifle3.blend --factory-startup -P r3_export.py

Writes out/rifle3.obj (+ .mtl), out/rifle3.fbx and prints the triangle count.
Every mesh gets a smart-projected UV set first, otherwise the OBJ carries no
UVs at all and the file is useless for texturing downstream.
"""
import bpy
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

sc = bpy.context.scene
# hide_render is what picks the magazine variant: both magazines live in the
# scene so the model can be switched, but the whole-gun OBJ/FBX must contain
# only the one that is currently shown.  Exporting the hidden one produced a
# file with two interpenetrating magazines.
meshes = [o for o in sc.objects
          if o.type == 'MESH' and o.name != 'Backdrop' and not o.hide_render]


def uv_all():
    for o in meshes:
        if not o.data.uv_layers:
            o.data.uv_layers.new(name='UVMap')
        bpy.context.view_layer.objects.active = o
        for ob in bpy.context.selected_objects:
            ob.select_set(False)
        o.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        try:
            bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.004)
        except Exception as e:                                  # noqa: BLE001
            print('  uv skipped', o.name, e)
        bpy.ops.object.mode_set(mode='OBJECT')


uv_all()

for ob in bpy.context.selected_objects:
    ob.select_set(False)
for o in meshes:
    o.select_set(True)

tris = 0
for o in meshes:
    o.data.calc_loop_triangles()
    tris += len(o.data.loop_triangles)

obj_path = os.path.join(OUT, 'rifle3.obj')
bpy.ops.wm.obj_export(
    filepath=obj_path,
    export_selected_objects=True,
    export_uv=True,
    export_normals=True,
    export_materials=True,
    apply_modifiers=True,
)
fbx_path = os.path.join(OUT, 'rifle3.fbx')
bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=True,
    object_types={'MESH'},
    mesh_smooth_type='FACE',
    use_mesh_modifiers=True,
    bake_space_transform=False,
)
print('EXPORT objects %d tris %d' % (len(meshes), tris))
print('EXPORT obj', obj_path)
print('EXPORT fbx', fbx_path)
