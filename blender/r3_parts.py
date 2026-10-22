"""r3_parts.py — weapon parts. Millimetres.
X = length (muzzle 0 -> butt 690), Z = up (bore axis 0), Y = lateral (0 = centre plane).
Every profile below is traced from the side-view silhouette of the reference sheet
(scale anchored on the 10 mm Picatinny pitch)."""

import bpy, bmesh, math
from bpy import context as C
from mathutils import Vector, Matrix
from r3_lib import (Part, fillet, arc, bez, S, TAU, boolop, join, apply_all, coll,
                    loop_ring, rounded_loop, offset_closed)

# =============================================================== master dims
LEN = 690.0

# handguard
HG_X0, HG_X1 = 64.0, 250.0
HG_W = 50.4
HG_ZT = 35.5
HG_ZB = -45.0

# rail geometry (M1913 look, 10 mm pitch)
RAIL_W = 21.2
RAIL_BASE_H = 5.9
RAIL_TOOTH_H = 3.2
RAIL_TOP = 44.6            # crown of the handguard / receiver rail
REAR_RAIL_TOP = 52.2       # crown of the raised rear rail

UR_X0, UR_X1 = 250.0, 478.0
UR_W = 46.4
UR_ZT = 35.5

PLATE_P = 1.6             # how far the gray magwell plate stands proud of the receiver
ST_X0 = 486.0
MAG_TOP_Z = -58.0
MAG_BOT_Z = -182.0   # traced outline bottom is -181.6; stay inside it


# ================================================================= helpers
def picatinny(part, x0, x1, z_base, w=RAIL_W, base_h=RAIL_BASE_H,
              tooth_h=RAIL_TOOTH_H, pitch=11.37, tooth_w=7.1, edge=1.6,
              base_cham=1.1, down=False, first=None):
    """Picatinny-style rail.

    NOTE: pitch and tooth width are measured FROM THIS SHEET (11.37 mm pitch,
    7.1 mm teeth), not the MIL-STD 10 mm value - the reference is AI-generated
    and its tooth pitch is non-standard. Matching the sheet matters more than
    matching the real standard, because the whole silhouette comparison is
    against this sheet.
    """
    hw = w * 0.5
    s = -1.0 if down else 1.0
    zb, zt = z_base, z_base + s * base_h
    c = base_cham
    part.prism([(-hw + c, zb), (hw - c, zb), (hw, zb + s * c), (hw, zt - s * c),
                (hw - c, zt), (-hw + c, zt), (-hw, zt - s * c), (-hw, zb + s * c)],
               'X', x0, x1)
    h = tooth_h
    a = (x0 + edge) if first is None else first
    while a + tooth_w <= x1 - edge + 0.01:
        # `first` may sit BEFORE x0 when the phase is inherited from an earlier
        # run of the same rail (the sheet's handguard teeth are phased off a
        # tooth at 69.6 that is hidden under the front sight).  Clamp the first
        # tooth's start so nothing floats in front of the rail's own base.
        aa = max(a, x0)
        if aa < a + tooth_w - 0.6:
            part.prism([(-hw * 0.87, zt + s * 0.02), (-hw * 0.79, zt + s * h * 0.5),
                        (-hw * 0.72, zt + s * h), (hw * 0.72, zt + s * h),
                        (hw * 0.79, zt + s * h * 0.5), (hw * 0.87, zt + s * 0.02)],
                       'X', aa, a + tooth_w)
        a += pitch


def R(prof, dz=0.0, dx=0.0):
    return [(x + dx, z + dz) for x, z in prof]


# ============================================================ 1 muzzle brake
def build_muzzle(mat):
    """Multi-stage cylindrical flash hider.

    The sheet's device is a CONSTANT-DIAMETER cylinder whose detail is cut
    INTO it: a few shallow ring grooves plus four rows of short slots. Two
    things had to be fixed here. (1) The first attempt used lens-shaped
    cutter prisms with duplicate endpoints at radius zero; the degenerate
    ends broke the boolean and left inverted slivers that rendered as
    STUBS sticking out of the barrel. Rectangular through-cutters are used
    instead - a box cutter on a lathe body is reliable, a self-touching
    polygon is not. (2) The grooves were in the wrong places: the sheet puts
    them at x = 10.5 and 20.5 behind the slots and at 50.6 / 54.0 in front
    of them, not bunched at both ends.
    """
    p = Part('MuzzleBrake', mat)
    R = 20.4
    BORE_R = 6.9
    # The device was judged too short on the assembled gun, so the whole nose
    # and body are shifted forward by XF: the collar end stays keyed to the
    # barrel at x=57.4 and only the free end grows.  Everything downstream
    # (bore cutter, dark bore tube, slot rows) is expressed off XF so the
    # three can never drift apart again.
    XF = -14.0
    REAR = 57.4
    GROOVES = [(XF + 10.5, 1.0, 2.8), (XF + 20.5, 1.0, 3.0),
               (50.6, 1.0, 3.0), (54.0, 0.8, 2.2)]
    # A rounded nose cone.  The crown itself is cut by the bore later, so the
    # profile only has to reach the bore radius, not close to a point - ending
    # at radius 0 made the lathe spin a needle tip inside the bore cutter and
    # left a ragged cone visible down the muzzle.
    prof = [(XF, BORE_R + 0.2), (XF + 1.2, BORE_R + 1.6),
            (XF + 2.6, 11.0), (XF + 4.4, 16.6), (XF + 6.4, 20.2)]
    for (xg, hw, dp) in GROOVES:
        prof += [(xg - hw - 0.6, R), (xg - hw, R - dp), (xg + hw, R - dp),
                 (xg + hw + 0.6, R)]
    prof += [(REAR - 0.8, R), (REAR, 18.2), (REAR, 0.0)]
    p.lathe(prof, seg=72)
    ob = p.build(smooth=True, angle=38, coll_name='Geo')

    # ---- BORE through the crown ---------------------------------------
    # The lathe profile closes at radius 0, so the device came out as a
    # SOLID turned slug: invisible from the side, glaringly wrong the moment
    # anyone looks down the muzzle. Cut a real bore through the nose and put
    # a dark tube behind it, or the hole just shows the steel inside the
    # brake and still reads solid.
    cb = Part('c', None)
    cb.cyl((XF - 10.0, 0.0, 0.0), (92.0, 0.0, 0.0), BORE_R, seg=56)
    boolop(ob, cb.build(smooth=False))
    # The bore used to run the whole 252 mm to the receiver as ONE object.
    # That is fine on an assembled gun but wrong the moment the parts are
    # separated: the muzzle comes off trailing a 200 mm tube.  It now stops
    # just past the crown (x=58) and the barrel carries its own bore.
    bore = Part('MuzzleBore', bpy.data.materials.get('M_Dark') or mat)
    bore.cyl((XF + 5.0, 0.0, 0.0), (58.0, 0.0, 0.0), BORE_R - 0.35, seg=48)
    bore.build(smooth=True, angle=40, coll_name='Geo')

    # four longitudinal rows of short slots, staggered row to row
    # four rows of slots spread over the extra length instead of three
    SLOT_X = [(9.5, 16.5), (18.5, 25.5), (27.5, 34.5), (36.5, 43.5)]
    for row in range(4):
        ang = 45.0 + 90.0 * row
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        for j, (x0, x1) in enumerate(SLOT_X):
            if row % 2 == 1 and j == 0:
                continue                      # break up the obvious pattern
            c = Part('c', None)
            # rectangular through-slot, 5 mm tall, cut clean through the wall
            c.box(x0, x1, -34.0, 34.0, -2.6, 2.6)
            for v in c.bm.verts:
                y, z = v.co.y, v.co.z
                v.co.y = y * ca - z * sa
                v.co.z = y * sa + z * ca
            boolop(ob, c.build(smooth=False))

    # rounded slot ends: a shallow lathe-free fillet would need real geometry,
    # so instead chamfer the cut rims with a light bevel pass
    md = ob.modifiers.new('bv', 'BEVEL')
    md.width = 0.55
    md.segments = 2
    md.limit_method = 'ANGLE'
    md.angle_limit = math.radians(50)
    if hasattr(md, 'use_clamp_overlap'):
        md.use_clamp_overlap = True
    C.view_layer.objects.active = ob
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier=md.name)
    return ob


# ================================================================ 2 barrel
def build_barrel(mat):
    p = Part('Barrel', mat)
    p.cyl((54, 0, 0), (66, 0, 0), 15.2, seg=44)    # barrel-nut shoulder
    p.cyl((66, 0, 0), (70, 0, 0), 13.8, seg=40)
    p.cyl((70, 0, 0), (252, 0, 0), 10.5, seg=36)
    ob = p.build(smooth=True, angle=45, coll_name='Geo')
    # dark bore, so the barrel still reads as a tube once it is out of the
    # handguard in the exploded view
    bb = Part('BarrelBore', bpy.data.materials.get('M_Dark') or mat)
    bb.cyl((54.0, 0.0, 0.0), (252.0, 0.0, 0.0), 6.55, seg=48)
    bb.build(smooth=True, angle=40, coll_name='Geo')
    return ob


