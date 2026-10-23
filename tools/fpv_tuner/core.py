# -*- coding: utf-8 -*-
"""core.py -- 第一人称定位的数学与几何，逐行对齐 TaCZ 1.20.1-1.1.8 的真实代码。

这个文件里每一条规则都能指到具体的 Java 行号，不是猜的：

  加载期（BedrockModel.java）
    convertPivot(bones, i)   有父：i==1 -> parent.pivot.y - pivot.y，否则 pivot - parent.pivot
                             无父：i==1 -> 24 - pivot.y，否则 pivot
    convertOrigin(bone,cube,i)  i==1 -> bone.pivot.y - origin.y - size.y，否则 origin - bone.pivot
    convertRotation(deg) = deg * pi/180

  渲染期（GunItemRendererWrapper.renderFirstPerson:202-206）
    translate(0, 1.5, 0)
    rotate Z 180°                      <- 基岩模型翻转
    FirstPersonRenderGunEvent.applyFirstPersonPositioningTransform:208-210
        translate(0, 1.5, 0); mulPose(M); translate(0, -1.5, 0)
    M = getPositioningNodeInverse(idle_view 链)

  把这三段乘开，两个 1.5 对消、Rz(180) 与 root 的 "1.5 - y/16" 特判也对消，
  最后就是一个干净式子（verify1.py 用照抄字节码的写法核对过，误差 1.6e-16）：

      P = Rz(180°) · inv(W)

  W 是定位组骨骼的世界矩阵，沿 root -> leaf 累乘 T(pos/16) · Rz · Ry · Rx。

  于是"调 pivot"到"屏幕上移动"是一条直线，实测（sens.py，aa12）：
      pivot.x += 1  ->  视空间 x += 0.0625   即往右
      pivot.y += 1  ->  视空间 y -= 0.0625   即往下
      pivot.z += 1  ->  视空间 z -= 0.0625   即往近处
  1 模型单位 = 1/16 方块，和 Blockbench 里看到的数字完全一致。
"""
import math

import numpy as np

# ---------------------------------------------------------------- 矩阵

def T(x, y, z):
    M = np.eye(4)
    M[:3, 3] = (x, y, z)
    return M


def Rx(d):
    """度。传弧度进来会静默把旋转缩小 57 倍——这是上一版踩过的坑。"""
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[1, 1], M[1, 2], M[2, 1], M[2, 2] = c, -s, s, c
    return M


