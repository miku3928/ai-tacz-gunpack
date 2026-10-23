# -*- coding: utf-8 -*-
"""render.py -- 软件光栅预览。

目的不是好看，是让"枪在屏幕的哪儿"这个问题在拖滑块的十几毫秒里有答案。
用的是游戏自己的约定：模型单位 /16 = 方块，+y 朝上，眼睛在原点朝 -z，
FOV 70（MC 默认）。

为什么快：改 idle_view 的 pivot/rotation 只改变最后一个 4x4 矩阵 P，
几何骨骼的世界矩阵一点没变。所以 Scene 把"模型空间顶点"缓存下来，
每帧只做一次 P 变换 + 投影，亮度查表，坐标转成 list 直接喂给 PIL。
"""
import math

import numpy as np
from PIL import Image, ImageDraw

import core

BG = (24, 26, 30)
GRID = (40, 43, 49)

LIGHT = np.array([-0.42, 0.66, -0.62])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
BASE = np.array([168, 172, 178], float)

GHOST = (226, 92, 92)

# 亮度量化成 64 级查表。逐面调 numpy 的 clip/multiply 在 3 万面时要 170ms，
# 换成一次查表只剩几毫秒，而 64 级人眼分不出来。
LEVELS = 64
LUT = [tuple(int(v) for v in np.clip(BASE * (0.42 + 0.58 * (i / (LEVELS - 1.0))),
                                     0, 255))
       for i in range(LEVELS)]
LUT_FLAT = LUT[LEVELS // 3]


def shade(n):
    """单面着色。热路径走 faces_of 里的向量化版本，这个给外部用。"""
    if n is None:
        return LUT_FLAT
    d = float(n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])
    if d <= 0.0:
        return LUT[0]
    i = int(d * (LEVELS - 1))
    return LUT[i if i < LEVELS else LEVELS - 1]


class Scene(object):
    """一把枪在一个定位组下的可复用几何。"""

    def __init__(self, geo, leaf=None, skip_hands=True):
        self.geo = geo
        self.leaf = leaf
        self.V, self.TR, self.kinds = core.collect_model(geo, skip_hands)
        self.TRI = (np.asarray(self.TR, dtype=np.int32) if self.TR is not None
                    else np.zeros((0, 3), np.int32))
        self.depth = 1.0
        self.center = ((self.V.min(0) + self.V.max(0)) * 0.5
                       if self.V is not None and len(self.V) else np.zeros(3))

    @property
    def empty(self):
        return self.V is None or len(self.V) == 0

    def view(self, P):
        if self.V is None:
            return None
        return (P[:3, :3] @ self.V.T).T + P[:3, 3]


def faces_of(V, TRI, w, h, fov, min_area=0.6, max_faces=None):
    """筛出能画的三角形，按深度从远到近排好，亮度也算好。

    返回 (idx, depth, shade_idx, sx, sy)。idx 是三角形序号；sx/sy 是全部顶点
    的投影。调用方用 list 索引，画的时候一次 numpy 调用都不发。
    """
    if V is None or len(TRI) == 0:
        return None
    ia, ib, ic = TRI[:, 0], TRI[:, 1], TRI[:, 2]
    A, B, C = V[ia], V[ib], V[ic]
    n = np.cross(B - A, C - A)
    ln = np.linalg.norm(n, axis=1)
    ln[ln < 1e-12] = 1.0
    n = n / ln[:, None]
    cen = (A + B + C) / 3.0

    sx, sy, ok = core.project(V, w, h, fov)
    vis = ok[ia] & ok[ib] & ok[ic]
    # 背面剔除：相机在原点，面心就是从眼睛指向这个面的向量；法线朝外时同向
    # 就是背面。这个判据不依赖三角形绕序，所以基岩模型的 y 翻转也不会失效。
    vis &= np.einsum('ij,ij->i', n, cen) < 0.0

    xa, xb, xc = sx[ia], sx[ib], sx[ic]
    ya, yb, yc = sy[ia], sy[ib], sy[ic]
    vis &= ~((np.maximum(np.maximum(xa, xb), xc) < -6) |
             (np.minimum(np.minimum(xa, xb), xc) > w + 6) |
             (np.maximum(np.maximum(ya, yb), yc) < -6) |
             (np.minimum(np.minimum(ya, yb), yc) > h + 6))

    area = np.abs((xb - xa) * (yc - ya) - (xc - xa) * (yb - ya)) * 0.5
    if min_area > 0:
        vis &= area >= min_area

    idx = np.nonzero(vis)[0]
    if idx.size == 0:
        return None
    if max_faces and idx.size > max_faces:
        # 面太多就只留屏幕上最大的那些。细碎三角形对"枪在哪儿"没有贡献，
        # 但每一个都要一次 PIL 调用，三万面就是 50ms。
        idx = idx[np.argsort(-area[idx])[:max_faces]]

    lum = np.einsum('ij,j->i', n[idx], LIGHT)
    np.clip(lum, 0.0, None, out=lum)
    shade_idx = (lum * (LEVELS - 1)).astype(np.int32)

    depth = -cen[idx, 2]
    order = np.argsort(-depth)
    return idx[order], depth[order], shade_idx[order], sx, sy


