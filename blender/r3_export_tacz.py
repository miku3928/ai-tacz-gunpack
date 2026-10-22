"""r3_export_tacz.py - bake rifle3.blend into a TaCZ (TML poly_mesh) geometry.

Coordinate mapping (verified against the shipped ti_ar15 pack, whose bounds
solve the constants exactly):

    units per metre U = 52.4476   (the 0.858 m rifle project mapped to 45 units)
    tx = -y_m * U                 (model +X is the shooter's RIGHT; the blend
    ty =  z_m * U + 12.0           keeps its right-side detail on -Y, so the
    tz = (x_m - 0.345) * U         whole gun is mirrored in Y and the winding is
                                   reversed to keep the normals consistent)

TaCZ model space: -Z is the muzzle, +Z the butt, +Y up, +X the right flank.
The camera bone in the stock guns sits at +X, i.e. the first-person view sees
the +X flank - that is why the ejection port has to end up on +X.

Every bone carries its own poly_mesh (PolyMeshModel keys meshMap by bone name)
and poly_mesh positions are ABSOLUTE model coordinates - the gun bone of the
shipped pack has pivot [0,12,0] yet its positions run from -22.5 to +22.5 in Z.

Output: work/tacz/geo.json + palette.json + report.txt
"""
import bpy, json, math, os, sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(ROOT, 'rifle3.blend')
OUT = os.path.join(ROOT, 'work', 'tacz')
os.makedirs(OUT, exist_ok=True)

U = 52.4476
CX = 0.345
OFFY = 12.0


def P3(xmm, ymm, zmm):
    return [round(-ymm / 1000.0 * U, 5),
            round(zmm / 1000.0 * U + OFFY, 5),
            round((xmm / 1000.0 - CX) * U, 5)]


def T(co):
    return (-co.y * U, co.z * U + OFFY, (co.x - CX) * U)


def TN(n):
    return (-n.y, n.z, n.x)


# ---- which mesh rides on which bone -------------------------------------
#
# TaCZ attachment plumbing, all of it name driven (BedrockGunModel computes
# "<type>_pos" / "<type>_default" by string concatenation):
#
#   <type>_pos      where an installed attachment is drawn
#   <type>_default  the part the gun ships with, hidden as soon as something
#                   is bolted on
#   mag_standard /  the two magazine bodies; the game shows exactly one,
#   mag_extended_N  picked by the installed extended_mag_level
#
# So every removable assembly becomes a *_default bone here, and the very same
# geometry is re-emitted (re-origined onto its mount) as a separate attachment
# model by r3_att_geo.py.  BufferTube stays on the gun: it is the receiver
# extension, not part of the stock.
DEFAULTS = {
    'muzzle': ('MuzzleBrake', 'MuzzleBore'),
    'scope': ('Optic', 'OpticGlass', 'OpticMount', 'Cap', 'Cap.001'),
    'stock': ('StockFrame', 'Cheek', 'StockGap', 'StockDet', 'ButtPad',
              'ButtRibs'),
}
MAGS = {
    'mag_standard': ('Magazine', 'MagFloor', 'MagSlot', 'MagNeck'),
    'mag_extended_1': ('MagazineBig', 'MagBigFloor', 'MagBigSlot',
                       'MagBigNeck'),
}
BONE_OF = {}
for _t, _names in DEFAULTS.items():
    for _n in _names:
        BONE_OF[_n] = _t + '_default'
for _b, _names in MAGS.items():
    for _n in _names:
        BONE_OF[_n] = _b
# The built-in optic is NOT a "scope_default" part: TaCZ only hides a gun's own
# part when it is called <type>_default, and SCOPE is the one type it skips in
# allAttachmentRender() (a scope is drawn by the scopePosPath branch instead).
# So a bone named scope_default stays visible next to every scope you install -
# two overlapping optics.  The bones that DO get hidden are the sight ones:
#   sight         visible when the scope slot is empty  (lambda$new$15)
#   sight_folded  visible when a scope IS mounted       (lambda$new$13)
#   mount         the rail base, visible only with a scope + show_mount
# Our optic body therefore lives on "sight", which disappears the moment a
# scope is attached, while the shipped scope_std attachment draws the optics.
for _n in DEFAULTS['scope']:
    BONE_OF[_n] = 'sight'