# ============================================================= 3 handguard
def build_handguard(mat_gray, mat_black):
    hw = HG_W * 0.5
    mat_core = bpy.data.materials.get('M_Dark') or mat_black

    # SECTION SHAPE, traced off the sheet. The handguard is NOT a straight
    # extrusion: the reference tapers at both ends.
    #   x=64  outer: top 34.9, bottom -36.3 (that is the barrel-nut collar)
    #   x=80  top 51.7, bottom -57.8      <- widest point, just behind the collar
    #   x=100 top 55.0, bottom -50.3
    #   x=240 top 41.5, bottom -51.2      <- has shrunk 13.5 mm at the top
    # so the top line falls 13.5 mm over 160 mm and the bottom drops 6.6 mm.
    # The front collar (64..80) flares OUT, which is what gives the
    # characteristic double-bevel nose the flat-sided box was missing.
    #
    # (z_top, z_bot) pairs, linearly interpolated along the length:
    # LEVEL BODY. The handguard is a straight tube: its top edge sits at the
    # rail base and its bottom edge is flat, both dead horizontal from x=84 all
    # the way to the receiver. Only the front barrel-nut collar is smaller.
    #
    # The previous version tapered the top from 55.0 down to 41.5, which turned
    # the whole handguard into a wedge - that was a mis-read: the tall 54-pixel
    # column at x=88..130 is the FOLDED FRONT SIGHT standing on the rail, not
    # the handguard roof. Reading it as the roof is what produced the sloping
    # silhouette the user objected to.
    KEYS = [(64.0, 34.6, -35.6), (74.0, 34.9, -36.6), (79.0, 35.3, -42.6),
            (84.0, 35.5, -45.0), (250.0, 35.5, -45.0)]

    def sect(x):
        for i in range(len(KEYS) - 1):
            x0, t0, b0 = KEYS[i]
            x1, t1, b1 = KEYS[i + 1]
            if x0 <= x <= x1:
                f = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
                return (t0 + (t1 - t0) * f, b0 + (b1 - b0) * f)
        return (KEYS[-1][1], KEYS[-1][2])

    # TRUE OCTAGONAL section, per the user's sketch and the front view.
    #
    # The previous version used a single chamfer of only 11 mm cut at 45 deg.
    # On an 80 mm tall section that put 86% of the height on two vertical
    # flanks, so the front view read as a rectangle with its corners filed
    # off - exactly what the user objected to. The reference (and the sketch)
    # is an octagon with LONG inward-sloping faces and a SHORT flat flank:
    #
    #      +---------+        narrow top face
    #     /           \       top chamfer slopes in
    #    |             |      middle bulges out to full width
    #     \           /       bottom chamfer slopes in
    #      +---------+        narrow bottom face
    #
    # The two chamfers are independent numbers so the angle can stay near
    # 60 deg instead of forced-45: horizontal CH and vertical CV.
    def chamfers(zt, zb):
        h = zt - zb
        cv = min(h * 0.26, 21.0)          # vertical run of each chamfer
        ch = min(hw * 0.46, cv * 0.60)    # horizontal run of each chamfer
        return cv, ch

    def ring_at(x, grow=0.0):
        zt, zb = sect(x)
        cv, ch = chamfers(zt, zb)
        cv += grow
        wi = hw + grow
        # widest plane runs from (zb+cv) to (zt-cv); top and bottom faces are
        # narrower by ch on each side, which is what makes the middle bulge.
        return [(wi, zt - cv), (wi, zb + cv), (wi - ch, zb), (-wi + ch, zb),
                (-wi, zb + cv), (-wi, zt - cv), (-wi + ch, zt), (wi - ch, zt)]

    XS = [64.0, 68.0, 72.0, 76.0, 80.0, 84.0, 88.0, 100.0, 130.0, 165.0,
          205.0, 240.0, 248.0, 250.0]
    rings = [[(x, y, z) for (y, z) in ring_at(x)] for x in XS]

    mat_g = bpy.data.materials.get('M_Gray2') or mat_gray
    p = Part('HG_body', mat_g)
    p.loft(rings, cap_start=True, cap_end=True)
    body = p.build(smooth=True, angle=34, coll_name='Geo')

    # hollow the shell so the vents read as voids, then cut them.
    dk = Part('HG_core', mat_core)
    inr = []
    for x in XS:
        zt, zb = sect(x)
        cv, ch = chamfers(zt, zb)
        # same octagon, inset by WALL on every face so the shell has a
        # constant wall thickness - an inset that ignores the chamfer would
        # punch through the sloping faces near the ends.
        # CORE MUST SIT STRICTLY INSIDE. The old version kept the outer
        # zt/zb and only shrank the chamfer length (cv2 = cv - 3.9). That
        # moves the chamfer's START DOWN to zt-cv2, so over the band
        # z 22..30 the core's vertical flank (hw2 = 21.8) ended up PROUD of
        # the body's sloping chamfer (21.7 at z=28) and rendered as a dark
        # stripe across the top of the handguard. Shrink the OUTLINE in z as
        # well as in y and keep the chamfer lengths equal: the core is then
        # inset by a constant 2*WALL along the sloping faces.
        WALL = 3.4
        hw2 = hw - WALL
        zt2 = zt - WALL
        zb2 = zb + WALL
        cv2 = max(1.0, cv)
        ch2 = max(1.0, ch - WALL * 0.8)
        inr.append([(x, y, z) for (y, z) in [
            (hw2, zt2 - cv2), (hw2, zb2 + cv2), (hw2 - ch2, zb2), (-hw2 + ch2, zb2),
            (-hw2, zb2 + cv2), (-hw2, zt2 - cv2), (-hw2 + ch2, zt2), (hw2 - ch2, zt2)]])
    dk.loft(inr, cap_start=True, cap_end=True)
    core = dk.build(smooth=True, angle=34, coll_name='Geo')

    # ---- black lower shroud -------------------------------------------
    # THE THIRD BAND. The sheet's handguard is not one grey shell: it is a
    # bright grey upper shell, a dark recessed channel with the rib ladder,
    # and a NEAR-BLACK lower shroud carrying the long slot (measured greys
    # 142 / 50 / 30). The model was a single mid-grey tube, which is exactly
    # why it read flat and "ugly" next to the reference.
    # Built as its own lofted shell, grown 0.5 mm so it covers the grey body
    # underneath rather than z-fighting with it.
    # Vertical tonal structure MEASURED off the sheet (mean grey through the
    # flank, x 210..240):  bright shell z +34..+13 (grey ~155), dark recessed
    # field z +12..-32 (~45-50 with the rib ladder), near-black shroud
    # z -28..-45 (~13). The model was one mid-grey tube, which is why it read
    # flat. The shroud's TOP EDGE must stay well above the section's chamfer
    # start (zb+cv), or the closed outline doubles back on itself and the loft
    # comes out empty - that was the first failure here.
    Z_SH = -27.0

    def low_ring(x, grow=0.5):
        zt, zb = sect(x)
        cv, ch = chamfers(zt, zb)
        wi = hw + grow
        cc = min(ch + grow, (zb + cv - Z_SH) * 0.5)
        return [(wi, Z_SH), (wi, zb + cv + grow), (wi - cc, zb - grow),
                (-wi + cc, zb - grow), (-wi, zb + cv + grow), (-wi, Z_SH)]

    mat_shroud = bpy.data.materials.get('M_Shroud') or mat_black
    sht = Part('HG_shroud', mat_shroud)
    sht.loft([[ (x, y, z) for (y, z) in low_ring(x)] for x in XS],
             cap_start=True, cap_end=True)
    shroud = sht.build(smooth=True, angle=34, coll_name='Geo')
    # Slot as a SUNKEN panel on the shroud (no boolean): a shallow inset box
    # painted with the darkest material reads as an opening without leaving
    # boolean remnants behind.
    slt = Part('HG_shroud_slot', bpy.data.materials.get('M_Dark') or mat_black)
    for sg in (-1, 1):
        slt.prism(rounded_loop(92.0, 240.0, -39.0, -33.6, 2.6, seg=10),
                  'Y', sg * (hw + 0.45), sg * (hw + 0.62))
    slt.build(smooth=False, angle=26, coll_name='Geo')

    # ---- top rail
    # The rail follows the handguard's tapered crown: it is NOT horizontal.
    # Tooth phase is set so the first tooth lands at x=75.4, matching the sheet.
    r = Part('HG_rail', mat_black)
    # The rail does NOT run the full handguard: the sheet is bare handguard
    # crown from x=64 to x=75 and rail from 75 onward (row z=+40 is empty
    # before x=75 and solid after).  Starting at HG_X0 put two teeth on the
    # nose where the sheet has smooth anodised shell.
    # Tooth phase solved from the sheet's visible teeth (137.9, 149.1, 160.7,
    # 171.5, 182.6, 193.8, 205.0, 216.6, 228.3, 240.4 -> pitch 11.39) which
    # extrapolates back to a hidden tooth at 69.6.  Teeth are 8.0 wide there,
    # not 7.1; the narrower value left gaps twice as wide as the reference.
    picatinny(r, 75.0, HG_X1, HG_ZT - 0.2, pitch=11.39, tooth_w=8.0, first=69.6)
    rail = r.build(smooth=True, angle=34, coll_name='Geo')

    # ---- bottom rail, likewise following the tapered underside
    b = Part('HG_bottom', mat_black)
    picatinny(b, 72.0, HG_X1 - 2.0, HG_ZB + 0.2, down=True)
    bot = b.build(smooth=True, angle=34, coll_name='Geo')

    # ---- front collar + the two round barrel-nut bosses
    # The collar is built from the same section function so it flares with the
    # barrel nut instead of forming a flat box face.
    f = Part('HG_front', mat_black)
    zt64, zb64 = sect(64.0)
    zt80, zb80 = sect(80.0)
    # the collar is the same octagon grown by 1.4 mm, so its chamfers continue
    # the shell's instead of cutting across them
    cv64, ch64 = chamfers(zt64, zb64)
    g = 1.4
    f.prism([(hw + g, zt64 - cv64 - g), (hw + g, zb64 + cv64 + g),
             (hw - ch64 + g, zb64 - g), (-hw + ch64 - g, zb64 - g),
             (-hw - g, zb64 + cv64 + g), (-hw - g, zt64 - cv64 - g),
             (-hw + ch64 - g, zt64 + g), (hw - ch64 + g, zt64 + g)],
            'X', HG_X0, HG_X0 + 8.0)
    # USER-FLAGGED FIX (m05171): this used to be two rods spanning the full
    # 61 mm width at z=+27 and z=-30, which read from any three-quarter view as
    # two fat cylinders bolted across the handguard - and a through-rod cannot
    # pass the bore axis anyway. They were a modelling error, and the sheet has
    # no cross-bolt there, so the collar is now plain.
    front = f.build(smooth=True, angle=34, coll_name='Geo')

    # ---- flank treatment
    # MEASURED off the sheet (work/hgscan.py + work/g_rib.png), not invented.
    # The flank is a grey anodised shell carrying ONE dark recessed band that
    # runs almost the whole length, and the band's identity is a raised RIB
    # LADDER over its rear two thirds plus a bolted plate at its front.
    #   rib ladder  : 11 ribs, x 144..256, pitch 10.3, rib 5.6 wide, z -2..-17
    #   front plate : x 70..142 with two socket bolts at x 78 and 118
    #   top vents   : two OVAL through-slots x 91..133 and 155..208, z 22..28
    # The previous single flat plate plus two bolts read as one big decal;
    # the ladder is what gives the flank its scale.
    s = Part('HG_side', mat_black)          # recessed band + bolts + slot
    mat_g3 = bpy.data.materials.get('M_Gray3') or mat_black
    g2 = Part('HG_sideplate', mat_g3)       # raised ribs (mid-dark) + front pad
    for sign in (-1, 1):
        ya = sign * (hw - 0.20)
        yb = sign * (hw + 1.00)
        ylo, yhi = min(ya, yb), max(ya, yb)

        # the recessed field, rounded at both ends.
        # HEIGHT IS MEASURED: a vertical grey scan through the flank
        # (x 210..240) gives bright shell ~155 down to z=+13, dark field ~50
        # from z=+12 all the way to z=-33, then near-black shroud ~13. This
        # band previously stopped at z=+5 / -19, so bright grey leaked out
        # above and below it and the flank read as one light slab.
        ZBAND_T, ZBAND_B = 12.5, -33.0
        band = rounded_loop(70.0, 258.0, ZBAND_B, ZBAND_T, 5.0, seg=5)
        s.prism(band, 'Y', ylo, yhi)

        # ---- raised rib ladder over the rear of the band
        # Each rib is a small trapezoid: narrower at the crest than at the
        # root, which is what makes it read as moulded rather than a stripe.
        # NOTE the material: the ribs are the BRIGHT element inside a near-black
        # recessed band, so they go on the grey part. Building them in the band's
        # own black made the ladder read as dark bumps on a light field, i.e.
        # exactly inverted from the sheet.
        x = 144.0
        while x + 5.6 <= 256.0:
            rib = [(x, -16.6), (x + 0.9, -1.4), (x + 4.7, -1.4), (x + 5.6, -16.6)]
            g2.prism(rib, 'Y', min(ylo, ylo + sign * 2.4), max(yhi, yhi + sign * 2.4))
            x += 10.3

        # ---- front bolted plate
        # The sheet's front fitting is a BLACK rounded plate standing just
        # proud of the grey shell with two socket bolts and a shallow finger
        # slot between them. It used to be built in grey, which made it render
        # as a bright rounded rectangle that is not in the reference at all.
        pad = rounded_loop(72.0, 142.0, -16.0, 3.0, 4.0, seg=8)
        s.prism(pad, 'Y', min(yhi, yhi + sign * 2.2), max(yhi, yhi + sign * 2.2))
        for xx in (78.0, 118.0):
            s.screw(xx, -2.0, sign * (hw + 3.6), r=2.6, depth=1.0)
        slot = rounded_loop(86.0, 112.0, -6.4, 1.2, 3.8, seg=6)
        s.prism(slot, 'Y', min(yhi, yhi + sign * 2.9), max(yhi, yhi + sign * 2.9))

    side = s.build(smooth=True, angle=34, bevel=0.6, coll_name='Geo')
    side_plate = g2.build(smooth=True, angle=34, bevel=0.7, coll_name='Geo')

    # ---- folding front sight, folded onto the rail
    # Folded front sight: a low, plain clamp block with a single shallow
    # protective rib. Deliberately minimal - the previous multi-wedge stack
    # (three prisms plus two screws piled up to z=64) read as clutter on the
    # silhouette and was the thing the user called ugly.
    # Folded front sight. In the sheet this is the ONLY thing standing above
    # the rail: a solid wedge whose front face rakes up from x=76 at z=44 to a
    # flat 54.5 crown between x=86 and x=120, then rakes back down to the rail
    # at x=136. Measured from the row scan of ref_side.png, not invented.
    fs = Part('BUIS_F', mat_black)
    # The sight is a BLOCK sitting on the rail base (z=41.2), not a wedge
    # floating at 43.0.  Measured from the sheet: at z=+42 the reference is
    # solid from x=75.0 to 134.6, i.e. the sight's own footprint covers the
    # rail teeth there.  With the base at 43.0 the tooth tips poked out around
    # the sight and it read as a broken crown.
    fs.prism([(75.0, 41.0), (87.0, 54.5), (120.0, 54.5), (136.0, 41.0)],
             'Y', -11.4, 11.4)
    # narrow raised spine on the crown + the clamp bolt
    fs.prism([(88.0, 53.6), (118.0, 53.6), (118.0, 55.4), (88.0, 55.4)],
             'Y', -8.0, 8.0)
    fs.screw(96.0, 48.4, 11.6, r=2.4, depth=0.9)
    fs.screw(118.0, 44.4, 11.6, r=1.9, depth=0.8)
    buisf = fs.build(smooth=True, angle=34, coll_name='Geo')

    # ---- QD sling socket
    # A QD socket is a shallow ring cut into the flank, not a rod pushed
    # through the shell (that showed as a third cylinder in three-quarter views).
    qd = Part('HG_qd', mat_black)
    qd.cyl((96.0, hw - 0.6, -30.0), (96.0, hw + 0.9, -30.0), 6.2, seg=22)
    qd.cyl((96.0, hw + 0.1, -30.0), (96.0, hw + 1.5, -30.0), 3.4, seg=18)
    qo = qd.build(smooth=True, angle=34, coll_name='Geo')

    # ---- cut-outs: triangular top vents and the long bottom slots.
    # The sheet's vents are wedge-shaped (tall at the front, tapering back), so
    # a plain box cutter would read wrong; these are real wedges.
    for sign in (-1, 1):
        # Top vents: STADIUM outlines. rounded_loop() with r = half the height
        # gives a true capsule, so the cut rim sweeps instead of cornering.
        for (xa, xb) in [(94.0, 148.0), (158.0, 226.0)]:
            cu = Part('c', None)
            vent = rounded_loop(xa, xb, 23.4, 29.6, 3.1, seg=10)
            cu.prism(vent, 'Y', sign * 10.0, sign * 40.0)
            boolop(body, cu.build(smooth=False))
        # Long bottom slot in the black lower shroud, also capsule-ended.
        # It must cut BOTH the grey body and the black shroud that covers it,
        # or the shroud seals the slot back up.
        slotpoly = rounded_loop(90.0, 242.0, -39.4, -33.2, 3.1, seg=10)
        slitpoly = rounded_loop(98.0, 236.0, -27.0, -23.6, 1.7, seg=8)
        for poly, ya, yb in ((slotpoly, 10.0, 40.0), (slitpoly, 13.0, 40.0)):
            # ONLY the grey body is cut.  Running the same cutter through the
            # closed shroud loft left a one-sided fin at y=-40 (the cutter's
            # own face) which showed up in the front elevation as a rod
            # hanging off the left flank.  The shroud is near-black anyway, so
            # the slot is represented there by a recessed panel instead.
            cu = Part('c', None)
            cu.prism(list(poly), 'Y', sign * ya, sign * yb)
            boolop(body, cu.build(smooth=False))
    return [body, shroud, rail, core, bot, side, side_plate, front, buisf, qo]


