import os, sys, zipfile, tempfile, shutil, subprocess, json
HERE = os.path.dirname(os.path.abspath(__file__))
Z = os.path.join(HERE, 'dist', '7x46_GunPack_1.0.0.zip')
tmp = tempfile.mkdtemp()
with zipfile.ZipFile(Z) as z:
    names = z.namelist()
    z.extractall(tmp)
print('files in zip:', len(names))
# every entry must be inside the pack, no absolute or parent paths
bad = [n for n in names if n.startswith('/') or '..' in n.split('/')]
print('unsafe entries:', bad)

root = os.path.join(tmp)
# re-run the path checks against the extracted tree
def has(rel):
    return os.path.exists(os.path.join(root, rel))
req = [
    'gunpack.meta.json',
    'assets/7x46/gunpack_info.json',
    'assets/7x46/display/ammo/7x46_display.json',
    'assets/7x46/geo_models/ammo/7x46.json',
    'assets/7x46/geo_models/shell/7x46_shell.json',
    'assets/7x46/lang/en_us.json',
    'assets/7x46/lang/zh_cn.json',
    'assets/7x46/textures/ammo/slot/7x46.png',
    'assets/7x46/textures/ammo/uv/7x46.png',
    'assets/7x46/textures/ammo/uv/7x46_n.png',
    'assets/7x46/textures/ammo/uv/7x46_s.png',
    'assets/7x46/textures/shell/7x46_shell.png',
    'assets/7x46/textures/shell/7x46_shell_n.png',
    'assets/7x46/textures/shell/7x46_shell_s.png',
    'data/7x46/index/ammo/7x46.json',
    'data/7x46/recipes/ammo/7x46.json',
]
missing = [r for r in req if not has(r)]
print('missing:', missing)

from PIL import Image
for rel in req:
    if rel.endswith('.png'):
        with Image.open(os.path.join(root, rel)) as im:
            info = (im.size, im.mode)
        print('%-52s %s %s' % (rel, info[0], info[1]))

# no stray files (e.g. .DS_Store, __pycache__)
extra = [n for n in names if not any(n == r for r in req)]
print('extra entries:', extra)
import time
time.sleep(0.2)
shutil.rmtree(tmp, ignore_errors=True)
print()
print('ZIP OK' if not (missing or bad or extra) else 'ZIP PROBLEM')
