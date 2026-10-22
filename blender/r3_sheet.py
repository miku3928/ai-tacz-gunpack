"""r3_sheet.py — build the three-view sheet, the overlay and the contact sheet (PIL)."""
from PIL import Image, ImageDraw, ImageFont
import numpy as np, os, sys

ROOT = 'C:/Users/miku/Documents/deepseek-harness/default-workspace/rifle3/'
OUT = ROOT + 'out/'
REF = ROOT + 'ref_side.png'

FONT = 'C:/Windows/Fonts/msyh.ttc'
def font(sz):
    try: return ImageFont.truetype(FONT, sz)
    except Exception: return ImageFont.load_default()


def load_bg(path, bg=(246, 246, 246)):
    im = Image.open(path).convert('RGBA')
    base = Image.new('RGB', im.size, bg)
    base.paste(im, mask=im.split()[3])
    return base


def crop_content(im, pad=0, thresh=246):
    a = np.array(im.convert('L'))
    m = a < thresh
    ys, xs = np.where(m)
    if not len(ys):
        return im
    return im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad),
                    min(im.width, xs.max() + pad), min(im.height, ys.max() + pad)))


def scale_to_w(im, w):
    h = int(round(im.height * w / im.width))
    return im.resize((w, h), Image.LANCZOS)


# ---------------------------------------------------------------- 3-view sheet
side = crop_content(load_bg(OUT + 'side_t.png'))
top = crop_content(load_bg(OUT + 'top_t.png'))
front = crop_content(load_bg(OUT + 'front_t.png'))

W = 2400
side = scale_to_w(side, W)
top = scale_to_w(top, W)
fh = int(front.height * 620 / front.width)
front = front.resize((620, fh), Image.LANCZOS)

M = 46
gap = 40
LBL = 34
H = (M + LBL + side.height + gap + LBL + top.height + gap + LBL + fh + M)
sheet = Image.new('RGB', (W + 2 * M, H), (246, 246, 246))
d = ImageDraw.Draw(sheet)
f = font(26)
y = M
d.text((M, y), '侧视 / SIDE  —  1:1 比例基准视图', fill=(70, 70, 76), font=f)
y += LBL
sheet.paste(side, (M, y)); y += side.height + gap
d.text((M, y), '俯视 / TOP', fill=(70, 70, 76), font=f)
y += LBL
sheet.paste(top, (M, y)); y += top.height + gap
d.text((M, y), '前视 / FRONT', fill=(70, 70, 76), font=f)
y += LBL
sheet.paste(front, (M + (W - 620) // 2, y))
sheet.save(OUT + 'sheet_3views.png')
print('sheet', sheet.size)


# ------------------------------------------------------------------- overlay
# reference: content bbox x 1..1482 (690 mm), bore row 257
ref = Image.open(REF).convert('L')
ra = np.array(ref)
refm = ra < 205
r_ys, r_xs = np.where(refm)
X0, YC, SC = 1, 257.0, 690.0 / 1481.0

ren = Image.open(OUT + 'side_t.png').convert('RGBA')
renm = np.array(ren)[..., 3] > 40

# Simpler: rebuild the model mask by mapping each render pixel through the camera
H, W = refm.shape
out = np.zeros((H, W), bool)
MMPP = 750.0 / 2400.0
ys, xs = np.where(renm)
mmx = xs * MMPP - (375.0 - 345.0)          # x in mm from the muzzle
mmz = ((ren.height * 0.5) - ys) * MMPP      # z in mm from the bore axis
px = np.round(X0 + mmx / SC).astype(int)
py = np.round(YC - mmz / SC).astype(int)
ok = (px >= 0) & (px < W) & (py >= 0) & (py < H)
out[py[ok], px[ok]] = True
dd = out.copy()
for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    dd |= np.roll(out, (dy, dx), (0, 1))
out = dd
inter = (out & refm).sum(); uni = (out | refm).sum()
print('IoU %.4f' % (inter / uni))

vis = np.full((H, W, 3), 255, np.uint8)
vis[refm & ~out] = [235, 90, 90]
vis[out & ~refm] = [80, 130, 235]
vis[out & refm] = [40, 40, 44]
ov = Image.fromarray(vis)
d = ImageDraw.Draw(ov)
d.rectangle([0, 0, 420, 40], fill=(255, 255, 255))
d.text((10, 8), f'silhouette IoU = {inter/uni:.3f}', fill=(30, 30, 34), font=font(24))
ov.save(OUT + 'overlay_vs_reference.png')
print('overlay saved')