# ========================================================= 4 upper receiver
def build_upper(mat_black, mat_gray):
    hw = UR_W * 0.5
    prof = [
        (250.0, -12.6), (250.0, 28.0), (251.0, 35.5), (302.0, 35.5),
        (416.0, 35.5), (420.0, 36.6), (422.0, 41.2), (476.0, 41.2),
        (478.0, 38.0), (478.0, -12.6),
    ]
    p = Part('Upper', mat_black)
    p.prism(prof, 'Y', -hw, hw)
    # ---- horizontal machined shelf on each flank
    # Measured: the sheet carries a bright band at z +14..+19 the whole length
    # of the receiver (grey 130-150) over a dark body (40-55). A flat flank
    # cannot produce that, so the section steps out here and the chamfers do
    # the work under the key light.
    # NOTE the outline must be a SIMPLE closed loop. The first version
    # doubled back on itself at the ends (so the chamfers were traced twice),
    # and Part.prism triangulated the self-touch into a degenerate fan - the
    # shelf existed but rendered as nothing. A plain chamfered octagon works.
    # The sheet's band is a 5 mm machined chamfer catching light along the
    # receiver's top edge, not a decorative stripe: 8.7 mm wide and 0.9 mm
    # proud made it read as a painted racing stripe in the hero render.
    SHELF_P, SHELF_Z0, SHELF_Z1 = 0.55, 14.6, 20.4
    band = [(254.0, SHELF_Z0), (256.0, SHELF_Z1), (470.0, SHELF_Z1),
            (472.0, SHELF_Z0)]
    for sgn in (-1, 1):
        p.prism(band, 'Y', sgn * hw, sgn * (hw + SHELF_P))
    ob = p.build(smooth=True, angle=30, bevel=1.2, bevel_seg=2, coll_name='Geo')

    # the machined flat itself, in the lighter grey
    # NOTE: this shelf is a MACHINED CHAMFER, not a painted stripe. Using the
    # bright M_Gray here made a light bar run the whole receiver, which the
    # sheet does not have - it reads as the darker grey catching the key light.
    gb = Part('UR_band', bpy.data.materials.get('M_Gray4') or mat_gray)
    b2 = [(256.0, SHELF_Z1), (470.0, SHELF_Z1), (470.0, SHELF_Z0 + 0.2),
          (256.0, SHELF_Z0 + 0.2)]
    for sgn in (-1, 1):
        gb.prism(b2, 'Y', sgn * (hw + SHELF_P), sgn * (hw + SHELF_P + 0.45))
    bandob = gb.build(smooth=True, angle=34, coll_name='Geo')

    r = Part('UR_rail', mat_black)
    # The RECEIVER rail is a different, tighter rail than the handguard's:
    # the sheet's receiver teeth measure pitch 9.95 and 5.3 wide (standard
    # MIL-STD), while the handguard's are 11.39 / 8.0.  Using one pitch for
    # both made the receiver teeth drift half a tooth by x=400.
    picatinny(r, 252.0, 419.0, 35.5, pitch=9.95, tooth_w=5.3, first=251.8)
    rail = r.build(smooth=True, angle=34, coll_name='Geo')

    # raised rear platform + rail + folding rear sight
    q = Part('UR_rear', mat_black)
    q.prism([(420.0, 35.4), (422.0, 41.2), (476.0, 41.2), (478.0, 38.0),
             (478.0, 29.0), (420.0, 29.0)], 'Y', -hw + 1.2, hw - 1.2)
    picatinny(q, 424.0, 477.0, 41.2, pitch=9.95, tooth_w=5.3, first=421.0)
    rear = q.build(smooth=True, angle=34, coll_name='Geo')

    # ejection port, forward assist, case deflector, charging handle
    d = Part('UR_detail', mat_black)
    d.prism([(302.0, -7.0), (372.0, -7.0), (372.0, 12.0), (302.0, 12.0)],
            'Y', -hw - 0.6, -hw + 2.8)
    d.prism([(298.0, -8.4), (374.0, -8.4), (374.0, 13.4), (298.0, 13.4)],
            'Y', -hw - 1.4, -hw + 0.3)
    d.cyl((376.0, -hw + 5.5, 5.0), (394.0, -hw + 5.5, 5.0), 6.6, seg=20)
    d.cyl((392.0, -hw + 5.5, 5.0), (396.0, -hw + 5.5, 5.0), 4.4, seg=16)
    # Case deflector.  This used to be a flat parallelogram extruded 6.4 mm
    # outboard of the flank, which in the isolated BODY render read as a
    # tilted plate bolted onto the side of the receiver.  On the sheet it is
    # a small ROUNDED lump about 3 mm proud - the brass never needs a ramp
    # that size, and a flat plate catching the key light is the single most
    # obvious wrong shape on the whole flank.
    # It has to sit BELOW the machined shelf: reaching up to z=17 pushed it
    # through the light band and it read as a lump growing out of the chamfer.
    d.prism(rounded_loop(376.0, 395.0, -1.0, 12.0, 4.2, seg=6), 'Y',
            -hw - 2.6, -hw + 0.4)
    d.box(430.0, 474.0, -6.6, 6.6, 29.0, 34.4)
    # socket bolts on the rear boss, and a shallow recessed panel forward of
    # them - both are clear in the sheet and were entirely missing.
    for zz in (12.0, -5.0):
        d.screw(445.0, zz, -hw - 0.5, r=2.7, depth=1.0)
    # Long horizontal panel groove.  Was a 3 mm raised plate which rendered as
    # a plain light rectangle across the flank; the sheet only has a machined
    # line here, so it is cut as a shallow dark strip sitting just inside the
    # surface instead of a proud slab.
    d.prism([(352.0, 3.4), (424.0, 3.4), (424.0, 5.0), (352.0, 5.0)], 'Y',
            -hw - 0.22, -hw + 0.30)
    detail = d.build(smooth=True, angle=34, coll_name='Geo')
    return [ob, bandob, rail, rear, detail]


