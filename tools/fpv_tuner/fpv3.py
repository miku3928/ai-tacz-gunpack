# -*- coding: utf-8 -*-
"""Offline first person preview that follows the engine byte-for-byte.

Chain (AnimateGeoItemRenderer.renderFirstPerson):
    pose = T(0,1.5,0) . Rz(180) . [ translate(0,1.5,0) . Minv . translate(0,-1.5,0) ]
    Minv = getPositioningNodeInverse(path to idle_view)  (walked leaf -> root)
and then per bone  world = W[bone] . baked_vertex   (PolyMesh bakes pos relative
to the bone pivot and negates Y).
"""
import sys, os, json, math
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fk2

def T(x, y, z):
    M = np.eye(4); M[:3, 3] = (x, y, z); return M

def Rz(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[0,0], M[0,1], M[1,0], M[1,1] = c, -s, s, c; return M

def Rx(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[1,1], M[1,2], M[2,1], M[2,2] = c, -s, s, c; return M

def Ry(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[0,0], M[0,2], M[2,0], M[2,2] = c, s, -s, c; return M

def path_to(by, leaf):
    p = []
    n = leaf
    while n is not None:
        p.append(by[n]); n = by[n].get('parent')
    return list(reversed(p))

def positioning_inverse(geo, leaf='idle_view'):
    by = {b['name']: b for b in geo['bones']}
    if leaf not in by:
        leaf = 'idle_view'
    M = np.eye(4)
    for part in reversed(path_to(by, leaf)):
        rot = part.get('rotation', [0, 0, 0])
        M = M @ Rx(rot[0]) @ Ry(rot[1]) @ Rz(rot[2])
        lp = fk2.local_pivot(part, by) / 16.0
        if part.get('parent') is not None:
            M = M @ T(-lp[0], -lp[1], -lp[2])
        else:
            M = M @ T(-lp[0], 1.5 - lp[1], -lp[2])
    return M

def pose_matrix(geo):
    Minv = positioning_inverse(geo)
    return T(0,1.5,0) @ Rz(180) @ T(0,1.5,0) @ Minv @ T(0,-1.5,0)

def baked(geo, bone):
    piv = np.array(bone.get('pivot', [0,0,0]), float)
    pm = bone['poly_mesh']
    pos = np.array(pm['positions'], float)
    v = (pos - piv) / 16.0
    v[:,1] = -v[:,1]
    return v

def cube_tris(bone, cube, Wm, M):
    """Box faces of a Bedrock cube, in the same baked frame as poly_mesh."""
    piv = np.array(bone.get('pivot', [0,0,0]), float)
    o = np.array(cube['origin'], float)
    s = np.array(cube['size'], float)
    infl = cube.get('inflate', 0.0)
    lo = o - infl; hi = o + s + infl
    rot = cube.get('rotation')
    Rc = np.eye(4)
    if rot:
        ctr = o + s * 0.5
        Rc = T(*ctr) @ Rx(rot[0]) @ Ry(rot[1]) @ Rz(rot[2]) @ T(*(-ctr))
    # Bedrock cube space: y grows downward, so origin is the *top* corner
    corners = []
    for zi in (0, 1):
        for yi in (0, 1):
            for xi in (0, 1):
                p = np.array([lo[0] + s[0]*xi + infl*xi*0, lo[1] + s[1]*yi, lo[2] + s[2]*zi])
                p = np.array([lo[0] if xi == 0 else hi[0],
                              lo[1] if yi == 0 else hi[1],
                              lo[2] if zi == 0 else hi[2]])
                q = (Rc @ np.array([p[0], p[1], p[2], 1.0]))[:3]
                corners.append((q - piv) / 16.0)
    v = np.array(corners)
    v[:,1] = -v[:,1]
    F = [(0,1,3,2), (4,6,7,5), (0,4,5,1), (2,3,7,6), (0,2,6,4), (1,5,7,3)]
    m = M @ Wm[bone['name']]
    out = []
    for f in F:
        w = v[list(f)]
        w = (m[:3,:3] @ w.T).T + m[:3,3]
        out.append(w[:3]); out.append(w[[0,2,3]])
    return out


def render(geofile, out, W=900, H=506, fov=70.0, anim=None, bg=(24,26,30)):
    G = json.load(open(geofile, encoding='utf-8'))['minecraft:geometry'][0]
    Wm = fk2.worlds(G, anim)
    M = pose_matrix(G)
    by = {b['name']: b for b in G['bones']}
    tris = []
    for b in G['bones']:
        if 'cubes' in b:
            for c in b['cubes']:
                tris.extend(cube_tris(b, c, Wm, M))
        if 'poly_mesh' not in b: continue
        v = baked(G, b)
        w = (M @ Wm[b['name']])[:3,:3] @ v.T + (M @ Wm[b['name']])[:3,3:4]
        w = w.T
        for poly in b['poly_mesh']['polys']:
            idx = [c[0] for c in poly]
            if len(idx) == 4 and idx[3] == idx[0]: idx = idx[:3]
            for i in range(1, len(idx)-1):
                tris.append(w[[idx[0], idx[i], idx[i+1]]])
    img = Image.new('RGB', (W, H), bg)
    zb = np.full((H, W), 1e9, float)
    px = np.array(img)
    f = 1.0 / math.tan(math.radians(fov) * 0.5)
    asp = W / float(H)
    light = np.array([0.4, 0.8, 0.45]); light /= np.linalg.norm(light)
    for tri in tris:
        z = tri[:,2]
        if (z > -0.05).any(): continue
        sx = (tri[:,0] * f / asp / -z * 0.5 + 0.5) * W
        sy = (-tri[:,1] * f / -z * 0.5 + 0.5) * H
        minx, maxx = int(max(0, math.floor(sx.min()))), int(min(W-1, math.ceil(sx.max())))
        miny, maxy = int(max(0, math.floor(sy.min()))), int(min(H-1, math.ceil(sy.max())))
        if minx > maxx or miny > maxy: continue
        n = np.cross(tri[1]-tri[0], tri[2]-tri[0])
        ln = np.linalg.norm(n)
        if ln < 1e-12: continue
        n /= ln
        shade = 0.35 + 0.65 * abs(float(n @ light))
        col = np.array([int(150*shade), int(152*shade), int(156*shade)])
        d = (sy[1]-sy[2])*(sx[0]-sx[2]) + (sx[2]-sx[1])*(sy[0]-sy[2])
        if abs(d) < 1e-9: continue
        Xs, Ys = np.meshgrid(np.arange(minx, maxx+1), np.arange(miny, maxy+1))
        l0 = ((sy[1]-sy[2])*(Xs-sx[2]) + (sx[2]-sx[1])*(Ys-sy[2])) / d
        l1 = ((sy[2]-sy[0])*(Xs-sx[2]) + (sx[0]-sx[2])*(Ys-sy[2])) / d
        l2 = 1.0 - l0 - l1
        m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not m.any(): continue
        zz = l0*1.0/z[0] + l1*1.0/z[1] + l2*1.0/z[2]
        zz = 1.0/np.where(np.abs(zz) < 1e-12, 1e-12, zz)
        sub = zb[miny:maxy+1, minx:maxx+1]
        upd = m & (zz < sub)
        if not upd.any(): continue
        sub[upd] = zz[upd]
        for c in range(3):
            ch = px[miny:maxy+1, minx:maxx+1, c]
            ch[upd] = col[c]
    Image.fromarray(px).save(out)
    # bbox in view
    allv = np.concatenate([t.reshape(-1,3) for t in tris], 0) if tris else np.zeros((1,3))
    print('%-28s tris %6d  view bbox x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f'
          % (os.path.basename(geofile), len(tris), allv[:,0].min(), allv[:,0].max(),
             allv[:,1].min(), allv[:,1].max(), allv[:,2].min(), allv[:,2].max()))

if __name__ == '__main__':
    render(sys.argv[1], sys.argv[2])
