# -*- coding: utf-8 -*-
"""TaCZ Bedrock FK, exactly as BedrockModel.convertPivot + BedrockPart implement it.

convertPivot(bone, i):
    if bone.parent is None:  i==1 ? 24 - pivot.y : pivot.x/z
    else:                    i==1 ? parent.pivot.y - pivot.y : pivot.x - parent.pivot.x

local(bone) = T(offset/16) . T(convertPivot/16) . Rz . Ry . Rx . S
  where offset comes from the animation 'position' channel, written as
  (px, -py, pz) and DIVIDED BY 16 (ModelTranslateListener.update negates Y;
  Animations.writeBedrockTranslation multiplies every keyframe by 0.0625f
  before storing it, so 1 JSON unit == 1/16 block == 1 model unit).
world(bone) = world(parent) . local(bone)

The /16 on offset was missing until 2026-10-22: the old file used T(offset)
directly, i.e. it read the JSON value as BLOCKS and therefore showed every
translated bone 16x too far.  Rest poses were unaffected (offset 0), which is
why all the pivot solving done on top of this file still stands.
"""
import math
import numpy as np

def T(x, y, z):
    M = np.eye(4); M[:3, 3] = (x, y, z); return M

def Rx(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[1,1], M[1,2], M[2,1], M[2,2] = c, -s, s, c; return M

def Ry(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[0,0], M[0,2], M[2,0], M[2,2] = c, s, -s, c; return M

def Rz(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[0,0], M[0,1], M[1,0], M[1,1] = c, -s, s, c; return M

def local_pivot(bone, by):
    p = np.array(bone.get('pivot', [0, 0, 0]), float)
    par = bone.get('parent')
    if par is None:
        return np.array([p[0], 24.0 - p[1], p[2]])
    q = np.array(by[par].get('pivot', [0, 0, 0]), float)
    return np.array([p[0] - q[0], q[1] - p[1], p[2] - q[2]])

def local(bone, by, chan):
    rot = list(chan.get('rotation', bone.get('rotation', [0, 0, 0])))
    pos = list(chan.get('position', [0, 0, 0]))
    scl = list(chan.get('scale', [1, 1, 1]))
    off = np.array([pos[0], -pos[1], pos[2]], float) / 16.0
    M = T(*off) @ T(*(local_pivot(bone, by) / 16.0)) @ Rz(rot[2]) @ Ry(rot[1]) @ Rx(rot[0])
    return M @ np.diag([scl[0], scl[1], scl[2], 1.0])

def worlds(geo, anim=None):
    bones = geo['bones']; by = {b['name']: b for b in bones}
    ch = (anim or {}).get('bones', {})
    out = {}
    def walk(b):
        if b['name'] in out: return out[b['name']]
        p = b.get('parent')
        M = (walk(by[p]) if p else np.eye(4)) @ local(b, by, ch.get(b['name'], {}))
        out[b['name']] = M
        return M
    for b in bones: walk(b)
    return out

def at(W, name):
    return W[name][:3, 3] * 16.0