# ========================================================= 5 lower receiver
def build_lower(mat_black, mat_gray):
    hw = UR_W * 0.5
    # The receiver's bottom edge rides ABOVE the trigger opening; the guard is a
    # separate bracket below it. (Letting the receiver plate extend down here is
    # exactly the stray material the user spotted on both flanks.)
    prof = [
        (286.0, -12.6), (286.0, -30.0), (287.0, -50.0), (289.0, -58.0),
        (292.0, -61.0), (350.0, -62.4), (353.0, -61.0), (355.0, -52.0),
        (346.0, -46.0), (346.0, -36.0), (408.0, -36.0), (417.0, -44.0),
        (420.0, -33.0), (426.0, -27.0), (470.0, -27.0), (478.0, -31.0),
        (478.0, -12.6),
    ]
    p = Part('Lower', mat_black)
    p.prism(prof, 'Y', -hw, hw)
    lower = p.build(smooth=True, angle=30, bevel=1.2, bevel_seg=2, coll_name='Geo')

    # ---- gray magwell plate -------------------------------------------
    # THE signature shape of this rifle: one large diagonal two-tone panel
    # covering the lower receiver's flank from the magwell front all the way
    # back over the trigger housing.
    #
    # NOTE ON METHOD: the outline below is DESIGNED, not traced. The sheet is
    # AI-generated and its panel boundary has inconsistent kinks and a blobby
    # front corner; reproducing those would bake generation artifacts into the
    # model. What is matched is the gesture - a long flat top edge with a step
    # down at the magwell, a raked rear edge, and a diagonal bottom that
    # follows the magazine well - drawn with clean machined lines.
    # Kept deliberately regular: a clean machined outline with no pointed
    # corner. The earlier version raked its rear edge up to z=-2.5 and dropped
    # to a point at (326,-66), which read as a shield/pennant hanging off the
    # receiver - the "irregular white polygon" the user objected to.
    # Footprint measured off the sheet's grey casting (work/gscan2.py): the
    # plate's top edge sits at z=-8 from x 275 to 340, its front edge is at
    # x=272, and its bottom follows the magwell down to z=-60.  The earlier
    # 278..352 box was ~8 mm short at the front and 6 mm short at the top,
    # which is what made it look like a small decal instead of the casting.
    # Outline fitted to the sheet's grey casting row by row (work/gscan2.py
    # plus a grey-run scan over x 265..420).  The measured envelope:
    #   front edge   x 275 at z -14, raking BACK to x 313 at z -62
    #   rear edge    x 349 at z -17, stepping in to x 331 at z -30 and
    #                easing out to x 338 at the bottom
    #   top edge     rises from (273,-9) to the rear "beak" at (341,+1.5)
    # The previous box (278..352, top edge dead level) covered 20 mm too much
    # flank and read as a blank slab, which is what made it look wrong.
    # Top edge measured column by column off the sheet (topmost grey pixel):
    #   x 285..328  FLAT at z -8.4
    #   x 335 -3.7 | x 341.5 +1.4 | x 349 +0.9   <- the raised rear "beak"
    # An earlier version ran one straight line from the front corner up to the
    # beak, which filled a large grey wedge ABOVE the flat top - the single
    # biggest reason the plate read as a blank blob.
    gp = [
        (274.0, -5.0),
        (285.0, -8.4),
        (328.0, -8.4),      # flat top edge
        (335.0, -3.7),
        (341.5, 1.4),       # beak apex
        (349.5, 0.9),
        (349.0, -17.0),
        (331.0, -30.0),
        (335.0, -58.0),
        (338.0, -68.0),
        (312.0, -68.0),
        (295.0, -55.0),
        (287.0, -46.0),
        (277.0, -31.0),
        (274.0, -19.0),
    ]
    # Two-level machined surface: a chamfered rim standing proud with the field
    # inside it sunk back. Built additively (sunk field + raised ring) so no
    # boolean is involved.
    gpi = [
        (283.4, -16.5), (344.6, -16.5), (348.2, -20.6), (348.2, -42.2),
        (336.2, -56.4), (304.0, -56.4), (288.4, -37.4), (283.4, -24.0),
    ]
    # FLAT PANEL, not a framed one. The previous version built a raised rim
    # ring around a sunken field; on the sheet the plate is a FLAT casting with
    # a single chamfered edge, and the framed version read as a plastic picture
    # frame bolted to the side of the gun - the "odd white polygon" complaint.
    # One prism, one chamfer, and let the material do the two-tone work.
    # NARROW RAISED RIM + SUNK FIELD (a real 0.6 mm step, not a decal).
    # Reference grey inside the plate runs 116/123/127/139/176 (p10/50/75/90/97):
    # the 176 band is the polished chamfered BORDER, the 123 bulk is the
    # sandblasted FIELD. A single flat prism cannot produce that, which is why
    # the plate kept reading as a blank pale slab. The rim is deliberately thin
    # (3.2 mm) - a wide frame was rejected earlier as a "picture frame".
    gpi = offset_closed(gp, 1.0)
    FIELD_D = 0.35
    gf = Part('LR_panel_f', mat_gray)
    gr = Part('LR_panel_r', bpy.data.materials.get('M_Gray2') or mat_gray)
    for sgn in (1, -1):
        a_in = hw - 0.3
        a_out = hw + PLATE_P
        a_fld = a_out - FIELD_D
        if sgn > 0:
            gf.prism(gpi, 'Y', a_in, a_fld)
            gr.ring_prism(gp, gpi, 'Y', a_fld, a_out)
        else:
            gf.prism(gpi, 'Y', -a_fld, -a_in)
            gr.ring_prism(gp, gpi, 'Y', -a_out, -a_fld)
    fld = gf.build(smooth=False, angle=24, bevel=0.5, bevel_seg=2, coll_name='Geo')
    rim = gr.build(smooth=False, angle=24, bevel=0.5, bevel_seg=2, coll_name='Geo')
    panel = rim

    # forward extension: the lower's front section under the handguard rear.
    # Kept clear of the trigger-guard zone (x > 344) so it cannot poke out
    # into the guard opening.
    x = Part('LR_front', mat_black)
    x.prism([(248.0, -8.0), (286.0, -8.0), (286.0, -50.0), (281.0, -53.0),
             (262.0, -50.0), (248.0, -42.0)], 'Y', -hw + 1.0, hw - 1.0)
    front = x.build(smooth=True, angle=34, bevel=1.0, bevel_seg=2, coll_name='Geo')

    # gray accent plate on the forward section (matches the sheet's two-tone)
    ga = Part('LR_front_gray', mat_gray)
    gp2 = [(252.0, -13.0), (284.0, -13.0), (284.0, -30.0), (268.0, -36.0),
           (254.0, -34.0)]
    ga.prism(gp2, 'Y', hw - 0.3, hw + 1.8)
    ga.prism(gp2, 'Y', -hw - 1.8, -hw + 0.3)
    fgray = ga.build(smooth=True, angle=34, bevel=0.7, coll_name='Geo')

    # ---- Trigger guard ------------------------------------------------
    # Keeping the current bracket form (the sheet is AI-generated and its loop
    # is not self-consistent), but built as a real annulus so it has a true
    # hole instead of relying on a boolean. Cavity traced from the sheet.
    # Trigger-guard opening, measured from the sheet row by row.  The bright
    # cavity fits an ellipse almost exactly: centre (374.5, -50.0), semi-axes
    # 21.0 x 10.7 mm.  Scanning ref_side.png gives cavity top z=-40.0 at
    # x=368, bottom z=-60.5 at x=380, front x=353.7 at z=-51.5 and rear
    # x=395.5 at z=-50 -- an ellipse reproduces all four within 0.5 mm, and
    # it reads as the big flowing arc the sheet shows instead of the angular
    # 13-gon it replaced.
    # The opening reads as a heavy INTEGRAL bow, not a thin wire loop: in the
    # sheet the dark frame around the white hole is ~9-10 mm wide on every side
    # and as deep (in Y) as the receiver, and its top simply disappears into the
    # receiver underside.  An earlier version used a 4.8 mm wall on a y +/-9.5
    # ring, which rendered as a floating wire hoop - the single most visible
    # remaining defect in the side view.
    # ---- TRIGGER GUARD -------------------------------------------------
    # Read straight off the sheet's close-up (m08147): the bow is a FLAT PLATE
    # with a rounded-rectangle hole, not an ellipse ring.  Its front wall is a
    # fat member that merges into the magwell cheek, its floor is a straight
    # bar at z=-65.2, and its top is buried under the receiver at z=-36.  Two
    # earlier builds (a 13-point traced cavity, then a scaled ellipse) both
    # read as a floating donut because the ring was one uniform loop; a plate
    # with a hole gets the thick front / thin rear for free.
    # ring_prism needs both loops to have the SAME point count, so the outer
    # profile is built with the same helper as the hole.  The asymmetry that
    # matters (thick front wall, thin rear wall) comes from the hole being
    # inset off-centre inside it: 13 mm at the front, 6 mm at the rear.
    # Hole measured off the sheet row-by-row: apex z=-40.5, floor z=-61, widest
    # 26 mm across at z=-50, top corners much rounder than the bottom ones.  The
    # OUTER loop runs 3 mm past the grip's front face so no white slit shows
    # between the guard's rear wall and the grip tang.
    # The opening's TOP edge is the receiver's own underside (z=-36.0), not a
    # bar of guard: on the sheet the trigger's shoe hangs from that edge into
    # the hole.  Building a bar above the hole makes the whole thing read as a
    # ring loop instead of a hole in an integral plate.
    # Hole's TOP edge sits at z=-41.2, leaving a continuous 5 mm band of guard
    # under the receiver.  That band is what the trigger's shoe pierces on the
    # sheet - run the hole up to -36 and the guard reads as an open ring with
    # the trigger dangling out of the sky (tried, looked wrong).
    HOLE = rounded_loop(355.0, 396.0, -61.0, -41.2, 9.5, seg=8)
    OUTER = rounded_loop(342.0, 412.0, -65.0, -34.0, 5.0, seg=8)
    GW = 12.0
    guard = Part('TriggerGuard', mat_black)
    guard.ring_prism(OUTER, HOLE, 'Y', -GW, GW)
    # RAISED BEAD round the hole - the cast look of the reference comes from
    # this proud step, not from wall thickness.  It grows OUTWARD from the
    # hole so the opening's size never changes.
    BEAD = 3.4
    # offset_closed() changes the point count, and ring_prism needs matching
    # loops; growing the rounded rectangle by the same amount per side keeps
    # the same construction (same count, same winding, same start angle).
    bead_out = rounded_loop(355.0 - BEAD, 396.0 + BEAD, -61.0 - BEAD,
                            -41.2 + BEAD, 9.5 + BEAD, seg=8)
    for sy in (-1.0, 1.0):
        guard.ring_prism(bead_out, HOLE, 'Y', sy * (GW - 2.4), sy * (GW + 1.7))
    # small socket screw in the web under the hole's front corner (visible in
    # the sheet at roughly (352,-63))
    for sy in (-1.0, 1.0):
        guard.cyl((352.6, sy * (GW - 1.0), -63.2), (352.6, sy * (GW + 0.9), -63.2),
                  2.3, seg=18)
    tg = guard.build(smooth=True, angle=36, bevel=1.3, bevel_seg=3,
                     coll_name='Geo')

    # ---- trigger -------------------------------------------------------
    # AR-pattern curved trigger. Built as a true circular ARC (constant
    # curvature), not a polyline: the blade is the annulus sector between
    # R_out and R_in about a centre above/behind the tip, so both edges sweep
    # smoothly and the section stays uniform along the whole length.
    tb = Part('Trigger', mat_black)
    # MEASURED arc (see this function's header): a near-constant 4.5-5.2 mm wide
    # blade whose centreline walks x 376.2 -> 384.2 from z -59.5 up to -44, then
    # holds and eases forward. That monotone path IS the crescent - the belly
    # bulges rearward in the middle third, exactly as the user's sketch shows.
    # The fat 13 mm block in the sheet at z=-37 is a SHOE at the very top, not
    # the blade, so it is modelled as its own block.
    # Tables are linearly interpolated (not splined): a Catmull-Rom through these
    # noisy samples overshoots between knots and put a kink in a smooth arc.
    # ---- TRIGGER --------------------------------------------------------
    # Built as a LOFT of rounded rings swept along the measured arc, not as an
    # extruded outline.  The prism version read as a bent piece of sheet metal:
    # a 5 mm plate with sharp corners has no roundness to catch light, so the
    # only thing visible was its silhouette plus a crease where the tip fan
    # triangulated.  A loft gives the blade a genuine elliptical section.
    ZS = [-56.0, -54.0, -52.0, -50.0, -48.0, -46.0, -44.0,
          -42.0, -40.0, -38.0, -36.6]
    XM = [377.60, 379.60, 381.10, 382.25, 383.00, 383.60, 384.10,
          384.45, 384.80, 385.00, 385.00]
    WD = [4.4, 4.6, 4.6, 4.7, 4.8, 5.2, 5.4, 6.0, 7.0, 9.0, 10.5]
    DEP = [3.4, 3.6, 3.7, 3.8, 3.9, 4.2, 4.4, 4.8, 5.2, 5.6, 5.8]

    def _lin(tab, z):
        if z <= ZS[0]:
            return tab[0]
        if z >= ZS[-1]:
            return tab[-1]
        for k in range(len(ZS) - 1):
            if ZS[k] <= z <= ZS[k + 1]:
                f = (z - ZS[k]) / (ZS[k + 1] - ZS[k])
                return tab[k] + (tab[k + 1] - tab[k]) * f
        return tab[-1]

    def tring(cxx, z, hxx, hyy, n=10):
        """Rounded-rectangle section in the XY plane at height z, as 3D pts."""
        pts = []
        rr = min(hxx * 0.44, hyy * 0.94)
        for k in range(n):
            an = TAU * k / n
            ca, sa = math.cos(an), math.sin(an)
            sx = 1.0 if ca >= 0 else -1.0
            sy = 1.0 if sa >= 0 else -1.0
            pts.append((cxx + sx * (hxx - rr) + rr * ca,
                        sy * (hyy - rr) + rr * sa, z))
        return pts

    NR = 20
    rings = []
    for i in range(NR + 1):
        z = ZS[0] + (ZS[-1] - ZS[0]) * i / float(NR)
        rings.append(tring(_lin(XM, z), z, _lin(WD, z) * 0.5,
                           _lin(DEP, z) * 0.5))
    # round the hook: three shrinking sections below the last table row, each
    # also nudged forward so the tip curls the way the sheet's does
    for k, sc in enumerate((0.80, 0.52, 0.22)):
        cxx = _lin(XM, ZS[0]) + 0.50 * (k + 1)
        rings.insert(0, tring(cxx, ZS[0] - 0.9 * (k + 1),
                              _lin(WD, ZS[0]) * 0.5 * sc,
                              _lin(DEP, ZS[0]) * 0.5 * sc))
    tb = Part('Trigger', mat_black)
    tb.loft(rings, cap_start=True, cap_end=True)
    # shoe: the fat block where the blade meets the receiver, capped 0.4 mm
    # above the receiver's underside so its own top face can never be seen
    # through the opening from below (a bug that cost three rebuilds).
    tb.prism([(379.2, -35.6), (390.6, -35.6), (390.6, -39.4), (379.6, -39.4)],
             'Y', -3.4, 3.4)
    tmx = _lin(XM, -36.6)
    for sy in (-1, 1):
        tb.cyl((tmx, sy * 1.2, -38.2), (tmx, sy * 4.1, -38.2), 2.7, seg=20)
    trig = tb.build(smooth=True, angle=60, bevel=1.1, bevel_seg=3, coll_name='Geo')

    # controls: mag release, bolt catch, selector, pins
    c = Part('LR_controls', mat_black)
    # The magazine release button used to be the first two calls here, welded
    # into LR_controls.  It is now its own object `MagRelease` (built below) so a
    # reload animation can push it in and out; welded in, it could only move with
    # the whole lower receiver.
    c.box(419.0, 432.0, hw - 0.3, hw + 3.6, -20.0, -8.0)
    c.cyl((431.0, hw - 0.2, -9.5), (431.0, hw + 2.2, -9.5), 6.6, seg=18)
    c.box(427.0, 452.0, hw + 0.4, hw + 4.2, -11.4, -8.0)

    # ---- SAFETY SELECTOR (user item 4.3) ---------------------------------
    # Missing entirely before. On the sheet it is the small paddle sitting
    # right above the trigger, on the lower receiver's flank at about z=-16.5,
    # x 399..419: a round boss with a two-lobed lever sticking out both fore
    # and aft. Measured from the sheet scan: bright widget spans x 399..419 at
    # z -15..-18 with a boss whose centre is near x=407.
    sel = Part('Selector', mat_black)
    for sign in (-1, 1):
        y = sign * hw
        # pivot boss
        sel.cyl((407.0, y, -16.5), (407.0, y + sign * 3.4, -16.5), 5.6, seg=20)
        sel.cyl((407.0, y + sign * 3.2, -16.5), (407.0, y + sign * 4.4, -16.5),
                3.0, seg=16)
        # fore lever: tapers to a rounded tip
        sel.prism([(407.0, -19.4), (418.5, -19.0), (419.6, -17.4),
                   (418.6, -15.5), (407.0, -15.0)],
                  'Y', y + sign * 1.2, y + sign * 3.6)
        # aft lever: shorter, fatter, angled slightly down
        sel.prism([(407.0, -18.6), (399.2, -19.6), (397.8, -18.0),
                   (398.6, -16.2), (407.0, -15.4)],
                  'Y', y + sign * 1.2, y + sign * 3.6)
    selo = sel.build(smooth=True, angle=36, bevel=0.7, coll_name='Geo')

    # ---- MAGAZINE RELEASE BUTTON ----------------------------------------
    # Own object, on the +Y flank just forward of the trigger guard - the AR
    # layout.  Pressing it moves it along -Y; its origin is set at the button
    # face by r3_rig.py so that translate() works on the object directly.
    mr = Part('MagRelease', mat_black)
    mr.cyl((355.0, hw, -34.0), (355.0, hw + 4.4, -34.0), 7.0, seg=18)
    mr.cyl((355.0, hw + 4.0, -34.0), (355.0, hw + 5.4, -34.0), 4.4, seg=16)
    magrel = mr.build(smooth=True, angle=36, bevel=0.6, coll_name='Geo')
    for xx in (300.0, 452.0):
        c.cyl((xx, hw - 1.0, -21.0), (xx, hw + 1.0, -21.0), 3.6, seg=16)
    ctrl = c.build(smooth=True, angle=34, coll_name='Geo')

    # magwell lip / flare
    # The magwell lip is an ANNULUS round the magazine, not a floor.  It used to
    # be a solid slab across the mouth, which meant a magazine could never be
    # withdrawn - invisible in stills, fatal to a reload animation.  Built on
    # axis 'Z' so the opening runs down the insertion axis: a ring in the XY
    # plane swept vertically.
    #
    # The hole is sized off the magazine's own section plus 0.6 mm of clearance,
    # so an inserted mag shows a realistic working gap instead of clipping.
    # The well was a SOLID SLAB across the mouth, so a magazine could never be
    # withdrawn - invisible in a still, fatal to a reload animation.
    #
    # It is now the two side walls of the well, not a full ring.  A ring would
    # need its outer edge outside the magazine, but the magazine's mouth reaches
    # x 280.8 and the lower receiver's own front wall is at x 289.8, i.e. the
    # magazine already overhangs the receiver by 9 mm at that height.  An honest
    # full ring would therefore have to stand 9 mm proud of the receiver's nose.
    # The sheet only shows these two cheek walls anyway.
    #
    # Clearance: the walls sit at |y| >= MAG_HY + 0.7 so the magazine slides
    # with a realistic working gap rather than clipping.
    MAG_HY = 12.8
    LIP_Z0, LIP_Z1 = -63.0, -55.0
    f = Part('LR_magwell', bpy.data.materials.get('M_Gray2') or mat_gray)
    for sg in (-1, 1):
        f.prism(rounded_loop(287.0, 352.0, LIP_Z0, LIP_Z1, 3.4, seg=6),
                'Y', sg * (MAG_HY + 0.7), sg * (hw - 0.4))
    flare = f.build(smooth=True, angle=34, bevel=0.7, coll_name='Geo')
    return [lower, panel, fld, fgray, front, tg, trig, ctrl, flare, selo,
            magrel]


