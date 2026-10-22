# r3_lib.py — geometry toolkit for the tactical rifle (all inputs in millimetres)
import bpy, bmesh, math
from mathutils import Vector, Matrix

D = bpy.data
C = bpy.context
TAU = math.pi * 2.0
S = 0.001

# --------------------------------------------------------------------- scene
def wipe():
    if C.object and C.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=True)
    for me in list(D.meshes):
        if me.users == 0: D.meshes.remove(me)
    for mt in list(D.materials):
        if mt.users == 0: D.materials.remove(mt)
    for c in list(D.collections):
        if c.users == 0: D.collections.remove(c)
    sc = C.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = 'MILLIMETERS'


def coll(name, parent=None):
    c = D.collections.get(name)
    if c is None:
        c = D.collections.new(name)
        (parent or C.scene.collection).children.link(c)
    return c


# ------------------------------------------------------------------ helpers
def V(*a):
    return Vector(a)


def fillet(pts, r, seg=5, closed=True):
    """Round the corners of a 2D polygon."""
    n = len(pts)
    out = []
    rng = range(n)
    for i in rng:
        p0 = Vector(pts[i - 1]); p1 = Vector(pts[i]); p2 = Vector(pts[(i + 1) % n])
        v1 = p0 - p1; v2 = p2 - p1
        l1, l2 = v1.length, v2.length
        if l1 < 1e-9 or l2 < 1e-9:
            out.append(tuple(p1)); continue
        u1 = v1 / l1; u2 = v2 / l2
        ang = u1.angle(u2)
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append(tuple(p1)); continue
        rr = r
        d = rr / math.tan(ang * 0.5)
        lim = min(l1, l2) * 0.45
        if d > lim:
            d = lim
            rr = d * math.tan(ang * 0.5)
        t1 = p1 + u1 * d
        t2 = p1 + u2 * d
        bis = (u1 + u2)
        if bis.length < 1e-6: bis = u1
        bis.normalize()
        ctr = p1 + bis * (rr / math.sin(ang * 0.5))
        a1 = math.atan2(t1.y - ctr.y, t1.x - ctr.x)
        a2 = math.atan2(t2.y - ctr.y, t2.x - ctr.x)
        da = a2 - a1
        while da > math.pi: da -= TAU
        while da < -math.pi: da += TAU
        for k in range(seg + 1):
            a = a1 + da * k / seg
            out.append((ctr.x + rr * math.cos(a), ctr.y + rr * math.sin(a)))
    return out


def arc(cx, cy, r, a0, a1, seg=12):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / seg)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / seg))) for k in range(seg + 1)]


def bez(p0, p1, p2, p3, n=16):
    """2D cubic bezier sample list."""
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0]
        y = u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]
        out.append((x, y))
    return out


def _poly_area(p):
    a = 0.0
    n = len(p)
    for i in range(n):
        x0, y0 = p[i]; x1, y1 = p[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a * 0.5


def offset_closed(path, d, ccw=None):
    """Offset a closed 2D polygon by d along its outward normal.

    Convex/rounded loops only - this is used for the trigger guard and similar
    machined loops, not for arbitrary concave shapes.
    """
    n = len(path)
    if ccw is None:
        ccw = _poly_area(path) > 0
    out = []
    for i in range(n):
        p0 = Vector(path[i - 1]); p1 = Vector(path[i]); p2 = Vector(path[(i + 1) % n])
        e0 = (p1 - p0); e1 = (p2 - p1)
        if e0.length < 1e-9: e0 = e1
        if e1.length < 1e-9: e1 = e0
        n0 = Vector((-e0.y, e0.x)); n1 = Vector((-e1.y, e1.x))
        if n0.length > 1e-9: n0.normalize()
        if n1.length > 1e-9: n1.normalize()
        nm = n0 + n1
        if nm.length < 1e-9: nm = n0
        nm.normalize()
        s = 1.0 if ccw else -1.0
        # miter correction so the wall thickness stays constant
        coshalf = max(0.35, nm.dot(n0))
        out.append((p1.x + s * nm.x * d / coshalf,
                    p1.y + s * nm.y * d / coshalf))
    return out


def rounded_loop(x0, x1, z0, z1, r, seg=4):
    """Rounded rectangle path as a closed point list (x,z), CCW."""
    pts = []
    pts += _arc(x1 - r, z0 + r, r, -90, 0, seg)
    pts += _arc(x1 - r, z1 - r, r, 0, 90, seg)
    pts += _arc(x0 + r, z1 - r, r, 90, 180, seg)
    pts += _arc(x0 + r, z0 + r, r, 180, 270, seg)
    return pts


def loop_ring(x0, x1, z0, z1, wall, r_out=None, r_in=None, seg=5):
    """Outer + inner point lists for a rounded-rect loop of constant wall."""
    r_out = r_out if r_out is not None else min((x1 - x0), (z1 - z0)) * 0.30
    r_in = r_in if r_in is not None else max(0.6, r_out - wall)
    outer = rounded_loop(x0, x1, z0, z1, r_out, seg)
    inner = rounded_loop(x0 + wall, x1 - wall, z0 + wall, z1 - wall, r_in, seg)
    return outer, inner


def _arc(cx, cy, r, a0, a1, seg=12):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / seg)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / seg)))
            for k in range(seg + 1)]


