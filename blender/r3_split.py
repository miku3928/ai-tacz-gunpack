"""r3_split.py — group the assembled rifle into named assemblies.

Creates five parent empties (MUZZLE / OPTIC / MAGAZINE / STOCK / BODY) plus one
Blender collection per group, parents every mesh to its group, and stamps a
custom property `grp` on each object so downstream scripts (isolated renders,
exploded view, per-part export) can select a group without name lists.

Run:
    blender -b --factory-startup -P r3_split.py
    blender -b --factory-startup -P r3_split.py -- --explode 60
"""
import bpy, sys, os, math

ROOT = os.path.dirname(os.path.abspath(__file__))
BLEND = ROOT + '/rifle3.blend'

# ---- group assignment -------------------------------------------------
# Names are matched EXACTLY; anything unlisted raises so a renamed part can
# never silently fall through into the wrong assembly.
GROUPS = {
    'MUZZLE': ['MuzzleBrake', 'MuzzleBore'],
    'OPTIC': ['Optic', 'OpticGlass', 'OpticMount', 'Cap', 'Cap.001'],
    # the magazine group is the magazine ONLY: the neck collar belongs to the
    # magazine (it rides on the mag body), the magwell stays on the receiver.
    'MAGAZINE': ['Magazine', 'MagFloor', 'MagSlot', 'MagNeck'],
    'MAGAZINE_BIG': ['MagazineBig', 'MagBigFloor', 'MagBigSlot', 'MagBigNeck'],
    'STOCK': ['StockFrame', 'Cheek', 'StockGap', 'StockDet',
              'ButtPad', 'ButtRibs', 'BufferTube'],
    'BODY': ['Barrel', 'BarrelBore', 'HG_body', 'HG_core', 'HG_front',
             'HG_shroud', 'HG_shroud_slot', 'HG_side', 'HG_sideplate',
             'HG_bottom', 'HG_rail', 'HG_qd', 'BUIS_F', 'BUIS_R',
             'Upper', 'UR_rail', 'UR_band', 'UR_detail', 'UR_rear',
             'Lower', 'LR_front', 'LR_front_gray', 'LR_panel_r',
             'LR_panel_f', 'LR_controls', 'LR_pins', 'LR_magwell',
             'TriggerGuard', 'Trigger', 'Selector', 'Grip',
                 'MagRelease'],
}

# group colour used by the isolated catalogue renders (RGB, linear-ish)
TINT = {
    'MUZZLE':   (0.62, 0.30, 0.22),
    'OPTIC':    (0.22, 0.38, 0.60),
    'MAGAZINE': (0.30, 0.46, 0.28),
    'MAGAZINE_BIG': (0.72, 0.40, 0.20),
    'STOCK':    (0.46, 0.34, 0.52),
    'BODY':     (0.30, 0.31, 0.33),
}

# exploded-view offset, millimetres, per group.  The muzzle travels forward,
# the optic straight up off its rail, the magazine straight down out of the
# magwell, the stock straight back; the body stays put as the reference.
# The magazine travels furthest on purpose: 37 mm of it lives INSIDE the
# magwell, so a shorter throw still shows a magazine with its top third
# missing - which is exactly the error this exploded view is meant to expose.
EXPLODE = {
    'MUZZLE':   (-95.0, 0.0, 0.0),
    'OPTIC':    (0.0, 0.0, 130.0),
    'MAGAZINE': (-30.0, 0.0, -215.0),
    'MAGAZINE_BIG': (-30.0, 0.0, -215.0),
    'STOCK':    (115.0, 0.0, 0.0),
    'BODY':     (0.0, 0.0, 0.0),
}