# ========================================================= 5b ejection side detail
def build_side_detail(mat_black, mat_gray):
    """Bolt catch / mag release / takedown pins visible on both flanks."""
    p = Part('LR_pins', mat_black)
    for sign in (-1, 1):
        y = sign * (UR_W * 0.5 + 0.2)
        for (xx, zz, r) in ((300.0, -21.0, 3.6), (452.0, -21.0, 3.6),
                            (330.0, -40.0, 3.2), (452.0, -40.0, 2.6)):
            p.cyl((xx, y, zz), (xx, y + sign * 1.2, zz), r, seg=14)
    return p.build(smooth=True, angle=34, coll_name='Geo')


# ================================================================= 6 grip
def _poly_span(poly, z):
    """min/max x of a closed polygon at height z."""
    xs = []
    n = len(poly)
    for i in range(n):
        a, za = poly[i - 1]
        b, zb = poly[i]
        if (za - z) * (zb - z) <= 0 and abs(zb - za) > 1e-6:
            xs.append(a + (b - a) * (z - za) / (zb - za))
    return (min(xs), max(xs)) if len(xs) >= 2 else None


def build_grip(mat):
    """Pistol grip: raked shaft with a moulded side panel.

    WHAT THE SHEET SHOWS (14x crop, work/grip2.png): the grip is a smooth
    moulded shaft whose side carries a TEXTURED PANEL set inside a raised
    border - a rounded-rectangle frame following the grip's rake. There are
    no transverse bands.

    The previous version built the texture as seven flat rib prisms stacked
    down the grip. Because each rib is a separate prism with its own bevel,
    they caught the light individually and read as a ladder of steps - the
    single worst artifact on the whole model at that point. Texture is a
    shader property, so it is now a stipple bump (M_Grip) and the only
    geometry is the border frame.
    """
    import importlib, r3_prof
    importlib.reload(r3_prof)
    poly = r3_prof.GRIP
    p = Part('Grip', mat)
    p.prism([(x, z) for x, z in poly], 'Y', -15.2, 15.2)
    ob = p.build(smooth=True, angle=34, bevel=3.2, bevel_seg=3, coll_name='Geo')

    # ---- raised border frame around the stipple panel
    # The frame follows the grip's own outline: every edge is sampled from
    # _poly_span() so it can never hang off the silhouette.
    #
    # Built as FOUR SEPARATE STRIPS, not one closed ribbon. A single outer loop
    # plus a reversed inner loop makes a lens whose ends taper to a point, and
    # the extruded result showed long diagonal creases across the panel - the
    # artifact visible in work/grip4.png. Four strips meet at square corners and
    # the bevel rounds them.
    MARGIN, FRAME = 5.6, 2.8
    Z0, Z1 = -124.0, -62.0
    NZ = 26
    fr = Part('GripPanel', mat)

    def span_at(z):
        sp = _poly_span(poly, z)
        return (sp[0] + MARGIN, sp[1] - MARGIN) if sp else None

    zs = [Z0 + (Z1 - Z0) * i / NZ for i in range(NZ + 1)]
    for sgn in (-1, 1):
        y0, y1 = sgn * 15.2, sgn * 16.2
        ylo, yhi = min(y0, y1), max(y0, y1)
        # left and right vertical strips
        for side in (0, 1):
            strip = []
            for z in zs:
                sp = span_at(z)
                if not sp:
                    continue
                x = sp[side]
                strip.append((x, z))
                strip.append((x + FRAME, z)) if side == 0 else None
            left_pts, right_pts = [], []
            for z in zs:
                sp = span_at(z)
                if not sp:
                    continue
                left_pts.append((sp[0], z))
                right_pts.append((sp[1], z))
            if side == 0:
                outer, inner = left_pts, [(x + FRAME, z) for (x, z) in left_pts]
            else:
                outer, inner = right_pts, [(x - FRAME, z) for (x, z) in right_pts]
            quad = outer + list(reversed(inner))
            fr.prism(quad, 'Y', ylo, yhi)
        # top and bottom horizontal caps
        for (za, zb) in ((Z1 - FRAME, Z1), (Z0, Z0 + FRAME)):
            spa, spb = span_at(za), span_at(zb)
            if not spa or not spb:
                continue
            quad = [(spa[0], za), (spa[1], za), (spb[1], zb), (spb[0], zb)]
            fr.prism(quad, 'Y', ylo, yhi)
    return ob


