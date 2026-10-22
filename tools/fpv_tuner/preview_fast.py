# -*- coding: utf-8 -*-
"""Fast offline first person preview, for interactive eye point tuning.

fpv3.render() re-bakes the whole mesh on every call and rasterises triangle by
triangle in numpy - fine for a one-off sheet, far too slow to drag a slider.  The
bone hierarchy is static here, so the vertex cloud in model space is computed
once and only the eye translation changes; drawing then goes through PIL's
polygon filler with a painter's sort.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fpv3
import fk2
from fpv3 import baked


class Previewer(object):
    def __init__(self, geofile):
        G = json.load(open(geofile, encoding='utf-8'))['minecraft:geometry'][0]
        self.skel = [{'name': b['name'], 'parent': b.get('parent'),
                      'pivot': b.get('pivot', [0, 0, 0])} for b in G['bones']]
        Wm = fk2.worlds(G)
        pts, tris, cols = [], [], []
        for b in G['bones']:
            base = len(pts)
            if 'cubes' in b:
                for c in b['cubes']:
                    for t in fpv3.cube_tris(b, c, Wm, np.eye(4)):
                        pts.extend(t)
                        tris.append((base, base + 1, base + 2))
                        cols.append((150, 152, 156))
                        base += 3
            if 'poly_mesh' not in b:
                continue
            v = baked(G, b)
            m = Wm[b['name']]
            w = (m[:3, :3] @ v.T).T + m[:3, 3]
            pts.extend(w)
            for poly in b['poly_mesh']['polys']:
                idx = [c[0] for c in poly]
                if len(idx) == 4 and idx[3] == idx[0]:
                    idx = idx[:3]
                for i in range(1, len(idx) - 1):
                    tris.append((base + idx[0], base + idx[i], base + idx[i + 1]))
                    cols.append((150, 152, 156))
        self.P = np.array(pts, float)
        self.T = np.array(tris, np.int32)
        self.C = np.array(cols, np.uint8)
        self.names = {b['name']: b for b in G['bones']}

    def pose(self, piv):
        G = {'bones': [dict(b) for b in self.skel]}
        for b in G['bones']:
            if b['name'] == 'idle_view':
                b['pivot'] = list(piv)
            if b['name'] == 'camera':
                b['pivot'] = [piv[0] - 0.25, piv[1] - 0.25, piv[2] - 0.75]
        return fpv3.pose_matrix(G)

    def render(self, piv, W=640, H=376, fov=70.0, bg=(22, 24, 28)):
        M = self.pose(piv)
        Q = (M[:3, :3] @ self.P.T).T + M[:3, 3]
        z = Q[:, 2]
        f = 1.0 / math.tan(math.radians(fov) * 0.5)
        asp = W / float(H)
        sx = (Q[:, 0] * f / asp / -z * 0.5 + 0.5) * W
        sy = (-Q[:, 1] * f / -z * 0.5 + 0.5) * H
        tri = self.T
        triz = z[tri]
        keep = (triz < -0.02).all(1)
        tri = tri[keep]
        if not len(tri):
            return Image.new('RGB', (W, H), bg)
        tz = triz[keep].mean(1)
        order = np.argsort(tz)          # far (very negative) first
        tri = tri[order]
        tz = tz[order]
        p0, p1, p2 = Q[tri[:, 0]], Q[tri[:, 1]], Q[tri[:, 2]]
        n = np.cross(p1 - p0, p2 - p0)
        ln = np.linalg.norm(n, axis=1)
        ln[ln < 1e-12] = 1.0
        n /= ln[:, None]
        light = np.array([0.35, 0.75, 0.55])
        light /= np.linalg.norm(light)
        sh = 0.30 + 0.70 * np.abs(n @ light)
        near = np.clip((-tz - 0.35) / 1.6, 0.0, 1.0)
        base = self.C[keep][order].astype(float)
        rgb = (base * sh[:, None] * (0.55 + 0.45 * near)[:, None]).astype(np.uint8)
        img = Image.new('RGB', (W, H), bg)
        d = ImageDraw.Draw(img)
        for i in range(len(tri)):
            a, b, c = tri[i]
            if min(z[a], z[b], z[c]) > -0.02:
                continue
            d.polygon([(sx[a], sy[a]), (sx[b], sy[b]), (sx[c], sy[c])],
                      fill=tuple(int(v) for v in rgb[i]))
        return img


def main():
    p = Previewer(sys.argv[1])
    piv = [float(v) for v in sys.argv[3].split(',')] if len(sys.argv) > 3 else [0, 16, 13]
    import time
    t = time.time()
    im = p.render(piv, W=640, H=376)
    print('render %.2fs  tris %d' % (time.time() - t, len(p.T)))
    im.save(sys.argv[2])


if __name__ == '__main__':
    main()