def collect_assignments():
    """name -> group, asserting every mesh is assigned exactly once."""
    seen = {}
    for g, names in GROUPS.items():
        for n in names:
            if n in seen:
                raise RuntimeError('object %r listed in both %s and %s'
                                   % (n, seen[n], g))
            seen[n] = g
    meshes = [o.name for o in bpy.data.objects if o.type == 'MESH'
              and o.name != 'Backdrop']
    missing = [n for n in meshes if n not in seen]
    orphan = [n for n in seen if n not in meshes]
    if missing:
        raise RuntimeError('unassigned meshes: %s' % missing)
    if orphan:
        raise RuntimeError('group lists objects that do not exist: %s' % orphan)
    return seen


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    offset = 0.0
    if '--explode' in argv:
        offset = float(argv[argv.index('--explode') + 1])

    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    assign = collect_assignments()

    # clean out any earlier run so the script is idempotent
    for g in list(GROUPS) + ['RIG']:
        old = bpy.data.collections.get(g)
        if old:
            for o in list(old.objects):
                old.objects.unlink(o)
            bpy.data.collections.remove(old)
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY' and o.name.startswith('GRP_'):
            bpy.data.objects.remove(o, do_unlink=True)

    # one empty per group, parked at the group's centroid so the origin is
    # meaningful when the group is moved or exported on its own
    empties = {}
    for g, names in GROUPS.items():
        pts = []
        for n in names:
            ob = bpy.data.objects[n]
            pts += [ob.matrix_world @ v.co for v in ob.data.vertices]
        cx = sum(p.x for p in pts) / len(pts) * 1000.0
        cy = sum(p.y for p in pts) / len(pts) * 1000.0
        cz = sum(p.z for p in pts) / len(pts) * 1000.0
        e = bpy.data.objects.new('GRP_' + g, None)
        e.empty_display_type = 'PLAIN_AXES'
        e.empty_display_size = 22.0
        e.location = (cx / 1000.0, cy / 1000.0, cz / 1000.0)
        e['grp'] = g
        e['count'] = len(names)
        sc.collection.objects.link(e)
        empties[g] = e

    # The empties' matrix_world is computed lazily.  Without this update the
    # inverse below is the IDENTITY (the location has not landed yet) and every
    # group ends up displaced by exactly its own empty's position.
    bpy.context.view_layer.update()

    # collections
    colls = {}
    for g in GROUPS:
        c = bpy.data.collections.new(g)
        sc.collection.children.link(c)
        colls[g] = c

    # parent meshes to their empty (keeping world transform) and file them
    for n, g in assign.items():
        ob = bpy.data.objects[n]
        # Setting .parent moves the child immediately; writing
        # matrix_parent_inverse afterwards does NOT reliably restore it
        # (the first run left every group offset by exactly its empty's
        # location).  Capture the world matrix, parent, then push the world
        # matrix back - that is order-independent and always exact.
        mw = ob.matrix_world.copy()
        ob.parent = empties[g]
        ob.matrix_parent_inverse = empties[g].matrix_world.inverted()
        ob.matrix_world = mw
        ob['grp'] = g
        for uc in list(ob.users_collection):
            uc.objects.unlink(ob)
        colls[g].objects.link(ob)

    # the old flat 'Geo' collection is now empty
    geo = bpy.data.collections.get('Geo')
    if geo and not geo.objects:
        bpy.data.collections.remove(geo)

    # Backdrop / lights / cameras stay in the scene collection
    rig = bpy.data.collections.new('RIG')
    sc.collection.children.link(rig)
    for o in list(sc.collection.objects):
        if o.type in ('LIGHT', 'CAMERA') or o.name == 'Backdrop':
            sc.collection.objects.unlink(o)
            rig.objects.link(o)

    if offset:
        for g, e in empties.items():
            dx, dy, dz = EXPLODE[g]
            e.location = (e.location.x + dx * offset / 1000.0,
                          e.location.y + dy * offset / 1000.0,
                          e.location.z + dz * offset / 1000.0)

    bpy.ops.wm.save_mainfile()
    counts = {g: len(names) for g, names in GROUPS.items()}
    print('SPLIT groups', len(GROUPS), 'meshes', len(assign), counts,
          'explode', offset)


if __name__ == '__main__':
    main()