# ================================================================ 7 stock
def build_stock(mat_poly, mat_gray, mat_rubber):
    """Skeleton stock. Every coordinate below is measured off ref_side.png.

    OUTER ENVELOPE (column scan, threshold <215):
      top    z +34.5 flat x 500..610, dips to +25.6 over x 620..648 (the neck),
             back to +33.5 over x 656..684
      bottom z -22 flat x 486..562, then a straight diagonal to (656,-86.4),
             then flat to x 686
      rear   x 686 butt pad face

    WINDOWS (flood-filled enclosed white regions - these are the real holes):
      MAIN    x 592..646, top edge z -2.5, right edge x 646, bottom edge the
              diagonal from (592,-14) to (646,-50)
      SLOT    thin diagonal, parallel to the bottom brace, ~4 mm wide
      LOZENGE x 531..566, z -3..-11 (the finger slot near the front)
      The recessed pocket in the rear post (x 655..681, z 6..26) is a MOULDED
      DEPRESSION, not a through hole - values there are 60-65, not background.
    """
    hw = 23.4
    t = Part('BufferTube', mat_poly)
    t.cyl((474, 0, 5.0), (503, 0, 5.0), 20.6, seg=32)
    t.cyl((475, 0, 5.0), (479, 0, 5.0), 22.6, seg=32)
    t.cyl((497, 0, 5.0), (503, 0, 5.0), 22.4, seg=32)
    tube = t.build(smooth=True, angle=40, coll_name='Geo')

    p = Part('StockFrame', mat_poly)
    # BOTTOM BRACE SLOPE is measured, not eyeballed. Per-column silhouette of
    # the sheet gives -22.8 at x570, -46.1 at x600, -85.3 at x650 and -86.4 at
    # x686: a straight run of slope -0.781 from (570,-22.8) to (656,-86.4).
    # The previous profile used -0.605 and so left the brace 4-6 mm too high
    # along its whole length, which the silhouette diff showed as a blue wedge.
    prof = [
        (486.0, 34.5), (610.0, 34.5), (616.0, 27.0), (620.0, 25.6),
        (646.0, 25.6), (652.0, 30.0), (658.0, 33.5), (682.0, 33.5),
        (686.0, 30.0), (686.0, -86.4), (652.0, -86.4), (632.0, -72.2),
        (570.0, -22.8), (490.0, -22.0), (486.0, -19.0),
    ]
    p.prism(prof, 'Y', -hw, hw)
    frame = p.build(smooth=False, angle=34, bevel=1.5, bevel_seg=2,
                    coll_name='Geo')

    # ---- the three real cut-outs
    # main window: the sheet's shape is a ROUNDED TRIANGLE - flat top, vertical
    # rear edge, and a diagonal hypotenuse running down-right. Small corner
    # radii are what stop it reading as a punched rectangle.
    main = [(596.0, -2.5), (642.0, -2.5), (645.4, -5.0), (646.0, -9.0),
            (646.0, -46.0), (643.0, -49.6), (638.0, -48.0), (620.0, -35.0),
            (604.0, -24.0), (595.0, -18.0), (592.2, -14.0), (592.0, -8.0)]
    loz = rounded_loop(531.0, 566.0, -11.0, -3.0, 3.6, seg=6)
    # thin slot: a 4 mm ribbon running parallel to the bottom brace
    def _band(x0, z0, x1, z1, w):
        import math as _m
        dx, dz = x1 - x0, z1 - z0
        L = _m.hypot(dx, dz)
        nx, nz = -dz / L * w * 0.5, dx / L * w * 0.5
        return [(x0 + nx, z0 + nz), (x1 + nx, z1 + nz),
                (x1 - nx, z1 - nz), (x0 - nx, z0 - nz)]
    # MEASURED. The row scan of the sheet puts this ribbon at 588..593 for
    # z -25, 603..607 for z -37 and 626..629 for z -55, i.e. the centreline
    # runs (590.5,-25) -> (627.5,-55), slope -0.81 - the SAME slope as the
    # bottom brace below it. The old band was at slope -0.60 and sat 10 mm
    # high, which is the red/blue pair straddling the slot in every diff.
    slot = _band(590.5, -25.0, 627.5, -55.0, 4.4)
    for w in (main, slot):
        cu = Part('c', None)
        cu.prism(list(w), 'Y', -hw - 9, hw + 9)
        boolop(frame, cu.build(smooth=False))

    # ---- cheek riser (the lighter comb on top)
    c = Part('Cheek', bpy.data.materials.get('M_Gray2') or mat_gray)
    cp = [(490.0, 17.0), (494.0, 13.5), (594.0, 13.5), (608.0, 19.0),
          (610.0, 34.6), (486.0, 34.6)]
    c.prism(cp, 'Y', -hw - 0.5, hw + 0.5)
    cheek = c.build(smooth=True, angle=34, bevel=2.4, bevel_seg=3,
                    coll_name='Geo')
    # dark shadow gap where the comb meets the beam - without this the riser
    # and the frame fuse into one heavy mass
    gq = Part('StockGap', bpy.data.materials.get('M_Dark') or mat_poly)
    gq.box(487.0, 607.0, -hw - 0.6, hw + 0.6, 14.6, 16.4)
    gap = gq.build(smooth=False, coll_name='Geo')

    # ---- thick separate rubber butt pad
    r = Part('ButtPad', mat_rubber)
    # PAD DEPTH IS MEASURED: per-column silhouette of the sheet ends at
    # x 686 (z -82.9) / x 688 (z -75.0) / x 690 (background below z 17).
    # The old pad ran out to x 694, i.e. 5 mm of solid rubber past the end of
    # the gun - the blue vertical band on the right of every silhouette diff.
    r.prism([(684.5, 30.5), (689.0, 26.5), (689.0, -84.0), (684.5, -87.5)],
            'Y', -hw + 1.2, hw - 1.2)
    pad = r.build(smooth=True, angle=30, bevel=2.8, bevel_seg=2,
                  coll_name='Geo')

    rr = Part('ButtRibs', mat_rubber)
    z = 24.0
    while z > -84.0:
        rr.box(688.4, 690.2, -hw + 1.6, hw - 1.6, z - 2.2, z + 2.2)
        z -= 10.4
    ribs = rr.build(smooth=True, angle=30, bevel=1.0, coll_name='Geo')

    # ---- rear-post moulded pocket + hardware
    d = Part('StockDet', mat_poly)
    d.prism([(657.0, 25.0), (680.0, 25.0), (681.5, 20.0), (680.0, 6.0),
             (659.0, 6.0), (655.5, 15.0)], 'Y', -hw - 0.05, -hw + 1.3)
    d.prism([(657.0, 25.0), (680.0, 25.0), (681.5, 20.0), (680.0, 6.0),
             (659.0, 6.0), (655.5, 15.0)], 'Y', hw - 1.3, hw + 0.05)
    d.box(499.0, 514.0, -hw - 1.2, hw + 1.2, -21.4, -11.0)
    d.cyl((507.0, -hw - 1.2, -16.2), (507.0, -hw - 3.6, -16.2), 4.4, seg=16)
    # vertical relief slot down the rear post (clearly visible in the sheet)
    for sy in (-1, 1):
        d.box(663.0, 667.4, sy * (hw + 0.02), sy * (hw + 1.1), -44.0, 2.0)
    # deep socket-head bolts: a proud ring plus a sunken dark face
    for (xx, zz) in ((668.0, 2.0), (668.0, -74.0)):
        for sy in (-1, 1):
            d.cyl((xx, sy * (hw + 0.02), zz), (xx, sy * (hw + 2.0), zz),
                  7.4, seg=22)
            d.cyl((xx, sy * (hw + 1.6), zz), (xx, sy * (hw + 2.3), zz),
                  5.4, seg=22)
    det = d.build(smooth=True, angle=34, coll_name='Geo')

    return [tube, frame, cheek, pad, ribs, det, gap]


