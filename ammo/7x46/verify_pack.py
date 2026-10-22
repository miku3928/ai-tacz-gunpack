# -*- coding: utf-8 -*-
"""Validate the assembled 7x46 gunpack: every declared resource path must exist.

tacz id convention:
  "<ns>:ammo/uv/x"   -> assets/<ns>/textures/ammo/uv/x.png
  "<ns>:shell/x"     -> both geo_models/shell/x.json and textures/shell/x.png
  "<ns>:xxxx_display"-> assets/<ns>/display/ammo/xxxx_display.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, 'dist', '7x46_gunpack')
NS = '7x46'

def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return json.load(f)

errs = []

def need(rel, what):
    p = os.path.join(PACK, rel)
    if not os.path.exists(p):
        errs.append('MISSING %-14s %s' % (what, rel))
    return p

# every json in the tree must parse
for root, _, files in os.walk(PACK):
    for fn in files:
        if fn.endswith('.json'):
            p = os.path.join(root, fn)
            try:
                load(p)
            except Exception as e:
                errs.append('BADJSON %s: %s' % (os.path.relpath(p, PACK), e))

meta = load(os.path.join(PACK, 'gunpack.meta.json'))
if meta.get('namespace') != NS:
    errs.append('meta namespace %r' % meta.get('namespace'))

info = load(os.path.join(PACK, 'assets', NS, 'gunpack_info.json'))
for k in ('version', 'name', 'desc', 'license', 'authors', 'date'):
    if k not in info:
        errs.append('gunpack_info missing ' + k)

idx = load(os.path.join(PACK, 'data', NS, 'index', 'ammo', NS + '.json'))
for k in ('name', 'display', 'stack_size', 'sort'):
    if k not in idx:
        errs.append('index missing ' + k)

disp = load(os.path.join(PACK, 'assets', NS, 'display', 'ammo', NS + '_display.json'))

def res(path, ext, sub):
    ns, _, rest = path.partition(':')
    if ns != NS:
        errs.append('bad namespace %r' % ns); return None
    return need('assets/%s/%s/%s%s' % (ns, sub, rest, ext), rest)

res(disp['model'], '.json', 'geo_models')
res(disp['texture'], '.png', 'textures')
res(disp['slot'], '.png', 'textures')
res(disp['shell']['model'], '.json', 'geo_models')
res(disp['shell']['texture'], '.png', 'textures')

# the _n/_s siblings should exist for whatever png the display points at
for pth in (disp['texture'], disp['shell']['texture']):
    for suf in ('_n', '_s'):
        base_p = os.path.join(PACK, 'assets', NS, 'textures', pth.split(':')[1] + '.png')
        sib = base_p[:-4] + suf + '.png'
        if not os.path.exists(sib):
            errs.append('MISSING map %s' % os.path.relpath(sib, PACK))

# geometry identifiers and declared texture sizes
for rel in ('assets/%s/geo_models/ammo/%s.json' % (NS, NS),
            'assets/%s/geo_models/shell/%s_shell.json' % (NS, NS)):
    g = load(os.path.join(PACK, rel))['minecraft:geometry'][0]
    d = g['description']
    cubes = sum(len(b.get('cubes', [])) for b in g['bones'])
    print('%-46s %-22s tex %dx%d bones %2d cubes %2d' % (
        rel, d['identifier'], d['texture_width'], d['texture_height'],
        len(g['bones']), cubes))

# lang must define every key referenced from index
for lg in ('en_us', 'zh_cn'):
    L = load(os.path.join(PACK, 'assets', NS, 'lang', lg + '.json'))
    for k in (idx['name'], info['name'], info['desc']):
        if k not in L:
            errs.append('lang %s missing %s' % (lg, k))

# slot icon is 32x32 like every stock one
from PIL import Image
ic = Image.open(os.path.join(PACK, 'assets', NS, 'textures', 'ammo', 'slot', NS + '.png'))
print('slot icon', ic.size, ic.mode)
if ic.size != (32, 32):
    errs.append('slot icon not 32x32')

# recipe must exist, reference our own ammo id and use a known group
rp = need('data/%s/recipes/ammo/%s.json' % (NS, NS), 'recipe')
if os.path.exists(rp):
    rc = load(rp)
    if rc.get('type') != 'tacz:gun_smith_table_crafting':
        errs.append('recipe type %r' % rc.get('type'))
    res_ = rc.get('result', {})
    if res_.get('id') != '%s:%s' % (NS, NS):
        errs.append('recipe result id %r' % res_.get('id'))
    if not rc.get('materials'):
        errs.append('recipe has no materials')
    for m in rc.get('materials', []):
        if 'count' not in m:
            errs.append('recipe material missing count: %r' % m)
    groups = ('pd_cartridges', 'ifp_rifle_cartridges', 'lc_specialized',
              'explosives', 'shotgun_shells', 'alternative_proj')
    if res_.get('group') not in groups:
        errs.append('recipe group %r not a known tab' % res_.get('group'))
    print('recipe %-24s -> %s x%s' % (res_.get('group'), res_.get('id'), res_.get('count')))

print()
if errs:
    print('FAIL', len(errs))
    for e in errs:
        print('  ' + e)
    sys.exit(1)
print('ALL CHECKS PASS')