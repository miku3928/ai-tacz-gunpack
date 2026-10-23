# -*- coding: utf-8 -*-
"""gui.py -- 第一人称定位调参器。

流程就是用户要的那条：选枪包 -> 选枪 -> 拖数值 -> 写回 -> 游戏里 /tacz reload。

预览用的矩阵是从 TaCZ 源码逐行推出来的（见 core.py 顶部注释），不是拟合的，
所以预览里枪的位置就是游戏里枪的位置。差别只在渲染质量：这里是软件光栅，
没有贴图、没有光影、没有手臂。

左键拖预览可以直接平移枪，这是最快的手感调整方式；方向键微调（0.25 单位，
按住 Shift 是 1 单位）；右侧滑块和输入框负责精确值和旋转。
"""
import os
import sys
import traceback

def _app_dir():
    """程序所在目录。

    打包成 exe 之后 __file__ 指向 PyInstaller 解包出来的临时目录，
    那个目录退出就没了 —— crash.log 写进去等于没写。所以要认 exe 自己。
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


HERE = _app_dir()
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Windows 上不声明 DPI 感知的话，整个窗口会被系统按位图拉伸，字全是糊的。
# 代价是所有尺寸都变成物理像素，所以窗口大小必须按屏幕算，不能写死。
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

import core
import pack
import render

W, H = 960, 540
DRAG_W, DRAG_H = 480, 270

# 优先用装了 TML 的那个实例 —— 不然 poly_mesh 的包放进去也看不出效果
DEFAULT_TACZ = r'E:\我的世界\.minecraft\versions\1.20.1-Forge_47.4.10\tacz'
FALLBACK_TACZ = [
    r'E:\我的世界\.minecraft\versions\亡者世界dlc\tacz',
]

FONT = ('Microsoft YaHei UI', 10)
FONT_B = ('Microsoft YaHei UI', 10, 'bold')
FONT_S = ('Microsoft YaHei UI', 9)

VIEW_LABEL = {'idle': '腰射', 'iron': '机瞄'}


def find_default_tacz():
    for cand in [DEFAULT_TACZ] + FALLBACK_TACZ:
        if os.path.isdir(cand):
            return cand
    root = r'E:\我的世界\.minecraft\versions'
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            cand = os.path.join(root, name, 'tacz')
            if os.path.isdir(cand):
                return cand
    return ''


class NumRow(ttk.Frame):
    """一条滑块 + 一个能直接打字的数字框，两边互相同步。"""

    def __init__(self, master, text, lo, hi, value, on_change=None, unit=''):
        super().__init__(master)
        self.lo, self.hi = lo, hi
        self.on_change = on_change
        self._busy = False

        ttk.Label(self, text=text, width=6, anchor='w', font=FONT).pack(side='left')
        self.var = tk.DoubleVar(value=value)
        self.scale = ttk.Scale(self, from_=lo, to=hi, orient='horizontal',
                               variable=self.var, command=self._moved)
        self.scale.pack(side='left', fill='x', expand=True, padx=(2, 6))
        self.evar = tk.StringVar(value='%.3f' % value)
        self.entry = ttk.Entry(self, textvariable=self.evar, width=8,
                               justify='right', font=FONT)
        self.entry.pack(side='left')
        self.entry.bind('<Return>', self._typed)
        self.entry.bind('<FocusOut>', self._typed)
        if unit:
            ttk.Label(self, text=unit, width=2, font=FONT_S,
                      foreground='#777').pack(side='left')

    def _moved(self, _v=None):
        if self._busy:
            return
        v = self.var.get()
        self._busy = True
        self.evar.set('%.3f' % v)
        self._busy = False
        if self.on_change:
            self.on_change(v)

    def _typed(self, _e=None):
        if self._busy:
            return
        try:
            v = float(self.evar.get())
        except ValueError:
            self.evar.set('%.3f' % self.var.get())
            return
        v = max(self.lo, min(self.hi, v))
        self._busy = True
        self.var.set(v)
        self.evar.set('%.3f' % v)
        self._busy = False
        if self.on_change:
            self.on_change(v)

    def set(self, v):
        v = max(self.lo, min(self.hi, float(v)))
        self._busy = True
        self.var.set(v)
        self.evar.set('%.3f' % v)
        self._busy = False

    def get(self):
        return float(self.var.get())


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('TaCZ 第一人称定位调参器')
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # 预览区按 16:9 定高度：左右两栏吃掉约 600px，剩下的给画布。
        w = min(1900, int(sw * 0.88))
        h = min(int(sh * 0.92), int((w - 610) * 9 / 16) + 130)
        self.geometry('%dx%d+%d+%d' % (w, h, (sw - w) // 2, max(0, (sh - h) // 3)))
        self.minsize(min(1100, w), min(660, h))
        self.configure(bg='#1a1c20')

        self.pk = None
        self.gun = None
        self.scene = None
        self.gscene = None
        self.gP = None
        self.orig = {}
        self.which = 'idle'
        self.dirty = False
        self.ghost = True
        self.backdrop = None
        self.backdrop_alpha = 0.55
        self._photo = None
        self._drag = None
        self._pending = None
        self._guns = []
        self._packs = []

        self._view_size_px = (W, H)
        self._canvas_px = (W, H)
        self.tacz_root = tk.StringVar(value=find_default_tacz())
        self.status = tk.StringVar(value='选一个枪包开始')
        self.info = tk.StringVar(value='')

        self._build()
        self._bind_keys()
        self.after(60, self.refresh_packs)

    # ------------------------------------------------------------------ 布局
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=(8, 6, 8, 2))
        top.grid(row=0, column=0, sticky='ew')
        ttk.Label(top, text='枪包目录', font=FONT).pack(side='left')
        ttk.Entry(top, textvariable=self.tacz_root, font=FONT).pack(
            side='left', fill='x', expand=True, padx=6)
        ttk.Button(top, text='浏览', command=self.browse_root, width=6).pack(side='left')
        ttk.Button(top, text='刷新', command=self.refresh_packs, width=6).pack(
            side='left', padx=(4, 0))

        body = ttk.Frame(self, padding=(8, 0, 8, 0))
        body.grid(row=1, column=0, sticky='nsew')
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ---- 左：枪包 + 枪列表
        left = ttk.Frame(body, width=236)
        left.grid(row=0, column=0, sticky='nsw', padx=(0, 8))
        left.grid_propagate(False)
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text='枪包', font=FONT_B).grid(row=0, column=0, sticky='w')
        self.pack_list = tk.Listbox(left, height=7, font=FONT, exportselection=False,
                                    activestyle='none', borderwidth=1,
                                    highlightthickness=0)
        self.pack_list.grid(row=1, column=0, sticky='ew', pady=(2, 8))
        self.pack_list.bind('<<ListboxSelect>>', self._pack_picked)

        row = ttk.Frame(left)
        row.grid(row=2, column=0, sticky='ew', pady=(0, 2))
        ttk.Label(row, text='找枪', font=FONT).pack(side='left')
        self.search = tk.StringVar()
        ttk.Entry(row, textvariable=self.search, font=FONT).pack(
            side='left', fill='x', expand=True, padx=(4, 0))
        self.search.trace_add('write', lambda *a: self.refresh_guns())

        self.gun_list = tk.Listbox(left, font=FONT, exportselection=False,
                                   activestyle='none', borderwidth=1,
                                   highlightthickness=0)
        self.gun_list.grid(row=3, column=0, sticky='nsew')
        self.gun_list.bind('<<ListboxSelect>>', self._gun_picked)

        # ---- 中：预览
        mid = ttk.Frame(body)
        mid.grid(row=0, column=1, sticky='nsew')
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)
        # 尺寸交给布局决定（sticky='nsew'），这里只给一个下限；
        # 写死宽高会让整个窗口被撑开、右侧面板被挤出屏幕。
        self.canvas = tk.Canvas(mid, width=640, height=360, bg='#181a1e',
                                highlightthickness=1, highlightbackground='#33363c')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.canvas.bind('<Button-1>', self._drag_start)
        self.canvas.bind('<B1-Motion>', self._drag_move)
        self.canvas.bind('<ButtonRelease-1>', self._drag_end)
        self.canvas.bind('<Configure>', self._canvas_resized)

        under = ttk.Frame(mid)
        under.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        self.ghost_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(under, text='显示原始位置', variable=self.ghost_var,
                        command=self._toggle_ghost).pack(side='left')
        ttk.Button(under, text='垫游戏截图', width=10,
                   command=self.pick_backdrop).pack(side='left', padx=(10, 0))
        ttk.Button(under, text='去掉截图', width=8,
                   command=self.clear_backdrop).pack(side='left', padx=4)
        self.alpha = tk.DoubleVar(value=0.55)
        ttk.Scale(under, from_=0.1, to=1.0, orient='horizontal', length=80,
                  variable=self.alpha, command=lambda v: self._alpha_changed()
                  ).pack(side='left', padx=(4, 0))
        ttk.Label(under, textvariable=self.info, font=FONT_S,
                  foreground='#8b95a1').pack(side='left', padx=12)

        # ---- 右：数值
        right = ttk.Frame(body, width=330)
        right.grid(row=0, column=2, sticky='ns', padx=(10, 0))
        right.grid_propagate(False)

        seg = ttk.Frame(right)
        seg.pack(fill='x')
        self.tab_var = tk.StringVar(value='idle')
        self.btn_idle = ttk.Radiobutton(seg, text='腰射 idle_view', value='idle',
                                        variable=self.tab_var, command=self._tab_changed)
        self.btn_iron = ttk.Radiobutton(seg, text='机瞄 iron_view', value='iron',
                                        variable=self.tab_var, command=self._tab_changed)
        self.btn_idle.pack(side='left')
        self.btn_iron.pack(side='left', padx=(12, 0))

        self.rows = {}
        box = ttk.LabelFrame(right, text=' 位置 pivot（模型单位，16 = 1 方块） ',
                             padding=(8, 6))
        box.pack(fill='x', pady=(8, 0))
        for key, label in (('x', '左右 x'), ('y', '上下 y'), ('z', '前后 z')):
            r = NumRow(box, label, -160, 160, 0,
                       on_change=lambda v, k=key: self._edited(k, v))
            r.pack(fill='x', pady=2)
            self.rows[key] = r

        box2 = ttk.LabelFrame(right, text=' 旋转 rotation（度） ', padding=(8, 6))
        box2.pack(fill='x', pady=(8, 0))
        for key, label in (('rx', '俯仰 X'), ('ry', '偏航 Y'), ('rz', '翻滚 Z')):
            r = NumRow(box2, label, -180, 180, 0,
                       on_change=lambda v, k=key: self._edited(k, v), unit='°')
            r.pack(fill='x', pady=2)
            self.rows[key] = r

        tools = ttk.Frame(right)
        tools.pack(fill='x', pady=(10, 0))
        ttk.Button(tools, text='回到原始值', command=self.revert,
                   width=9).pack(side='left')
        self.copy_btn = ttk.Button(tools, text='从机瞄复制',
                                   command=self.copy_other, width=10)
        self.copy_btn.pack(side='left', padx=5)
        ttk.Button(tools, text='居中', command=self.center_on_cross,
                   width=7).pack(side='left')

        act = ttk.Frame(right)
        act.pack(fill='x', pady=(10, 0))
        self.save_btn = ttk.Button(act, text='写回枪包  Ctrl+S', command=self.save)
        self.save_btn.pack(fill='x')

        fovrow = ttk.Frame(right)
        fovrow.pack(fill='x', pady=(10, 0))
        ttk.Label(fovrow, text='视角 FOV', font=FONT).pack(side='left')
        self.fov = tk.DoubleVar(value=70.0)
        sp = ttk.Spinbox(fovrow, from_=30, to=110, increment=1, width=6,
                         textvariable=self.fov, command=self._fov_changed)
        sp.pack(side='left', padx=6)
        sp.bind('<Return>', lambda e: self._fov_changed())
        ttk.Label(fovrow, text='游戏设置里的 FOV', font=FONT_S,
                  foreground='#7d8794').pack(side='left')

        ttk.Label(right, text='写完后在游戏里执行 /tacz reload 立刻生效，不用重启。\n'
                              '原文件会自动留一份 .bak。方向键微调，Shift+方向键走 1 单位。',
                  font=FONT_S, foreground='#7d8794',
                  wraplength=310, justify='left').pack(anchor='w', pady=(8, 0))

        bar = ttk.Frame(self, padding=(8, 4, 8, 6))
        bar.grid(row=2, column=0, sticky='ew')
        ttk.Label(bar, textvariable=self.status, font=FONT_S,
                  foreground='#9aa3ad').pack(side='left')

    def _canvas_resized(self, e):
        """画布跟着窗口变，但只在尺寸真的变了的时候重画。

        真正用来渲染的永远是一块 16:9 的区域：游戏窗口绝大多数是 16:9，
        画布形状不一致的话，预览的透视就和游戏对不上，看到的"偏左一点"
        到游戏里会变成偏得更多。
        """
        w = max(320, e.width)
        h = max(180, e.height)
        if w / float(h) > 16.0 / 9.0:
            vh = h
            vw = int(round(h * 16.0 / 9.0))
        else:
            vw = w
            vh = int(round(w * 9.0 / 16.0))
        if (vw, vh) == getattr(self, '_view_size_px', None) and \
                (w, h) == getattr(self, '_canvas_px', None):
            return
        self._view_size_px = (vw, vh)
        self._canvas_px = (w, h)
        if self.gun:
            self.redraw(full=True)

    def _bind_keys(self):
        self.bind('<Control-s>', lambda e: self.save())
        self.bind('<Control-z>', lambda e: self.revert())
        self.bind('<Control-Tab>', lambda e: self._swap_tab())
        for key, dx, dy, dz in (('Left', -1, 0, 0), ('Right', 1, 0, 0),
                                ('Up', 0, -1, 0), ('Down', 0, 1, 0),
                                ('Prior', 0, 0, -1), ('Next', 0, 0, 1)):
            self.bind('<%s>' % key, lambda e, a=dx, b=dy, c=dz: self.nudge(a, b, c, 0.25))
            self.bind('<Shift-%s>' % key, lambda e, a=dx, b=dy, c=dz: self.nudge(a, b, c, 1.0))

    # ------------------------------------------------------------- 枪包/枪
    def browse_root(self):
        d = filedialog.askdirectory(initialdir=self.tacz_root.get() or 'E:\\')
        if d:
            self.tacz_root.set(d)
            self.refresh_packs()

    def refresh_packs(self):
        self.pack_list.delete(0, 'end')
        self._packs = pack.find_packs(self.tacz_root.get())
        if not self._packs:
            self.status.set('这个目录下没找到枪包：%s' % self.tacz_root.get())
            return
        for p in self._packs:
            self.pack_list.insert('end', os.path.basename(p))
        self.status.set('找到 %d 个枪包' % len(self._packs))
        self.pack_list.selection_set(0)
        self._pack_picked()

    def _pack_picked(self, _e=None):
        sel = self.pack_list.curselection()
        if not sel:
            return
        try:
            self.pk = pack.Pack(self._packs[sel[0]])
        except Exception as exc:
            self.status.set('读不了这个枪包：%s' % exc)
            return
        self.refresh_guns()

    def refresh_guns(self):
        self.gun_list.delete(0, 'end')
        self._guns = []
        if not self.pk:
            return
        q = self.search.get().strip().lower()
        for g in self.pk.playable():
            if q and q not in g.name.lower() and q not in g.identifier.lower():
                continue
            self._guns.append(g)
            tag = ('腰' if g.has_idle else '') + ('机' if g.has_iron else '')
            if g.n_poly and not g.n_cubes:
                tag += '  网格'
            self.gun_list.insert('end', '%-22s %s' % (g.name[:22], tag))
        self.status.set('%s：%d 把枪可用'
                        % (os.path.basename(self.pk.path), len(self._guns)))
        if self._guns:
            self.gun_list.selection_set(0)
            self._gun_picked()

    def _gun_picked(self, _e=None):
        sel = self.gun_list.curselection()
        if not sel or not self._guns:
            return
        g = self._guns[sel[0]]
        if self.dirty and not messagebox.askyesno(
                '还没写回', '当前这把枪有改动还没写回，切换会丢掉。继续？'):
            return
        self.gun = g
        self.orig = {}
        for which in ('idle', 'iron'):
            b = g.view_bone(which)
            self.orig[which] = None if b is None else {
                'pivot': list(b.get('pivot') or [0, 0, 0]),
                'rotation': (list(b['rotation']) if b.get('rotation') else None),
            }
        self.dirty = False
        if g.has_idle:
            self.which = 'idle'
        elif g.has_iron:
            self.which = 'iron'
        self.tab_var.set(self.which)
        self.btn_idle.configure(state='normal' if g.has_idle else 'disabled')
        self.btn_iron.configure(state='normal' if g.has_iron else 'disabled')
        self.copy_btn.configure(text='从机瞄复制' if self.which == 'idle' else '从腰射复制')
        self._build_scenes()
        self._load_values()
        self.redraw(full=True)
        if self.scene is not None and self.scene.empty:
            self.status.set('这把枪没有任何几何体，预览画不出来')

    def _build_scenes(self):
        self.scene = None
        self.gscene = None
        self.gP = None
        if not self.gun:
            return
        try:
            self.scene = render.Scene(self.gun.geo, self.which)
        except Exception:
            traceback.print_exc()
        o = self.orig.get(self.which)
        if o:
            try:
                ggeo = self._ghost_geo()
                self.gscene = render.Scene(ggeo, self.which)
                self.gP = core.view_matrix(ggeo, self.which)
            except Exception:
                traceback.print_exc()

    # ------------------------------------------------------------- 数值
    def _tab_changed(self):
        self.which = self.tab_var.get()
        self.copy_btn.configure(text='从机瞄复制' if self.which == 'idle' else '从腰射复制')
        self._build_scenes()
        self._load_values()
        self.redraw(full=True)

    def _swap_tab(self):
        if not self.gun:
            return
        if self.which == 'idle' and self.gun.has_iron:
            self.tab_var.set('iron')
        elif self.gun.has_idle:
            self.tab_var.set('idle')
        self._tab_changed()

    def _load_values(self):
        if not self.gun:
            return
        o = self.orig.get(self.which)
        if o is None:
            for r in self.rows.values():
                r.set(0)
            return
        p = o['pivot']
        rot = o['rotation'] or [0, 0, 0]
        for k, v in zip(('x', 'y', 'z'), p):
            self.rows[k].set(v)
        for k, v in zip(('rx', 'ry', 'rz'), rot):
            self.rows[k].set(v)

    def _current(self):
        return ([self.rows['x'].get(), self.rows['y'].get(), self.rows['z'].get()],
                [self.rows['rx'].get(), self.rows['ry'].get(), self.rows['rz'].get()])

    def _apply(self, pivot, rot):
        b = self.gun.view_bone(self.which)
        if b is None:
            return
        b['pivot'] = [round(float(v), 5) for v in pivot]
        o = self.orig.get(self.which) or {}
        if all(abs(v) < 1e-9 for v in rot) and o.get('rotation') is None:
            b.pop('rotation', None)
        else:
            b['rotation'] = [round(float(v), 5) for v in rot]

    def _edited(self, key, value):
        if not self.gun:
            return
        pivot, rot = self._current()
        idx = 0 if key in ('x', 'rx') else (1 if key in ('y', 'ry') else 2)
        (pivot if key in ('x', 'y', 'z') else rot)[idx] = value
        self._apply(pivot, rot)
        self.dirty = True
        self.redraw()

    def nudge(self, dx, dy, dz, step):
        if not self.gun:
            return
        pivot, rot = self._current()
        pivot = [pivot[0] + dx * step, pivot[1] + dy * step, pivot[2] + dz * step]
        for k, v in zip(('x', 'y', 'z'), pivot):
            self.rows[k].set(v)
        self._apply(pivot, rot)
        self.dirty = True
        self.redraw(full=False)

    # ------------------------------------------------------------- 预览
    def redraw(self, full=True):
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(0 if full else 12, lambda: self._draw(full))

    def _draw(self, full):
        self._pending = None
        if not self.gun or self.scene is None:
            return
        vw, vh = self._view_size()
        cw, ch = getattr(self, '_canvas_px', (vw, vh))
        if full:
            w, h = vw, vh
        else:
            w, h = max(320, vw // 2), max(180, vh // 2)
        P = core.view_matrix(self.gun.geo, self.which)
        gP = self.gP if (self.ghost and self.gscene is not None) else None
        try:
            img = render.draw_scene(self.scene, P, w, h, fov=self.fov.get(),
                                    ghost=self.gscene, ghost_P=gP,
                                    backdrop=self.backdrop,
                                    backdrop_alpha=self.backdrop_alpha)
        except Exception:
            traceback.print_exc()
            return
        if not full:
            img = img.resize((vw, vh), Image.BILINEAR)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete('all')
        ox = (cw - vw) // 2
        oy = (ch - vh) // 2
        self.canvas.create_rectangle(0, 0, cw, ch, fill='#101114', outline='')
        self.canvas.create_image(ox, oy, anchor='nw', image=self._photo)
        self.canvas.create_rectangle(ox, oy, ox + vw, oy + vh,
                                     outline='#3a3f47')
        self._update_info(P)

    def _ghost_geo(self):
        import copy
        geo = copy.deepcopy(self.gun.geo)
        o = self.orig[self.which]
        b = core.by_name(geo).get(self.which)
        if b is not None:
            b['pivot'] = list(o['pivot'])
            if o['rotation'] is None:
                b.pop('rotation', None)
            else:
                b['rotation'] = list(o['rotation'])
        return geo

    def _update_info(self, P=None):
        if not self.gun or self.scene is None:
            return
        P = P if P is not None else core.view_matrix(self.gun.geo, self.which)
        box = render.screen_box(self.scene, P, *self._view_size(), fov=self.fov.get())
        if not box:
            self.info.set('枪不在画面里')
            return
        o = self.orig.get(self.which)
        d = ''
        if o:
            p = [self.rows['x'].get(), self.rows['y'].get(), self.rows['z'].get()]
            dd = [p[i] - o['pivot'][i] for i in range(3)]
            if any(abs(v) > 1e-6 for v in dd):
                d = '    相对原始 %+.1f %+.1f %+.1f 单位' % tuple(dd)
        vw, vh = self._view_size()
        ctr = render.screen_center(self.scene, P, vw, vh, fov=self.fov.get())
        off = ''
        if box[0] < 0 or box[1] > vw or box[2] < 0 or box[3] > vh:
            off = '（有部分在画面外）'
        self.info.set('中心 %.0f, %.0f   范围 x %.0f~%.0f  y %.0f~%.0f%s%s'
                      % (ctr[0], ctr[1], max(0, box[0]), min(vw, box[1]),
                         max(0, box[2]), min(vh, box[3]), off, d))

    def _view_size(self):
        return getattr(self, '_view_size_px', (W, H))

    def _origin(self):
        vw, vh = self._view_size()
        cw, ch = getattr(self, '_canvas_px', (vw, vh))
        return (cw - vw) // 2, (ch - vh) // 2

    def _fov_changed(self):
        try:
            v = float(self.fov.get())
        except Exception:
            v = 70.0
        self.fov.set(max(30.0, min(110.0, v)))
        if self.gun:
            self.redraw(full=True)

    def pick_backdrop(self):
        p = filedialog.askopenfilename(
            title='选一张游戏内截图',
            filetypes=[('图片', '*.png *.jpg *.jpeg *.bmp'), ('全部', '*.*')])
        if not p:
            return
        try:
            im = Image.open(p).convert('RGB')
        except Exception as exc:
            messagebox.showerror('读不了这张图', str(exc))
            return
        self.backdrop = im
        self.status.set('已载入截图 %s（%dx%d），把它当背景来对齐'
                        % (os.path.basename(p), im.width, im.height))
        self.redraw(full=True)

    def clear_backdrop(self):
        self.backdrop = None
        self.redraw(full=True)
        self.status.set('已去掉截图背景')

    def _alpha_changed(self):
        self.backdrop_alpha = float(self.alpha.get())
        if self.backdrop is not None:
            self.redraw(full=False)

    def _toggle_ghost(self):
        self.ghost = bool(self.ghost_var.get())
        self.redraw()

    # ------------------------------------------------------------- 拖拽
    def _measure_ppu(self):
        """实测"1 个模型单位等于几个屏幕像素"，而不是按深度估。

        估出来的数在透视下会偏，拖起来就和鼠标不同步；这里直接把 pivot 推 1
        个单位，看重心在屏幕上移动了多少像素，两个方向分别量。
        """
        if not self.gun or self.scene is None or self.scene.empty:
            return None
        pivot, rot = self._current()
        try:
            c0 = render.screen_center(self.scene, core.view_matrix(self.gun.geo, self.which), *self._view_size(), fov=self.fov.get())
            out = []
            for i in (0, 1):
                p = list(pivot)
                p[i] += 1.0
                self._apply(p, rot)
                c1 = render.screen_center(self.scene, core.view_matrix(self.gun.geo, self.which), *self._view_size(), fov=self.fov.get())
                self._apply(pivot, rot)
                if not c0 or not c1:
                    return None
                out.append(max(abs(c1[i] - c0[i]), 0.5))
            return out
        finally:
            self._apply(pivot, rot)

    def _drag_start(self, e):
        if not self.gun:
            return
        ppu = self._measure_ppu()
        if not ppu:
            ppu = [render.px_per_unit(self.scene.depth, self._view_size()[1], self.fov.get())] * 2
        ox, oy = self._origin()
        self._drag = (e.x - ox, e.y - oy, list(self._current()[0]), ppu)

    def _drag_move(self, e):
        if not self._drag or not self.gun or self.scene is None:
            return
        x0, y0, p0, ppu = self._drag
        pivot, rot = self._current()
        pivot[0] = p0[0] + (e.x - x0) / ppu[0]
        pivot[1] = p0[1] + (e.y - y0) / ppu[1]
        self.rows['x'].set(pivot[0])
        self.rows['y'].set(pivot[1])
        self._apply(pivot, rot)
        self.dirty = True
        self.redraw(full=False)

    def _drag_end(self, _e):
        if self._drag:
            self._drag = None
            self.redraw(full=True)

    # ------------------------------------------------------------- 动作
    def revert(self):
        if not self.gun:
            return
        o = self.orig.get(self.which)
        if not o:
            return
        b = self.gun.view_bone(self.which)
        b['pivot'] = list(o['pivot'])
        if o['rotation'] is None:
            b.pop('rotation', None)
        else:
            b['rotation'] = list(o['rotation'])
        self._load_values()
        self.dirty = False
        self.redraw(full=True)
        self.status.set('已回到原始值')

    def copy_other(self):
        if not self.gun:
            return
        other = 'iron' if self.which == 'idle' else 'idle'
        o = self.orig.get(other)
        if not o:
            self.status.set('这把枪没有%s定位组' % VIEW_LABEL[other])
            return
        pivot = list(o['pivot'])
        rot = list(o['rotation'] or [0, 0, 0])
        for k, v in zip(('x', 'y', 'z'), pivot):
            self.rows[k].set(v)
        for k, v in zip(('rx', 'ry', 'rz'), rot):
            self.rows[k].set(v)
        self._apply(pivot, rot)
        self.dirty = True
        self.redraw(full=True)
        self.status.set('已把%s的值复制到%s' % (VIEW_LABEL[other], VIEW_LABEL[self.which]))

    def center_on_cross(self):
        if not self.gun or self.scene is None:
            return
        pivot, rot = self._current()
        self._apply(pivot, rot)
        ppu = self._measure_ppu() or [render.px_per_unit(self.scene.depth, self._view_size()[1], self.fov.get())] * 2
        P = core.view_matrix(self.gun.geo, self.which)
        ctr = render.screen_center(self.scene, P, *self._view_size(), fov=self.fov.get())
        if not ctr:
            self.status.set('枪不在画面里，先把它调回来')
            return
        cw, ch = self._view_size()
        pivot[0] += (cw * 0.5 - ctr[0]) / ppu[0]
        pivot[1] += (ch * 0.5 - ctr[1]) / ppu[1]
        for k, v in zip(('x', 'y', 'z'), pivot):
            self.rows[k].set(v)
        self._apply(pivot, rot)
        self.dirty = True
        self.redraw(full=True)
        self.status.set('已把枪的重心对到准星')

    def save(self):
        if not self.gun:
            return
        try:
            ok, how = self.pk.save(self.gun)
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror('写回失败', str(exc))
            return
        b = self.gun.view_bone(self.which)
        self.orig[self.which] = {
            'pivot': list(b.get('pivot')),
            'rotation': (list(b['rotation']) if b.get('rotation') else None),
        }
        self.dirty = False
        self._build_scenes()
        self.redraw(full=True)
        self.status.set('已写回 %s（%s）。到游戏里执行 /tacz reload'
                        % (os.path.basename(self.gun.member), how))


CRASH_LOG = os.path.join(HERE, 'crash.log')


def _report_crash(exc_type, exc, tb):
    """pythonw 没有控制台，不把异常写到看得见的地方，用户只会看到窗口一闪。"""
    import traceback
    text = ''.join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(CRASH_LOG, 'a', encoding='utf-8') as f:
            f.write(text + '\n')
    except Exception:
        pass
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            'TaCZ 调参器启动失败',
            '%s: %s\n\n详细信息写在这个文件里：\n%s' % (exc_type.__name__, exc, CRASH_LOG))
        root.destroy()
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)


def _run_selftest_cli(argv):
    """--selftest [枪包目录]：不开窗口跑一遍自检，结果写到文件里。

    打包成 exe 之后没有控制台，stdout 看不见，所以同时写一份
    selftest_report.txt 到程序目录。
    """
    import selftest
    root = None
    for a in argv:
        if os.path.isdir(a):
            root = a
            break
    if root is None:
        root = find_default_tacz()
    import io
    buf = io.StringIO()
    real = sys.stdout
    sys.stdout = buf
    try:
        code = selftest.main_with_root(root) if hasattr(selftest, 'main_with_root') \
            else selftest.main()
    finally:
        sys.stdout = real
    text = buf.getvalue()
    out = os.path.join(HERE, 'selftest_report.txt')
    try:
        with open(out, 'w', encoding='utf-8') as f:
            f.write(text)
    except Exception:
        out = '(写不进程序目录)'
    # 用消息框给一个结论，windowed 模式下这是唯一看得见的反馈
    try:
        root_win = tk.Tk()
        root_win.withdraw()
        ok = (code == 0)
        messagebox.showinfo(
            '自检' + ('通过' if ok else '失败'),
            ('全部通过' if ok else '有检查项失败') +
            '\n\n完整报告：\n%s\n\n（自检目录：%s）' % (out, root))
        root_win.destroy()
    except Exception:
        pass
    return code


def main():
    sys.excepthook = _report_crash
    if '--selftest' in sys.argv:
        raise SystemExit(_run_selftest_cli(sys.argv[1:]))
    try:
        App().mainloop()
    except Exception:
        import traceback
        _report_crash(*sys.exc_info())
        raise


if __name__ == '__main__':
    main()