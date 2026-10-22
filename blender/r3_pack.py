"""r3_pack.py - assemble the finished TaCZ gun pack from the exported pieces.

Inputs (all produced by the earlier stages):
    work/tacz/geo.json               r3_export_tacz.py
    work/tacz/palette.json           r3_export_tacz.py
    work/tacz/rifle3.animation.json  r3_anim.py
    work/icons/side.png              work/icons.py
    work/icons/q34.png               work/icons.py

Output:
    work/pack/                       the unpacked pack tree
    out/Rifle3_GunPack_1.0.0.zip     the thing that goes into <instance>/tacz/

The layout follows the official tacz_default_gun pack exactly; the only
difference is model_type "mesh" + a poly_mesh geo, which is what the mesh
loader (TML) hooks into.
"""
import io
import json
import os
import shutil
import zipfile

from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
TACZ = os.path.join(ROOT, 'work', 'tacz')
ICONS = os.path.join(ROOT, 'work', 'icons')
PACK = os.path.join(ROOT, 'work', 'pack')
OUT = os.path.join(ROOT, 'out')

NS = 'rifle3'
GUN = 'rifle3'
VERSION = '1.0.0'
NAME_EN = 'R3 Carbine'
NAME_ZH = 'R3 卡宾枪'
PACK_NAME_EN = 'Rifle3 Armory'
PACK_NAME_ZH = 'Rifle3 军械库'

# ------------------------------------------------------------------ companion --
# The rifle is chambered in a fictional cartridge (7x46mm) that was authored as
# its own little gun pack: a namespace, an ammo index, a display, a box geo, a
# shell geo, an 8-texture set, a lang pair and a crafting recipe.  Rather than
# re-emitting all of that under "rifle3:", the companion pack is merged into our
# zip unchanged.  TaCZ resolves indexes across the WHOLE resource tree
# (FileToIdConverter scans every namespace), and this is exactly what the
# installed third-party packs do -- e.g. CUST GunsmithPack ships emxarms /
# emxcust / trisdyna under a single gunpack.meta.json whose namespace is
# emxcust.  So "7x46:7x46" stays a legal ammo id even though our meta says
# "rifle3".
#
# The only entry that must NOT be copied is the root gunpack.meta.json: one zip
# is one gun pack and it can only have one namespace.
COMPANION_ZIP = os.path.join(
    os.path.dirname(ROOT), 'tacz_sheets', '7x46', 'dist', '7x46_GunPack_1.0.0.zip')
COMPANION_SKIP = ('gunpack.meta.json',)

# Cartridge the rifle feeds on.  "tacz:556x45" is the fallback whenever the
# companion pack is unavailable, so the gun never ends up with a dangling ammo
# reference (TaCZ would then refuse to load the whole gun index).
AMMO = '7x46:7x46'
AMMO_FALLBACK = 'tacz:556x45'

# ------------------------------------------------------------------ attachments --
# The rifle is modelled as five assemblies.  Four of them are TaCZ attachments:
# they are re-origined onto their mounting interface by r3_att_geo.py and listed
# here; the gun keeps an identical copy on its <type>_default bone, which the
# game hides the moment one of these is installed.
#
#   id            type          source geo   slot icon render   icon px
ATTACHMENTS = [
    ('muzzle_std', 'muzzle', 'muzzle_std', 'MUZZLE', 64,
     'R3 Extended Flash Hider', 'R3 加长消焰器',
     {'weight': 0.28, 'ads': {'addend': 0.01},
      'inaccuracy': {'multiplier': 0.92},
      'recoil': {'pitch': {'multiplier': 0.92}, 'yaw': {'multiplier': 0.84}}},
     1),
    ('scope_std', 'scope', 'scope_std', 'OPTIC', 64,
     'R3 1-4x Optic', 'R3 1-4 倍瞄准镜',
     {'weight': 0.42, 'ads': {'addend': 0.05},
      'aim_inaccuracy': {'multiplier': 0.72}},
     2),
    ('stock_std', 'stock', 'stock_std', 'STOCK', 64,
     'R3 Skeleton Stock', 'R3 镂空枪托',
     {'weight': 0.28, 'ads': {'addend': -0.02},
      'recoil': {'pitch': {'multiplier': 0.88}, 'yaw': {'multiplier': 0.9}}},
     3),
    # The quad-stack magazine has no model of its own: its geometry is the gun's
    # mag_extended_1 bone and TaCZ renders it from extended_mag_level.  This is
    # how all 11 official extended magazines are built.
    ('mag_ext_1', 'extended_mag', None, 'MAGAZINE_BIG', 32,
     'R3 Quad-Stack Magazine', 'R3 四排扩容弹匣',
     {'weight': 0.4, 'ads': {'addend': 0.02}, 'extended_mag_level': 1},
     4),
]


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def dump(path, obj, indent=2):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        if indent is None:
            json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
        else:
            json.dump(obj, f, indent=indent, ensure_ascii=False)
        f.write('\n')