# ============================================================ 8 magazine
def build_mag(mat_mag, mat_brass, big=False):
    """Magazine: swept shell on a raked arc, FLAT side panels, two crisp
    lengthwise channels, and a base plate that is a continuation of the body.

    WHY THE SHAPE READ AS AWKWARD.  Three separate causes:
      1. the section was a rounded rectangle with a large corner radius, so the
         flanks read as a smooth tube rather than flat panels;
      2. the width table swelled two thirds of the way down and pinched at both
         ends - a balloon belly no real magazine has;
      3. the base plate was a hand-built quadrilateral floating below the body,
         so its front corner jutted out as a beak.
    Now the flanks are flat with tight corners, the width is monotone, and the
    base plate is LOFTED FROM THE BODY'S OWN RING FUNCTION at two stations
    below the mouth - which makes it automatically square to the magazine axis
    and perfectly flush with the flanks.

    The magazine also runs UP INTO the magwell (ZHID), because a detached one
    is much taller than the part you see on the rifle.  That hidden section is
    inset on both axes and has its channels switched off; the inset RAMPS in
    over the hidden length instead of stepping, so the isolated view has no
    shoulder.
    """
    # `big=True` builds the QUAD-STACK EXTENDED magazine: same section
    # machinery, but the body is twice as thick in Y (two staggered pairs
    # instead of one pair, i.e. 双排 -> 四排) and the spine runs much further
    # down, so the body alone is ~70% longer.  Nothing else changes, which is
    # the point - the rake, the channels and the base-plate construction all
    # come from the same code, so the two magazines are visibly the same family.
    #
    # Y is the LEFT-RIGHT axis, so widening in Y leaves the SIDE silhouette
    # untouched: the quad mag is fatter from the front and above, but from the
    # side it still sits inside the reference's outline.
    ZTOP, ZBOT = -58.0, -164.0
    ZHID = -21.0
    TH_PLATE = 12.0
    # --- quad-stack geometry
    HV_NARROW = 12.8          # half width inside the magwell (must clear it)
    HV_QUAD = 19.0            # 38 mm overall -> four 5.56 columns
    QUAD_Z0, QUAD_Z1 = -62.0, -72.0   # flare starts just below the receiver's
                                      # bottom edge (-62.4) and opens over 10 mm
    if big:
        # Length: a quad body plus a full straight extension looked
        # exaggerated - the first version (ZBOT -232) reached 200 mm below the
        # receiver against the standard magazine's 128.  -206 keeps a clear
        # "big magazine" read at 158 mm while staying believable on a carbine.
        ZBOT = -206.0
        TH_PLATE = 14.0

    # ---- SPINE: one quadratic fitted to the sheet's centreline.  A 3-point
    # CIRCLE fit is degenerate here (its centre lands on the middle sample), so
    # a quadratic is the honest choice - it is smooth by construction and
    # cannot overshoot the way a spline through 15 noisy samples did.
    A0, B0, C0 = 305.13, 0.3013, -1.7751e-3
    ZREF = -110.0

    def _u(z):
        return z - ZREF

    # Where the standard magazine ends.  Below this the quad version continues
    # with a STRAIGHT run instead of extrapolating the quadratic.
    #
    # Why: the quadratic's curvature grows with distance from ZREF, so pushing
    # it another 74 mm down turned the body into a scythe - slope at the floor
    # reached 0.76 (37 deg off vertical) and the whole magazine read as a
    # banana.  Real extended magazines are the standard body plus extra length,
    # so the quad one is IDENTICAL to the standard one from the mouth to
    # ZBEND and then simply keeps that slope.  It also guarantees the two
    # magazines look like the same family and that the quad one still fits the
    # magwell exactly.
    ZBEND = -164.0
    M_BEND = B0 + 2.0 * C0 * (ZBEND - ZREF)
    X_BEND = A0 + B0 * (ZBEND - ZREF) + C0 * (ZBEND - ZREF) ** 2

    def cx_at(z):
        if big and z < ZBEND:
            return X_BEND + M_BEND * (z - ZBEND)
        u = _u(z)
        return A0 + B0 * u + C0 * u * u

    def slope_at(z):
        if big and z < ZBEND:
            return M_BEND
        return B0 + 2.0 * C0 * _u(z)

    # ---- perpendicular half width: MONOTONE, widest at the mouth, easing in
    # as it goes down.  The previous table (35.6 .. 34.2 .. 37.4 .. 36.2) put a
    # bulge at two thirds height and pinched both ends; that is the balloon.
    # A real magazine body is essentially PARALLEL-SIDED in the side view; only
    # the arc changes.  The old table tapered 1.5 mm towards the floor, and once
    # the base plate was given a proper overhang that taper read as a waist
    # followed by a bulge.
    WH = [34.60, 34.55, 34.50, 34.46, 34.42, 34.39, 34.36, 34.34, 34.32,
          34.30, 34.28, 34.26, 34.24, 34.22, 34.20]

    def H_at(z):
        t = max(0.0, min(1.0, (z - ZTOP) / (ZBOT - ZTOP)))
        f = t * (len(WH) - 1)
        i = max(0, min(len(WH) - 2, int(f)))
        return WH[i] + (WH[i + 1] - WH[i]) * (f - i)

    def hv_at(z):
        t = max(0.0, min(1.0, (z - ZTOP) / (ZBOT - ZTOP)))
        if not big:
            return HV_NARROW - 0.5 * t
        # Quad body.  It CANNOT be wide up at the mouth - the hidden section has
        # to pass through the magwell - so it stays at the single-pair width
        # until it is clear of the well wall (which ends at z -63) and then
        # flares out over 16 mm.  A smoothstep, because a linear ramp left a
        # visible crease where it met the straight body.
        if z >= QUAD_Z0:
            return HV_NARROW - 0.5 * t
        if z <= QUAD_Z1:
            return HV_QUAD
        r = (QUAD_Z0 - z) / (QUAD_Z0 - QUAD_Z1)
        sm = r * r * (3.0 - 2.0 * r)
        return HV_NARROW + (HV_QUAD - HV_NARROW) * sm

    # --------------------------------------------------- cross-section ring
    # Channel half width / depth.  On the quad body the two channels move
    # further apart and get wider: the flank is 41 mm instead of 25 mm, so at
    # the double-stack offsets they would crowd the middle.
    GW, GD = (4.4, 1.0) if big else (3.3, 1.0)
    GC = 0.34 if big else 0.27   # channel centre, as a fraction of hu
    RIB = 0.55                 # spine rib standing proud on the end faces

    def ring(z, hu_add=0.0, hv_add=0.0, groove=True, ne=30, nc=4, nf=3):
        cx = cx_at(z)
        m = slope_at(z)
        L = math.sqrt(1.0 + m * m)
        # H_at is the HORIZONTAL half width, so the perpendicular half width of
        # the section is H/L.  Derivation, because this was wrong twice:
        # a section tilted by slope m and swept along z projects onto a row as
        # 2*(hu/L)*(1 + m*m) = 2*hu*L; setting hu = H/L therefore gives exactly
        # 2H at every height.  Using H*L instead made the body swell with depth
        # (73 mm at the mouth, 81 mm at the floor) - the "awkward" shape.
        hu = max(4.0, H_at(z) / L + hu_add)
        hv = max(4.0, hv_at(z) + hv_add)
        # TIGHT corner radius: the flanks have to read as flat panels, so only
        # the last 3 mm roll over.  The old 5.2 mm radius is what turned the
        # whole body into a soft tube.
        rad = min(2.0, hu * 0.14, hv * 0.32)
        cu, cv = hu - rad, hv - rad

        def side(sgn):
            out = []
            for i in range(2 * ne + 1):
                u = -cu + 2.0 * cu * i / (2 * ne)
                dd = 0.0
                if groove:
                    for gc in (-GC * hu, GC * hu):
                        q = abs(u - gc) / GW
                        if q < 1.0:
                            # flat-bottomed channel with sharp shoulders -
                            # a cosine profile read as a soft dent
                            dd += GD * (1.0 if q < 0.62 else (1.0 - q) / 0.38)
                    # Fade the channel out over the last 10 mm before it enters
                    # the magwell.  Stepping it off at ZTOP left a visible
                    # break across the flank in the isolated view.
                    dd *= max(0.0, min(1.0, (ZTOP + 10.0 - z) / 10.0))
                out.append((u, sgn * (hv - dd)))
            return out

        def arc(cu0, cv0, a0, a1, n):
            return [(cu0 + rad * math.cos(a0 + (a1 - a0) * i / n),
                     cv0 + rad * math.sin(a0 + (a1 - a0) * i / n))
                    for i in range(1, n + 1)]

        def endface(sgn, vf, vt):
            out = []
            for i in range(1, nf + 1):
                v = vf + (vt - vf) * i / nf
                bump = RIB * max(0.0, math.cos(math.pi * 0.5 * v / cv)) ** 2
                out.append((sgn * (hu + bump), v))
            return out

        P = []
        P += side(+1)                                       # +v face
        P += arc(cu, cv, math.pi * 0.5, 0.0, nc)            # -> (hu, cv)
        P += endface(+1, cv, -cv)                           # rear spine
        P += arc(cu, -cv, 0.0, -math.pi * 0.5, nc)          # -> (cu, -hv)
        P += list(reversed(side(-1)))[1:]                   # -v face
        P += arc(-cu, -cv, -math.pi * 0.5, -math.pi, nc)    # -> (-hu, -cv)
        P += endface(-1, -cv, cv)                           # front spine
        P += arc(-cu, cv, math.pi, math.pi * 0.5, nc)[:-1]  # close the loop

        nx, nz = 1.0 / L, -m / L
        return [(cx + u * nx, v, z + u * nz) for (u, v) in P]

    # ------------------------------------------------------------ 1. shell
    NSEG = 36
    rings = []
    for i in range(NSEG + 1):
        z = ZHID + (ZBOT - ZHID) * i / NSEG
        if z > ZTOP + 0.01:
            # Inside the magwell.  The inset has to be GREATEST at the top and
            # zero at the mouth - the previous ramp ran the other way, so the
            # hidden section flared out wider than the body and left a hard
            # shoulder right where the rifle would cover it.
            fr = max(0.0, min(1.0, (ZTOP - z) / (ZTOP - ZHID)))
            rings.append(ring(z, hu_add=-3.6 * fr, hv_add=-0.5 * fr,
                              groove=False))
        else:
            rings.append(ring(z))
    NM = 'MagazineBig' if big else 'Magazine'
    NF = 'MagBigFloor' if big else 'MagFloor'
    NS = 'MagBigSlot' if big else 'MagSlot'
    NN = 'MagBigNeck' if big else 'MagNeck'
    p = Part(NM, mat_mag)
    p.loft(rings, cap_start=True, cap_end=True)
    # a LOW smoothing angle keeps the panel breaks crisp; at 52 deg the flat
    # cheeks and the channels all averaged into one soft gradient
    mag = p.build(smooth=True, angle=32, coll_name='Geo')

    # ------------------------------------------- 2. base plate
    # RESTORED to the version the user preferred (m09340: "keep the original
    # base plate, the new one does not look as good").  Two attempts to improve
    # it both failed visibly and are recorded here so they are not retried:
    #   * a traced chevron prism - the plate's side silhouette in the sheet is
    #     a downward point, but prisming that in world z made a boot-shaped
    #     block hanging off the end, because the magazine is RAKED;
    #   * a 29 mm slab with a proud bead - read as a suitcase, far too heavy.
    # What works is a short loft off the body's own ring function, one crisp
    # step out, then a constant section to the floor.
    mat_d = bpy.data.materials.get('M_Polymer') or mat_mag
    f = Part(NF, mat_d)
    f.loft([ring(ZBOT + 3.0, groove=False),
            ring(ZBOT + 1.0, hu_add=0.55, hv_add=0.95, groove=False),
            ring(ZBOT - TH_PLATE, hu_add=0.55, hv_add=0.95, groove=False)],
           cap_start=True, cap_end=True)
    fl = f.build(smooth=True, angle=34, bevel=0.7, bevel_seg=2,
                 coll_name='Geo')

    # ------------------------------------- 3. retaining lip on the plate face
    ch = Part(NS, mat_d)
    ch.loft([ring(ZBOT - TH_PLATE + 2.2, hu_add=0.80, hv_add=1.45,
                  groove=False),
             ring(ZBOT - TH_PLATE + 0.6, hu_add=0.80, hv_add=1.45,
                  groove=False)],
            cap_start=True, cap_end=True)
    ch.build(smooth=True, angle=40, coll_name='Geo')

    # ------------------------------------------------------- 4. magwell top
    # The mouth is at the TOP OF THE HIDDEN SECTION, not at the magwell mouth:
    # what pokes out of the rifle is only the lower two thirds of the part.
    # Feed lips are two raised rails with the feed opening between them, not
    # one solid slab across the top.
    nk = Part(NN, mat_mag)
    cxT = cx_at(ZHID)
    mT = slope_at(ZHID)
    LT = math.sqrt(1.0 + mT * mT)
    huT = 34.60 / LT - 3.4
    hvT = hv_at(ZHID) - 0.5
    # Two rails with the feed opening between them, flush with the body.  The
    # first version made one full-width slab 1 mm wider than the body, so the
    # mouth read as a lid sitting on top of the magazine.
    for sgn in (-1, 1):
        nk.box(cxT - huT + 1.6, cxT + huT - 1.6,
               sgn * (hvT - 2.2), sgn * (hvT - 0.02),
               ZHID - 1.0, ZHID + 1.2)
    # front catch lug and the rear guide lug
    nk.box(cxT - huT - 0.5, cxT - huT + 5.0, -(hvT - 4.2), (hvT - 4.2),
           ZHID - 11.0, ZHID - 3.2)
    nk.box(cxT + huT - 5.0, cxT + huT + 0.5, -(hvT - 4.2), (hvT - 4.2),
           ZHID - 9.0, ZHID - 2.6)
    neck = nk.build(smooth=False, angle=30, bevel=0.5, bevel_seg=2,
                    coll_name='Geo')

    print('  MAG body (%.1f,%.1f)->(%.1f,%.1f)  plate top z %.1f bottom z %.1f'
          % (cx_at(ZHID), ZHID, cx_at(ZBOT), ZBOT,
             ZBOT + 2.0, ZBOT - TH_PLATE))
    return [mag, neck, fl]


def build_mag_big(mat_mag, mat_brass):
    """Quad-stack extended magazine (双排 -> 四排, and longer).

    Same family as the standard magazine - identical rake, identical channel
    treatment, identical base-plate construction - but 41 mm thick instead of
    26 mm and running 74 mm deeper.  Roughly 100 rounds where the standard one
    holds 30, which is the SureFire MAG5-100 class.
    """
    return build_mag(mat_mag, mat_brass, big=True)