def draw_scene(scene, P, w, h, fov=core.FOV, ghost=None, ghost_P=None,
               bg=BG, grid=True, cross=True, backdrop=None, backdrop_alpha=0.55,
               max_faces=None):
    """画一帧。backdrop 是玩家自己的游戏截图，压暗垫在下面用来对齐位置。"""
    if backdrop is not None:
        img = backdrop.convert('RGB').resize((w, h), Image.BILINEAR)
        if backdrop_alpha < 1.0:
            veil = Image.new('RGB', (w, h), bg)
            img = Image.blend(img, veil, 1.0 - max(0.0, min(1.0, backdrop_alpha)))
        dr = ImageDraw.Draw(img)
    else:
        img = Image.new('RGB', (w, h), bg)
        dr = ImageDraw.Draw(img)
        if grid:
            _grid(dr, w, h)

    V = scene.view(P)
    if V is not None and len(V):
        z = -V[:, 2]
        vis = z[z > 0.05]
        scene.depth = max(float(np.median(vis)) if vis.size else 1.0, 0.05)

    if ghost is not None and ghost_P is not None and not ghost.empty:
        gv = ghost.view(ghost_P)
        gf = faces_of(gv, ghost.TRI, w, h, fov,
                      min_area=_min_area_for(len(ghost.TRI), w, h) * 2.0,
                      max_faces=max_faces or 12000)
        if gf is not None:
            layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            _paint(layer_draw(layer), gv, ghost.TRI, gf, fill=GHOST + (34,),
                   outline=GHOST + (150,))
            img = Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')
            dr = ImageDraw.Draw(img)

    if V is not None:
        faces = faces_of(V, scene.TRI, w, h, fov,
                         min_area=_min_area_for(len(scene.TRI), w, h),
                         max_faces=max_faces)
        if faces is not None:
            _paint(dr, V, scene.TRI, faces)

    _cross(dr, w, h, cross)
    return img


def layer_draw(layer):
    return ImageDraw.Draw(layer)


def _paint(dr, V, TRI, faces, fill=None, outline=None):
    idx, _depth, sidx, sx, sy = faces
    sxl, syl = sx.tolist(), sy.tolist()
    ia = TRI[idx, 0].tolist()
    ib = TRI[idx, 1].tolist()
    ic = TRI[idx, 2].tolist()
    poly = dr.polygon
    for k in range(len(idx)):
        a = ia[k]
        poly([(sxl[a], syl[a]),
              (sxl[ib[k]], syl[ib[k]]),
              (sxl[ic[k]], syl[ic[k]])],
             fill=(fill if fill is not None else LUT[sidx[k]]),
             outline=outline)


def _min_area_for(ntri, w, h):
    """面越多、分辨率越低，就越该丢掉细碎的小三角形。"""
    if ntri <= 12000:
        return 0.6
    return max(0.6, 1.5 * (w * h) / (1288.0 * 724.0))


def screen_box(scene, P, w, h, fov=core.FOV, lo=2.0, hi=98.0):
    """可见顶点的屏幕范围，用分位数而不是 min/max。

    贴近平裁剪面的顶点会投影到几十万像素外，直接取极值会让"枪占多大一块"
    变成没意义的数字，也会让"居中"算出荒唐的量。
    """
    V = scene.view(P)
    if V is None:
        return None
    sx, sy, ok = core.project(V, w, h, fov)
    if not ok.any():
        return None
    return (float(np.percentile(sx[ok], lo)), float(np.percentile(sx[ok], hi)),
            float(np.percentile(sy[ok], lo)), float(np.percentile(sy[ok], hi)))


def screen_center(scene, P, w, h, fov=core.FOV):
    """枪在屏幕上的重心（中位数），比包围盒稳得多。"""
    V = scene.view(P)
    if V is None:
        return None
    sx, sy, ok = core.project(V, w, h, fov)
    if not ok.any():
        return None
    return float(np.median(sx[ok])), float(np.median(sy[ok]))


def px_per_unit(depth, h, fov=core.FOV):
    """屏幕上 1 个模型单位等于多少像素（在 depth 深度上）。"""
    depth = max(float(depth or 1.0), 0.05)
    blocks_per_px = 2.0 * math.tan(math.radians(fov) * 0.5) * depth / float(h)
    return 1.0 / (16.0 * blocks_per_px)


def _grid(dr, w, h):
    step = max(24, w // 24)
    for x in range(0, w, step):
        dr.line([(x, 0), (x, h)], fill=GRID)
    for y in range(0, h, step):
        dr.line([(0, y), (w, y)], fill=GRID)


def _cross(dr, w, h, on):
    if not on:
        return
    cx, cy = w // 2, h // 2
    dr.line([(cx - 16, cy), (cx + 16, cy)], fill=(226, 92, 92))
    dr.line([(cx, cy - 16), (cx, cy + 16)], fill=(226, 92, 92))
    dr.rectangle([w // 10, h // 10, w - w // 10, h - h // 10],
                 outline=(52, 56, 62))


def blend(base, top, alpha=0.5):
    """把预览图半透明叠到一张截图上，用来看重合度。"""
    a = base.convert('RGBA')
    b = top.convert('RGBA')
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    b.putalpha(int(255 * max(0.0, min(1.0, alpha))))
    return Image.alpha_composite(a, b).convert('RGB')


# 兼容旧调用
def render(geo, w=900, h=560, fov=core.FOV, leaf=None, skip_hands=True,
           bg=BG, grid=True, cross=True, alpha=255):
    return draw_scene(Scene(geo, leaf, skip_hands),
                      core.view_matrix(geo, leaf), w, h, fov,
                      bg=bg, grid=grid, cross=cross)