BONE_OF.update({
    'Bolt': 'bolt',
    'ChargingHandle': 'charge_handle',
    'BoltCatch': 'bolt_catch',
    'Trigger': 'trigger',
    'Selector': 'selector',
    'MagRelease': 'mag_release',
})

# The two sculpted gloves from the abandoned "build real hands" attempt are
# not shipped: TaCZ replaces the hand bones with the vanilla player arms, so
# any geometry of our own would just be a second, wrong hand.
SKIP = ('Backdrop', 'Cube', 'Plane', 'Hand_R', 'Hand_L')

# ---- bone tree: (name, parent, pivot[, rotation]) -----------------------
# The optional 4th item is a Bone rotation baked into the geometry.  It is only
# used by the refit_* bones: the attachment screen walks those bones with
# getPositioningNodeInverse() and applies *their* rotation, so a refit view
# without rotation points the gun at the camera ("gun stabs you in the face").
# Every official gun carries [0,90,0] there; see r3_pack.py / work/refit_*.py.
BONES = [
    # root pivot sits at the shoulder like every official gun (m4a1 [0,7,-1.4],
    # hk416d [0,7.1,6.85], ak47 [0,8.2,6.5]); rotating about [0,0,0] would swing
    # the whole rifle around a point below the trigger and look wrong.
    ('root', None, [0.0, 8.0, 4.0]),
    ('gun', 'root', P3(345, 0, 0)),

    # ---- hand rig -------------------------------------------------------
    # TaCZ does not model hands: BedrockGunModel registers a functional
    # renderer for the bones named righthand_pos / lefthand_pos and draws the
    # *vanilla player arms* at whatever world matrix those bones end up with
    # (BedrockPart = T(animPos) T(pivot/16) Rz Ry Rx S, pivot relative to the
    # parent with Y negated).  So all we ship is the transform chain; any cube
    # or poly_mesh on those bones is thrown away at render time.
    #
    # The chain below is a verbatim copy of the official m4a1 chain, collapsed
    # from three bones to two:
    #     m4a1:  gun_and_righthand[0,7,-1.425] -> righthand[6,19,0] (rot+pos)
    #            -> righthand_pos[0,8,0]
    #     ours:  gun -> righthand -> righthand_pos
    # The two local pivots were solved so that the composite matrix is
    # identical, then the whole chain was slid so that the righthand_pos origin
    # lands on (grip centre + the median offset measured over 37 official guns,
    # 3.3 / 1.9 / 15.9 model units) and lefthand_pos on (handguard centre +
    # the median over 20 guns, 2.7 / 6.6 / 18.2).  Scale is part of the chain
    # (1, 1.5, 1) exactly as in m4a1, and it does stretch the child pivot.
    ('righthand', 'gun', [-0.055, 7.761, 3.979]),
    ('righthand_pos', 'righthand', [-6.055, -3.239, 3.979]),
    ('lefthand', 'gun', [1.463, 8.29, -8.937]),
    ('lefthand_pos', 'lefthand', [7.463, -2.71, -8.937]),
    ('magazine', 'gun', P3(318, 0, -20)),
    # Both magazine bodies hang off the magazine bone, so the reload animation
    # (which only moves `magazine`) carries whichever one the game picked.
    ('mag_standard', 'magazine', P3(318, 0, -20)),
    ('mag_extended_1', 'magazine', P3(318, 0, -20)),
    # TaCZ picks the magazine body from extended_mag_level 1/2/3 and hides the
    # other two.  We only modelled one extended body, so levels 2 and 3 reuse
    # it verbatim (clone happens at assembly time - see CLONE below).
    ('mag_extended_2', 'magazine', P3(318, 0, -20)),
    ('mag_extended_3', 'magazine', P3(318, 0, -20)),
    ('bolt', 'gun', P3(434, 0, 4)),
    ('charge_handle', 'gun', P3(417, 0, 6)),
    ('bolt_catch', 'gun', P3(403, -26, -20)),
    ('trigger', 'gun', P3(384.9, 0, -36.2)),
    ('selector', 'gun', P3(407, 0, -16.5)),
    ('mag_release', 'gun', P3(355, 23.2, -34)),
    ('constraint', 'root', P3(345, 0, 0)),

    # ---- attachment mounts ------------------------------------------------
    # Each pivot is the mechanical interface, not the centroid:
    #   muzzle  x 54  the barrel's muzzle face, i.e. where a device threads on
    #   scope   x331 z45  centre of the mount footprint on the receiver rail
    #   stock   x497  on the receiver extension, inside the stock's front bore
    # The *_default child carries the shipped part; because poly_mesh positions
    # are absolute model coordinates, both a default and the equivalent
    # attachment (re-origined onto this same point) land in exactly the same
    # place, so installing the standard muzzle device is visually a no-op.
    ('muzzle_pos', 'gun', P3(54, 0, 0)),
    ('muzzle_default', 'muzzle_pos', P3(54, 0, 0)),
    ('muzzle_flash', 'gun', P3(-37, 0, 0)),
    ('shell', 'gun', P3(337, -24, 3)),
    ('scope_pos', 'gun', P3(331, 0, 45)),
    ('sight', 'scope_pos', P3(331, 0, 45)),
    ('stock_pos', 'gun', P3(497, 0, 0)),
    ('stock_default', 'stock_pos', P3(497, 0, 0)),
    # Foregrip / laser mounts.  TaCZ looks up "<type>_pos" for every attachment
    # type the gun allows, so without these two bones the official grips and
    # lasers are rejected by the attachment screen.  Both sit where the part
    # would physically bolt on: the grip under the M-LOK bottom face of the
    # handguard (z -45.5 mm), the laser on the right-hand M-LOK row (z -20 mm,
    # y -28 mm - the exporter mirrors Y, so blend -Y is model +X, the right side
    # where every official gun puts its laser: m4a1 laser_pos x +1.47).
    # Neither carries geometry - a bare *_pos bone is the mount.
    ('grip_pos', 'gun', P3(157, 0, -45.5)),
    ('laser_pos', 'gun', P3(157, -28, -20)),
    # Some official attachments declare an "adapter" in their display json
    # ("adapter": "ar_stock_adapter" on 9 of the 9 official stocks, and
    # "laser_adapter" on laser_compact).  That name is a node in the *gun* model:
    # AttachmentRender resolves adapterNodeName against our bone list, so an
    # adapter stock hangs off ar_stock_adapter when it exists.  Both are empty
    # bones sitting exactly on the matching *_pos mount, so they are free.
    ('ar_stock_adapter', 'gun', P3(497, 0, 0)),
    ('laser_adapter', 'gun', P3(157, -28, -20)),
    # --- the view bones --------------------------------------------------
    # TaCZ translates the whole model by minus the idle_view pivot, so the eye
    # ends up exactly ON idle_view and the gun hangs in front of it.  It does
    # not rescale anything, so the apparent size of the rifle is decided purely
    # by how far idle_view sits from the parts you are meant to see.
    #
    # The first playtest put idle_view 5.4 units behind the scope eyepiece: the
    # ocular lens alone then covered half the screen ("糊脸").  The eye belongs
    # at the back of the receiver, at the scope axis, a couple of units right of
    # the centreline - that is where the official rifles sit (13% of the length
    # forward of the butt, 0.65-0.79 of the height above the bottom).
    #
    # Model space here: -Z muzzle, +Z butt, +Y up, +X right.  The scope axis is
    # at y 16.16 (79 mm above the bore) and its rear lens at z 3.5.
    ('camera', None, [6.75, 18.75, 18.75]),
    ('views', None, [0, 0, 0]),
    ('idle_view', 'views', [7, 19, 19.5]),
    ('iron_view', 'views', [0.0, 16.2, 5.2]),
    # ---- attachment screen (press Z) ---------------------------------------
    # Pivots solved by work/refit_solve3.py so that the part the button selects
    # lands at camera (0, -0.2, 1.45) - exactly where m4a1/ak47/hk416d put the
    # gun in their refit_view.  Rotations are the official ones; only rotation
    # decides the orientation, the pivot only decides which part fills the
    # frame.  The grip/laser views are new bones: without them TaCZ falls back
    # to refit_view for those attachment types.
    ('refit_view', 'views', [23.3, 12.17, -0.36], [0, 90, 0]),
    ('refit_muzzle_view', 'views', [20.09, 15.2, -3.66], [0, 120, 0]),
    ('refit_stock_view', 'views', [23.2, 15.2, 7.97], [0, 90, 0]),
    ('refit_scope_view', 'views', [17.77, 17.56, -15.65], [0, 50, 0]),
    ('refit_extended_mag_view', 'views', [17.17, 26.88, -1.42], [0, 90, 35]),
    ('refit_grip_view', 'views', [23.2, 12.81, -9.86], [0, 90, 0]),
    ('refit_laser_view', 'views', [13.95, 20.05, 5.4], [15, 135, 0]),

    ('positioning', None, [0, 0, 0]),
    ('fixed', 'positioning', P3(345, 0, 15)),
    ('ground', 'positioning', P3(345, 0, -45)),
    ('thirdperson_hand', 'positioning', P3(345, 0, 0)),
]


def srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


# Hand-tuned sRGB palette.  The Principled base colours are physically dark
# (0.01-0.04 linear) and only read as mid grey because the studio rig blasts
# them with area lights; sampling them straight would ship a nearly black gun.
# The ordering follows the material set, the values follow the palette that the
# previous ThermalIQ pack proved readable in game.
PALETTE_SRGB = {
    'M_Black':    (52, 52, 56),
    'M_Dark':     (24, 24, 26),
    'M_Glass':    (26, 38, 58),
    'M_Gray':     (96, 98, 96),
    'M_Gray2':    (78, 80, 78),
    'M_Gray3':    (122, 124, 128),   # the bolt: must read through the port
    'M_Gray4':    (84, 86, 84),
    'M_Grip':     (34, 34, 36),
    'M_Mag':      (104, 104, 106),
    'M_Optic':    (42, 44, 50),
    'M_Polymer':  (44, 44, 48),
    'M_Rubber':   (34, 34, 36),
    'M_Shroud':   (38, 38, 40),
    'M_Steel':    (150, 152, 156),
}


def base_color(mat):
    if mat is not None and mat.name in PALETTE_SRGB:
        return PALETTE_SRGB[mat.name]
    return (128, 128, 128)


def _geometric_normal(corners, slot):
    """Face normal implied by the winding, in TaCZ space.

    Newell's method rather than a 3-point cross: on slivers (the boolean solver
    leaves thousands of them) the first three corners are nearly collinear and
    the cross product points anywhere, which made the winding test flip the
    wrong way.  Newell integrates over the whole polygon and stays sane.
    """
    pts = []
    seen = set()
    for c in corners:
        if c[0] in seen:      # a triangle repeats its first corner as the 4th
            continue
        seen.add(c[0])
        pts.append(Vector(slot['pos_arr'][c[0]]))
    if len(pts) < 3:
        return None
    n = Vector((0.0, 0.0, 0.0))
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        n.x += (p.y - q.y) * (p.z + q.z)
        n.y += (p.z - q.z) * (p.x + q.x)
        n.z += (p.x - q.x) * (p.y + q.y)
    return n if n.length > 1e-4 else None     # ~0.05 mm^2 of face area


