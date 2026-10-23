# -*- coding: utf-8 -*-
"""pack.py -- 读枪包、找枪、把改好的定位组写回去。

一个枪包可以是三种形态，游戏里三种都吃（GunPackLoader.scanExtensions 用
Files.newDirectoryStream 遍历 tacz/，目录和 .zip 都收）：
    * 一个目录（有 assets/ 或直接是 assets 本身）
    * 一个 .zip
    * 单个 geo.json

写回有两条路，先试"只改数字"的文本替换，失败才退回整体重写。
理由是枪包进 git 的时候，整体重写会把整个文件的缩进和换行全冲掉，
以后看 diff 就没法看了。
"""
import io
import json
import os
import re
import shutil
import zipfile

import core

GEO_KEYS = ('minecraft:geometry', 'geometry')
GUN_RE = re.compile(r'assets/(?P<ns>[^/]+)/geo_models/gun/(?P<file>[^/]+\.json)$')
GEO_RE = re.compile(r'assets/(?P<ns>[^/]+)/geo_models/(?P<sub>[^/]+)/(?P<file>[^/]+\.json)$')


def geometries(doc):
    for k in GEO_KEYS:
        if k in doc:
            v = doc[k]
            return v if isinstance(v, list) else [v]
    return []


def identifier(geo, fallback):
    return (geo.get('description') or {}).get('identifier') or fallback


class Gun(object):
    """一把枪 = 一个枪包成员里的一个 geometry 定义。"""

    def __init__(self, pack, member, doc, index, geo):
        self.pack = pack
        self.member = member
        self.doc = doc
        self.index = index
        self.geo = geo
        self.name = os.path.basename(member)[:-5]
        self.identifier = identifier(geo, self.name)
        self.geo_by = core.by_name(geo)
        self.has_idle = core.IDLE in self.geo_by
        self.has_iron = core.IRON in self.geo_by
        self.kind = (member.split('geo_models/')[-1].split('/')[0]
                     if 'geo_models/' in member else '?')
        self.n_cubes = sum(len(b.get('cubes') or []) for b in geo['bones'])
        self.n_poly = sum(1 for b in geo['bones'] if b.get('poly_mesh'))
        self.n_bones = len(geo['bones'])

    @property
    def playable(self):
        return self.kind == 'gun' and (self.has_idle or self.has_iron)

    def label(self):
        bits = [self.name]
        if self.has_idle:
            bits.append('腰射')
        if self.has_iron:
            bits.append('机瞄')
        if self.n_poly and not self.n_cubes:
            bits.append('poly_mesh')
        return '  '.join(bits)

    def view_bone(self, which='idle'):
        name = core.IDLE if which == 'idle' else core.IRON
        return self.geo_by.get(name)

    def pivot(self, which='idle'):
        b = self.view_bone(which)
        return list(b.get('pivot') or [0, 0, 0]) if b else None

    def rotation(self, which='idle'):
        b = self.view_bone(which)
        return list(b.get('rotation') or [0, 0, 0]) if b else None

    def set_view(self, which='idle', pivot=None, rotation=None):
        b = self.view_bone(which)
        if b is None:
            return False
        if pivot is not None:
            b['pivot'] = [round(float(v), 5) for v in pivot]
        if rotation is not None:
            vals = [round(float(v), 5) for v in rotation]
            # [0, 0, 0] 和"不写这个键"在游戏里完全等价，那就别写，
            # 免得给本来干净的枪包塞一个没意义的键。
            if all(abs(v) < 1e-9 for v in vals):
                b.pop('rotation', None)
            else:
                b['rotation'] = vals
        return True