def Ry(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[0, 0], M[0, 2], M[2, 0], M[2, 2] = c, s, -s, c
    return M


def Rz(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    M = np.eye(4); M[0, 0], M[0, 1], M[1, 0], M[1, 1] = c, -s, s, c
    return M


def euler(rot):
    return Rz(rot[2]) @ Ry(rot[1]) @ Rx(rot[0])


# ---------------------------------------------------------------- 骨骼

VIEW_PARENTS = ('views', 'view')
IDLE, IRON = 'idle_view', 'iron_view'


def by_name(geo):
    return {b['name']: b for b in geo['bones']}


def chain(geo_by, leaf):
    """root -> leaf。找不到就返回空。"""
    out, n, guard = [], leaf, 0
    while n and n in geo_by and guard < 512:
        out.append(geo_by[n])
        n = geo_by[n].get('parent')
        guard += 1
    return list(reversed(out))


def convert_pivot(bone, geo_by):
    p = list(bone.get('pivot') or [0, 0, 0])
    par = bone.get('parent')
    if par and par in geo_by:
        q = list(geo_by[par].get('pivot') or [0, 0, 0])
        return [p[0] - q[0], q[1] - p[1], p[2] - q[2]]
    return [p[0], 24.0 - p[1], p[2]]


def convert_origin(bone, cube):
    p = list(bone.get('pivot') or [0, 0, 0])
    o = list(cube.get('origin') or [0, 0, 0])
    s = list(cube.get('size') or [0, 0, 0])
    return [o[0] - p[0], p[1] - o[1] - s[1], o[2] - p[2]]


def bone_local(bone, geo_by):
    pos = convert_pivot(bone, geo_by)
    rot = list(bone.get('rotation') or [0, 0, 0])
    return T(pos[0] / 16.0, pos[1] / 16.0, pos[2] / 16.0) @ euler(rot)


def bone_world(geo_by, leaf):
    M = np.eye(4)
    for b in chain(geo_by, leaf):
        M = M @ bone_local(b, geo_by)
    return M


ALIASES = {'idle': IDLE, 'iron': IRON, IDLE: IDLE, IRON: IRON}


def bone_name(which):
    return ALIASES.get(which, which)


def resolve_view(geo_by, want=None):
    """want 可以是 'idle' / 'iron' 这样的别名，也可以是骨骼全名。

    显式指定但骨骼不存在时返回 None，**不回退到另一个定位组**——
    回退会让"机瞄"标签页悄悄显示腰射的画面，这种错最难查。
    """
    if want:
        name = bone_name(want)
        return name if name in geo_by else None
    for n in (IDLE, IRON):
        if n in geo_by:
            return n
    for parent in VIEW_PARENTS:
        if parent in geo_by:
            for b in geo_by.values():
                if b.get('parent') == parent and b['name'].endswith('_view'):
                    return b['name']
    return None


def view_matrix(geo, leaf=None):
    """P = Rz(180) · inv(W_leaf)。这就是"眼睛在哪、朝哪"的完整答案。"""
    geo_by = by_name(geo)
    leaf = resolve_view(geo_by, leaf)
    if leaf is None:
        return np.eye(4)
    return Rz(180.0) @ np.linalg.inv(bone_world(geo_by, leaf))


def view_bones(geo):
    geo_by = by_name(geo)
    return [n for n in geo_by if n.endswith('_view')]


# ---------------------------------------------------------------- 几何

CUBE_FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
              (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]

HAND_KEYS = ('lefthand', 'righthand', 'left_hand', 'right_hand', 'hand', 'arm')


def is_hand(name):
    n = (name or '').lower()
    return any(k in n for k in HAND_KEYS)


def cube_verts(bone, cube):
    """模型单位，已按 TaCZ 的 convertOrigin 转成"相对骨骼枢轴"。"""
    o = convert_origin(bone, cube)
    s = list(cube.get('size') or [0, 0, 0])
    infl = float(cube.get('inflate') or 0.0)
    lo = np.array(o, float) - infl
    hi = lo + np.array(s, float) + 2.0 * infl
    v = []
    for zi in (0, 1):
        for yi in (0, 1):
            for xi in (0, 1):
                v.append([lo[0] if xi == 0 else hi[0],
                          lo[1] if yi == 0 else hi[1],
                          lo[2] if zi == 0 else hi[2]])
    return np.array(v, float)


def poly_mesh_verts(bone, pm):
    """poly_mesh 的局部顶点与三角面。

    TML（Tacz Mesh Loader）的 PolyMesh 构造器里写得很死（字节码逐行核对过）：

        bakedX = ( pos.x - pivot.x) / 16
        bakedY = -(pos.y - pivot.y) / 16      <- y 取反
        bakedZ = ( pos.z - pivot.z) / 16

    然后交给 TaczPartAdapter.applyTransform，也就是 BedrockPart 那套
    translate(offset)·translate(x/16,y/16,z/16)·Rz·Ry·Rx·scale。
    所以 poly_mesh 和 cube 走的是**完全相同的下游管线**，区别只在
    "顶点相对骨骼枢轴怎么烘"这一步：cube 用 convertOrigin，poly_mesh 用上式。

    早先把它当成"模型绝对坐标、直接乘 P"是错的 —— 那样枪会缩到 1/1.55，
    而且不同骨骼的网格会互相错位。真实截图叠加验证过：只有这一种烘法
    能和游戏里的画面严丝合缝对上。
    """
    pos = np.asarray(pm.get('positions') or [], float)
    if pos.size == 0:
        return None, []
    pos = pos.reshape(-1, 3)
    piv = np.asarray(bone.get('pivot') or [0, 0, 0], float)
    v = (pos - piv) * np.array([1.0, -1.0, 1.0]) / 16.0

    polys = pm.get('polys') or []
    # 绝大多数包是清一色四角面，走这条路能把 12304 次 Python 循环省掉
    try:
        arr = np.asarray(polys, dtype=np.int64)
        if arr.ndim == 3 and arr.shape[2] == 3 and arr.shape[1] in (3, 4):
            idx = arr[:, :, 0]
            if idx.shape[1] == 4:
                a, b, cc, d = idx[:, 0], idx[:, 1], idx[:, 2], idx[:, 3]
                # 三角面在 TML 里是把首角再补一遍凑成四角，第二个三角会退化
                # （a, cc, a），这里直接不生成它，能省掉一万多个空三角形。
                keep = d != a
                tris = np.concatenate([
                    np.stack([a, b, cc], 1), np.stack([a, cc, d], 1)[keep]])
            else:
                tris = idx
            return v, tris.astype(np.int32)
    except (ValueError, TypeError):
        pass

    tris = []
    for poly in polys:
        try:
            idx = [int(k[0]) for k in poly]
        except (TypeError, IndexError, ValueError):
            continue
        # TML 只认 3 角面和 4 角面（其他直接丢），4 角面按扇形三角化
        if len(idx) >= 4 and idx[-1] == idx[0]:
            idx = idx[:-1]
        if len(idx) not in (3, 4):
            continue
        for i in range(1, len(idx) - 1):
            tris.append((idx[0], idx[i], idx[i + 1]))
    return v, np.asarray(tris, dtype=np.int32) if tris else np.zeros((0, 3), np.int32)


def collect_model(geo, skip_hands=True, only=None):
    """顶点已经在"模型空间"（骨骼变换已乘），只差最后那一个 P。

    这样做的理由很实在：改 idle_view 的 pivot/rotation 只会改变 P，
    不会改变任何几何骨骼的 W。所以模型空间那一步可以缓存，拖滑块时
    只需要再做一次 4x4 变换 —— 从 84ms 降到十几毫秒。
    """
    geo_by = by_name(geo)
    V, TR, kinds = [], [], {'cubes': 0, 'polys': 0}
    for b in geo['bones']:
        if skip_hands and is_hand(b['name']):
            continue
        if only and b['name'] not in only:
            continue
        W = bone_world(geo_by, b['name'])
        for c in (b.get('cubes') or []):
            v = cube_verts(b, c) / 16.0
            base = sum(len(x) for x in V)
            V.append((W[:3, :3] @ v.T).T + W[:3, 3])
            kinds['cubes'] += 1
            for f in CUBE_FACES:
                a, bb, cc, d = [base + i for i in f]
                TR.append((a, bb, cc)); TR.append((a, cc, d))
        pm = b.get('poly_mesh')
        if pm and pm.get('positions'):
            v, tris = poly_mesh_verts(b, pm)
            if v is not None and len(v) and len(tris):
                base = sum(len(x) for x in V)
                V.append((W[:3, :3] @ v.T).T + W[:3, 3])
                kinds['polys'] += 1
                TR.append(np.asarray(tris, np.int32) + base)
    if not V:
        return None, [], kinds
    flat = []
    for t in TR:
        if isinstance(t, np.ndarray):
            flat.append(t.reshape(-1, 3))
        else:
            flat.append(np.asarray(t, np.int32).reshape(-1, 3))
    tri = np.vstack(flat) if flat else np.zeros((0, 3), np.int32)
    return np.vstack(V), tri, kinds


def collect(geo, leaf=None, skip_hands=True, only=None):
    """-> (视空间顶点，三角形，来源统计)。"""
    V, TR, kinds = collect_model(geo, skip_hands, only)
    if V is None:
        return None, [], kinds
    P = view_matrix(geo, leaf)
    return (P[:3, :3] @ V.T).T + P[:3, 3], TR, kinds


# ---------------------------------------------------------------- 投影

FOV = 70.0
NEAR = 0.02


def project(V, w, h, fov=FOV):
    z = -V[:, 2]
    t = math.tan(math.radians(fov) * 0.5)
    ok = z > NEAR
    safe = np.where(ok, z, 1.0)
    sx = (V[:, 0] / (safe * t * (w / float(h))) * 0.5 + 0.5) * w
    sy = (0.5 - V[:, 1] / (safe * t) * 0.5) * h
    return sx, sy, ok


def screen_box(geo, w, h, fov=FOV, leaf=None):
    V, _, _ = collect(geo, leaf)
    if V is None:
        return None
    sx, sy, ok = project(V, w, h, fov)
    if not ok.any():
        return None
    return (float(sx[ok].min()), float(sx[ok].max()),
            float(sy[ok].min()), float(sy[ok].max()))