def _stored_normal(corners, slot):
    """Mean of the corner normals.  On smooth faces the four corners carry
    slightly different normals, so testing against corner 0 alone misjudges the
    quad; the mean is what the face is actually meant to look like."""
    n = Vector((0.0, 0.0, 0.0))
    seen = set()
    for c in corners:
        if c[0] in seen:      # a triangle repeats its first corner as the 4th
            continue
        seen.add(c[0])
        n += Vector(slot['nrm_arr'][c[1]])
    return n


def emit(corners, slot, slivers, obname):
    """Append one polygon (triangle or quad) with its winding matched to the
    stored normals.  Dropped if it has no usable area in TaCZ space."""
    g = _geometric_normal(corners, slot)
    if g is None:
        slivers[obname] = slivers.get(obname, 0) + 1
        return
    if g.dot(_stored_normal(corners, slot)) < 0:
        corners = corners[::-1]
    if len(corners) == 3:
        corners = corners + [corners[0]]
        slot['tri'] += 1
    elif len(corners) == 4:
        slot['tri'] += 2
    else:
        return
    slot['polys'].append(corners)


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    # Both magazines live in the scene and the unused one is hidden.  A hidden
    # object is not evaluated, so to_mesh() would hand back the un-evaluated
    # base mesh; unhide everything first and let the depsgraph catch up.
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            ob.hide_render = False
            ob.hide_viewport = False
            try:
                ob.hide_set(False)
            except RuntimeError:
                pass
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    # ---- palette ------------------------------------------------------
    mats = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.name.startswith(SKIP):
            continue
        for s in ob.material_slots:
            if s.material and s.material.name not in [m.name for m in mats]:
                mats.append(s.material)
    mats.sort(key=lambda m: m.name)
    mat_idx = {m.name: i for i, m in enumerate(mats)}
    palette = [{'name': m.name, 'rgb': list(base_color(m))} for m in mats]
    print('PALETTE', [(p['name'], p['rgb']) for p in palette])

    # ---- gather -------------------------------------------------------
    meshes = {}          # bone -> dict of arrays
    for name, _, *_rest in BONES:
        meshes[name] = {'pos': {}, 'pos_arr': [], 'nrm': {}, 'nrm_arr': [],
                        'polys': [], 'tri': 0}

    stats = {}
    slivers = {}
    for ob in sorted(bpy.data.objects, key=lambda o: o.name):
        if ob.type != 'MESH' or ob.name.startswith(SKIP):
            continue
        bone = BONE_OF.get(ob.name, 'gun')
        slot = meshes[bone]
        eo = ob.evaluated_get(dg)
        me = eo.to_mesh()
        mw = ob.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        cn = me.corner_normals
        me.calc_loop_triangles()
        tri_of_poly = {}
        for lt in me.loop_triangles:
            tri_of_poly.setdefault(lt.polygon_index, []).append(tuple(lt.loops))
        slotmats = [s.material.name if s.material else None
                    for s in ob.material_slots]
        for poly in me.polygons:
            # Drop slivers.  The EXACT booleans on the muzzle brake and the
            # fire-control parts leave thousands of faces under 0.01 mm^2;
            # they are invisible at any resolution, they confuse the winding
            # test, and TML rebuilds normals from the winding (a degenerate
            # triangle can hand it a NaN).  1e-8 m^2 == 0.01 mm^2.
            if poly.area < 1e-8:
                slivers[ob.name] = slivers.get(ob.name, 0) + 1
                continue
            mi = poly.material_index
            mname = slotmats[mi] if mi < len(slotmats) else None
            uvi = mat_idx.get(mname, 0)
            corners = []
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                co = mw @ me.vertices[vi].co
                p = T(co)
                n = TN((nmat @ Vector(cn[li].vector)).normalized())
                pk = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
                nk = (round(n[0], 3), round(n[1], 3), round(n[2], 3))
                pi = slot['pos'].get(pk)
                if pi is None:
                    pi = len(slot['pos_arr'])
                    slot['pos'][pk] = pi
                    slot['pos_arr'].append(pk)
                ni = slot['nrm'].get(nk)
                if ni is None:
                    ni = len(slot['nrm_arr'])
                    slot['nrm'][nk] = ni
                    slot['nrm_arr'].append(nk)
                corners.append([pi, ni, uvi])
            # The Y mirror reverses handedness, so the corner order has to be
            # flipped to keep the winding outward.  Do it per polygon instead of
            # blanket-reversing: TML ignores the normals array (FORCE_FLAT_SHADING
            # rebuilds them from the winding) so the winding *is* the shading
            # normal.  Comparing the geometric normal against Blender's stored
            # normal keeps the two in agreement even on the faces where the
            # boolean solver left an inverted loop.
            if len(corners) > 4:
                # Fan triangulating an n-gon from corner 0 is wrong on concave
                # polygons and leaves slivers on the rounded ones (a sliver's
                # own winding implies a random normal).  Ask Blender for its
                # tessellation instead and emit each triangle on its own.
                lut = dict(zip(poly.loop_indices, corners))
                for lt in tri_of_poly.get(poly.index, ()):
                    tri = [lut[lt[0]], lut[lt[1]], lut[lt[2]]]
                    emit(tri, slot, slivers, ob.name)
                continue
            emit(corners, slot, slivers, ob.name)
        npoly = len(me.polygons)
        eo.to_mesh_clear()
        stats.setdefault(bone, []).append((ob.name, npoly))

    # ---- assemble -----------------------------------------------------
    # Bones that ship the same geometry as another bone (extra magazine
    # levels).  Copying the assembled poly_mesh is both cheaper and safer
    # than re-emitting the same objects three times.
    CLONE = {'mag_extended_2': 'mag_extended_1',
             'mag_extended_3': 'mag_extended_1'}
    bones_out = []
    report = []
    for name, parent, pivot, *rest in BONES:
        b = {'name': name, 'pivot': pivot}
        if parent:
            b['parent'] = parent
        if rest and rest[0] is not None:
            # Rest pose rotation.  The animation format overrides rotation per
            # channel, so bones that never get animated (the refit_* views)
            # keep this value at runtime.
            b['rotation'] = list(rest[0])
        slot = meshes[name]
        if not slot['polys'] and name in CLONE:
            slot = meshes[CLONE[name]]
        if slot['polys']:
            pos = [None] * len(slot['pos'])
            for k, i in slot['pos'].items():
                pos[i] = [k[0], k[1], k[2]]
            nrm = [None] * len(slot['nrm'])
            for k, i in slot['nrm'].items():
                nrm[i] = [k[0], k[1], k[2]]
            b['poly_mesh'] = {
                'normalized_uvs': True,
                'positions': pos,
                'normals': nrm,
                # Stripe atlas: material i owns a full-height 32px column of a
                # 512x512 texture, so u = (2i+1)/32 and v is irrelevant.  TML
                # negates V (FLIP_UV_V=1) and the sampler may clamp, so a
                # vertically uniform column keeps the colour correct either way.
                'uvs': [[(2 * i + 1) / 32.0, 0.5] for i in range(len(mats))],
                'polys': slot['polys'],
            }
            xs = [p[0] for p in pos]
            ys = [p[1] for p in pos]
            zs = [p[2] for p in pos]
            report.append('%-14s verts %6d  norm %6d  polys %6d  tris %6d  '
                          'x %7.2f..%7.2f  y %7.2f..%7.2f  z %7.2f..%7.2f'
                          % (name, len(pos), len(nrm), len(slot['polys']),
                             slot['tri'], min(xs), max(xs), min(ys), max(ys),
                             min(zs), max(zs)))
        else:
            report.append('%-14s (empty)' % name)
        bones_out.append(b)

    geo = {
        'format_version': '1.12.0',
        'minecraft:geometry': [{
            'description': {
                'identifier': 'geometry.rifle3',
                'texture_width': 512,
                'texture_height': 512,
                'visible_bounds_width': 6,
                'visible_bounds_height': 4,
                'visible_bounds_offset': [0, 1, 0],
            },
            'bones': bones_out,
        }],
    }
    # ---- self audit ---------------------------------------------------
    bad = degen = 0
    samples = []
    for name, parent, pivot, *rest in BONES:
        slot = meshes[name]
        if not slot['polys']:
            continue
        for poly in slot['polys']:
            g = _geometric_normal(poly, slot)
            if g is None:
                degen += 1
                continue
            s = _stored_normal(poly, slot)
            if g.dot(s) < 0:
                bad += 1
                if len(samples) < 4:
                    samples.append((name, [round(v, 2) for v in g],
                                    [round(v, 2) for v in s]))
    print('SLIVERS', sum(slivers.values()), sorted(slivers.items(),
                                                    key=lambda kv: -kv[1])[:6])
    print('AUDIT bad %d degen %d of %d'
          % (bad, degen, sum(len(m['polys']) for m in meshes.values())))
    for s in samples:
        print('  SAMPLE', s)

    with open(os.path.join(OUT, 'geo.json'), 'w', encoding='utf-8') as f:
        json.dump(geo, f, separators=(',', ':'))
    with open(os.path.join(OUT, 'palette.json'), 'w', encoding='utf-8') as f:
        json.dump(palette, f, indent=1)

    total_tris = sum(m['tri'] for m in meshes.values())
    lines = ['total tris %d' % total_tris, ''] + report
    for bone in sorted(stats):
        lines.append('%s <- %s' % (bone, ', '.join('%s(%d)' % t for t in stats[bone])))
    txt = '\n'.join(lines)
    with open(os.path.join(OUT, 'report.txt'), 'w', encoding='utf-8') as f:
        f.write(txt + '\n')
    print(txt)
    print('geo bytes', os.path.getsize(os.path.join(OUT, 'geo.json')))


if __name__ == '__main__':
    main()
