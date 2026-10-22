"""r3_grp_render.py — isolated catalogue renders, one per assembly.

Each group is rendered twice with everything else hidden:
  <G>_iso.png   three-quarter view, auto-framed on the group's bounding box
  <G>_side.png  orthographic side elevation, exact 1:1 mm scale

Also renders the exploded assembly if --explode is passed.

Run:
    blender -b rifle3.blend --factory-startup -P r3_grp_render.py
    blender -b rifle3.blend --factory-startup -P r3_grp_render.py -- --explode
"""
import bpy, sys, os, math
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = ROOT + '/work/'
GROUPS = ['MUZZLE', 'OPTIC', 'MAGAZINE', 'MAGAZINE_BIG', 'STOCK', 'BODY']


def enable_gpu():
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.refresh_devices()
    got = False
    for d in prefs.devices:
        d.use = (d.type == 'OPTIX')
        got = got or d.use
    bpy.context.scene.cycles.device = 'GPU' if got else 'CPU'


def group_bbox(g):
    """World-space bbox of every mesh carrying grp == g, in metres."""
    pts = []
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.get('grp') == g:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def only(g):
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name != 'Backdrop':
            o.hide_render = (o.get('grp') != g)


def make_cam(name, loc, look):
    cd = bpy.data.cameras.new(name)
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def shoot(cam, path, w, h, spp=64, transparent=True):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.cycles.samples = spp
    sc.render.film_transparent = transparent
    sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    sc = bpy.context.scene
    enable_gpu()
    sc.render.engine = 'CYCLES'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = 0.62
    sc.render.film_transparent = True
    # the backdrop is for the assembled hero shot only
    bd = bpy.data.objects.get('Backdrop')
    if bd:
        bd.hide_render = True

    if '--explode' in argv:
        # The offsets live in r3_split.EXPLODE.  Applying them HERE, in memory,
        # matters: r3_split saves the file after moving the empties, so using
        # its --explode flag leaves the whole project permanently exploded.
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        import r3_split
        i = argv.index('--explode')
        amount = float(argv[i + 1]) if i + 1 < len(argv) else 60.0
        for g, (dx, dy, dz) in r3_split.EXPLODE.items():
            e = bpy.data.objects.get('GRP_' + g)
            if not e:
                continue
            e.location = (e.location.x + dx * amount / 1000.0,
                          e.location.y + dy * amount / 1000.0,
                          e.location.z + dz * amount / 1000.0)
        bpy.context.view_layer.update()

        # Frame by projecting every bounding-box corner onto the camera's own
        # axes.  Sizing off the world-space bbox span overestimates badly for
        # an oblique view (the previous version left the whole assembly sitting
        # in a third of the frame).
        pts = [o.matrix_world @ Vector(c) for o in bpy.data.objects
               if o.type == 'MESH' and o.name != 'Backdrop'
               for c in o.bound_box]
        ctr = Vector((sum(p.x for p in pts), sum(p.y for p in pts),
                      sum(p.z for p in pts))) / len(pts)
        lens, W, H = 62.0, 2200, 1240
        d = Vector((0.46, -0.84, 0.28)).normalized()
        back = -d                                    # camera looks along -d
        right = back.cross(Vector((0, 0, 1))).normalized()
        up = right.cross(back).normalized()
        # project onto the plane through ctr
        xs = [(p - ctr).dot(right) for p in pts]
        ys = [(p - ctr).dot(up) for p in pts]
        half_w = max(abs(min(xs)), abs(max(xs)))
        half_h = max(abs(min(ys)), abs(max(ys)))
        t = math.tan(math.atan(18.0 / lens))         # horizontal half-FOV
        tv = t * H / W
        dist = max(half_w / t, half_h / tv) * 1.10
        cam = make_cam('CAM_Exp', ctr + d * dist, ctr)
        cam.data.lens = lens
        sc.render.film_transparent = True
        shoot(cam, WORK + 'exploded.png', W, H, 128)
        # `hi`/`lo` are only bound in the per-group loop below; this branch has
        # its own `pts`, so the span has to come from those.
        span = (max(p.x for p in pts) - min(p.x for p in pts)) * 1000
        print('GRP exploded ok  amount %.1f  span %.0fmm' % (amount, span))
        return

    bbox = {}
    for g in GROUPS:
        only(g)
        lo, hi = group_bbox(g)
        ctr = (lo + hi) * 0.5
        size = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)

        # three-quarter, aimed so the group fills the frame.  The distance is
        # solved from the camera's own HORIZONTAL field of view - a fixed
        # multiple of the bbox size does not work because the groups differ in
        # aspect ratio by an order of magnitude (the muzzle is 57 mm long and
        # 40 mm across, the stock is 216 mm by 122 mm).
        d = Vector((0.62, -0.72, 0.30)).normalized()
        lens, W, H = 80.0, 1000, 700
        hfov = 2.0 * math.atan(18.0 / lens)              # 36 mm sensor, fit=AUTO
        vfov = 2.0 * math.atan(18.0 * H / W / lens)
        extent = max(size, (hi.y - lo.y) * 1.0)
        dist = (extent * 0.5) / math.tan(min(hfov, vfov) * 0.5) * 1.22
        cam = make_cam('CAM_%s_iso' % g, ctr + d * dist, ctr)
        cam.data.lens = lens
        shoot(cam, WORK + '%s_iso.png' % g, W, H, 72)

        # orthographic side elevation at exact 1:1 scale
        o = make_cam('CAM_%s_side' % g, (ctr.x, ctr.y - 1.6, ctr.z), ctr)
        o.data.type = 'ORTHO'
        # leave a 12% margin so nothing touches the frame edge
        o.data.ortho_scale = max(hi.x - lo.x, hi.z - lo.z) * 1.12
        px_per_m = 1400.0 / o.data.ortho_scale
        shoot(o, WORK + '%s_side.png' % g, 1400,
              max(120, int(round((hi.z - lo.z) * 1.30 * px_per_m))), 64)

        bbox[g] = {
            'size': [round((hi.x - lo.x) * 1000.0, 1),
                     round((hi.y - lo.y) * 1000.0, 1),
                     round((hi.z - lo.z) * 1000.0, 1)],
            'parts': sum(1 for o in bpy.data.objects
                         if o.type == 'MESH' and o.get('grp') == g),
        }
        print('GRP %-9s bbox x %.0f..%.0f z %.0f..%.0f  size %.1fmm'
              % (g, lo.x * 1000, hi.x * 1000, lo.z * 1000, hi.z * 1000, size * 1000))

    # The catalogue sheet labels each group with its real size and part count.
    # Publishing them here instead of hard-coding them in r3_catalog.py means
    # the sheet can never quote a stale dimension again - the magazine grew
    # 37 mm the moment its hidden section was added, and the sheet kept saying
    # 134 mm until this file existed.
    import json
    with open(WORK + 'grp_bbox.json', 'w') as fh:
        json.dump(bbox, fh, indent=1)
    print('GRP done')


if __name__ == '__main__':
    main()