# ================================================================= 9 optic
def build_optic(mat_steel, mat_glass):
    """Red-dot / prism sight, matched to the enlarged reference crop.

    The reference (m04282) reads as a series of HARD STEPS, and that stepping is
    the whole character of the part - a smooth monotone tube loses it:
      objective bell : big cylinder r=22.6, raised band near its mouth,
                       then a sharp step DOWN to the 19.4 tube;
      centre housing : flat-sided cast block, 34.4 tall x 30 wide, small corner
                       rounds; only this section is non-circular;
      side turret    : a LARGE disc (~33 dia) standing well proud, with a
                       raised outer rim and a recessed field - modelled as a
                       two-level disc, not a flat button;
      top turret     : wide knurled drum set FORWARD of centre;
      rear           : step up to a knurled focus ring, then a narrower collar;
      mount          : waisted block with a trapezoid top, and two BIG bolt
                       discs whose faces read as circles from the side.
    The flip caps are slim hinged STRAPS angled up and out - see the note below,
    because three earlier versions modelled them as full lens discs and they
    rendered as blobs or hairlines.
    """
    Z = 76.2
    HB, HT = -17.2, 17.2          # housing half-height about Z
    HWID = 15.0                   # housing half-width in Y

    def rr_ring(x, cz0, hz, hy, r, n=5):
        r = min(r, hy * 0.9, hz * 0.9)
        pts = []
        for (cy, dz, a0) in ((hy - r, hz - r, 0.0), (-hy + r, hz - r, 90.0),
                             (-hy + r, -hz + r, 180.0), (hy - r, -hz + r, 270.0)):
            for k in range(n + 1):
                a = math.radians(a0 + 90.0 * k / n)
                pts.append((x, cy + r * math.cos(a), cz0 + dz + r * math.sin(a)))
        return pts

    def kx(x, r, r2, n):
        pts = []
        for i in range(n * 2):
            rr = r if i % 2 == 0 else r2
            a = TAU * i / (n * 2)
            pts.append((x, rr * math.cos(a), Z + rr * math.sin(a)))
        return pts

    def ky(y, r, r2, n, xc, zc):
        pts = []
        for i in range(n * 2):
            rr = r if i % 2 == 0 else r2
            a = TAU * i / (n * 2)
            pts.append((xc + rr * math.cos(a), y, zc + rr * math.sin(a)))
        return pts

    def kz(z, r, r2, n, xc):
        pts = []
        for i in range(n * 2):
            rr = r if i % 2 == 0 else r2
            a = TAU * i / (n * 2)
            pts.append((xc + rr * math.cos(a), rr * math.sin(a), z))
        return pts

    p = Part('Optic', mat_steel)

    # ---- objective bell: rim, groove, raised band, then a HARD step down
    p.cyl((234.0, 0, Z), (238.6, 0, Z), 22.6, seg=56)
    p.cyl((238.6, 0, Z), (241.4, 0, Z), 21.6, seg=56)      # groove
    p.cyl((241.4, 0, Z), (249.4, 0, Z), 23.0, seg=56)      # raised band
    p.cyl((249.4, 0, Z), (250.6, 0, Z), 22.2, seg=56)      # chamfer
    p.cyl((250.6, 0, Z), (268.0, 0, Z), 21.8, seg=56)
    p.cyl((268.0, 0, Z), (274.0, 0, Z), 21.8, r2=19.4, seg=56)   # taper in
    p.cyl((274.0, 0, Z), (282.0, 0, Z), 19.4, seg=56)
    p.cyl((282.0, 0, Z), (286.0, 0, Z), 20.2, seg=56)      # step collar

    # ---- centre: flat-sided cast housing
    hz0 = (HT - HB) * 0.5
    rz = Z + (HT + HB) * 0.5
    rings = []
    for (x, sc, r) in ((286.0, 0.90, 5.0), (294.0, 1.00, 5.6),
                       (364.0, 1.00, 5.6), (374.0, 0.90, 5.0)):
        rings.append(rr_ring(x, rz, hz0 * sc, HWID * sc, r))
    p.loft(rings, cap_start=True, cap_end=True)

    # ---- rear: step up to the knurled focus ring, then a narrower collar
    p.cyl((374.0, 0, Z), (384.0, 0, Z), 19.4, seg=56)
    p.cyl((384.0, 0, Z), (388.0, 0, Z), 19.4, r2=21.6, seg=56)
    p.cyl((388.0, 0, Z), (392.0, 0, Z), 21.6, seg=56)
    p.loft([kx(392.0, 21.8, 20.9, 30), kx(402.0, 21.8, 20.9, 30)])
    p.cyl((402.0, 0, Z), (406.0, 0, Z), 21.8, seg=56)
    p.cyl((406.0, 0, Z), (412.0, 0, Z), 20.4, seg=56)      # narrower collar

    # ---- top turret: WIDE knurled drum, set forward of the housing centre
    TX = 330.0
    # MEASURED: the sheet's turret crown is a flat run at z=+105.3 from x=323
    # to x=345, so the drum tops out 29.1 mm above the bore axis, not 35.6.
    p.cyl((TX, 0, Z + 17.0), (TX, 0, Z + 18.6), 10.6, seg=36)
    p.loft([kz(Z + 18.6, 13.4, 12.4, 34, TX),
            kz(Z + 27.2, 13.4, 12.4, 34, TX)])
    p.cyl((TX, 0, Z + 27.2), (TX, 0, Z + 29.1), 13.4, seg=48)
    # small sealed plug just behind the turret (clearly visible in the sheet)
    p.cyl((366.0, 0, Z + 19.0), (366.0, 0, Z + 22.4), 6.2, seg=24)
    p.cyl((366.0, 0, Z + 22.4), (366.0, 0, Z + 23.6), 4.6, seg=20)

    # ---- LARGE side turret: raised rim + recessed field + centre boss
    SY = 330.0
    p.cyl((SY, -14.0, Z - 0.5), (SY, -18.6, Z - 0.5), 16.6, seg=52)   # base
    p.cyl((SY, -18.6, Z - 0.5), (SY, -23.4, Z - 0.5), 15.6, seg=52)   # rim
    p.loft([ky(-23.4, 15.6, 15.0, 34, SY, Z - 0.5),
            ky(-25.6, 15.6, 15.0, 34, SY, Z - 0.5)])                  # knurl
    p.cyl((SY, -25.6, Z - 0.5), (SY, -26.6, Z - 0.5), 15.6, seg=52)   # outer lip
    p.cyl((SY, -26.4, Z - 0.5), (SY, -26.9, Z - 0.5), 12.4, seg=48)   # recessed
    p.cyl((SY, -26.8, Z - 0.5), (SY, -27.6, Z - 0.5), 5.2, seg=28)    # centre boss
    # Lever tab on the turret's front edge.  These were written in RAW z (-12..8)
    # instead of Z-relative, which left a small block floating in mid air a
    # hundred millimetres below the scope.  Invisible on the assembled gun
    # (buried inside the receiver) and only surfaced once the optic was
    # rendered on its own.
    p.prism([(315.0, Z - 8.0), (321.0, Z - 12.0), (321.0, Z + 8.0),
             (315.0, Z + 6.0)], 'Y', -21.0, -14.0)
    ob = p.build(smooth=True, angle=32, coll_name='Geo')

    g = Part('OpticGlass', mat_glass)
    g.cyl((233.4, 0, Z), (234.4, 0, Z), 21.2, seg=44)
    g.cyl((412.1, 0, Z), (413.0, 0, Z), 18.2, seg=44)
    gl = g.build(smooth=True, angle=60, coll_name='Geo')

    # ---- mount: waisted block, trapezoid top, two BIG bolt discs
    m = Part('OpticMount', mat_steel)
    m.prism([(288.0, 41.0), (374.0, 41.0), (374.0, 58.0), (288.0, 58.0)],
            'Y', -15.0, 15.0)
    m.prism([(294.0, 57.4), (368.0, 57.4), (364.0, 63.0), (298.0, 63.0)],
            'Y', -15.0, 15.0)
    # waist notch front and rear so it is not a plain slab
    m.prism([(286.0, 47.0), (292.0, 47.0), (292.0, 53.0), (286.0, 53.0)],
            'Y', -15.6, 15.6)
    m.prism([(370.0, 47.0), (376.0, 47.0), (376.0, 53.0), (370.0, 53.0)],
            'Y', -15.6, 15.6)
    for xx in (302.0, 360.0):
        # big bolt disc standing proud of the mount flank, with a hex socket
        m.cyl((xx, -15.0, 50.0), (xx, -19.6, 50.0), 9.4, seg=36)
        m.cyl((xx, -19.5, 50.0), (xx, -20.6, 50.0), 7.8, seg=36)
        m.cyl((xx, -20.4, 50.0), (xx, -21.6, 50.0), 4.6, seg=6)
    mo = m.build(smooth=True, angle=34, coll_name='Geo')

    # ---- flip caps: two TILTED DISCS standing up over the tube.
    # MEASURED (work/capscan.py): each cap reads in the side view as a band
    # about 30 mm long and 10-12 mm across, tilted ~35 deg from vertical and
    # leaning up toward the tube centre. That is a disc seen at a steep angle:
    # a 34 mm cover whose normal is perpendicular to the band but tilted about
    # 0.4 into Y, which is exactly what makes the band 10 mm wide rather than a
    # hairline. Three earlier attempts modelled this as a strap or a flat
    # face-on disc and both read wrong; the reference is a hinged COVER.
    def _nrm(v):
        l = math.sqrt(sum(c * c for c in v))
        return (v[0] / l, v[1] / l, v[2] / l)

    caps = []
    # MEASURED from the sheet (bright-row runs above the tube, threshold<205):
    #   front cover band runs (251,96) -> (279,113) -> apex about (278,119)
    #   rear  cover band runs (402,96) -> (373,113)
    # i.e. both covers lean ~45 deg, not the ~30 deg the first version used,
    # and their hinges sit at x=254 / x=398, not 240 / 405.  The steeper and
    # more forward caps reached x=240 and read as antennae over the bell.
    for (hx, sgn, R, CR) in ((254.0, 1.0, 14.0, 10.4), (398.0, -1.0, 13.6, 10.2)):
        d = _nrm((sgn * 0.68, 0.0, 0.73))          # up and inward over the tube
        n = _nrm((-sgn * 0.78, 0.42, 0.46))        # disc normal (Y tilt = band width)
        hz = 94.0
        cx = hx + d[0] * 15.0
        cz = hz + d[2] * 15.0
        c = Part('Cap', mat_steel)
        # hinge barrel on the bell rim, pin along Y, plus its lock screw
        c.cyl((hx, -7.4, hz), (hx, 7.4, hz), 4.4, seg=24)
        c.cyl((hx, -8.6, hz), (hx, 8.6, hz), 1.8, seg=16)
        c.screw(hx, hz, -7.4, r=2.0, depth=0.8)
        # the cover: bright rim disc with a proud darker inner face
        c.cyl((cx - n[0] * 1.5, -n[1] * 1.5, cz - n[2] * 1.5),
              (cx + n[0] * 1.5, n[1] * 1.5, cz + n[2] * 1.5), R, seg=48)
        c.cyl((cx - n[0] * 3.0, -n[1] * 3.0, cz - n[2] * 3.0),
              (cx - n[0] * 0.9, -n[1] * 0.9, cz - n[2] * 0.9), CR, seg=44)
        # short neck tying the cover back to its hinge
        mx, mz = hx + d[0] * 6.0, hz + d[2] * 6.0
        c.box(mx - 4.6, mx + 4.6, -4.4, 4.4, mz - 3.2, mz + 3.2)
        obc = c.build(smooth=True, angle=44, coll_name='Geo')
        caps.append(obc)
    return [ob, gl, mo] + caps


# ============================================================== 10 rear BUIS
def build_sights(mat):
    p = Part('BUIS_R', mat)
    # folded rear sight: a flat wedge lying on the raised rail
    p.prism([(424.0, 44.0), (438.0, 51.4), (462.0, 51.4), (470.0, 46.0),
             (470.0, 44.0)], 'Y', -11.6, 11.6)
    p.prism([(440.0, 51.2), (460.0, 51.2), (460.0, 53.4), (440.0, 53.4)], 'Y', -7.8, 7.8)
    p.screw(434.0, 47.0, 11.8, r=2.2, depth=0.9)
    p.screw(458.0, 47.0, 11.8, r=2.2, depth=0.9)
    return p.build(smooth=True, angle=34, coll_name='Geo')
