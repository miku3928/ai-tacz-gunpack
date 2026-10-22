# -*- coding: utf-8 -*-
"""Assemble the finished 7x46 gunpack tree and zip it.

Layout mirrors the stock pack, only with our own namespace:
  gunpack.meta.json            -> {"namespace": "7x46"}
  assets/7x46/...              -> geo_models, textures, display, lang, info
  data/7x46/index/ammo/...     -> the item registration
"""
import json, os, shutil, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
NS = '7x46'
DIST = os.path.join(HERE, 'dist')
PACK = os.path.join(DIST, NS + '_gunpack')
SRC = os.path.join(HERE, 'pack')

def w(rel, data):
    p = os.path.join(PACK, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if isinstance(data, (dict, list)):
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
    else:
        shutil.copyfile(data, p)
    return p

if os.path.isdir(DIST):
    shutil.rmtree(DIST)

# ---- pack manifest -------------------------------------------------------
w('gunpack.meta.json', {'namespace': NS})

w('assets/%s/gunpack_info.json' % NS, {
    'version': '1.0.0',
    'name': 'pack.%s.name' % NS,
    'desc': 'pack.%s.desc' % NS,
    'license': 'CC BY-NC-SA 4.0',
    'authors': ['DSH'],
    'date': '2026-10-21',
    'url': '',
})

# ---- item registration ---------------------------------------------------
w('data/%s/index/ammo/%s.json' % (NS, NS), {
    'name': '%s.ammo.%s.name' % (NS, NS),
    'display': '%s:%s_display' % (NS, NS),
    'stack_size': 60,
    'sort': 25,   # after every stock ammo (12g is 24)
})

# ---- crafting recipe -----------------------------------------------------
# same shape as the stock ifp_rifle_cartridges recipes (5.56x45 = copper15 +
# gunpowder3 -> 45 rounds); ours adds lapis for the AP core and pays 4 powder,
# so it comes out a little rarer but hits harder.
w('data/%s/recipes/ammo/%s.json' % (NS, NS), {
    'materials': [
        {'item': {'tag': 'forge:ingots/copper'}, 'count': 15},
        {'item': {'tag': 'forge:gunpowder'}, 'count': 4},
        {'item': {'tag': 'forge:gems/lapis'}, 'count': 4},
    ],
    'result': {
        'type': 'ammo',
        'group': 'ifp_rifle_cartridges',
        'id': '%s:%s' % (NS, NS),
        'count': 40,
    },
    'type': 'tacz:gun_smith_table_crafting',
})

# ---- display -------------------------------------------------------------
w('assets/%s/display/ammo/%s_display.json' % (NS, NS), {
    'model': '%s:ammo/%s' % (NS, NS),
    'texture': '%s:ammo/uv/%s' % (NS, NS),
    'slot': '%s:ammo/slot/%s' % (NS, NS),
    'shell': {
        'model': '%s:shell/%s_shell' % (NS, NS),
        'texture': '%s:shell/%s_shell' % (NS, NS),
    },
    'tracer_color': '#FFB347',
})

# ---- geometry ------------------------------------------------------------
w('assets/%s/geo_models/ammo/%s.json' % (NS, NS),
  json.load(open(os.path.join(SRC, 'geo_models', 'ammo', '7x46.json'), encoding='utf-8')))
w('assets/%s/geo_models/shell/%s_shell.json' % (NS, NS),
  json.load(open(os.path.join(SRC, 'geo_models', 'shell', '7x46_shell.json'), encoding='utf-8')))

# ---- textures ------------------------------------------------------------
for src, dst in [
    ('7x46_uv.png',            'ammo/uv/%s.png'),
    ('7x46_uv_n.png',          'ammo/uv/%s_n.png'),
    ('7x46_uv_s.png',          'ammo/uv/%s_s.png'),
    ('textures/shell/7x46_shell.png',   'shell/%s_shell.png'),
    ('textures/shell/7x46_shell_n.png', 'shell/%s_shell_n.png'),
    ('textures/shell/7x46_shell_s.png', 'shell/%s_shell_s.png'),
]:
    w('assets/%s/textures/' % NS + (dst % NS), os.path.join(SRC, src))

# item slot icon (32x32, straight copy of the delivered icon)
w('assets/%s/textures/ammo/slot/%s.png' % (NS, NS), os.path.join(HERE, '7x46.png'))

# ---- lang ----------------------------------------------------------------
w('assets/%s/lang/en_us.json' % NS, {
    'pack.%s.name' % NS: '7x46 Experimental Cartridge',
    'pack.%s.desc' % NS: 'A fictional 7x46mm intermediate rifle cartridge with a black-tipped AP projectile.',
    '%s.ammo.%s.name' % (NS, NS): '§e7x46mm Bullet',
})
w('assets/%s/lang/zh_cn.json' % NS, {
    'pack.%s.name' % NS: '7x46 实验弹',
    'pack.%s.desc' % NS: '一种架空的 7x46mm 中间威力步枪弹，配黑尖穿甲弹头。',
    '%s.ammo.%s.name' % (NS, NS): '§e7x46mm 步枪子弹',
})

# ---- zip -----------------------------------------------------------------
zp = os.path.join(DIST, NS + '_GunPack_1.0.0.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(PACK):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            z.write(fp, os.path.relpath(fp, PACK).replace('\\', '/'))

n = sum(len(f) for _, _, f in os.walk(PACK))
print('files', n)
print('pack ', PACK)
print('zip  ', zp, os.path.getsize(zp), 'bytes')