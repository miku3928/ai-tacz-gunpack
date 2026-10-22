"""r3_export_groups.py — one OBJ/FBX per assembly, plus a manifest.

The five assemblies live under GRP_<name> empties created by r3_split.py.  This
script exports each one on its own, at the ASSEMBLED position, so the files can
be re-imported onto the same coordinates and still line up.

Run:
    blender -b rifle3.blend --factory-startup -P r3_export_groups.py

Writes out/groups/<NAME>.obj (+ .mtl) and out/groups/<NAME>.fbx, and prints one
line per group with the file size and triangle count for the manifest.
"""
import bpy
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'out', 'groups')
# Two magazine variants are exported on purpose: MAGAZINE is the standard
# 30-round magazine from the reference sheet, MAGAZINE_BIG is the quad-stack
# extended one.  They are alternatives, not parts of one assembly.
GROUPS = ['MUZZLE', 'OPTIC', 'MAGAZINE', 'MAGAZINE_BIG', 'STOCK', 'BODY']


def in_group(ob, g):
    """True when ob belongs to group g, via the tag or the parent empty."""
    if ob.type != 'MESH':
        return False
    if ob.get('grp') == g:
        return True
    p = ob.parent
    return bool(p and p.name == 'GRP_' + g)


def main():
    os.makedirs(OUT, exist_ok=True)
    sc = bpy.context.scene

    # UVs: every group is exported unwrapped so the OBJ/FBX is usable in a
    # texturing app rather than a bare triangle soup.
    #
    # Both magazine variants are exported but only one is visible at a time
    # (r3_make.set_mag_variant), and smart_project raises "Cannot edit hidden
    # object" on the hidden one.  unhide() has to clear BOTH the object flag
    # (hide_viewport) and the per-view-layer flag (hide_set/hide_get) - the
    # poll looks at the view layer, so clearing only hide_viewport changed
    # nothing.
    def unhide(ob):
        ob.hide_viewport = False
        try:
            ob.hide_set(False)
        except RuntimeError:
            pass

    was_hidden = {}
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            was_hidden[ob.name] = (ob.hide_viewport, ob.hide_get())
            unhide(ob)
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.name != 'Backdrop':
            if not ob.data.uv_layers:
                bpy.ops.object.select_all(action='DESELECT')
                ob.select_set(True)
                bpy.context.view_layer.objects.active = ob
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02)
                bpy.ops.object.mode_set(mode='OBJECT')
    for n, (hv, hs) in was_hidden.items():
        o = bpy.data.objects.get(n)
        if o:
            o.hide_viewport = hv
            try:
                o.hide_set(hs)
            except RuntimeError:
                pass

    for g in GROUPS:
        members = [o for o in bpy.data.objects if in_group(o, g)]
        if not members:
            print('EXPORT %-9s SKIP (no members)' % g)
            continue

        # isolation by selection: the exporters write the selected objects only,
        # which avoids having to unparent anything.
        # Exporting the HIDDEN magazine variant only works if the object-level
        # hide_viewport is cleared as well: obj_export skips objects hidden
        # that way, and MAGAZINE_BIG came out as a 0.1 KB stub until it was.
        bpy.ops.object.select_all(action='DESELECT')
        saved = []
        for o in members:
            saved.append((o, o.hide_viewport, o.hide_get()))
            o.hide_viewport = False
            try:
                o.hide_set(False)
            except RuntimeError:
                pass
            o.select_set(True)
        bpy.context.view_layer.objects.active = members[0]

        tris = sum(len(o.data.loop_triangles) if o.data.loop_triangles
                   else sum(max(0, len(p.vertices) - 2) for p in o.data.polygons)
                   for o in members)

        obj_path = os.path.join(OUT, '%s.obj' % g)
        bpy.ops.wm.obj_export(
            filepath=obj_path,
            export_selected_objects=True,
            export_materials=True,
            export_uv=True,
            export_normals=True,
            apply_modifiers=True,
            # Blender's own OBJ convention: the scene's +Z becomes the file's
            # +Y.  Forcing forward='Y', up='Z' left the magazine lying on its
            # side (its length ended up on the file's Y instead of X), which a
            # round-trip import caught immediately.
            forward_axis='NEGATIVE_Z', up_axis='Y',
        )
        fbx_path = os.path.join(OUT, '%s.fbx' % g)
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            use_selection=True,
            apply_scale_options='FBX_SCALE_ALL',
            object_types={'MESH'},
            mesh_smooth_type='FACE',
            use_mesh_modifiers=True,
            path_mode='COPY',
            embed_textures=False,
        )
        print('EXPORT %-9s parts %2d  tris %6d  obj %6.1f KB  fbx %6.1f KB'
              % (g, len(members), tris,
                 os.path.getsize(obj_path) / 1024.0,
                 os.path.getsize(fbx_path) / 1024.0))
        for o, hv, hs in saved:
            o.hide_viewport = hv
            try:
                o.hide_set(hs)
            except RuntimeError:
                pass

    print('EXPORT done ->', OUT)


if __name__ == '__main__':
    main()