def arc(cx, cy, r, a0, a1, seg=12):
    return _arc(cx, cy, r, a0, a1, seg)


# ------------------------------------------------------------------- Part
class Part:
    """Accumulates geometry in a bmesh. All coordinates in mm."""

    def __init__(self, name, mat=None):
        self.name = name
        self.bm = bmesh.new()
        self.mat = mat
        self.ob = None
        self.M = None

    def xform(self, mat):
        """Set a 4x4 transform applied to the whole part at build time (mm space)."""
        self.M = mat

    # ---- primitives -------------------------------------------------
    def box(self, x0, x1, y0, y1, z0, z1):
        bm = self.bm
        vs = []
        for z in (z0, z1):
            for y in (y0, y1):
                for x in (x0, x1):
                    vs.append(bm.verts.new((x * S, y * S, z * S)))
        # 0:(x0,y0,z0) 1:(x1,y0,z0) 2:(x0,y1,z0) 3:(x1,y1,z0)
        # 4:(x0,y0,z1) ...
        f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4),
             (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
        for a, b, c, d in f:
            bm.faces.new((vs[a], vs[b], vs[c], vs[d]))
        return vs

    def prism(self, pts, axis, a0, a1, cap=True):
        """Extrude a closed 2D polygon. axis 'Y': pts are (x,z) -> y from a0..a1."""
        bm = self.bm
        def P(u, v, a):
            if axis == 'Y': return (u * S, a * S, v * S)
            if axis == 'X': return (a * S, u * S, v * S)
            return (u * S, v * S, a * S)
        v0 = [bm.verts.new(P(u, v, a0)) for u, v in pts]
        v1 = [bm.verts.new(P(u, v, a1)) for u, v in pts]
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            try: bm.faces.new((v0[i], v0[j], v1[j], v1[i]))
            except ValueError: pass
        if cap:
            try: bm.faces.new(v0)
            except ValueError: pass
            try: bm.faces.new(list(reversed(v1)))
            except ValueError: pass
        return v0 + v1

    def tube(self, pts_out, pts_in, axis, a0, a1, cap=True):
        """Closed hollow prism: outer + inner profiles (same count / winding)."""
        bm = self.bm
        def P(u, v, a):
            if axis == 'Y': return (u * S, a * S, v * S)
            if axis == 'X': return (a * S, u * S, v * S)
            return (u * S, v * S, a * S)
        n = len(pts_out)
        o0 = [bm.verts.new(P(u, v, a0)) for u, v in pts_out]
        o1 = [bm.verts.new(P(u, v, a1)) for u, v in pts_out]
        i0 = [bm.verts.new(P(u, v, a0)) for u, v in pts_in]
        i1 = [bm.verts.new(P(u, v, a1)) for u, v in pts_in]
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((o0[k], o0[j], o1[j], o1[k]))
            bm.faces.new((i0[j], i0[k], i1[k], i1[j]))
            if cap:
                bm.faces.new((o0[j], o0[k], i0[k], i0[j]))
                bm.faces.new((o1[k], o1[j], i1[j], i1[k]))
        return o0 + o1 + i0 + i1

    def cyl(self, p0, p1, r, seg=32, r2=None, cap=True):
        bm = self.bm
        p0 = Vector((p0[0] * S, p0[1] * S, p0[2] * S))
        p1 = Vector((p1[0] * S, p1[1] * S, p1[2] * S))
        d = p1 - p0
        L = d.length
        if L < 1e-9: return []
        r2 = r if r2 is None else r2
        ret = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg,
                                   radius1=r * S, radius2=r2 * S, depth=L)
        vs = ret['verts']
        q = Vector((0, 0, 1)).rotation_difference(d.normalized())
        bmesh.ops.transform(bm, matrix=Matrix.Translation((p0 + p1) * 0.5) @ q.to_matrix().to_4x4(),
                            verts=vs)
        return vs

    def lathe(self, prof, seg=64, cx=0.0, cz=0.0):
        """Closed (x, radius) profile revolved about the X axis at (y=0, z=cz)."""
        bm = self.bm
        rings = []
        for k in range(seg):
            a = TAU * k / seg
            ca, sa = math.cos(a), math.sin(a)
            ring = [bm.verts.new(((cx + t) * S, r * ca * S, (cz + r * sa) * S)) for t, r in prof]
            rings.append(ring)
        n = len(prof)
        for k in range(seg):
            A, B = rings[k], rings[(k + 1) % seg]
            for j in range(n):
                j2 = (j + 1) % n
                try: bm.faces.new((A[j], A[j2], B[j2], B[j]))
                except ValueError: pass
        return [v for r in rings for v in r]

    def loft(self, rings, cap_start=True, cap_end=True, closed_ring=True):
        """rings: list of equal-length point lists [(x,y,z)..]; bridged in order."""
        bm = self.bm
        vr = [[bm.verts.new((p[0] * S, p[1] * S, p[2] * S)) for p in ring] for ring in rings]
        n = len(rings[0])
        lim = n if closed_ring else n - 1
        for k in range(len(vr) - 1):
            A, B = vr[k], vr[k + 1]
            for i in range(lim):
                j = (i + 1) % n
                try: bm.faces.new((A[i], A[j], B[j], B[i]))
                except ValueError: pass
        if cap_start:
            try: bm.faces.new(vr[0])
            except ValueError: pass
        if cap_end:
            try: bm.faces.new(vr[-1])
            except ValueError: pass
        return [v for r in vr for v in r]

    def wedge(self, prof_xr, a0, a1, seg=8, cx=0.0, cz=0.0, rmin=0.0):
        """Solid swept over an angular sector. prof_xr = [(x, r)] closed polygon."""
        bm = self.bm
        rings = []
        for k in range(seg + 1):
            a = math.radians(a0 + (a1 - a0) * k / seg)
            ca, sa = math.cos(a), math.sin(a)
            rings.append([bm.verts.new(((cx + t) * S, r * ca * S, (cz + r * sa) * S))
                          for t, r in prof_xr])
        n = len(prof_xr)
        for k in range(seg):
            A, B = rings[k], rings[k + 1]
            for j in range(n):
                j2 = (j + 1) % n
                try: bm.faces.new((A[j], A[j2], B[j2], B[j]))
                except ValueError: pass
        try: bm.faces.new(rings[0])
        except ValueError: pass
        try: bm.faces.new(list(reversed(rings[-1])))
        except ValueError: pass
        return [v for r in rings for v in r]

    def ring_prism(self, outer, inner, axis='Y', a0=0.0, a1=0.0):
        """Extrude an ANNULAR closed loop (outer wall + inner wall) between a0..a1.

        This is the correct way to build a loop-shaped part such as a trigger
        guard: solid prism + boolean leaves stray material when the cutter does
        not fully pass through, whereas a true annulus has a real hole.
        Signatures: outer and inner must be the same length and same winding.
        """
        bm = self.bm
        n = len(outer)
        assert n == len(inner), 'ring_prism: outer/inner length mismatch'
        def P(u, v, a):
            if axis == 'Y': return (u * S, a * S, v * S)
            if axis == 'X': return (a * S, u * S, v * S)
            return (u * S, v * S, a * S)
        o0 = [bm.verts.new(P(u, v, a0)) for u, v in outer]
        o1 = [bm.verts.new(P(u, v, a1)) for u, v in outer]
        i0 = [bm.verts.new(P(u, v, a0)) for u, v in inner]
        i1 = [bm.verts.new(P(u, v, a1)) for u, v in inner]
        for k in range(n):
            j = (k + 1) % n
            # outer skin
            bm.faces.new((o0[k], o0[j], o1[j], o1[k]))
            # inner skin (wound the other way so its normals face the hole)
            bm.faces.new((i0[j], i0[k], i1[k], i1[j]))
            # front and back annular caps
            bm.faces.new((o0[j], o0[k], i0[k], i0[j]))
            bm.faces.new((o1[k], o1[j], i1[j], i1[k]))
        return o0 + o1 + i0 + i1

    def sphere(self, c, r, seg=24, rings=12, scale=(1, 1, 1)):
        bm = self.bm
        ret = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r * S)
        vs = ret['verts']
        for v in vs:
            v.co.x *= scale[0]; v.co.y *= scale[1]; v.co.z *= scale[2]
            v.co += Vector((c[0] * S, c[1] * S, c[2] * S))
        return vs

    # ---- detail helpers ---------------------------------------------
    def screw(self, x, z, y, axis='Y', r=2.4, depth=0.9, socket=1.35):
        """Round socket-head cap screw sitting on a surface at y (facing +Y)."""
        s = 1 if axis == 'Y' else -1
        p0 = (x, y, z)
        p1 = (x, y + s * depth, z)
        self.cyl(p0, p1, r, seg=14)
        self.cyl((x, y + s * depth * 0.45, z), (x, y + s * (depth + 0.35), z), socket, seg=6)
        self.cyl((x, y + s * depth * 0.7, z), (x, y + s * (depth + 0.4), z), socket * 0.55, seg=14)

    def pin(self, x, z, y, r=1.6, length=1.2):
        self.cyl((x, y, z), (x, y + length, z), r, seg=12)

    # ---- finalize ----------------------------------------------------
    def build(self, smooth=True, angle=32.0, bevel=0.0, bevel_seg=2, coll_name=None,
              bevel_angle=26.0, merge=1e-4):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge * S)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if self.M is not None:
            bm.transform(self.M)
        me = D.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        ob = D.objects.new(self.name, me)
        (coll(coll_name) if coll_name else C.scene.collection).objects.link(ob)
        if self.mat:
            me.materials.append(self.mat)
        if bevel > 0:
            md = ob.modifiers.new('bevel', 'BEVEL')
            md.width = bevel * S
            md.segments = bevel_seg
            md.limit_method = 'ANGLE'
            md.angle_limit = math.radians(bevel_angle)
            if hasattr(md, 'use_clamp_overlap'): md.use_clamp_overlap = True
            if hasattr(md, 'clamp_overlap'): md.clamp_overlap = True
            md.miter_outer = 'MITER_ARC'
            md.harden_normals = False
            C.view_layer.objects.active = ob
            for o in C.selected_objects: o.select_set(False)
            ob.select_set(True)
            bpy.ops.object.modifier_apply(modifier=md.name)
        if smooth:
            for p in me.polygons: p.use_smooth = True
            md = ob.modifiers.new('es', 'EDGE_SPLIT')
            md.split_angle = math.radians(angle)
        self.ob = ob
        return ob


