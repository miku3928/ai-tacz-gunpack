# -*- coding: utf-8 -*-
"""fpv_tuner.py - dial in a TaCZ gun's first-person eye point by eye.

Why this exists
---------------
The whole first-person placement of a TaCZ gun is decided by ONE number: the
pivot of the "idle_view" bone.  TaCZ translates the model by -idle_view, so the
camera sits exactly there and the gun hangs in front of it; nothing is rescaled.
Guessing that number from screenshots is painful - this puts the same projection
the game uses behind three sliders so you can just look at it.

It reproduces, byte for byte, the chain of
    AnimateGeoItemRenderer.applyFirstPersonPositioningTransform
    -> FirstPersonRenderGunEvent.getPositioningNodeInverse(path to idle_view)
so what you see here is what the game draws.  See README.md for the derivation.

Usage
-----
    python fpv_tuner.py                       # auto-find a geo next to the tool
    python fpv_tuner.py path/to/geo.json      # a bare geometry file
    python fpv_tuner.py path/to/pack.zip      # read AND write straight into a pack
    python fpv_tuner.py --selftest [out.png]  # headless render, for CI

Controls
--------
    drag left button  pan (x / y)
    wheel, PgUp/PgDn  distance (z, the sensitive one)
    arrow keys        fine nudge
    load a game screenshot as an overlay, then slide its opacity to match

Screen mapping (measured with 20-degree single-axis probes, not guessed)
    idle_view x +  ->  gun slides RIGHT
    idle_view y +  ->  gun slides DOWN
    idle_view z +  ->  gun gets BIGGER / closer   (most sensitive)
    idle_view z -  ->  gun backs away

The camera bone is kept 0.25 / 0.25 / 0.75 behind idle_view, which is what the
official guns do; it only steers the view-bob rotation, not placement.
"""
import json
import math
import os
import re
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fpv3
import fk2
from preview_fast import Previewer

CAM_OFF = (0.25, 0.25, 0.75)
MEMBER_HINT = re.compile(r'^assets/[^/]+/geo_models/gun/[^/]+\.json$')


# ------------------------------------------------------------------ loading --
def geo_root(g):
    geo = g.get('minecraft:geometry', g.get('geometry'))
    return geo[0] if isinstance(geo, list) else geo


def dump_json(path, g):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(g, f, separators=(',', ':'))
        f.write('\n')


def write_zip_member(path, member, g):
    """Rewrite one member in place, keeping every other entry's metadata."""
    buf = json.dumps(g, separators=(',', ':')).encode('utf-8')
    tmp = path + '.tmp'
    with zipfile.ZipFile(path) as zin, \
            zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = buf if it.filename == member else zin.read(it.filename)
            zout.writestr(it, data)
    os.replace(tmp, path)


def open_source(path):
    """Return (geo_dict, label, writer).

    writer(new_geo) puts the modified geometry back where it came from, so a
    tuned value can go straight into the pack without a Blender re-export.
    """
    if path.lower().endswith('.zip'):
        z = zipfile.ZipFile(path)
        member = None
        for n in z.namelist():
            if MEMBER_HINT.match(n):
                member = n
                break
        if member is None:
            z.close()
            raise SystemExit('no assets/<ns>/geo_models/gun/*.json inside ' + path)
        geo = json.loads(z.read(member).decode('utf-8'))
        z.close()
        return (geo,
                os.path.basename(path) + ' :: ' + member,
                lambda g: write_zip_member(path, member, g))
    with open(path, encoding='utf-8') as f:
        geo = json.load(f)
    return geo, os.path.basename(path), lambda g: dump_json(path, g)


def find_geo():
    for rel in ('../../work/tacz/geo.json',
                '../../work/pack/assets/rifle3/geo_models/gun/rifle3_geo.json',
                'geo.json'):
        p = os.path.normpath(os.path.join(HERE, rel))
        if os.path.exists(p):
            return p
    return None


# ------------------------------------------------------------------ studio ---
def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