# ------------------------------------------------------------------ textures --
def premul_resize(im, size):
    """Resize RGBA without the dark halo that straight-alpha resampling gives."""
    im = im.convert('RGBA')
    r, g, b, a = im.split()
    a_f = a.point(lambda v: v)
    px = im.load()
    w, h = im.size
    out = Image.new('RGBA', (w, h))
    op = out.load()
    for y in range(h):
        for x in range(w):
            R, G, B, A = px[x, y]
            f = A / 255.0
            op[x, y] = (int(R * f), int(G * f), int(B * f), A)
    out = out.resize(size, Image.LANCZOS)
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            R, G, B, A = px[x, y]
            if A:
                f = 255.0 / A
                px[x, y] = (min(255, int(R * f)), min(255, int(G * f)),
                            min(255, int(B * f)), A)
    return out


def make_uv_atlas(palette, path):
    """512x512 stripe atlas: material i owns the full-height column x=32i..32i+31.

    TML negates V (FLIP_UV_V=1) and the sampler may clamp negatives, so the
    previous 16x16 / 2x2-block layout was at the mercy of the V convention.
    A vertically uniform column is immune: any v samples the same colour, and
    the 32px width leaves plenty of margin for linear filtering and mipmaps.
    """
    im = Image.new('RGB', (512, 512), (0, 0, 0))
    px = im.load()
    for i, p in enumerate(palette):
        r, g, b = p['rgb']
        for dy in range(512):
            for dx in range(32):
                px[i * 32 + dx, dy] = (r, g, b)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    return im


def make_hud(src, path):
    """384x128 HUD image.  The official ones are light grey silhouettes so they
    stay readable over the dark HUD backdrop; our render is a mid-grey studio
    shot, so lift the luminance into that band and keep the alpha."""
    im = premul_resize(Image.open(src), (384, 128))
    px = im.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            if not a:
                continue
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
            v = 0.36 + 0.56 * lum
            px[x, y] = (int(255 * v), int(255 * min(1.0, v * 1.01)),
                        int(255 * min(1.0, v * 1.04)), a)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    return im


def make_slot(src, path):
    im = premul_resize(Image.open(src), (64, 64))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    return im


def make_icon(src, path, size):
    """Square attachment-slot icon.

    The group renders are 1000x700 with the part floating somewhere inside, so
    crop to the alpha bbox first and then fit it into 86% of the canvas: the
    slot grid draws these edge to edge and a part that touches the border reads
    as clipped.
    """
    im = Image.open(src).convert('RGBA')
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    inner = int(size * 0.86)
    w, h = im.size
    k = min(inner / float(w), inner / float(h))
    im = premul_resize(im, (max(1, int(w * k)), max(1, int(h * k))))
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    canvas.save(path)
    return canvas


