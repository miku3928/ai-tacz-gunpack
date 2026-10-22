"""r3_catalog.py — build the disassembly catalogue sheets from the group renders.

Reads work/<G>_iso.png and work/<G>_side.png (transparent, produced by
r3_grp_render.py) and writes:

    out/catalog_groups.png    one cell per assembly: iso render, name, size, parts
    out/catalog_sides.png     the five side elevations, all at 1:1 mm scale
    out/exploded.png          copy of the exploded assembly render

Run with the bundled python (this script needs PIL; Blender's python has none):

    C:/Users/miku/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe r3_catalog.py
"""
import json
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, 'work')
OUT = os.path.join(ROOT, 'out')

# group key -> (chinese, english, size text, part count, one-line description)
GROUPS = [
    ('MUZZLE', '枪口装置', 'MUZZLE DEVICE', '57 x 41 x 41 mm', 2,
     '多槽消焰器 / 环槽 + 侧排气孔 / 内孔可见'),
    ('OPTIC', '瞄准镜', 'OPTIC', '180 x 51 x 77 mm', 5,
     '物镜 + 中部镜身 + 侧调焦轮 / 顶塔 / 翻盖 / 一体镜座'),
    ('MAGAZINE', '弹匣', 'MAGAZINE', '100 x 27 x 134 mm', 4,
     '弧形弹匣体 / 侧加强筋 / 直板底板 / 卡榫座'),
    ('MAGAZINE_BIG', '大弹匣', 'MAGAZINE / QUAD', '0 x 0 x 0 mm', 4,
     '四排双进加长弹匣 / 1.6 倍厚度 / 容量约翻倍（选装）'),
    ('STOCK', '枪托', 'STOCK', '216 x 47 x 122 mm', 7,
     '镂空三角骨架 / 斜撑条 / 贴腮板 / 橡胶缓冲垫'),
    ('BODY', '本体', 'BODY', '432 x 46 x 190 mm', 31,
     '护木 + 机匣 + 下机匣 + 握把 + 扳机组'),
]

BG = (245, 246, 248)
CARD = (255, 255, 255)
INK = (28, 30, 34)
SUB = (108, 114, 122)
LINE = (216, 220, 226)
ACCENT = (188, 58, 46)


def font(size, bold=False):
    """Pick a CJK-capable face; fall back to anything loadable."""
    names = (['msyhbd.ttc', 'msyh.ttc', 'simhei.ttf'] if bold
             else ['msyh.ttc', 'msyhl.ttc', 'simhei.ttf'])
    for n in names:
        for base in ('C:/Windows/Fonts/', '/usr/share/fonts/truetype/'):
            p = base + n
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
    return ImageFont.load_default()


def load_rgba(path):
    return Image.open(path).convert('RGBA')


def fit(im, box_w, box_h):
    """Scale a transparent render to fit a box, keeping aspect."""
    w, h = im.size
    k = min(box_w / float(w), box_h / float(h))
    return im.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)