class Pack(object):
    """一个枪包。gun 列表在构造时就扫好，后面改的是内存里的 doc。"""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        if not os.path.exists(self.path):
            raise IOError('路径不存在：%s' % path)
        if os.path.isdir(self.path):
            self.kind = 'dir'
        elif self.path.lower().endswith('.zip'):
            self.kind = 'zip'
        else:
            self.kind = 'file'
        self.guns = []
        self._scan()

    # -- 扫描 ---------------------------------------------------------------
    def _members(self):
        """-> [(member_name, read_bytes)]"""
        if self.kind == 'file':
            with open(self.path, 'rb') as f:
                return [(os.path.basename(self.path), f.read())]
        if self.kind == 'zip':
            out = []
            with zipfile.ZipFile(self.path) as z:
                for n in z.namelist():
                    if n.endswith('.json') and '/geo_models/' in '/' + n:
                        out.append((n, z.read(n)))
            return out
        out = []
        for root, _dirs, files in os.walk(self.path):
            for fn in files:
                if not fn.endswith('.json'):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, self.path).replace('\\', '/')
                if 'geo_models' not in rel:
                    continue
                with open(full, 'rb') as f:
                    out.append((rel, f.read()))
        return out

    def _scan(self):
        for member, raw in self._members():
            if not (GEO_RE.search(member) or GUN_RE.search(member)):
                continue
            try:
                doc = json.loads(raw.decode('utf-8-sig'))
            except Exception:
                continue
            geos = geometries(doc)
            for i, geo in enumerate(geos):
                if not isinstance(geo, dict) or 'bones' not in geo:
                    continue
                try:
                    self.guns.append(Gun(self, member, doc, i, geo))
                except Exception:
                    continue
        self.guns.sort(key=lambda g: (not g.playable, g.member, g.name))

    def playable(self):
        return [g for g in self.guns if g.playable]

    # -- 写回 ---------------------------------------------------------------
    def _raw_of(self, gun):
        if self.kind == 'file':
            with open(self.path, 'rb') as f:
                return f.read()
        if self.kind == 'zip':
            with zipfile.ZipFile(self.path) as z:
                return z.read(gun.member)
        full = os.path.join(self.path, gun.member.replace('/', os.sep))
        with open(full, 'rb') as f:
            return f.read()

    def save(self, gun, dry_run=False):
        """把 gun.doc 里的改动写回磁盘。返回 (ok, 说明)。

        先试文本级替换（只动被改的那几个数字），验不过就整体重写。
        """
        raw = self._raw_of(gun)
        text = raw.decode('utf-8-sig')
        patched, how = _patch_text(text, gun)
        if patched is None:
            patched = json.dumps(gun.doc, ensure_ascii=False, indent=2)
            how = 'rewrite'
        if dry_run:
            return True, how
        self._backup(gun.member)
        data = patched.encode('utf-8')
        if self.kind == 'file':
            with open(self.path, 'wb') as f:
                f.write(data)
        elif self.kind == 'zip':
            _rewrite_zip_member(self.path, gun.member, data)
        else:
            full = os.path.join(self.path, gun.member.replace('/', os.sep))
            with open(full, 'wb') as f:
                f.write(data)
        return True, how

    def _backup(self, member):
        if self.kind == 'file':
            shutil.copy2(self.path, self.path + '.bak')
            return
        if self.kind == 'zip':
            shutil.copy2(self.path, self.path + '.bak')
            return
        full = os.path.join(self.path, member.replace('/', os.sep))
        shutil.copy2(full, full + '.bak')


# ---------------------------------------------------------------- 文本级补丁

def _bone_spans(text, name):
    """在原始 JSON 文本里找出名字为 name 的骨骼对象的大致范围。

    只做定位，不做解析——真正的正确性由改完之后 json.loads 验证。
    """
    out = []
    for m in re.finditer(r'"name"\s*:\s*"%s"' % re.escape(name), text):
        # 往左找这个对象的 '{'
        i = m.start()
        depth = 0
        start = None
        while i > 0:
            i -= 1
            ch = text[i]
            if ch == '}':
                depth += 1
            elif ch == '{':
                if depth == 0:
                    start = i
                    break
                depth -= 1
        if start is None:
            continue
        depth = 0
        j = start
        end = None
        while j < len(text):
            ch = text[j]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
            j += 1
        if end:
            out.append((start, end))
    return out


def _fmt_num(v):
    v = round(float(v), 5)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ('%.5f' % v).rstrip('0').rstrip('.')


def _arr(vals):
    return '[' + ', '.join(_fmt_num(v) for v in vals) + ']'


def _patch_text(text, gun):
    """只替换被改动的 pivot / rotation 数组，其余一个字节都不动。"""
    edits = []
    for which in ('idle', 'iron'):
        b = gun.view_bone(which)
        if b is None:
            continue
        for start, end in _bone_spans(text, b['name']):
            body = text[start:end]
            for key in ('pivot', 'rotation'):
                m = re.search(r'"%s"\s*:\s*\[[^\]]*\]' % key, body)
                if key in b:
                    new = '"%s": %s' % (key, _arr(b[key]))
                    if m:
                        edits.append((start + m.start(), start + m.end(), new))
                    else:
                        # 原本没有这个键，塞到 name 后面
                        nm = re.search(r'"name"\s*:\s*"[^"]*"', body)
                        if nm:
                            pos = start + nm.end()
                            edits.append((pos, pos, ', "%s": %s' % (key, _arr(b[key]))))
                elif m:
                    # 字典里已经没有这个键了（比如 rotation 归零），文本里也要删掉，
                    # 连同前导的那个逗号，否则会留下 ", }" 这种非法 JSON。
                    s0 = start + m.start()
                    while s0 > start and text[s0 - 1] in ' \t':
                        s0 -= 1
                    if s0 > start and text[s0 - 1] == ',':
                        s0 -= 1
                    edits.append((s0, start + m.end(), ''))
    if not edits:
        return None, 'none'
    edits.sort(key=lambda e: -e[0])
    out = text
    for s, e, new in edits:
        out = out[:s] + new + out[e:]
    try:
        check = json.loads(out)
    except Exception:
        return None, 'invalid'
    return out, 'patch'


def _rewrite_zip_member(zip_path, member, data):
    tmp = zip_path + '.tmp'
    with zipfile.ZipFile(zip_path) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            buf = data if item.filename == member else zin.read(item.filename)
            zout.writestr(item, buf)
    os.replace(tmp, zip_path)


# ---------------------------------------------------------------- 便捷入口

def find_packs(root):
    """在 tacz/ 目录下找出所有枪包（目录形态与 zip 形态）。"""
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isdir(full):
            if os.path.isdir(os.path.join(full, 'assets')):
                out.append(full)
        elif name.lower().endswith('.zip'):
            out.append(full)
    return out