# -------------------------------------------------------------------- content --
def build():
    if os.path.isdir(PACK):
        shutil.rmtree(PACK)

    # Decide the cartridge before writing the gun data: the ammo id must point
    # at a real ammo index or TaCZ drops the entire gun index on the floor.
    ammo = AMMO if os.path.exists(COMPANION_ZIP) else AMMO_FALLBACK

    geo = load(os.path.join(TACZ, 'geo.json'))
    palette = load(os.path.join(TACZ, 'palette.json'))
    anim = load(os.path.join(TACZ, 'rifle3.animation.json'))

    geo['minecraft:geometry'][0]['description']['identifier'] = 'geometry.%s' % GUN
    dump(os.path.join(PACK, 'assets', NS, 'geo_models', 'gun', '%s_geo.json' % GUN), geo,
         indent=None)
    dump(os.path.join(PACK, 'assets', NS, 'animations', '%s.animation.json' % GUN), anim)

    make_uv_atlas(palette, os.path.join(PACK, 'assets', NS, 'textures', 'gun', 'uv', '%s.png' % GUN))
    make_hud(os.path.join(ICONS, 'side.png'),
             os.path.join(PACK, 'assets', NS, 'textures', 'gun', 'hud', '%s.png' % GUN))
    make_slot(os.path.join(ICONS, 'q34.png'),
              os.path.join(PACK, 'assets', NS, 'textures', 'gun', 'slot', '%s.png' % GUN))

    # ---- pack metadata ----------------------------------------------------
    dump(os.path.join(PACK, 'gunpack.meta.json'), {'namespace': NS})
    dump(os.path.join(PACK, 'assets', NS, 'gunpack_info.json'), {
        'version': VERSION,
        'name': 'pack.%s.name' % NS,
        'desc': 'pack.%s.desc' % NS,
        'license': 'All Rights Reserved',
        'authors': ['DSH Blender Agent'],
        'date': '2026-10-21',
        'url': '',
    })

    # ---- display ----------------------------------------------------------
    dump(os.path.join(PACK, 'assets', NS, 'display', 'guns', '%s_display.json' % GUN), {
        'model': '%s:gun/%s_geo' % (NS, GUN),
        'texture': '%s:gun/uv/%s' % (NS, GUN),
        # "mesh" is what the shipped ThermalIQ pack used and what the mesh
        # loader hooks: it swaps the BedrockGunModel for a poly_mesh one as soon
        # as the geo file carries poly_mesh blocks.
        'model_type': 'mesh',
        'hud': '%s:gun/hud/%s' % (NS, GUN),
        'slot': '%s:gun/slot/%s' % (NS, GUN),
        'animation': '%s:%s' % (NS, GUN),
        'use_default_animation': 'rifle',
        'third_person_animation': 'default',
        'transform': {
            'scale': {
                'thirdperson': [0.6, 0.6, 0.6],
                'ground': [0.6, 0.6, 0.6],
                'fixed': [1.2, 1.2, 1.2],
            },
        },
        'muzzle_flash': {
            'texture': 'tacz:flash/common_muzzle_flash',
            'scale': 0.75,
        },
        'iron_zoom': 1.33,
        'zoom_model_fov': 45,
        'shell': {
            'initial_velocity': [5, 2, 1],
            'random_velocity': [1, 1, 0.25],
            'acceleration': [0.0, -10, 0.0],
            'angular_velocity': [360, -1200, 90],
            'living_time': 1.0,
        },
        'sounds': {
            'shoot': 'tacz:m4a1/m4a1_shoot',
            'shoot_3p': 'tacz:m4a1/m4a1_shoot_3p',
            'silence': 'tacz:m4a1/m4a1_silence',
            'silence_3p': 'tacz:m4a1/m4a1_silence_3p',
            'draw': 'tacz:m4a1/m4a1_draw',
            'put_away': 'tacz:m4a1/m4a1_put_away',
            # reload / inspect cues: the state machine plays these keys, and the
            # animation file carries matching sound_effects timings.
            'reload_empty': 'tacz:m4a1/m4a1_reload_empty',
            'reload_tactical': 'tacz:m4a1/m4a1_reload_tactical',
            'inspect': 'tacz:m4a1/m4a1_inspect',
            'dry_fire': 'tacz:dry_fire',
            'fire_select': 'tacz:fire_select',
            'head_hit': 'tacz:head_hit',
            'flesh_hit': 'tacz:flesh_hit',
            'kill': 'tacz:kill',
            'melee_push': 'tacz:melee_stock/melee_stock_01',
            'melee_stock': 'tacz:melee_stock/melee_stock_02',
        },
        'offhand_show': {
            'pos': [1, 19, 4],
            'rotate': [0, 0, 50],
            'scale': [0.5, 0.5, 0.5],
        },
        'hotbar_show': {
            '0': {
                'pos': [-1, 19, 3],
                'rotate': [-180, 0, 130],
                'scale': [0.5, 0.5, 0.5],
            },
        },
    })

    # ---- index + data -----------------------------------------------------
    dump(os.path.join(PACK, 'data', NS, 'index', 'guns', '%s.json' % GUN), {
        'name': '%s.gun.%s.name' % (NS, GUN),
        'display': '%s:%s_display' % (NS, GUN),
        'data': '%s:%s_data' % (NS, GUN),
        'type': 'rifle',
        'tooltip': '%s.gun.%s.desc' % (NS, GUN),
        'sort': 100,
    })

    # feed = the frame the magazine seats (reload_empty insert ends at 1.32 s),
    # cooldown = when the rifle is usable again.  Both follow the animation file.
    dump(os.path.join(PACK, 'data', NS, 'data', 'guns', '%s_data.json' % GUN), {
        'ammo': ammo,
        'ammo_amount': 30,
        # TaCZ hard-requires exactly three entries (official m4a1 uses
        # [40, 50, 60] for its level 1/2/3 magazines) -- a shorter array throws
        # "extended_mag_ammo_amount size must is 3" and the WHOLE gun index
        # fails to load (the item degrades to item.tacz.modern_kinetic_gun with
        # a magenta missing texture).  Level 1 is our own quad stack, levels 2
        # and 3 come from the official extended_mag_2/3 and from the ammo mods
        # (fmj/hp/i all carry extended_mag_level 3, he carries level 1).
        'extended_mag_ammo_amount': [60, 75, 90],
        'bolt': 'closed_bolt',
        'rpm': 720,
        'bullet': {
            'life': 0.75,
            'bullet_amount': 1,
            'damage': 8.5,
            'tracer_count_interval': 0,
            'extra_damage': {
                'armor_ignore': 0.40,
                'head_shot_multiplier': 1.5,
                'damage_adjust': [
                    {'distance': 25, 'damage': 8.5},
                    {'distance': 60, 'damage': 7.5},
                    {'distance': 'infinite', 'damage': 6.5},
                ],
            },
            'speed': 275,
            'gravity': 0.15,
            'knockback': 0,
            'friction': 0.015,
            'ignite': False,
            'pierce': 1,
        },
        'reload': {
            'type': 'magazine',
            'feed': {'empty': 1.32, 'tactical': 1.20},
            'cooldown': {'empty': 2.05, 'tactical': 1.90},
        },
        'draw_time': 0.45,
        'put_away_time': 0.4333,
        'aim_time': 0.16,
        'sprint_time': 0.18,
        'weight': 3.6,
        'movement_speed': {'base': 0.0, 'aim': -0.15, 'reload': -0.1},
        'crawl_recoil_multiplier': 0.5,
        'fire_mode': ['auto', 'semi'],
        'recoil': {
            'pitch': [
                {'time': 0, 'value': [0.35, 0.35]},
                {'time': 0.3, 'value': [0.25, 0.25]},
                {'time': 0.5, 'value': [-0.125, -0.125]},
                {'time': 0.65, 'value': [0, 0]},
            ],
            'yaw': [
                {'time': 0, 'value': [0.1, 0.2]},
                {'time': 0.3, 'value': [0.1, 0.2]},
                {'time': 0.5, 'value': [0, 0]},
            ],
        },
        'inaccuracy': {'stand': 5, 'move': 5.5, 'sneak': 2.75, 'lie': 1.5, 'aim': 0.1},
        'melee': {
            'distance': 1,
            'cooldown': 0.6,
            'default': {
                'animation_type': 'melee_stock',
                'distance': 1,
                'range_angle': 30,
                'damage': 2,
                'knockback': 0.5,
                'prep': 0.1,
            },
        },
        # exactly the mount nodes the geo carries: muzzle_pos, scope_pos,
        # stock_pos, grip_pos, laser_pos and the magazine / mag_extended_1 pair.
        # The five *_pos bones are the contract TaCZ looks up by name
        # (GunModelConstant.ATTACHMENT_POS_SUFFIX = "_pos"), so an official
        # attachment of a listed type always finds a place to hang.
        'allow_attachment_types': ['scope', 'stock', 'muzzle', 'grip', 'laser',
                                   'extended_mag'],
        # The rifle is modelled WITH its optic, so the optic ships installed
        # rather than lying in the inventory.  This is how the official AUG and
        # P90 do it ({"scope": "tacz:scope_aug_default"}), and it is also what
        # makes aiming down the scope work at all: a built-in *_default bone is
        # just geometry, only an installed attachment is a real sight.
        'builtin_attachments': {'scope': '%s:scope_std' % NS},
    })

    # ---- attachments -----------------------------------------------------
    tags = {}
    for (aid, atype, src, icon, px, name_en, name_zh, data, sort) in ATTACHMENTS:
        display = {
            'slot': '%s:attachment/slot/%s' % (NS, aid),
            'sounds': {
                'install': 'tacz:attachments/attachment_general_a',
                'uninstall': 'tacz:attachments/attachment_general_uninstall',
            },
        }
        if src:
            # the attachment reuses the gun's stripe atlas: r3_att_geo.py keeps
            # the UVs untouched, so one 512x512 palette serves the whole pack
            display['model'] = '%s:attachment/%s_geo' % (NS, src)
            display['texture'] = '%s:gun/uv/%s' % (NS, GUN)
            gdst = os.path.join(PACK, 'assets', NS, 'geo_models',
                                'attachment', '%s_geo.json' % aid)
            os.makedirs(os.path.dirname(gdst), exist_ok=True)
            shutil.copyfile(os.path.join(TACZ, 'att', '%s_geo.json' % src), gdst)
        if atype == 'extended_mag':
            display['sounds'] = {
                'install': 'tacz:attachments/extended_mag_install',
                'uninstall': 'tacz:attachments/extended_mag_uninstall',
            }
        if atype == 'scope':
            # Without these three keys the sight is just a tube glued to the
            # camera: TaCZ never enters scope mode, the ADS camera sits inside
            # the geometry and the screen is covered by the rear lens.  A fixed
            # 4.25x prism is exactly what the official single-power scopes
            # declare (scope_98k zoom[4.25] fov 30, scope_acq zoom[4.25] fov 35);
            # single power needs no "views" / "views_fov" arrays.
            display['zoom'] = [4.25]
            display['scope'] = True
            display['fov'] = 35.0

        dump(os.path.join(PACK, 'assets', NS, 'display', 'attachments',
                          '%s_display.json' % aid), display)
        make_icon(os.path.join(ROOT, 'work', '%s_iso.png' % icon),
                  os.path.join(PACK, 'assets', NS, 'textures', 'attachment',
                               'slot', '%s.png' % aid), px)
        dump(os.path.join(PACK, 'data', NS, 'index', 'attachments',
                          '%s.json' % aid), {
            'name': '%s.attachment.%s.name' % (NS, aid),
            'display': '%s:%s_display' % (NS, aid),
            'data': '%s:%s_data' % (NS, aid),
            'type': atype,
            'sort': sort,
        })
        dump(os.path.join(PACK, 'data', NS, 'data', 'attachments',
                          '%s_data.json' % aid), data)
        tags.setdefault(atype, []).append('%s:%s' % (NS, aid))

    # Attachment membership is by tag, exactly like the official pack: the gun
    # lists "#ns:tag" and each tag file lists the items in it.  Using our own
    # namespace keeps the pack self-contained instead of borrowing tacz: tags,
    # which would silently break if the official pack is not installed.
    for atype, ids in tags.items():
        dump(os.path.join(PACK, 'data', NS, 'tacz_tags', 'attachments',
                          '%s.json' % atype), ids)
    # Our own tags keep the pack usable on its own, but the interesting
    # attachments are the official ones: extended_mag_1/2/3 are the only way to
    # reach mag_extended_2/3, and the ammo mods (fmj / hp / i) also carry an
    # extended_mag_level, which is why fitting FMJ swaps the magazine body.
    # Tags are a global registry keyed by resource location, so a "#tacz:" entry
    # resolves even though the file lives in another pack.
    allowed = ['#%s:%s' % (NS, t) for t in sorted(tags)]
    # The official packs' own tags: fitting any of the 19 official scopes /
    # sights, the 9 stocks, the 12 grips or the lasers is then a normal in-game
    # operation instead of being refused by the attachment screen.
    allowed += ['#tacz:scope_scope', '#tacz:scope_sight', '#tacz:muzzle',
                '#tacz:stock', '#tacz:grip', '#tacz:ar_laser',
                '#tacz:extended_mag', '#tacz:ammo_mod_no_he']
    dump(os.path.join(PACK, 'data', NS, 'tacz_tags', 'attachments',
                      'allow_attachments', '%s.json' % GUN), allowed)

    # ---- language ---------------------------------------------------------
    dump(os.path.join(PACK, 'assets', NS, 'lang', 'en_us.json'), {
        'pack.%s.name' % NS: PACK_NAME_EN,
        'pack.%s.desc' % NS: 'A Blender-modelled carbine in 7x46mm, with full reload animations.',
        '%s.gun.%s.name' % (NS, GUN): NAME_EN,
        '%s.gun.%s.desc' % (NS, GUN): 'A procedurally modelled carbine. Chambered in the fictional 7x46mm cartridge.',
        **{'%s.attachment.%s.name' % (NS, a[0]): a[5] for a in ATTACHMENTS},
    })
    dump(os.path.join(PACK, 'assets', NS, 'lang', 'zh_cn.json'), {
        'pack.%s.name' % NS: PACK_NAME_ZH,
        'pack.%s.desc' % NS: 'Blender 程序化建模的 7x46mm 卡宾枪，带完整换弹动画。',
        '%s.gun.%s.name' % (NS, GUN): NAME_ZH,
        '%s.gun.%s.desc' % (NS, GUN): '程序化建模的卡宾枪，发射架空的 7x46mm 弹。',
        **{'%s.attachment.%s.name' % (NS, a[0]): a[6] for a in ATTACHMENTS},
    })

    # ---- companion cartridge pack -----------------------------------------
    merge_companion()

    # ---- zip --------------------------------------------------------------
    os.makedirs(OUT, exist_ok=True)
    zpath = os.path.join(OUT, 'Rifle3_GunPack_%s.zip' % VERSION)
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(PACK):
            for f in sorted(files):
                full = os.path.join(base, f)
                rel = os.path.relpath(full, PACK).replace(os.sep, '/')
                z.write(full, rel)
    return zpath


