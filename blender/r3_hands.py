"""r3_hands.py - add the two first-person gloves to the finished rifle.

WHY GEOMETRY AND NOT TaCZ'S ARM RENDERER
----------------------------------------
TaCZ draws the player's own arm at the world transform of the bones named
righthand_pos / lefthand_pos.  Those bones are driven by the animation position
channel, and the official 55 guns all share one set of hand constants while
their grips sit in very different places - i.e. the mapping is empirical, not
derivable.  A first attempt shipped the bones and produced a player-skin bicep
parked in a corner of the screen, which is precisely the chuanbang the user
ruled out.  Modelled gloves are deterministic: they are part of the gun, they
are placed by the same coordinates as the grip and the handguard they wrap, and
what you see in the offline render is what the game draws.

SIDES.  +Y is the shooter's RIGHT (the ejection-port side, see r3_bolt.py):
    right glove  palm on +Y, fingers wrap the grip forward edge to -Y
    left  glove  palm on -Y, fingers wrap the handguard underside to +Y

Rig
---
    Hand_R  part of the gun bone (never moves relative to the rifle)
    Hand_L  its own bone; r3_anim.py slides it down the magwell with the
            magazine during a reload

Shape rules, learned the hard way:
  * a hand is NOT a box next to a cylinder.  The palm is a rounded slab that
    follows the surface it presses on, and every finger is an ARC of at least
    five points that wraps that surface.
  * fingers must START INSIDE the palm and finish curled onto the far side,
    or the silhouette shows gaps between hand and gun.
  * four separate tubes read as a row of sausages.  Keep the pitch just under
    two radii so the fingers merge into one mass, and let the bevel draw the
    separation.

Run:  blender -b rifle3.blend --python r3_hands.py
"""
import bpy
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import r3_lib as L
import r3_prof

S = 0.001


def span(z, poly):
    """(min x, max x) of a 2-D outline at height z."""
    lo_best, hi_best = None, None
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        if abs(z0 - z1) < 1e-9:
            if abs(z - z0) < 1e-6:
                lo_best = min(x0, x1) if lo_best is None else min(lo_best, x0, x1)
                hi_best = max(x0, x1) if hi_best is None else max(hi_best, x0, x1)
            continue
        lo, hi = min(z0, z1), max(z0, z1)
        if lo <= z <= hi:
            t = (z - z0) / (z1 - z0)
            v = x0 + (x1 - x0) * t
            lo_best = v if lo_best is None else min(lo_best, v)
            hi_best = v if hi_best is None else max(hi_best, v)
    if lo_best is None:
        return (420.0, 470.0)
    return (lo_best, hi_best)


def rr_ring(cx, cz, hx, hz, r, y, n=6):
    """Rounded rectangle in the XZ plane at depth y (a loft ring)."""
    r = min(r, hx * 0.95, hz * 0.95)
    pts = []
    for (dx, dz, a0) in ((hx - r, hz - r, 0.0), (-hx + r, hz - r, 90.0),
                         (-hx + r, -hz + r, 180.0), (hx - r, -hz + r, 270.0)):
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((cx + dx + r * math.cos(a), y, cz + dz + r * math.sin(a)))
    return pts


def tube(p, pts, radii, segs=12):
    for i in range(len(pts) - 1):
        p.cyl(pts[i], pts[i + 1], radii[i], seg=segs, r2=radii[i + 1])


def arc(center, radius, a0, a1, n):
    """n+1 points on an arc about the X axis (a finger wrapping a surface)."""
    out = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / float(n))
        out.append((center[0], center[1] + radius * math.cos(a),
                    center[2] + radius * math.sin(a)))
    return out