class Studio(object):
    def __init__(self, path):
        self.geo, self.label, self.writer = open_source(path)
        self.root = geo_root(self.geo)
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        try:
            dump_json(tmp, self.geo)
            self.pv = Previewer(tmp)
        finally:
            os.remove(tmp)
        self.eye0 = self.get('idle_view')
        self.cam0 = self.get('camera')

    # -- bone helpers ------------------------------------------------------
    def get(self, name):
        for b in self.root['bones']:
            if b['name'] == name:
                return list(b.get('pivot', [0, 0, 0]))
        return [0, 0, 0]

    def set(self, name, xyz):
        for b in self.root['bones']:
            if b['name'] == name:
                b['pivot'] = [round(float(v), 5) for v in xyz]
                return True
        return False

    # -- rendering ---------------------------------------------------------
    def render(self, idle, W=640, H=376, fov=70.0, ref=None, alpha=0.55,
               cross=True):
        im = self.pv.render(idle, W=W, H=H, fov=fov)
        if ref is not None:
            bg = ref.convert('RGB').resize((W, H), Image.LANCZOS)
            im = Image.blend(im, bg, clamp(alpha, 0.0, 1.0))
        if cross:
            d = ImageDraw.Draw(im)
            cx, cy = W * 0.5, H * 0.5
            d.line([(cx - 14, cy), (cx + 14, cy)], fill=(255, 90, 90))
            d.line([(cx, cy - 14), (cx, cy + 14)], fill=(255, 90, 90))
            d.rectangle([1, 1, W - 2, H - 2], outline=(90, 90, 100))
        return im

    def screen_bbox(self, idle, W=640, H=376, fov=70.0):
        M = self.pv.pose(idle)
        Q = (M[:3, :3] @ self.pv.P.T).T + M[:3, 3]
        z = Q[:, 2]
        keep = z < -0.05
        if not keep.any():
            return None
        Q = Q[keep]
        z = z[keep]
        f = 1.0 / math.tan(math.radians(fov) * 0.5)
        asp = W / float(H)
        sx = (Q[:, 0] * f / asp / -z * 0.5 + 0.5) * W
        sy = (-Q[:, 1] * f / -z * 0.5 + 0.5) * H
        return sx.min(), sx.max(), sy.min(), sy.max()


# ------------------------------------------------------------------ cli ------
def selftest(path, out=None):
    st = Studio(path)
    im = st.render(st.eye0, W=640, H=376)
    out = out or os.path.join(HERE, 'selftest.png')
    im.save(out)
    bb = st.screen_bbox(st.eye0)
    print('source     ', st.label)
    print('idle_view  ', st.eye0, ' camera', st.cam0)
    print('tris       ', len(st.pv.T))
    if bb:
        print('gun on screen  x %.0f..%.0f   y %.0f..%.0f  (640x376)' % bb)
        print('frame share    w %.2f  h %.2f'
              % ((bb[1] - bb[0]) / 640.0, (bb[3] - bb[2]) / 376.0))
    print('selftest ->', out)