def merge_companion():
    """Merge the 7x46 cartridge pack into our tree, minus its root meta file.

    Return True when the cartridge is available, False when the caller must
    fall back to a stock cartridge.  Everything is copied byte for byte: the
    companion's indexes / displays / geos / textures / lang are already wired
    to the "7x46" namespace, and rewriting them to "rifle3:" would mean also
    rewriting every id string inside them for no gain.
    """
    if not os.path.exists(COMPANION_ZIP):
        print('companion pack missing, ammo stays %s: %s'
              % (AMMO_FALLBACK, COMPANION_ZIP))
        return False
    n = 0
    with zipfile.ZipFile(COMPANION_ZIP) as z:
        for info in z.infolist():
            rel = info.filename.replace('\\', '/')
            if info.is_dir() or rel in COMPANION_SKIP:
                continue
            dst = os.path.join(PACK, *rel.split('/'))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as f:
                f.write(z.read(info))
            n += 1
    print('companion cartridge merged: %d files from %s'
          % (n, os.path.basename(COMPANION_ZIP)))
    return True


def report(zpath):
    print('pack zip:', zpath, os.path.getsize(zpath), 'bytes')
    with zipfile.ZipFile(zpath) as z:
        for n in sorted(z.namelist()):
            print('  %-64s %8d' % (n, z.getinfo(n).file_size))


if __name__ == '__main__':
    report(build())