def build_right_hand(mat):
    """Right glove clamped round the pistol grip.  side = +1."""
    p = L.Part('Hand_R', mat)
    poly = r3_prof.GRIP
    side = 1.0

    ZC = -78.0
    lo, hi = span(ZC, poly)
    CX = (lo + hi) * 0.5
    HX = (hi - lo) * 0.5

    # ---- palm: a rounded slab pressed flat on the +Y flank -------------
    # Deliberately a little larger than the grip section so the grip
    # disappears INTO the hand instead of poking through it.
    palm = [
        rr_ring(CX + 2.0, ZC + 2.0, HX * 0.80, 30.0, 12.0, side * 13.0),
        rr_ring(CX + 2.0, ZC, HX * 0.95, 34.0, 14.0, side * 19.0),
        rr_ring(CX + 3.0, ZC - 2.0, HX * 0.93, 34.0, 15.0, side * 28.0),
        rr_ring(CX + 7.0, ZC - 7.0, HX * 0.74, 27.0, 14.0, side * 35.0),
    ]
    p.loft(palm, cap_start=True, cap_end=True)

    # ---- fingers: one arc per finger, pitch 16.5 on an 8.8 radius -------
    pitch = 16.5
    z0 = ZC + pitch * 1.5
    for k in range(4):
        z = z0 - pitch * k
        flo, fhi = span(z, poly)
        r = 8.8 - 0.30 * k
        cx = flo - 2.0
        cz = z + 3.0
        pts = [(CX - HX * 0.45, side * 26.0, z)]
        pts = pts + arc((cx, side * 17.0, cz), 15.0, 0.0, 62.0, 2)
        pts = pts + arc((cx, side * 4.0, cz), 15.0, 90.0, 175.0, 3)
        pts.append((cx + 9.0, -side * 12.0, z + 2.0))
        radii = [r] * (len(pts) - 1) + [r * 0.78]
        tube(p, pts, radii)

    # ---- thumb: rides the back of the grip toward the safety -----------
    lo_t, hi_t = span(-52.0, poly)
    tube(p, [(hi_t - 14.0, side * 30.0, -56.0),
             (hi_t - 4.0, side * 32.0, -46.0),
             (hi_t - 12.0, side * 30.0, -36.0),
             (lo_t + 32.0, side * 22.0, -30.0),
             (lo_t + 18.0, side * 12.0, -28.0)],
         [10.6, 10.2, 9.4, 8.6, 7.4])

    return p.build(smooth=True, angle=40, bevel=2.8, bevel_seg=3)


def build_left_hand(mat):
    """Left glove on the handguard, thumb over the top (C-clamp)."""
    p = L.Part('Hand_L', mat)
    side = -1.0
    XC, ZC = 156.0, -8.0

    palm = [
        rr_ring(XC, ZC, 22.0, 18.0, 9.0, side * 24.0),
        rr_ring(XC, ZC, 30.0, 26.0, 12.0, side * 31.0),
        rr_ring(XC, ZC, 32.0, 28.0, 13.0, side * 39.0),
        rr_ring(XC + 5.0, ZC - 2.0, 26.0, 23.0, 13.0, side * 45.0),
    ]
    p.loft(palm, cap_start=True, cap_end=True)

    pitch = 16.5
    for k in range(4):
        x = XC - pitch * 1.5 + pitch * k
        r = 8.8 - 0.30 * k
        cz = -30.0
        pts = [(x, side * 38.0, -18.0)]
        pts = pts + arc((x, side * 30.0, cz), 15.0, 0.0, 70.0, 2)
        pts = pts + arc((x, side * 14.0, cz), 15.0, 90.0, 180.0, 3)
        pts.append((x + 1.0, -side * 2.0, -44.0))
        radii = [r] * (len(pts) - 1) + [r * 0.78]
        tube(p, pts, radii)

    # ---- thumb over the top --------------------------------------------
    tube(p, [(XC + 22.0, side * 42.0, 6.0),
             (XC + 8.0, side * 38.0, 22.0),
             (XC - 10.0, side * 28.0, 32.0),
             (XC - 28.0, side * 12.0, 35.0)],
         [10.4, 9.8, 9.0, 7.6])

    return p.build(smooth=True, angle=40, bevel=2.8, bevel_seg=3)


def main():
    for nm in ('Hand_R', 'Hand_L'):
        ob = bpy.data.objects.get(nm)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.name.startswith('Hand_R') or me.name.startswith('Hand_L'):
            bpy.data.meshes.remove(me)

    mat = bpy.data.materials.get('M_Grip')
    if mat is None:
        raise SystemExit('M_Grip missing - run r3_make.py first')

    r = build_right_hand(mat)
    l = build_left_hand(mat)
    coll = bpy.data.collections.get('Geo')
    for ob in (r, l):
        for c in ob.users_collection:
            c.objects.unlink(ob)
        (coll or bpy.context.scene.collection).objects.link(ob)
        ob['grp'] = 'BODY'
        print('%-8s verts %4d  faces %4d' % (ob.name, len(ob.data.vertices),
                                             len(ob.data.polygons)))

    bpy.ops.wm.save_mainfile()
    print('SAVED', bpy.data.filepath)


if __name__ == '__main__':
    main()
