# -*- coding: utf-8 -*-
"""生成图标：深色圆角底 + 红色准星 + 一支斜指右上的步枪侧影。

小尺寸下能认出来的只有三件事：细长的枪管、方块状的机匣、下垂的弹匣。
枪托和握把要短，不然整体会像一辆车。准星要压在枪口延长线上，
离开枪身就变成两个不相干的图案了。
"""
import os

from PIL import Image, ImageDraw

S = 512
SS = 4
BG = (26, 28, 32, 255)
BODY = (196, 202, 210, 255)
DARK = (110, 116, 124, 255)
MID = (152, 158, 166, 255)
RED = (228, 96, 96, 255)


def build():
    n = S * SS
    k = n / 512.0
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        [0, 0, n - 1, n - 1], radius=int(n * 0.20), fill=BG)

    gun = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    g = ImageDraw.Draw(gun)

    # 横放的步枪，基准点 (250, 300)，画完整体旋转 -18°
    g.polygon([(92 * k, 288 * k), (166 * k, 280 * k),
               (166 * k, 324 * k), (92 * k, 332 * k)], fill=DARK)      # 枪托
    g.rectangle([158 * k, 272 * k, 302 * k, 324 * k], fill=BODY)       # 机匣
    g.rectangle([196 * k, 258 * k, 298 * k, 274 * k], fill=MID)        # 上导轨
    g.rectangle([298 * k, 282 * k, 370 * k, 316 * k], fill=MID)        # 护木
    g.rectangle([366 * k, 290 * k, 468 * k, 310 * k], fill=BODY)       # 枪管
    g.rectangle([460 * k, 284 * k, 484 * k, 316 * k], fill=DARK)       # 消焰器
    g.rectangle([400 * k, 272 * k, 416 * k, 292 * k], fill=DARK)       # 准星座
    g.polygon([(204 * k, 324 * k), (252 * k, 324 * k),
               (264 * k, 396 * k), (216 * k, 396 * k)], fill=DARK)     # 弹匣
    g.polygon([(278 * k, 324 * k), (314 * k, 324 * k),
               (326 * k, 372 * k), (290 * k, 372 * k)], fill=DARK)     # 握把

    gun = gun.rotate(-18, resample=Image.BICUBIC, center=(290 * k, 300 * k))
    img.alpha_composite(gun)

    d = ImageDraw.Draw(img)
    # 准星压在枪口正上方的延长线上
    cx, cy = 424 * k, 176 * k
    gap, ln, wd = 26 * k, 52 * k, 12 * k
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([(cx + dx * gap, cy + dy * gap),
                (cx + dx * (gap + ln), cy + dy * (gap + ln))],
               fill=RED, width=int(wd))
    r = 9 * k
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)

    return img.resize((S, S), Image.LANCZOS)


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    im = build()
    im.save(os.path.join(here, 'icon.png'))
    im.save(os.path.join(here, 'icon.ico'),
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                   (128, 128), (256, 256)])
    im.resize((48, 48), Image.LANCZOS).save(os.path.join(here, '_icon48.png'))
    print('icon written')