# ---------------------------------------------------------------- booleans
def ensure(ob):
    if not ob.users_collection:
        try: C.scene.collection.objects.link(ob)
        except Exception: pass


def boolop(target, cutter, op='DIFFERENCE'):
    ensure(target); ensure(cutter)
    md = target.modifiers.new('bl', 'BOOLEAN')
    md.operation = op
    md.object = cutter
    md.solver = 'EXACT'
    md.use_self = False
    C.view_layer.objects.active = target
    for o in C.selected_objects: o.select_set(False)
    target.select_set(True)
    bpy.ops.object.modifier_apply(modifier=md.name)
    D.objects.remove(cutter, do_unlink=True)
    return target


def apply_all(ob):
    C.view_layer.objects.active = ob
    for md in list(ob.modifiers):
        try: bpy.ops.object.modifier_apply(modifier=md.name)
        except Exception as e: print('mod fail', ob.name, md.name, e)


# ------------------------------------------------------------------ materials
def mkmat(name, base, rough=0.5, metal=0.0, coat=0.0, trans=0.0, ior=1.45,
          bump=0.0, bump_scale=200.0, bump_detail=2.0, spec=0.5,
          emit=None, aniso=0.0, rough_var=0.0, tint_noise=None):
    m = D.materials.get(name)
    if m: return m
    m = D.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    def seti(k, v):
        if k in b.inputs: b.inputs[k].default_value = v
    seti('Base Color', (base[0], base[1], base[2], 1.0))
    seti('Roughness', rough)
    seti('Metallic', metal)
    seti('Coat Weight', coat)
    seti('Coat Roughness', 0.1)
    seti('Specular IOR Level', spec)
    if aniso > 0:
        seti('Anisotropic', aniso)
    if trans > 0:
        seti('Transmission Weight', trans)
        seti('IOR', ior)
        try:
            m.use_screen_refraction = True
            m.use_raytrace_refraction = True
        except Exception: pass
    if emit:
        seti('Emission Color', (emit[0], emit[1], emit[2], 1.0))
        seti('Emission Strength', emit[3])
    if tint_noise:
        tex = nt.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = tint_noise[0]
        tex.inputs['Detail'].default_value = 4.0
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.4
        ramp.color_ramp.elements[0].color = (base[0], base[1], base[2], 1)
        ramp.color_ramp.elements[1].position = 0.65
        ramp.color_ramp.elements[1].color = (tint_noise[1][0], tint_noise[1][1], tint_noise[1][2], 1)
        nt.links.new(tex.outputs['Fac'], ramp.inputs['Fac'])
        nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    if bump > 0:
        tex = nt.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = bump_scale
        tex.inputs['Detail'].default_value = bump_detail
        bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump
        bp.inputs['Distance'].default_value = 0.0004
        nt.links.new(tex.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


# ------------------------------------------------------------------- misc
def join(objs, name):
    objs = [o for o in objs if o]
    if not objs: return None
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    for o in C.selected_objects: o.select_set(False)
    for o in objs: o.select_set(True)
    C.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = C.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def mirror_y(ob):
    md = ob.modifiers.new('mir', 'MIRROR')
    md.use_axis = (False, True, False)
    md.use_bisect_axis = (False, False, False)
    return ob
