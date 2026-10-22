"""r3_att_geo.py - turn the gun's *_default bones into standalone attachments.

TaCZ places an attachment at the world position of the gun's <type>_pos bone and
draws the attachment model in that bone's space, so an attachment model has to be
authored with its mounting interface sitting on the origin.  Our gun geometry is
in absolute model coordinates, therefore a part becomes an attachment by simply
subtracting its mount pivot from every vertex - no re-modelling, no second source
of truth, and the installed part lands exactly where the built-in one was.

The scope is the exception: a scope is not just a shape, it is a set of NODES
that TaCZ looks up by name when you aim down it.  A body without them renders as
a solid tube glued to the camera - the "screen smeared over by a grey slab"
failure.  So the scope attachment also gets, authored in the same mount space:

    scope_body    the tube itself (our geometry)
    ocular        the aperture disc - drawn to the STENCIL buffer only, it is
                  the hole the world is seen through
    ocular_ring   the annulus just outside that hole (hides the stencil edge)
    division      the reticle, a thin cross floating inside the tube
    scope_view    empty bone whose pivot IS the eye point

The optic was bored through (r = 11 mm) in work/bore_optic.py, otherwise the
stencil hole would look straight into a solid metal end cap.

Input : work/tacz/geo.json
Output: work/tacz/att/<id>_geo.json

Run with plain python (no Blender needed):
    <bundled python> r3_att_geo.py
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
TACZ = os.path.join(ROOT, 'work', 'tacz')
OUT = os.path.join(TACZ, 'att')

# must match r3_export_tacz.py
U = 52.4476          # TaCZ model units per metre
AXIS_Z_MM = 76.2     # optical axis height above the bore, in Blender mm
BORE_R = 11.0        # bore radius in Blender mm (see work/bore_optic.py)

# ---- sight picture -------------------------------------------------------
# The stencil hole is NOT the bore.  TaCZ draws the world first and then the gun
# on top, cutting the gun away wherever the "ocular" bone is; whatever is left
# around the hole is the black frame the player sees.  The frame is therefore
# (rear housing silhouette - hole), and with the hole at the 11 mm bore the
# housing's rear face (r 21.8 mm) showed a band as wide as the picture itself.
# Official scopes keep the hole at 1.01-1.13x the visible body: the hole is
# nearly the full tube and the bezel is a hairline.
#
# Our rear housing measures r 1.1434 model units (work/scopeprof.py), so the
# hole goes to 1.02, i.e. 1.12x the hole radius against a 1.1434 housing - the
# same hairline bezel the official scopes have (they measure 1.01-1.13).
APERTURE_R = 1.02    # model units
RING_OUTER = 1.1434  # = the rear housing radius; anything bigger floats free

# attachment id -> (source bone on the gun, mount bone whose pivot is the origin)
SPEC = [
    ('muzzle_std', 'muzzle_default', 'muzzle_pos'),
    ('scope_std', 'sight', 'scope_pos'),
    ('stock_std', 'stock_default', 'stock_pos'),
]

# material palette indices (materials are sorted by name in the exporter)
UV_STEEL = (2 * 13 + 1) / 32.0     # M_Steel  150,152,156 - the reticle
UV_DARK = (2 * 1 + 1) / 32.0       # M_Dark    24, 24, 26 - the ocular ring


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, separators=(',', ':'))
        f.write('\n')


class Builder(object):
    """Accumulates poly_mesh arrays; positions and normals dedupe separately so
    a corner is [posIdx, nrmIdx, uvIdx] with the two indices unrelated."""

    def __init__(self):
        self.pos = []
        self.nrm = []
        self.uvs = []
        self.polys = []
        self._pk = {}
        self._nk = {}

    def vert(self, p, n):
        pk = (round(p[0], 5), round(p[1], 5), round(p[2], 5))
        nk = (round(n[0], 3), round(n[1], 3), round(n[2], 3))
        pi = self._pk.get(pk)
        if pi is None:
            pi = len(self.pos)
            self._pk[pk] = pi
            self.pos.append([pk[0], pk[1], pk[2]])
        ni = self._nk.get(nk)
        if ni is None:
            ni = len(self.nrm)
            self._nk[nk] = ni
            self.nrm.append([nk[0], nk[1], nk[2]])
        return pi, ni

    def uv(self, u):
        for i, v in enumerate(self.uvs):
            if abs(v[0] - u) < 1e-9:
                return i
        self.uvs.append([round(u, 6), 0.5])
        return len(self.uvs) - 1

    def poly(self, pts, uvi, n=(0.0, 0.0, 1.0)):
        corners = [self.vert(p, n) for p in pts]
        self.polys.append([[pi, ni, uvi] for pi, ni in corners])

    def as_poly_mesh(self):
        return {
            'normalized_uvs': True,
            'positions': self.pos,
            'normals': self.nrm,
            'uvs': self.uvs,
            'polys': self.polys,
        }


def ring_pts(cx, cy, z, r, seg):
    return [(cx + r * math.cos(2 * math.pi * i / seg),
             cy + r * math.sin(2 * math.pi * i / seg), z) for i in range(seg)]


def add_disc(b, cx, cy, z, r, seg, uvi):
    """Filled circle facing +z (the eye side)."""
    pts = ring_pts(cx, cy, z, r, seg)
    for i in range(seg):
        b.poly([(cx, cy, z), pts[i], pts[(i + 1) % seg]], uvi)


def add_annulus(b, cx, cy, z, r_in, r_out, seg, uvi):
    inner = ring_pts(cx, cy, z, r_in, seg)
    outer = ring_pts(cx, cy, z, r_out, seg)
    for i in range(seg):
        j = (i + 1) % seg
        b.poly([inner[i], outer[i], outer[j], inner[j]], uvi)


def add_bar(b, x0, x1, y0, y1, z, uvi):
    b.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], uvi)


def scope_nodes(pm, pivot, desc):
    """The five bones TaCZ's scope renderer looks for, in mount space."""
    # optical axis: the same P3() mapping the exporter uses, minus the mount
    axis_y = (AXIS_Z_MM * 0.001) * U + 12.0 - pivot[1]
    axis_x = 0.0
    bore = BORE_R * 0.001 * U

    body = Builder()
    body.pos = [list(p) for p in pm['positions']]
    body.nrm = [list(n) for n in pm['normals']]
    body.uvs = [list(u) for u in pm['uvs']]
    body.polys = [list(p) for p in pm['polys']]
    for p in body.pos:
        body._pk[(p[0], p[1], p[2])] = len(body._pk)
    for n in body.nrm:
        body._nk[(n[0], n[1], n[2])] = len(body._nk)

    z_rear = max(p[2] for p in body.pos)
    z_front = min(p[2] for p in body.pos)

    # ---- ocular: the stencil hole -------------------------------------
    oc = Builder()
    oc.uvs = body.uvs
    add_disc(oc, axis_x, axis_y, z_rear - 0.006, APERTURE_R, 32, body.uv(body.uvs[0][0]))

    # ---- ocular_ring: the bezel just outside it -----------------------
    rg = Builder()
    rg.uvs = body.uvs
    add_annulus(rg, axis_x, axis_y, z_rear - 0.006, APERTURE_R, RING_OUTER, 32,
                rg.uv(UV_DARK))

    # ---- division: reticle, floating 0.35 units inside the tube -------
    dv = Builder()
    dv.uvs = body.uvs
    uz = dv.uv(UV_STEEL)
    zr = z_rear - 0.35
    t = 0.018
    L = APERTURE_R * 0.80
    add_bar(dv, axis_x - L, axis_x + L, axis_y - t, axis_y + t, zr, uz)   # horizontal
    add_bar(dv, axis_x - t, axis_x + t, axis_y - L, axis_y + L, zr, uz)   # vertical
    # four short ticks either side of the cross centre
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_bar(dv, axis_x + sx * 0.30 - t * 0.6, axis_x + sx * 0.30 + t * 0.6,
                    axis_y + sy * 0.30 - t * 3.0, axis_y + sy * 0.30 + t * 3.0, zr, uz)

    bones = [
        {'name': 'scope_body', 'pivot': [0, 0, 0],
         'poly_mesh': body.as_poly_mesh()},
        {'name': 'ocular', 'pivot': [axis_x, axis_y, z_rear - 0.006],
         'poly_mesh': oc.as_poly_mesh()},
        {'name': 'ocular_ring', 'pivot': [axis_x, axis_y, z_rear],
         'poly_mesh': rg.as_poly_mesh()},
        {'name': 'division', 'pivot': [axis_x, axis_y, zr],
         'poly_mesh': dv.as_poly_mesh()},
        # Eye relief 5.3 units == 101 mm, which is what the official
        # scope_1873_6x uses (ocular z 4.25, scope_view z 10) and what makes the
        # aperture subtend ~6 degrees - a full sight picture with the classic
        # black vignette instead of a pin hole.
        {'name': 'scope_view', 'pivot': [round(axis_x, 5), round(axis_y, 5),
                                         round(z_rear + 5.3, 5)]},
    ]
    print('  scope axis y %.3f  bore r %.3f  z front %.3f  rear %.3f  eye %.3f'
          % (axis_y, bore, z_front, z_rear, z_rear + 5.3))
    return bones


