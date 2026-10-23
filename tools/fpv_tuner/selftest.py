# -*- coding: utf-8 -*-
"""selftest.py -- 不开窗口，把整条链跑一遍并核对几个必须成立的等式。

    python selftest.py [枪包目录]

三件事：
  1. 照抄 TaCZ 字节码算出的矩阵 与 闭式 Rz(180)·inv(W) 必须逐元素相等
  2. pivot 每加 1 个模型单位，视空间正好移动 1/16 方块，方向符合直觉
  3. 写回再读回来，pivot / rotation 必须一模一样，且没动到别的字节
"""
import os
import shutil
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import core
import pack
import render

DEFAULT = r'E:\我的世界\.minecraft\versions\亡者世界dlc\tacz'
FAIL = []


def check(name, ok, detail=''):
    print('  %s %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAIL.append(name)


# ---------------------------------------------------------------- 1. 矩阵
def code_inverse(geo_by, leaf):
    """FirstPersonRenderGunEvent.getPositioningNodeInverse 的逐行转写。"""
    M = np.eye(4)
    for part in reversed(core.chain(geo_by, leaf)):
        x, y, z = core.convert_pivot(part, geo_by)
        rot = list(part.get('rotation') or [0, 0, 0])
        M = M @ core.Rx(-rot[0]) @ core.Ry(-rot[1]) @ core.Rz(-rot[2])
        if part.get('parent'):
            M = M @ core.T(-x / 16.0, -y / 16.0, -z / 16.0)
        else:
            M = M @ core.T(-x / 16.0, 1.5 - y / 16.0, -z / 16.0)
    return M


def pose_literal(geo_by, leaf):
    """renderFirstPerson 里那三段的直译。"""
    return (core.T(0, 1.5, 0) @ core.Rz(180.0) @ core.T(0, 1.5, 0)
            @ code_inverse(geo_by, leaf) @ core.T(0, -1.5, 0))


def test_matrix(guns):
    print('[1] 闭式矩阵 vs 字节码直译')
    worst = 0.0
    for g in guns:
        for which in ('idle', 'iron'):
            if not g.view_bone(which):
                continue
            by = core.by_name(g.geo)
            leaf = core.bone_name(which)     # 'idle' -> 'idle_view'
            A = pose_literal(by, leaf)
            B = core.view_matrix(g.geo, which)
            worst = max(worst, float(np.abs(A - B).max()))
    check('最大误差 < 1e-9', worst < 1e-9, '实际 %.2e' % worst)


# ---------------------------------------------------------------- 2. 灵敏度
def test_sensitivity(guns):
    print('[2] pivot 灵敏度')
    g = guns[0]
    for which in ('idle', 'iron'):
        b = g.view_bone(which)
        if not b:
            continue
        p0 = list(b['pivot'])
        base = core.view_matrix(g.geo, which)
        want = {'x': np.array([1.0, 0, 0]), 'y': np.array([0, -1.0, 0]),
                'z': np.array([0, 0, -1.0])}
        for i, ax in enumerate('xyz'):
            q = list(p0)
            q[i] += 16.0
            b['pivot'] = q
            d = (core.view_matrix(g.geo, which) - base)[:3, 3]
            b['pivot'] = p0
            ok = np.allclose(d, want[ax], atol=1e-9)
            check('%s.pivot.%s += 16 -> %s' % (which, ax, want[ax]), ok,
                  '实际 %s' % np.round(d, 4))


# ---------------------------------------------------------------- 3. 写回
def test_save(guns, src_pack):
    print('[3] 写回再读回')
    tmp = tempfile.mkdtemp()
    try:
        dst = os.path.join(tmp, 'pack')
        shutil.copytree(src_pack, dst)
        p1 = pack.Pack(dst)
        g1 = [x for x in p1.playable() if x.name == guns[0].name][0]
        before_pivot = g1.pivot('idle')
        before_rot = g1.rotation('idle')
        g1.set_view('idle', pivot=[before_pivot[0] + 1.5,
                                   before_pivot[1] - 2.25,
                                   before_pivot[2] + 0.5],
                    rotation=[1.0, -2.0, 3.5])
        ok, how = p1.save(g1)
        p2 = pack.Pack(dst)
        g2 = [x for x in p2.playable() if x.name == guns[0].name][0]
        check('写回成功', ok, how)
        check('pivot 一致', g2.pivot('idle') == g1.pivot('idle'),
              '%s -> %s' % (before_pivot, g2.pivot('idle')))
        check('rotation 一致', g2.rotation('idle') == [1.0, -2.0, 3.5],
              str(g2.rotation('idle')))
        check('留了 .bak', os.path.exists(
            os.path.join(dst, g1.member.replace('/', os.sep)) + '.bak'))
        # 文本级替换：除了被编辑的那个骨骼，别的 JSON 内容一个字都不该动
        import json
        raw = open(os.path.join(dst, g1.member.replace('/', os.sep)),
                   encoding='utf-8').read()
        orig = open(os.path.join(src_pack, g1.member.replace('/', os.sep)),
                    encoding='utf-8').read()
        a = json.loads(orig)
        b = json.loads(raw)
        ga = pack.geometries(a)[0]
        gb = pack.geometries(b)[0]
        for bone in ga['bones']:
            if bone['name'] == g1.view_bone('idle')['name']:
                bone['pivot'] = None
                bone['rotation'] = None
        for bone in gb['bones']:
            if bone['name'] == g1.view_bone('idle')['name']:
                bone['pivot'] = None
                bone['rotation'] = None
        check('除了被编辑的骨骼，内容完全没变', ga == gb)
        check('文件长度变化很小', abs(len(raw) - len(orig)) < 120,
              '%d -> %d 字节' % (len(orig), len(raw)))
        # 原本没有 rotation 键的枪，归零之后键要真的消失，不能留下 "rotation": [0,0,0]
        raw_orig = json.load(open(os.path.join(
            src_pack, g1.member.replace('/', os.sep)), encoding='utf-8'))
        bone_orig = [b for b in pack.geometries(raw_orig)[0]['bones']
                     if b['name'] == g1.view_bone('idle')['name']][0]
        had_rot = 'rotation' in bone_orig
        g2.set_view('idle', rotation=[0, 0, 0])
        p2.save(g2)
        p3 = pack.Pack(dst)
        g3 = [x for x in p3.playable() if x.name == guns[0].name][0]
        bone_now = g3.view_bone('idle')
        if had_rot:
            check('原本就有 rotation 键，归零后保留', 'rotation' in bone_now)
        else:
            check('原本没有 rotation 键，归零后不新增', 'rotation' not in bone_now,
                  'pivot %s' % (bone_now.get('pivot'),))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- 4. 渲染
def test_render(guns):
    print('[4] 渲染与取景')
    g = guns[0]
    sc = render.Scene(g.geo, 'idle')
    check('有几何体', not sc.empty, '%d 顶点 / %d 三角形'
          % (0 if sc.empty else len(sc.V), len(sc.TRI)))
    P = core.view_matrix(g.geo, 'idle')
    box = render.screen_box(sc, P, 960, 540)
    ctr = render.screen_center(sc, P, 960, 540)
    check('包围盒在合理范围', box is not None and box[1] > box[0])
    check('重心落在屏幕内', 0 < ctr[0] < 960 and 0 < ctr[1] < 540,
          '%.0f, %.0f' % ctr)
    img = render.draw_scene(sc, P, 960, 540)
    check('出图', img.size == (960, 540))


# ---------------------------------------------------------------- 5. poly_mesh
def test_poly_mesh(packs):
    """poly_mesh 必须按 TML 的规则烘：相对 pivot，y 取反，再走骨骼矩阵。

    核对两件事：(a) 烘完的顶点落在骨骼附近，不是飞到天上去；
    (b) 整枪的轴对齐尺寸和 cube 版同一把枪同量级（rifle3 是 3.4 x 18.5 x 36.9）。
    """
    print('[5] poly_mesh 烘焙')
    target = None
    for p in packs:
        try:
            pk = pack.Pack(p)
        except Exception:
            continue
        for g in pk.playable():
            if g.n_poly and not g.n_cubes:
                target = g
                break
        if target:
            break
    if target is None:
        print('  SKIP 这批枪包里没有 poly_mesh 模型')
        return
    print('  用 %s 的 %s' % (os.path.basename(target.pack.path), target.name))
    sc = render.Scene(target.geo, 'idle')
    check('有几何体', not sc.empty, '%d 顶点 / %d 三角形'
          % (0 if sc.empty else len(sc.V), len(sc.TRI)))
    if sc.empty:
        return
    size = (sc.V.max(0) - sc.V.min(0)) * 16.0
    check('尺寸在合理量级', 3.0 < size[2] < 200.0,
          '%.1f x %.1f x %.1f 模型单位' % tuple(size))
    check('没有退化三角形', bool(np.all(sc.TRI[:, 0] != sc.TRI[:, 2])),
          '首尾同点的三角面会让画家算法画出脏边')
    box = core.screen_box(target.geo, 960, 540)
    check('能投影到屏幕', box is not None and box[1] > box[0])


def main_with_root(root):
    """给 gui.py --selftest 用：目录已经定好了，不再看 argv。"""
    sys_argv_backup = list(sys.argv)
    sys.argv = [sys.argv[0], root]
    try:
        return main()
    finally:
        sys.argv = sys_argv_backup


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    packs = pack.find_packs(root)
    if not packs:
        print('没找到枪包：%s' % root)
        return 1
    src = [p for p in packs if os.path.basename(p) == 'tacz_default_gun']
    src = src[0] if src else packs[0]
    print('枪包：%s' % src)
    pk = pack.Pack(src)
    guns = [g for g in pk.playable() if g.has_idle and g.n_cubes]
    print('可用枪 %d 把，取前 6 把做矩阵核对\n' % len(guns))
    if not guns:
        print('这个枪包里没有带 cube 的枪，换个枪包试试')
        return 1

    test_matrix(guns[:6])
    print()
    test_sensitivity(guns[:1])
    print()
    test_save(guns[:1], src)
    print()
    test_render(guns[:1])
    print()
    test_poly_mesh(packs)
    print()
    if FAIL:
        print('%d 项失败：%s' % (len(FAIL), ', '.join(FAIL)))
        return 1
    print('全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())