def gui(path):
    import tkinter as tk
    from tkinter import ttk, filedialog
    from PIL import ImageTk

    st = Studio(path)
    root = tk.Tk()
    root.title('TaCZ first-person eye tuner  -  ' + st.label)
    W, H = 640, 376

    state = {'idle': list(st.eye0), 'fov': 70.0, 'ref': None, 'alpha': 0.55,
             'busy': False, 'dragging': False}

    canvas = tk.Canvas(root, width=W, height=H, bg='#16181c',
                       highlightthickness=0)
    canvas.grid(row=0, column=0, padx=8, pady=8)
    img_item = canvas.create_image(0, 0, anchor='nw')

    side = ttk.Frame(root, padding=(4, 8))
    side.grid(row=0, column=1, sticky='n')

    out = tk.StringVar()
    read = ttk.Label(side, textvariable=out, font=('Consolas', 9), justify='left')
    read.grid(row=98, column=0, columnspan=3, sticky='w', pady=(8, 0))

    def show_values():
        i = state['idle']
        bb = st.screen_bbox(i, W, H, state['fov'])
        tail = ''
        if bb:
            tail = ('\non screen  w %.2f h %.2f of frame'
                    % ((bb[1] - bb[0]) / float(W), (bb[3] - bb[2]) / float(H)))
        out.set('idle_view  [%.3f, %.3f, %.3f]\n'
                'camera     [%.3f, %.3f, %.3f]%s'
                % (i[0], i[1], i[2],
                   i[0] - CAM_OFF[0], i[1] - CAM_OFF[1], i[2] - CAM_OFF[2], tail))

    def draw(*_):
        state['busy'] = False
        half = state['dragging']
        res = (W // 2, H // 2) if half else (W, H)
        im = st.render(state['idle'], W=res[0], H=res[1], fov=state['fov'],
                       ref=state['ref'], alpha=state['alpha'])
        if half:
            im = im.resize((W, H), Image.BILINEAR)
        photo = ImageTk.PhotoImage(im)
        canvas.itemconfig(img_item, image=photo)
        canvas.image = photo
        show_values()

    def schedule(*_):
        if state['busy']:
            return
        state['busy'] = True
        root.after(15, draw)

    sliders = {}

    def on_slide(i, v):
        state['idle'][i] = round(v, 3)
        schedule()

    def bump(i, d):
        lo, hi = ((0, (0.0, 40.0)), (1, (0.0, 48.0)), (2, (2.0, 48.0)))[i]
        state['idle'][i] = round(clamp(state['idle'][i] + d, lo, hi), 3)
        if i in sliders:
            sliders[i].set(state['idle'][i])
        schedule()

    for idx, (label, lo, hi) in enumerate(
            [('x  left/right', 0.0, 40.0), ('y  up/down', 0.0, 48.0),
             ('z  near/far', 2.0, 48.0)]):
        ttk.Label(side, text=label).grid(row=idx, column=0, sticky='w')
        s = ttk.Scale(side, from_=lo, to=hi, length=210,
                      command=lambda v, i=idx: on_slide(i, float(v)))
        s.set(state['idle'][idx])
        s.grid(row=idx, column=1, padx=4, pady=2)
        sliders[idx] = s

    nudge = ttk.Frame(side)
    nudge.grid(row=3, column=0, columnspan=3, pady=(0, 6))
    for nm, i in (('x', 0), ('y', 1), ('z', 2)):
        ttk.Button(nudge, text=nm + '-', width=4,
                   command=lambda i=i: bump(i, -0.05)).pack(side='left')
        ttk.Button(nudge, text=nm + '+', width=4,
                   command=lambda i=i: bump(i, 0.05)).pack(side='left')

    def set_fov(v):
        state['fov'] = round(float(v), 1)
        schedule()

    ttk.Label(side, text='fov overlay').grid(row=4, column=0, sticky='w')
    fs = ttk.Scale(side, from_=45, to=100, length=210,
                   command=set_fov)
    fs.set(state['fov'])
    fs.grid(row=4, column=1, padx=4, pady=2)

    ref_lbl = tk.StringVar(value='overlay: none')

    def load_ref():
        p = filedialog.askopenfilename(
            title='pick a game screenshot to overlay',
            filetypes=[('images', '*.png;*.jpg;*.jpeg;*.webp'), ('all', '*.*')])
        if not p:
            return
        state['ref'] = Image.open(p)
        ref_lbl.set('overlay: ' + os.path.basename(p)[:26])
        schedule()

    def clear_ref():
        state['ref'] = None
        ref_lbl.set('overlay: none')
        schedule()

    ttk.Button(side, text='load screenshot', command=load_ref).grid(
        row=6, column=0, columnspan=2, sticky='w', pady=(8, 0))
    ttk.Button(side, text='clear', width=6, command=clear_ref).grid(
        row=6, column=2, sticky='e')
    ttk.Label(side, textvariable=ref_lbl, font=('Consolas', 9)).grid(
        row=7, column=0, columnspan=3, sticky='w')

    def set_alpha(v):
        state['alpha'] = float(v)
        schedule()

    ttk.Scale(side, from_=0.0, to=0.9, length=210,
              command=set_alpha).grid(row=8, column=0, columnspan=3, sticky='w')
    ttk.Label(side, text='<- overlay opacity ->',
              font=('Consolas', 8)).grid(row=9, column=0, columnspan=3,
                                         sticky='w')

    def apply_geo():
        i = state['idle']
        st.set('idle_view', i)
        st.set('camera', [i[0] - CAM_OFF[0], i[1] - CAM_OFF[1],
                          i[2] - CAM_OFF[2]])
        try:
            st.writer(st.geo)
        except Exception as e:              # noqa: BLE001 - report, never crash
            out.set('write failed: %s\n%s' % (e, out.get()))
            return
        out.set('written to %s\n%s' % (st.label, out.get()))

    def save_json():
        i = state['idle']
        data = {'idle_view': [round(v, 3) for v in i],
                'camera': [round(i[0] - CAM_OFF[0], 3),
                           round(i[1] - CAM_OFF[1], 3),
                           round(i[2] - CAM_OFF[2], 3)]}
        p = os.path.join(HERE, 'eye_tuned.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1)
        out.set('saved eye_tuned.json\n' + out.get())

    def reset():
        for k in range(3):
            state['idle'][k] = st.eye0[k]
            sliders[k].set(st.eye0[k])
        schedule()

    bar = ttk.Frame(side)
    bar.grid(row=100, column=0, columnspan=3, sticky='w', pady=(8, 0))
    ttk.Button(bar, text='write geo', command=apply_geo).pack(side='left')
    ttk.Button(bar, text='export json', command=save_json).pack(side='left', padx=6)
    ttk.Button(bar, text='reset', command=reset).pack(side='left')

    drag = {'x': 0, 'y': 0, 'k': 0.012}

    def on_press(ev):
        state['dragging'] = True
        drag['x'], drag['y'] = ev.x, ev.y
        state['busy'] = False
        schedule()

    def on_move(ev):
        if not state['dragging']:
            return
        dx = (ev.x - drag['x']) * drag['k']
        dy = (ev.y - drag['y']) * drag['k']
        drag['x'], drag['y'] = ev.x, ev.y
        state['idle'][0] = round(clamp(state['idle'][0] + dx, 0, 40), 3)
        state['idle'][1] = round(clamp(state['idle'][1] + dy, 0, 48), 3)
        for k in (0, 1):
            sliders[k].set(state['idle'][k])
        schedule()

    def on_release(_ev):
        state['dragging'] = False
        state['busy'] = False
        schedule()

    def on_wheel(ev):
        bump(2, -0.25 if ev.delta > 0 else 0.25)

    canvas.bind('<ButtonPress-1>', on_press)
    canvas.bind('<B1-Motion>', on_move)
    canvas.bind('<ButtonRelease-1>', on_release)
    canvas.bind('<MouseWheel>', on_wheel)

    def on_key(ev):
        table = {'Left': (0, -0.05), 'Right': (0, 0.05),
                 'Up': (1, 0.05), 'Down': (1, -0.05),
                 'Prior': (2, 0.1), 'Next': (2, -0.1)}
        if ev.keysym in table:
            i, d = table[ev.keysym]
            bump(i, d)

    root.bind('<Key>', on_key)
    canvas.focus_set()

    hint = ('drag = pan    wheel / PgUp / PgDn = distance    arrows = nudge\n'
            '"write geo" edits the file itself; "export json" only saves numbers')
    ttk.Label(side, text=hint, font=('Consolas', 8), justify='left').grid(
        row=101, column=0, columnspan=3, sticky='w', pady=(8, 0))

    root.after(50, draw)
    root.mainloop()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    path = args[0] if args else find_geo()
    if not path:
        raise SystemExit('no geometry found - pass a geo.json or a pack .zip')
    path = os.path.abspath(path)
    if '--selftest' in sys.argv:
        selftest(path, args[1] if len(args) > 1 else None)
    else:
        gui(path)


if __name__ == '__main__':
    main()