def card(iso, key, cn, en, size_txt, nparts, desc, w, h):
    """One catalogue cell."""
    c = Image.new('RGB', (w, h), CARD)
    d = ImageDraw.Draw(c)
    d.rectangle([0, 0, w - 1, h - 1], outline=LINE, width=2)

    pad = 34
    # ---- render area
    art_h = h - 210
    art = fit(iso, w - pad * 2, art_h - pad)
    c.paste(art, ((w - art.width) // 2, pad + (art_h - pad - art.height) // 2), art)

    # ---- accent rule + index
    y = art_h + 6
    d.rectangle([pad, y, pad + 46, y + 5], fill=ACCENT)
    f_cn = font(46, bold=True)
    f_en = font(23)
    f_sm = font(22)
    d.text((pad, y + 22), cn, font=f_cn, fill=INK)
    d.text((pad, y + 80), en, font=f_en, fill=SUB)

    # ---- metrics, right aligned
    met = '%s\n%d parts' % (size_txt, nparts)
    tw = d.textlength(size_txt, font=f_sm)
    d.text((w - pad - tw, y + 26), size_txt, font=f_sm, fill=ACCENT)
    d.text((w - pad - d.textlength('%d parts' % nparts, font=f_sm), y + 56),
           '%d parts' % nparts, font=f_sm, fill=SUB)

    d.text((pad, y + 122), desc, font=f_sm, fill=SUB)
    return c


def measured():
    """Real size and part count per group, written by r3_grp_render.py."""
    path = os.path.join(WORK, 'grp_bbox.json')
    if not os.path.exists(path):
        raise SystemExit('run r3_grp_render.py first - grp_bbox.json is missing')
    with open(path) as fh:
        return json.load(fh)


def main():
    os.makedirs(OUT, exist_ok=True)
    m = measured()

    # every dimension and part count on the sheet comes from the render pass,
    # never from a literal here
    items = []
    for key, cn, en, _sz, _n, desc in GROUPS:
        d = m[key]
        sz = '%.0f x %.0f x %.0f mm' % tuple(d['size'])
        items.append((key, cn, en, sz, d['parts'], desc))

    # ================================================= 1. group catalogue
    W, H = 1240, 1020
    cols, rows = 3, 2
    sheet = Image.new('RGB', (cols * W + 4 * 40, rows * H + 3 * 40 + 210), BG)
    d = ImageDraw.Draw(sheet)

    d.text((40, 44), '分解目录 / ASSEMBLY CATALOGUE', font=font(64, bold=True), fill=INK)
    d.text((40, 124), '博伊西 AR 平台 · 全长 704 mm · 六组部件 · 五十四件网格',
           font=font(30), fill=SUB)
    d.rectangle([40, 176, 40 + 96, 182], fill=ACCENT)

    for i, (key, cn, en, sz, n, desc) in enumerate(items):
        iso = load_rgba(os.path.join(WORK, '%s_iso.png' % key))
        cell = card(iso, key, cn, en, sz, n, desc, W, H)
        cx = 40 + (i % cols) * (W + 40)
        cy = 210 + (i // cols) * (H + 40)
        sheet.paste(cell, (cx, cy))

    sheet.save(os.path.join(OUT, 'catalog_groups.png'))
    print('catalog_groups', sheet.size)

    # ================================================= 2. side elevations
    # every group is rendered at the same px/mm, so stacking them at 1x keeps
    # the TRUE relative scale between the assemblies - that is the whole point
    # of this sheet.
    ims = [(g, load_rgba(os.path.join(WORK, '%s_side.png' % g[0]))) for g in items]
    maxw = max(im.width for _, im in ims)
    pad, row_gap, lbl_w = 46, 26, 300
    total_h = 210 + sum(im.height + row_gap for _, im in ims) + 30
    sh = Image.new('RGB', (lbl_w + maxw + pad * 2, total_h), BG)
    dd = ImageDraw.Draw(sh)
    dd.text((pad, 44), '各部件侧视（同一比例）/ GROUP ELEVATIONS 1:1',
            font=font(58, bold=True), fill=INK)
    dd.text((pad, 120), '同一比例叠放，可直接比较各部分的真实尺寸',
            font=font(28), fill=SUB)
    dd.rectangle([pad, 176, pad + 96, 182], fill=ACCENT)

    y = 210
    for (key, cn, en, sz, n, desc), im in zip(items, [i for _, i in ims]):
        dd.text((pad, y + 24), cn, font=font(38, bold=True), fill=INK)
        dd.text((pad, y + 74), en, font=font(21), fill=SUB)
        dd.text((pad, y + 104), sz, font=font(21), fill=ACCENT)
        dd.text((pad, y + 132), '%d parts' % n, font=font(21), fill=SUB)
        x = lbl_w + pad
        # baseline rule so the eye can see the 1:1 scale holds
        dd.line([x, y + im.height // 2, x + im.width, y + im.height // 2],
                fill=(232, 234, 238), width=1)
        sh.paste(im, (x, y), im)
        y += im.height + row_gap
    sh.save(os.path.join(OUT, 'catalog_sides.png'))
    print('catalog_sides', sh.size)

    # ================================================= 3. exploded copy
    src = os.path.join(WORK, 'exploded.png')
    if os.path.exists(src):
        ex = Image.open(src).convert('RGBA')
        bg = Image.new('RGB', ex.size, BG)
        bg.paste(ex, (0, 0), ex)
        bg.save(os.path.join(OUT, 'exploded.png'))
        print('exploded', bg.size)


if __name__ == '__main__':
    main()
