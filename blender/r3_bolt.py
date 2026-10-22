"""r3_bolt.py - add the moving action parts and open the ejection port.

The static model is a solid shell: the upper receiver has no ejection port, no
bolt, no charging handle and no bolt catch, so there is nothing to animate when
the rifle runs dry.  This script adds the three parts the reload needs and cuts
the two openings they ride in:

    Bolt            bolt carrier + bolt face, slides along the bore axis (+X)
    ChargingHandle  side charger on the -Y flank, bolted to the carrier
    BoltCatch       paddle on the -Y flank of the lower, rotates about Y

    port  x 301.5..372.5, z -6.5..12.0, cut from the -Y wall in to y = -8.0
    slot  x 402..444,     z -1.0..13.0, same depth - the charging handle track

Cut rules learned the hard way:  a cutter whose faces are EXACTLY coplanar with
the geometry it cuts makes the EXACT solver keep the coincident faces, and the
first run left UR_detail's proud port plate bridging the hole it was meant to
open.  Every cutter below is half a millimetre proud of the face it meets.

Idempotent: the three new objects are deleted first and the cuts are re-run
(boolean difference against already-removed material is a no-op).

Run:
    blender -b rifle3.blend --factory-startup -P r3_bolt.py
"""
import bpy, bmesh, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r3_lib as L
from r3_lib import Part, S, boolop

ROOT = os.path.dirname(os.path.abspath(__file__))
BLEND = ROOT + '/rifle3.blend'

NEW = ['Bolt', 'ChargingHandle', 'BoltCatch']

# ---- openings, millimetres ----------------------------------------------
PORT = (301.5, 372.5, -40.0, -8.0, -6.5, 12.0)    # x0 x1 y0 y1 z0 z1
SLOT = (402.0, 444.0, -40.0, -8.0, -1.0, 13.0)
CUT_TARGETS = ['Upper', 'UR_detail']

# ---- action parts, millimetres ------------------------------------------
# The bolt is deliberately LONGER than the port on both ends: a carrier that
# stopped flush with the window would read as a plate screwed into the hole
# instead of a part sliding behind it.
BOLT_X = (286.0, 434.0)
BOLT_Y = (-18.5, 6.0)     # outer face 6 mm behind the plate, so the window reads as an opening
BOLT_Z = (-2.0, 10.5)


def M(name, fallback='M_Black'):
    return bpy.data.materials.get(name) or bpy.data.materials[fallback]


def cutter(name, box):
    p = Part(name, None)
    p.box(*box)
    return p.build(smooth=False, coll_name='Geo')


def open_window(target_name, box):
    """Delete the faces of `target_name` that lie inside `box`.

    The EXACT boolean is not enough here: UR_detail is the proud port plate and
    it is built from several overlapping shells, so the solver removed the
    outer cap but left the inner caps in place - the window stayed closed and
    the bolt behind it was invisible.  Deleting the faces outright is
    deterministic: the plate keeps its 2-4 mm bezel ring around the hole.
    """
    ob = bpy.data.objects.get(target_name)
    if ob is None:
        raise RuntimeError('missing window target %r' % target_name)
    x0, x1, y0, y1, z0, z1 = [v * S for v in box]
    mw = ob.matrix_world.copy()
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    doomed = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        if x0 < c.x < x1 and y0 < c.y < y1 and z0 < c.z < z1:
            doomed.append(f)
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context='FACES')
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(doomed)


def cut(target_name, box, tag):
    ob = bpy.data.objects.get(target_name)
    if ob is None:
        raise RuntimeError('missing cut target %r' % target_name)
    boolop(ob, cutter('cut_%s_%s' % (target_name, tag), box))
    return ob


def build_bolt():
    p = Part('Bolt', M('M_Gray3'))
    x0, x1 = BOLT_X
    y0, y1 = BOLT_Y
    z0, z1 = BOLT_Z
    p.box(x0, x1, y0, y1, z0, z1)                    # carrier body
    p.box(x0 - 6.0, x0 + 8.0, y0 + 1.5, y1 - 1.5, z0 + 1.0, z1 - 1.0)   # bolt face
    p.box(x0 - 4.0, x0 + 2.0, y0 + 2.5, y1 - 2.5, z0 + 3.0, z1 - 3.0)   # firing pin tail
    p.box(x1 - 40.0, x1 - 8.0, y0 + 1.0, y0 + 5.0, z1 - 3.0, z1)        # gas key
    return p.build(smooth=True, angle=30, bevel=0.5, bevel_seg=1,
                   coll_name='Geo')


def build_charge_handle():
    p = Part('ChargingHandle', M('M_Black'))
    p.box(402.0, 432.0, -34.0, -24.0, 0.0, 12.0)     # outside knob
    p.box(408.0, 426.0, -24.5, -21.0, 1.5, 10.5)     # neck through the slot
    p.box(410.0, 424.0, -21.5, -9.0, 2.5, 9.5)       # stem, joins the carrier
    return p.build(smooth=True, angle=30, bevel=0.7, bevel_seg=1,
                   coll_name='Geo')


def build_bolt_catch():
    p = Part('BoltCatch', M('M_Black'))
    p.box(396.0, 414.0, -28.0, -23.0, -26.0, -13.0)  # paddle
    p.box(392.0, 399.0, -27.2, -23.0, -15.5, -10.5)  # hook up to the carrier
    p.box(396.0, 414.0, -29.2, -27.4, -24.0, -15.0)  # serrated face
    return p.build(smooth=True, angle=30, bevel=0.5, bevel_seg=1,
                   coll_name='Geo')


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    for n in NEW:
        old = bpy.data.objects.get(n)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)

    for t in CUT_TARGETS:
        cut(t, PORT, 'port')
        cut(t, SLOT, 'slot')

    # the proud port plate keeps its caps through the boolean, so punch it open
    n = open_window('UR_detail', PORT)
    print('UR_detail window faces removed:', n)

    obs = [build_bolt(), build_charge_handle(), build_bolt_catch()]

    # file them with the rest of the body so the scene stays consistent with
    # what r3_split.py produces
    grp = bpy.data.objects.get('GRP_BODY')
    body = bpy.data.collections.get('BODY')
    for ob in obs:
        if grp:
            mw = ob.matrix_world.copy()
            ob.parent = grp
            ob.matrix_parent_inverse = grp.matrix_world.inverted()
            ob.matrix_world = mw
        ob['grp'] = 'BODY'
        if body:
            for uc in list(ob.users_collection):
                uc.objects.unlink(ob)
            body.objects.link(ob)

    bpy.ops.wm.save_mainfile()
    print('BOLT ok', [(o.name, len(o.data.polygons)) for o in obs])
    print('UPPER faces', len(bpy.data.objects['Upper'].data.polygons),
          'UR_detail faces', len(bpy.data.objects['UR_detail'].data.polygons))


if __name__ == '__main__':
    main()