def main():
    geo = load(os.path.join(TACZ, 'geo.json'))
    root = geo['minecraft:geometry'][0]
    bones = {b['name']: b for b in root['bones']}
    src_desc = root['description']

    for att_id, src, mount in SPEC:
        pm = bones[src].get('poly_mesh')
        if not pm:
            raise SystemExit('%s has no poly_mesh - export the gun first' % src)
        pivot = bones[mount]['pivot']
        pos = [[round(p[0] - pivot[0], 5),
                round(p[1] - pivot[1], 5),
                round(p[2] - pivot[2], 5)] for p in pm['positions']]
        xs = [p[0] for p in pos]
        ys = [p[1] for p in pos]
        zs = [p[2] for p in pos]
        moved = dict(pm)
        moved['positions'] = pos

        if att_id == 'scope_std':
            out_bones = scope_nodes(moved, pivot, src_desc)
        else:
            out_bones = [{
                # the root bone sits ON the mounting interface: if the game
                # ever rotates the position node the part swings about the
                # mount instead of about some arbitrary point in the middle
                'name': att_id,
                'pivot': [0, 0, 0],
                'poly_mesh': {
                    'normalized_uvs': pm['normalized_uvs'],
                    'positions': pos,
                    'normals': pm['normals'],
                    'uvs': pm['uvs'],
                    'polys': pm['polys'],
                },
            }]

        out = {
            'format_version': '1.12.0',
            'minecraft:geometry': [{
                'description': {
                    'identifier': 'geometry.%s' % att_id,
                    'texture_width': src_desc['texture_width'],
                    'texture_height': src_desc['texture_height'],
                    'visible_bounds_width': 4,
                    'visible_bounds_height': 3,
                    'visible_bounds_offset': [0, 0, 0],
                },
                'bones': out_bones,
            }],
        }
        path = os.path.join(OUT, '%s_geo.json' % att_id)
        dump(path, out)
        tris = sum(2 if len(poly) == 4 else 1 for poly in pm['polys'])
        print('%-12s from %-14s verts %5d  polys %5d  tris %5d  '
              'x %6.2f..%6.2f  y %6.2f..%6.2f  z %6.2f..%6.2f  %d bytes'
              % (att_id, src, len(pos), len(pm['polys']), tris,
                 min(xs), max(xs), min(ys), max(ys), min(zs), max(zs),
                 os.path.getsize(path)))


if __name__ == '__main__':
    main()
