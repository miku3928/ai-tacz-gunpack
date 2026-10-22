"""tacz_check.py - offline validator for ANY TaCZ gun pack (model agnostic).

Usage:
    python tacz_check.py <pack.zip | pack_dir> [<pack2> ...]
    python tacz_check.py <pack> --quiet      # only the summary line
    python tacz_check.py <pack> --json out.json
    python tacz_check.py <pack> --no-refs    # do not consult sibling packs

Why this exists
---------------
Almost every way a TaCZ pack can be wrong fails SILENTLY: the gun simply does not
appear, the texture is magenta, the attachment list is empty, the animation does
not play, a face is black.  None of those print a stack trace you can act on.
This script reproduces, offline, every check that would otherwise cost a game
restart to discover.

It knows nothing about a particular gun.  The namespace is read from
gunpack.meta.json, every index entry is enumerated from the pack itself, and a
pack that holds several namespaces (legal, and common in the wild) is walked
namespace by namespace.

Cross-pack references
---------------------
TaCZ resolves every resource through one resource manager that sees the whole
tacz/ folder AND the copy of tacz_default_gun it unpacks from its own jar.  A
pack pointing at tacz:m4a1 (clips), at another namespace's ammo, or at a tag
that aggregates other packs is therefore CORRECT.  Unless --no-refs is given,
every zip/folder sitting next to the pack being checked - plus that jar copy -
is opened read-only and used to resolve such names.  A reference that no
installed pack provides is still an error.

How the rules were tuned
------------------------
Every rule here was run against the official tacz_default_gun (55 guns) and a
dozen third-party packs.  Whenever the official data violated a rule, the rule
was wrong, not the pack: the initial rule set produced 1281 errors on the
official pack and now produces 1 (a genuine missing file).  Rules that merely
describe a style would have been noise; what is left is what TaCZ actually
refuses to render.

Exit code is 1 when at least one ERROR is found.
"""
import io
import json
import os
import re
import sys
import zipfile

# ---------------------------------------------------------------------------
# source abstraction: a zip, or an unpacked directory (official packs ship both)
# ---------------------------------------------------------------------------


class Pack:
    def __init__(self, path, refs=(), prefix=None):
        self.path = path
        # Sibling packs, opened read-only.  TaCZ resolves every resource through
        # one shared resource manager that sees the whole tacz/ folder plus the
        # jar's built-in tacz_default_gun copy, so a pack that references
        # tacz:m4a1 (animations), tacz:shell/12g_shell (geo) or a namespace owned
        # by another zip is perfectly legal.  Only a name that NO installed pack
        # provides is a packaging bug.
        self.refs = list(refs)
        self.zip = None
        self.root = None
        if os.path.isdir(path):
            self.root = path
            names = []
            for dp, _dn, fn in os.walk(path):
                for f in fn:
                    full = os.path.join(dp, f)
                    rel = os.path.relpath(full, path).replace(os.sep, "/")
                    names.append(rel)
        else:
            self.zip = zipfile.ZipFile(path)
            names = [n for n in self.zip.namelist() if not n.endswith("/")]
        # Some packs wrap everything in one directory; find the real root.
        # For the copy TaCZ unpacks from its own jar the caller passes the prefix
        # explicitly (assets/tacz/custom/tacz_default_gun/).
        if prefix is None:
            prefix = ""
        if not prefix and "gunpack.meta.json" not in names and not any(
                n.startswith("assets/") or n.startswith("data/") for n in names):
            tops = {n.split("/")[0] for n in names if "/" in n}
            for t in sorted(tops):
                if ("%s/gunpack.meta.json" % t) in names or any(
                        n.startswith("%s/assets/" % t) for n in names):
                    prefix = t + "/"
                    break
        self.prefix = prefix
        self.names = sorted(n[len(prefix):] for n in names if n.startswith(prefix))
        self.nameset = set(self.names)
        self.raw_names = names

    def has(self, name):
        return name in self.nameset

    def find(self, name):
        """'self' | 'ref' | None - where (if anywhere) a resource lives."""
        if name in self.nameset:
            return "self"
        for r in self.refs:
            if name in r.nameset:
                return "ref"
        return None

    def owns(self, ns, folder):
        """True when this pack ships at least one file from that tree.

        Used to tell "this pack forgot a file" from "this pack leans on a
        sibling / the built-in default pack".
        """
        for pre in ("assets/%s/%s/" % (ns, folder),
                    "data/%s/%s/" % (ns, folder)):
            if any(n.startswith(pre) for n in self.names):
                return True
        return False

    def read(self, name):
        if name not in self.nameset:
            for r in self.refs:
                if name in r.nameset:
                    return r.read(name)
        name = self.prefix + name
        if self.zip is not None:
            return self.zip.read(name)
        with open(os.path.join(self.root, name.replace("/", os.sep)), "rb") as f:
            return f.read()

    def text(self, name):
        return self.read(name).decode("utf-8-sig", errors="replace")


# ---------------------------------------------------------------------------
# json that tolerates the things official packs actually ship
# ---------------------------------------------------------------------------


def _strip_js(t):
    """Remove // and /* */ comments plus trailing commas, string aware.

    The official pack is full of // comments and trailing commas; a plain
    json.load raises on line 11 and the temptation is to 'fix' the pack.
    Do not.  Strip on read instead.
    """
    out = []
    i = 0
    n = len(t)
    in_str = False
    esc = False
    while i < n:
        c = t[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and t[i + 1] == "/":
            while i < n and t[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and t[i + 1] == "*":
            i += 2
            while i + 1 < n and not (t[i] == "*" and t[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    s = "".join(out)
    return re.sub(r",(\s*[}\]])", r"\1", s)


class JsonFileError(Exception):
    """A json file in the pack does not parse.

    Real packs in the wild ship broken tags (one EMX pack is missing commas in
    tacz_tags/attachments/muzzle.json), and a checker that dies on the first
    one is useless against a pack you are trying to diagnose.
    """

    def __init__(self, name, cause):
        self.name = name
        self.cause = cause
        Exception.__init__(self, "%s: %s" % (name, cause))


def load_json(pack, name):
    try:
        return json.loads(_strip_js(pack.text(name)))
    except json.JSONDecodeError as e:
        raise JsonFileError(name, e)


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------


class Report:
    def __init__(self, label):
        self.label = label
        self.errors = []
        self.warns = []
        self.notes = []
        # tag files are pack-wide but get re-read once per gun that references
        # them; remember what has already been reported so a single broken tag
        # does not produce one identical error per gun.
        self.tag_seen = set()

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def note(self, msg):
        self.notes.append(msg)


# ---------------------------------------------------------------------------
# helpers shared by the checks
# ---------------------------------------------------------------------------


def res_path(loc, folder, ext=".json"):
    """'ns:path/name' -> 'assets/ns/<folder>/path/name<ext>'."""
    ns, _, path = (loc or "").partition(":")
    return "assets/%s/%s/%s%s" % (ns, folder, path, ext)


def ref_index_lookup(pack, ns, folder, name):
    """Look a data/<ns>/index/<folder>/<name>.json up in the sibling packs.

    Used by the tag chain: a tag may aggregate attachments whose index entry
    lives in a different installed pack (the CUST pack's #emxarms:grip lists
    ids that only EMX-Arms indexes).  Returns the parsed object or None.
    """
    n = "data/%s/index/%s/%s.json" % (ns, folder, name)
    for r in pack.refs:
        if n in r.nameset:
            try:
                return load_json(r, n)
            except JsonFileError:
                return None
    return None


def resolve(pack, rep, who, name, what):
    """Locate a resource reference and report where it lives.

    Returns 'self' / 'ref' / None.  'ref' means some other installed pack (or
    the copy TaCZ ships inside its own jar) provides the file: that is legal and
    common - the whole tacz/ folder and the jar share one resource manager - so
    it is a note, never an error.  Only None is a packaging bug.
    """
    w = pack.find(name)
    if w == "ref":
        rep.note("%s: %s comes from another installed pack (%s)"
                 % (who, what, name))
    return w


def geo_of(pack, loc, rep, who):
    """Resolve a 'ns:path/to/geo' model location to its geometry dict."""
    p = res_path(loc, "geo_models")
    if not resolve(pack, rep, who, p, "model"):
        rep.err("%s: model %r does not resolve to %s" % (who, loc, p))
        return None, None
    g = load_json(pack, p)
    root = g.get("minecraft:geometry") or g.get("geometry")
    if not root:
        rep.err("%s: %s has no minecraft:geometry block" % (who, p))
        return None, None
    return root[0], p


def poly_winding(pm):
    """(bad, good, degenerate) counted over a poly_mesh.

    TML renders poly_mesh with flat shading and back-face culling off but normal
    driven lighting: a polygon whose winding disagrees with its stored normals
    lights as if it faced the other way, i.e. it goes black.  Newell's method
    rather than three consecutive corners, because boolean solvers leave
    thousands of slivers whose first three corners are nearly collinear.
    """
    pos = pm["positions"]
    nrm = pm["normals"]
    bad = good = deg = 0
    for poly in pm["polys"]:
        ids = []
        seen = set()
        for c in poly:
            if c[0] in seen:
                continue
            seen.add(c[0])
            ids.append(c[0])
        if len(ids) < 3:
            deg += 1
            continue
        nx = ny = nz = 0.0
        m = len(ids)
        for k in range(m):
            a = pos[ids[k]]
            b = pos[ids[(k + 1) % m]]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        if nx * nx + ny * ny + nz * nz < 1e-12:
            deg += 1
            continue
        sx = sy = sz = 0.0
        for c in poly:
            nn = nrm[c[1]]
            sx += nn[0]
            sy += nn[1]
            sz += nn[2]
        if nx * sx + ny * sy + nz * sz < 0:
            bad += 1
        else:
            good += 1
    return bad, good, deg


def check_geo(pack, geo, gpath, rep, who, texture_size):
    """Bone graph + poly_mesh integrity for one geometry."""
    desc = geo.get("description", {})
    tw = desc.get("texture_width")
    th = desc.get("texture_height")
    if not tw or not th:
        rep.err("%s: %s description has no texture_width/height - UVs would be "
                "computed against a zero size" % (who, gpath))
    elif texture_size and (tw, th) != texture_size:
        # Official packs do this on purpose in a dozen places (a model may use
        # only part of a shared atlas, and normalized_uvs poly_mesh does not
        # care at all).  Cube UVs do care, so keep it visible as a note.
        rep.note("%s: %s declares %dx%d but the texture is %s - cube UVs are "
                 "in texels and would land elsewhere"
                 % (who, gpath, tw, th, texture_size))

    names = []
    parent = {}
    for b in geo.get("bones", []):
        n = b.get("name")
        if not n:
            rep.err("%s: %s has a bone without a name" % (who, gpath))
            continue
        if n in parent:
            rep.err("%s: %s duplicate bone %r" % (who, gpath, n))
        names.append(n)
        parent[n] = b.get("parent")
    known = set(names)
    for n, p in parent.items():
        if p and p not in known:
            rep.err("%s: %s bone %r has unknown parent %r" % (who, gpath, n, p))
    for n in parent:
        seen = set()
        cur = n
        while cur:
            if cur in seen:
                rep.err("%s: %s bone parent cycle at %r" % (who, gpath, cur))
                break
            seen.add(cur)
            cur = parent.get(cur)

    tris = 0
    mesh_bones = []
    bad_total = 0
    for b in geo.get("bones", []):
        pm = b.get("poly_mesh")
        if not pm:
            continue
        n = b.get("name")
        mesh_bones.append(n)
        for key in ("positions", "normals", "uvs", "polys"):
            if key not in pm:
                rep.err("%s: %s bone %r poly_mesh lacks %r" % (who, gpath, n, key))
        if any(k not in pm for k in ("positions", "normals", "uvs", "polys")):
            continue
        if pm.get("normalized_uvs") is not True:
            rep.err("%s: %s bone %r poly_mesh: normalized_uvs must be true, "
                    "otherwise UVs are read as texels" % (who, gpath, n))
        pos, nrm, uvs, polys = pm["positions"], pm["normals"], pm["uvs"], pm["polys"]
        if not pos or not polys:
            rep.err("%s: %s bone %r poly_mesh is empty" % (who, gpath, n))
        for i, p in enumerate(pos):
            if not isinstance(p, list) or len(p) != 3:
                rep.err("%s: %s bone %r positions[%d] is not 3d" % (who, gpath, n, i))
                break
        for i, p in enumerate(nrm):
            if not isinstance(p, list) or len(p) != 3:
                rep.err("%s: %s bone %r normals[%d] is not 3d" % (who, gpath, n, i))
                break
        for i, uv in enumerate(uvs):
            if not isinstance(uv, list) or len(uv) != 2:
                rep.err("%s: %s bone %r uvs[%d] is not 2d" % (who, gpath, n, i))
                break
            if not (-1e-6 <= uv[0] <= 1 + 1e-6 and -1e-6 <= uv[1] <= 1 + 1e-6):
                rep.err("%s: %s bone %r uvs[%d]=%r is outside 0..1 while "
                        "normalized_uvs is set" % (who, gpath, n, i, uv))
                break
        badcorner = False
        for i, poly in enumerate(polys):
            if len(poly) not in (3, 4):
                rep.err("%s: %s bone %r polys[%d] has %d corners (TML expects 3 "
                        "or 4; n-gons must be triangulated first)"
                        % (who, gpath, n, i, len(poly)))
                badcorner = True
                break
            for c in poly:
                if not isinstance(c, list) or len(c) != 3:
                    rep.err("%s: %s bone %r polys[%d] corner is not "
                            "[position, normal, uv]" % (who, gpath, n, i))
                    badcorner = True
                    break
                if not (0 <= c[0] < len(pos) and 0 <= c[1] < len(nrm)
                        and 0 <= c[2] < len(uvs)):
                    rep.err("%s: %s bone %r polys[%d] corner index out of range "
                            "(%r vs %d/%d/%d of p/n/uv)"
                            % (who, gpath, n, i, c, len(pos), len(nrm), len(uvs)))
                    badcorner = True
                    break
            if badcorner:
                break
            tris += len(poly) - 2
        if not badcorner:
            bad, good, deg = poly_winding(pm)
            bad_total += bad
            if deg:
                rep.warn("%s: %s bone %r has %d degenerate polygons (zero area)"
                         % (who, gpath, n, deg))
            if bad:
                rep.warn("%s: %s bone %r has %d/%d polygons wound against their "
                         "normals - these render black (reversed winding)"
                         % (who, gpath, n, bad, good + bad))
    return {"tris": tris, "bones": known, "parent": parent,
            "mesh_bones": mesh_bones, "bad_winding": bad_total,
            "tw": tw, "th": th}


def _null_channel(cv):
    """True when a channel contributes nothing (all values zero).

    Used to tell a real additive hand animation from the official habit of
    writing {"lefthand": {"position": [0, 0, 0]}} in shoot (hk_g3).
    """
    def flat(v):
        if isinstance(v, bool):
            return False
        if isinstance(v, (int, float)):
            return abs(v) < 1e-9
        if isinstance(v, list):
            return all(flat(x) for x in v)
        if isinstance(v, dict):
            return all(flat(x) for x in v.values())
        return True
    return flat(cv)


def check_animation(pack, anim, apath, rep, who, geo_info):
    if anim.get("format_version") != "1.8.0":
        rep.err("%s: %s format_version %r - TaCZ parses Bedrock 1.8.0"
                % (who, apath, anim.get("format_version")))
    anims = anim.get("animations") or {}
    if not anims:
        rep.err("%s: %s contains no animations" % (who, apath))
    bones = geo_info["bones"]
    for name, a in anims.items():
        # animation_length is optional: official static clips (static_semi,
        # static_VG, handle_on, ...) are a bare pose with "loop": true and no
        # length at all.  Fall back to the last keyframe time.
        length = a.get("animation_length")
        if length is None:
            length = 0.0
            for chans in (a.get("bones") or {}).values():
                for cv in chans.values():
                    if isinstance(cv, dict):
                        for t in cv:
                            try:
                                length = max(length, float(t))
                            except (TypeError, ValueError):
                                pass
        for bn, chans in (a.get("bones") or {}).items():
            if bn not in bones:
                # Official packs do this too (b93r animates barrel2 and
                # bullet_in_barrel on a model that has neither), so it is a
                # warning: the channel is dropped and the part simply does not
                # move - ugly, not fatal.
                rep.warn(f"{who}: {apath} clip {name!r} animates unknown bone "
                         f"{bn!r} - the channel is silently dropped")
            for cn, cv in chans.items():
                where = f"{who}: {apath} {name}/{bn}/{cn}"
                if cn == "relative_to":
                    # Legal per-bone modifier (official uzi / m16a1 write
                    # "relative_to": {"rotation": "entity"} on camera).
                    continue
                if cn not in ("position", "rotation", "scale"):
                    rep.err(f"{where}: unknown channel")
                    continue
                # A channel is either a constant or a map of keyframes.  The
                # constant may be a bare number: official clips write
                # "scale": 0 to hide a part (Bedrock reads a scalar as the same
                # value on all three axes).  Only scale does this in practice,
                # but the parser accepts it for every channel, so we do too.
                if isinstance(cv, (int, float)) and not isinstance(cv, bool):
                    if cn != "scale":
                        rep.warn(f"{where}: constant is a bare number {cv!r} "
                                 f"(legal, but unusual outside scale)")
                    continue
                if isinstance(cv, list):
                    if len(cv) != 3:
                        rep.err(f"{where}: constant value has {len(cv)} "
                                f"components, expected 3")
                    continue
                if not isinstance(cv, dict):
                    rep.err(f"{where}: neither a constant nor a keyframe map "
                            f"(got {type(cv).__name__})")
                    continue
                prev = -1e9
                for t, v in cv.items():
                    try:
                        ft = float(t)
                    except ValueError:
                        rep.err(f"{where}: key {t!r} is not a time")
                        break
                    if ft < prev - 1e-9:
                        rep.err(f"{where}: keyframes out of order at {t}")
                        break
                    prev = ft
                    if isinstance(v, dict):
                        # Bedrock's {"post": [...], "pre": [...], "lerp_mode":
                        # "catmullrom"} form is legal; unwrap it.
                        if "post" not in v:
                            rep.err(f"{where}: keyframe {t} is an object "
                                    f"without 'post' (got keys {sorted(v)})")
                            break
                        v = v["post"]
                    if not isinstance(v, list) or len(v) != 3:
                        rep.err(f"{where}: keyframe {t} is not a 3 component "
                                f"array (got {v!r})")
                        break
                    # Compare at 1/10000 s.  A key written as 0.4667 in a clip
                    # whose length is also printed 0.4667 can differ in the fifth
                    # decimal and is not "beyond" anything; only a real overshoot
                    # (official taurus500: 3.1 in a 3.0833 clip) is worth a note.
                    if round(ft, 4) > round(length + 1e-9, 4):
                        rep.warn(f"{where}: keyframe {t} is beyond "
                                 f"animation_length {length:.4f} (TaCZ never "
                                 f"reaches it)")
        for t, se in (a.get("sound_effects") or {}).items():
            if "effect" not in se:
                rep.err(f"{who}: {apath} {name} sound_effects[{t}] has no effect")
        # NOTE: the "shoot animates a hand" rule lives in check_pack(), not here,
        # because it only applies to guns driven by the built-in state machine.
    return anims


# ---------------------------------------------------------------------------
# schema: what the TaCZ deserializers actually demand
# ---------------------------------------------------------------------------
# Extracted from the jar (Gson @SerializedName fields) rather than from a doc,
# so these are the keys the loader will really try to populate.
GUN_DATA_KEYS = {
    "ammo": str,
    "ammo_amount": int,
    "extended_mag_ammo_amount": list,
    "bolt": str,
    "rpm": int,
    "rpm_min": int,
    "bullet": dict,
    "draw_time": (int, float),
    "put_away_time": (int, float),
    "sprint_time": (int, float),
    "aim_time": (int, float),
    "bolt_action_time": (int, float),
    "bolt_feed_time": (int, float),
    "reload": dict,
    "fire_mode": list,
    "recoil": dict,
    "weight": (int, float),
    "allow_attachment_types": list,
}
GUN_DATA_REQUIRED = ("ammo", "ammo_amount", "reload", "bullet", "rpm")
# Exactly the AttachmentType enum inside the jar (dumped from the constant pool):
# scope / muzzle / stock / grip / laser / extended_mag / NONE, and NONE is only
# the "no slot" sentinel.  A bayonet is NOT a type - the official bayonet_m9
# index entry says type "muzzle" and merely sits under a tag called bayonet_ar.
ATTACHMENT_TYPES = {"scope", "muzzle", "stock", "grip", "laser", "extended_mag"}
POS_OF = {"scope": "scope_pos", "muzzle": "muzzle_pos", "stock": "stock_pos",
          "grip": "grip_pos", "laser": "laser_pos"}
# extended_mag has no single mount bone name: official guns use magazine /
# mag / mag_and_lefthand / magzine (sic, ai_awp).  Any bone whose name starts
# with "mag" satisfies it; the per-level mag_extended_N bone is checked on the
# attachment itself.
MAG_BONE_PREFIX = ("mag",)
# Official tag name -> AttachmentType.  Tag names are NOT the enum names:
# the official pack ships dozens of tags (scope_sight, grip_vertical,
# pistol_muzzle, light_extended_mag, oem_stock, ammo_mod_no_he, ...) that all
# collapse onto the seven real types.  Only used for tags in another pack,
# whose files we cannot read; an unknown name maps to None and is ignored
# rather than reported, because a tag we have never seen may be anything.
CROSS_TYPE = {
    "ammo_mod": "extended_mag", "ammo_mod_no_he": "extended_mag",
    "extended_mag": "extended_mag", "light_extended_mag": "extended_mag",
    "shotgun_extended_mag": "extended_mag",
    "sniper_extended_mag": "extended_mag",
    "scope": "scope", "scope_scope": "scope", "scope_sniper": "scope",
    "scope_lowsight": "scope", "scope_sight": "scope",
    "pistol_sight": "scope",
    "muzzle": "muzzle", "muzzle_brake": "muzzle", "muzzle_silencer": "muzzle",
    "muzzle_compensator": "muzzle", "pistol_muzzle": "muzzle",
    "muzzle_shotgun": "muzzle", "muzzle_shotgun_silencer": "muzzle",
    "stock": "stock", "oem_stock": "stock", "grip": "grip",
    "grip_vertical": "grip", "grip_magwell": "grip",
    "ar_laser": "laser", "pistol_laser": "laser",
    # The official bayonets are muzzle attachments that happen to live under a
    # bayonet tag (data/tacz/index/attachments/bayonet_m9.json -> "type":"muzzle").
    "bayonet": "muzzle", "bayonet_ar": "muzzle", "bayonet_ak": "muzzle",
    "bayonet_other": "muzzle",
}
SCOPE_NODES = ("scope_body", "ocular", "ocular_ring", "division", "scope_view")
# The default state machine looks these up by name; a missing one is a silent
# no-op in game (the gun simply does nothing when you press the key).
DSM_ANIMS = ("static_idle", "static_bolt_caught", "draw", "put_away", "shoot",
             "inspect", "inspect_empty", "reload_empty", "reload_tactical")


def check_gun_data(gd, rep, who, geo_info):
    for k in GUN_DATA_REQUIRED:
        if k in gd:
            continue
        if k == "ammo_amount" and "heat" in gd:
            # Heat weapons (official minigun) have no magazine and omit it.
            rep.note("%s: no ammo_amount, but the gun is heat based - fine" % who)
            continue
        rep.err("%s: gun data is missing required key %r" % (who, k))
    for k, want in GUN_DATA_KEYS.items():
        if k in gd and not isinstance(gd[k], want):
            rep.err("%s: gun data %r has type %s, expected %s"
                    % (who, k, type(gd[k]).__name__,
                       "/".join(t.__name__ for t in (want if isinstance(want, tuple) else (want,)))))
    ammo = gd.get("ammo")
    if isinstance(ammo, str) and ":" not in ammo:
        rep.err("%s: gun data ammo %r is not a resource location (ns:id)"
                % (who, ammo))
    # TaCZ's GunData deserializer throws unless this holds exactly three values
    # (levels 1/2/3).  One value fails the WHOLE gun index: the item degrades to
    # item.tacz.modern_kinetic_gun with a magenta icon.
    emaa = gd.get("extended_mag_ammo_amount")
    if emaa is not None:
        if not isinstance(emaa, list) or len(emaa) != 3:
            rep.err("%s: extended_mag_ammo_amount must be exactly 3 entries "
                    "(levels 1/2/3), got %r - Gson rejects the whole gun index"
                    % (who, emaa))
        elif not all(isinstance(v, int) and v > 0 for v in emaa):
            rep.err("%s: extended_mag_ammo_amount entries must be positive ints, "
                    "got %r" % (who, emaa))
    rel = gd.get("reload")
    if isinstance(rel, dict):
        if rel.get("type") not in ("magazine", "iterative", "inventory", None):
            rep.warn("%s: unknown reload.type %r" % (who, rel.get("type")))
        feed = rel.get("feed") or {}
        cool = rel.get("cooldown") or {}
        for k in ("empty", "tactical"):
            if k in feed and k in cool:
                if not feed[k] < cool[k]:
                    # Official shotguns (m1014/m870/spas_12) and the kar98
                    # invert this on purpose: for shell-by-shell reloads the
                    # cooldown is the delay between single shells, not the
                    # length of the whole reload.  Only worth a warning.
                    rep.warn("%s: reload.feed.%s (%s) is not shorter than "
                             "cooldown.%s (%s) - normal for shell-by-shell "
                             "reloads, suspicious for magazine swaps"
                             % (who, k, feed[k], k, cool[k]))
    allowed = gd.get("allow_attachment_types") or []
    for t in allowed:
        if t not in ATTACHMENT_TYPES:
            rep.err("%s: allow_attachment_types lists unknown type %r"
                    % (who, t))
        elif t in POS_OF and geo_info and POS_OF[t] not in geo_info["bones"]:
            # TaCZ registers a functional renderer per <type>_pos and creates
            # the missing bone at the model origin rather than skipping it, so
            # the part still appears - in the wrong place.  Official db_short
            # does exactly this (its stock hangs off attachment_adapter).
            rep.warn("%s: allow_attachment_types lists %r but the gun geo has no "
                     "%s bone - TaCZ would draw that attachment at the model "
                     "origin instead of on a mount"
                     % (who, t, POS_OF[t]))
    ma = gd.get("ammo_amount")
    if isinstance(ma, int) and ma <= 0:
        rep.err("%s: ammo_amount %r is not positive" % (who, ma))


def check_display(dsp, rep, who, geo_info, pack):
    for k in ("model", "texture", "slot", "hud", "animation"):
        if not dsp.get(k):
            rep.err("%s: display is missing %r" % (who, k))
    if dsp.get("model"):
        p = res_path(dsp["model"], "geo_models")
        if not resolve(pack, rep, who, p, "display.model"):
            rep.err("%s: display.model %r -> missing %s"
                    % (who, dsp["model"], p))
    for k, folder in (("texture", "textures"), ("slot", "textures"),
                      ("hud", "textures")):
        if dsp.get(k):
            p = res_path(dsp[k], folder, ".png")
            if not resolve(pack, rep, who, p, "display." + k):
                rep.err("%s: display.%s %r -> missing %s" % (who, k, dsp[k], p))
    if dsp.get("animation"):
        ns, _, path = dsp["animation"].partition(":")
        # TaCZ 1.1.8 accepts Bedrock .animation.json AND gltf clips
        # (GltfManager uses FileToIdConverter("animations", ".gltf"); the whole
        # suffuse pack animates with .gltf only).
        cands = ["assets/%s/animations/%s.animation.json" % (ns, path),
                 "assets/%s/animations/%s.gltf" % (ns, path)]
        where = [w for w in (pack.find(c) for c in cands) if w]
        if not where:
            rep.err("%s: display.animation %r -> neither %s nor a .gltf clip "
                    "exists (no clip would ever play)"
                    % (who, dsp["animation"], cands[0]))
        elif where[0] == "ref":
            rep.note("%s: clips for %r come from another installed pack"
                     % (who, dsp["animation"]))
    # The one hard rule TML imposes: a poly_mesh model is only understood when
    # the display says so.  TML registers the literal string "mesh" (its log
    # line says "meshy" - a lie); anything else and the model never loads, with
    # no error at all.
    if geo_info and geo_info["mesh_bones"]:
        if dsp.get("model_type") != "mesh":
            rep.err("%s: geo carries poly_mesh but display.model_type is %r - "
                    "TML only binds a poly_mesh model when it is exactly 'mesh'"
                    % (who, dsp.get("model_type")))
    elif dsp.get("model_type") == "mesh":
        rep.warn("%s: display.model_type is 'mesh' but the geo has no poly_mesh "
                 "(all cubes)" % who)
    # display.shell is PHYSICS ONLY (initial_velocity / acceleration / living
    # time).  The casing geometry comes from the ammo display's own shell block,
    # which check_ammo() verifies.  Official m4a1/ak47 carry exactly five keys
    # here and no model at all - do not demand one.
    sc = dsp.get("shell")
    if sc is None:
        rep.warn("%s: display has no shell block - nothing is ejected on firing"
                 % who)
    elif not isinstance(sc, dict):
        rep.err("%s: display.shell is not an object" % who)
    else:
        for k in ("initial_velocity", "acceleration", "living_time"):
            if k not in sc:
                rep.warn("%s: display.shell lacks %r (TaCZ falls back to a "
                         "default)" % (who, k))


def check_attachment(pack, aid, ix, rep, gun_geo_info):
    """One attachment: index -> display -> data, plus its model."""
    atype = ix.get("type")
    if atype not in ATTACHMENT_TYPES:
        rep.err("%s: unknown attachment type %r" % (aid, atype))
    if not ix.get("name"):
        rep.err("%s: index has no name key (the tooltip would be blank)" % aid)
    dloc = ix.get("display") or ""
    dpath = res_path(dloc, "display/attachments")
    if not resolve(pack, rep, aid, dpath, "display"):
        rep.err("%s: display %r -> missing %s" % (aid, dloc, dpath))
        return
    try:
        dsp = load_json(pack, dpath)
    except JsonFileError as e:
        rep.err("%s: %s" % (aid, e))
        return
    dns, _, drest = (ix.get("data") or "").partition(":")
    ddat = "data/%s/data/attachments/%s.json" % (dns, drest)
    if not resolve(pack, rep, aid, ddat, "data"):
        rep.err("%s: data %r -> missing %s" % (aid, ix.get("data"), ddat))
        return
    try:
        adat = load_json(pack, ddat)
    except JsonFileError as e:
        rep.err("%s: %s" % (aid, e))
        return

    slot = dsp.get("slot")
    if not slot:
        rep.err("%s: display has no slot texture (blank in the attachment menu)"
                % aid)
    elif not resolve(pack, rep, aid, res_path(slot, "textures", ".png"),
                     "slot texture"):
        rep.err("%s: slot texture -> missing %s"
                % (aid, res_path(slot, "textures", ".png")))

    if atype == "extended_mag":
        lvl = adat.get("extended_mag_level")
        if lvl is None:
            # Ammo modifiers (fmj / hp / i) are filed under extended_mag with no
            # level and no geometry: they change the bullet, not the magazine.
            if dsp.get("model"):
                rep.warn("%s: extended_mag with a model but no "
                         "extended_mag_level - TaCZ will treat it as an ammo "
                         "modifier and never draw the model" % aid)
            return
        if not isinstance(lvl, int) or lvl < 1:
            rep.err("%s: extended_mag_level %r is not a positive int" % (aid, lvl))
        elif gun_geo_info and ("mag_extended_%d" % lvl) not in gun_geo_info["bones"]:
            rep.err("%s: level %d needs bone mag_extended_%d; the gun has %s"
                    % (aid, lvl, lvl,
                       [b for b in gun_geo_info["mesh_bones"]
                        if b.startswith("mag_")] or "none"))
        if dsp.get("model"):
            rep.err("%s: an extended magazine must NOT carry a model - its body "
                    "is a bone inside the gun" % aid)
        return

    if not dsp.get("model"):
        if dsp.get("adapter"):
            # Adapter-style parts (official oem_stock_*) carry no model: the
            # geometry is a bone inside the gun, hung off attachment_adapter.
            rep.note("%s: adapter %r with no model - the geometry lives in the "
                     "gun's attachment_adapter subtree"
                     % (aid, dsp.get("adapter")))
            return
        # Third-party packs ship a few of these (CUST stock_bomx, FMIC hac_ap);
        # the part draws nothing, which is a look problem, not a loader problem.
        rep.warn("%s: display.model missing - the part draws nothing" % aid)
        return
    g, gpath = geo_of(pack, dsp["model"], rep, aid)
    if not g:
        return
    abones = g.get("bones", [])
    names = [b.get("name") for b in abones]

    def has_geom(b):
        # Cube-based Bedrock models are as valid as poly_mesh; the official
        # scopes are all cubes.
        return bool(b.get("poly_mesh") or b.get("cubes"))

    if all(n in names for n in SCOPE_NODES):
        by = {b["name"]: b for b in abones}

        def subtree_has_geom(root):
            # Official scopes keep scope_body empty and hang the tube, mount
            # and knobs off it as children (scope_standard_8x puts 191 cubes on
            # "scope").  Only an entirely empty subtree is a real problem.
            alive = {root}
            changed = True
            while changed:
                changed = False
                for b in abones:
                    if b.get("parent") in alive and b["name"] not in alive:
                        alive.add(b["name"])
                        changed = True
            return any(has_geom(by[n]) for n in alive if n in by)

        if not subtree_has_geom("scope_body"):
            rep.err("%s: scope_body and all its children are empty - nothing to "
                    "see through" % aid)
        if has_geom(by.get("scope_view") or {}):
            rep.err("%s: scope_view must stay empty; it is the eye anchor"
                    % aid)
        for n in ("ocular", "division"):
            if not has_geom(by[n]) and not subtree_has_geom(n):
                rep.warn("%s: %s and all its children are empty - the scope "
                         "shows no %s"
                         % (aid, n, "aperture" if n == "ocular" else "reticle"))
    elif len(abones) != 1:
        # Official attachments routinely ship a small bone tree (laser_lopro
        # has 9 bones, grip_vertical_ranger 13).  TaCZ draws the whole model on
        # the mount, so this is only worth a note.
        rep.note("%s: attachment geo has %d bones (fine - TaCZ draws the whole "
                 "model on the mount)" % (aid, len(abones)))
    if abones and abones[0].get("pivot") != [0, 0, 0]:
        # 56 official attachments do this (laser_lopro: [-18.02, -1.63, -0.25]).
        # TaCZ treats the attachment geo as already living in mount space, so a
        # non-zero root pivot is simply how the author placed it - information,
        # not a defect.
        rep.note("%s: root pivot %r is not the origin - the part sits that far "
                 "from the mount point (fine, and common)"
                 % (aid, abones[0].get("pivot")))
    desc = g.get("description", {})
    tw, th = desc.get("texture_width"), desc.get("texture_height")
    far = 0.0
    for b in abones:
        pm = b.get("poly_mesh")
        if not pm:
            continue
        for poly in pm.get("polys", []):
            for c in poly:
                if not (0 <= c[0] < len(pm["positions"])):
                    rep.err("%s: %s polys index out of range" % (aid, b.get("name")))
                    return
        if tw and th:
            for uv in pm.get("uvs", []):
                if not (-1e-6 <= uv[0] <= 1 + 1e-6):
                    rep.warn("%s: %s uv %r outside 0..1" % (aid, b.get("name"), uv))
                    break
        far = max([far] + [max(abs(v) for v in p) for p in pm["positions"]])
    if far > 48:
        rep.warn("%s: geometry reaches %.0f model units from its mount - check "
                 "that it was re-origined onto the mount point" % (aid, far))


# ---------------------------------------------------------------------------
# one pack
# ---------------------------------------------------------------------------


def check_pack(path, quiet=False, refs=()):
    pack = Pack(path, refs)
    rep = Report(os.path.basename(path.rstrip("/\\")))
    if not quiet:
        print("=" * 78)
        print("PACK %s" % path)
        if pack.prefix:
            print("  (entries are wrapped in %r)" % pack.prefix)

    meta = None
    if pack.has("gunpack.meta.json"):
        meta = load_json(pack, "gunpack.meta.json")
    else:
        rep.err("gunpack.meta.json is missing - TaCZ will not list this pack at "
                "all (GunPackLoader reads only this file to find packs)")
    ns_meta = (meta or {}).get("namespace")

    # Every namespace that ships assets or data.  A single zip is allowed to
    # carry several (official packs in the wild do: e.g. emxarms/emxcust/trisdyna
    # in one zip), and each shows up as its own line in the gun pack list.
    ns_assets = {n.split("/")[1] for n in pack.names
                 if n.startswith("assets/") and n.count("/") > 1}
    ns_data = {n.split("/")[1] for n in pack.names
               if n.startswith("data/") and n.count("/") > 1}
    ns_all = sorted(ns_assets | ns_data)
    if not quiet:
        print("  namespaces: meta=%r assets=%s data=%s"
              % (ns_meta, sorted(ns_assets), sorted(ns_data)))
    if ns_meta and ns_meta not in ns_all:
        # The meta namespace is the PACK's identity (it names the row in the gun
        # pack list); the resources themselves may live under other namespaces.
        # EMX-Arms ships meta "emitech" with everything under emxarms, and it
        # works.  Only a note.
        rep.note("gunpack.meta.json namespace %r has no assets/ or data/ tree of "
                 "its own (the pack's resources use %s) - legal, the meta "
                 "namespace is just the pack's name" % (ns_meta, ns_all))

    # ---- guns -----------------------------------------------------------
    gun_reports = []
    for ns in ns_all:
        for n in pack.names:
            if not (n.startswith("data/%s/index/guns/" % ns) and n.endswith(".json")):
                continue
            gid = n.rsplit("/", 1)[1][:-5]
            who = "%s:%s" % (ns, gid)
            try:
                ix = load_json(pack, n)
            except JsonFileError as e:
                rep.err("%s: %s" % (who, e))
                continue
            dloc = ix.get("display") or ""
            dp = res_path(dloc, "display/guns")
            if not resolve(pack, rep, who, dp, "display"):
                rep.err("%s: display %r -> missing %s" % (who, dloc, dp))
                continue
            try:
                dsp = load_json(pack, dp)
            except JsonFileError as e:
                rep.err("%s: %s" % (who, e))
                continue
            dns, _, drest = (ix.get("data") or "").partition(":")
            datp = "data/%s/data/guns/%s.json" % (dns, drest)
            if not resolve(pack, rep, who, datp, "gun data"):
                rep.err("%s: data %r -> missing %s" % (who, ix.get("data"), datp))
                continue
            try:
                gd = load_json(pack, datp)
            except JsonFileError as e:
                rep.err("%s: %s" % (who, e))
                continue

            geo_info = None
            if dsp.get("model"):
                g, gpath = geo_of(pack, dsp["model"], rep, who)
                if g:
                    ts = None
                    tp = res_path(dsp.get("texture"), "textures", ".png")
                    if pack.find(tp):
                        try:
                            from PIL import Image
                            ts = Image.open(io.BytesIO(pack.read(tp))).size
                        except Exception:
                            ts = None
                    geo_info = check_geo(pack, g, gpath, rep, who, ts)
                    gd_get = gd
                    # model_type rule needs the geo
                    if geo_info["mesh_bones"] and dsp.get("model_type") != "mesh":
                        rep.err("%s: geo has poly_mesh (%d bones) but "
                                "display.model_type=%r; TML binds only the exact "
                                "string 'mesh' - the model silently never loads"
                                % (who, len(geo_info["mesh_bones"]),
                                   dsp.get("model_type")))
            check_display(dsp, rep, who, geo_info, pack)
            check_gun_data(gd, rep, who, geo_info)

            anims = {}
            aloc = dsp.get("animation")
            if aloc:
                ans, _, apath = aloc.partition(":")
                ap = "assets/%s/animations/%s.animation.json" % (ans, apath)
                if pack.find(ap) and geo_info:
                    try:
                        anims = check_animation(pack, load_json(pack, ap), ap,
                                                rep, who, geo_info)
                    except JsonFileError as e:
                        rep.err("%s: %s" % (who, e))
            if anims:
                # The 9 names below are what default_state_machine.lua asks for.
                # A pack that ships its own Lua state machine (display.state_machine)
                # calls whatever it likes, so the check only applies to guns on
                # the built-in animation set.  Even then it is a warn: an absent
                # clip is skipped silently, the gun still works.
                on_builtin = str(dsp.get("use_default_animation") or "") in (
                    "rifle", "pistol", "shotgun", "sniper", "smg", "mg")
                if on_builtin:
                    for need in DSM_ANIMS:
                        if need not in anims:
                            rep.warn("%s: no %r animation; the default state "
                                     "machine calls it by name and silently does "
                                     "nothing" % (who, need))
                for k in ("empty", "tactical"):
                    an = "reload_" + k
                    if an in anims:
                        cool = ((gd.get("reload") or {}).get("cooldown") or {}).get(k)
                        ln = anims[an].get("animation_length")
                        if isinstance(cool, (int, float)) and isinstance(ln, (int, float)):
                            if cool > ln + 1e-6:
                                rep.warn("%s: reload.cooldown.%s %.3f > %s length "
                                         "%.3f (the gun becomes usable after the "
                                         "clip ends)" % (who, k, cool, an, ln))
                # hands.  The official convention is that the static pose
                # clips own the arms and the dynamic clips leave them alone
                # (m4a1's shoot animates root/bolt/camera only).  "shoot" is
                # played additively on top of static_idle, so a hand channel
                # there is added to the static pose and the arm folds double -
                # that is the one real bug worth flagging.
                hb_names = [h for h in ("righthand", "lefthand")
                            if h in (geo_info or {}).get("bones", set())]
                # Only the built-in state machines run shoot additively
                # (default_state_machine.lua:323 runAnimation("shoot", track,
                # true, ...)).  A gun with its own Lua state machine decides for
                # itself, so the rule cannot be applied to it.
                builtin_sm = dsp.get("use_default_animation") in (
                    "rifle", "pistol", "shotgun", "sniper", "smg", "mg")
                for an in ("shoot", "shoot_3p"):
                    a = anims.get(an)
                    if not a:
                        continue
                    for hb in hb_names:
                        chans = (a.get("bones") or {}).get(hb)
                        if chans and not all(_null_channel(v)
                                             for v in chans.values()):
                            (rep.err if builtin_sm else rep.note)(
                                "%s: %r animates %s - %s" %
                                (who, an, hb,
                                 "shoot is additive over static_idle, so the "
                                 "static arm pose and this one are summed and "
                                 "the arm folds double"
                                 if builtin_sm else
                                 "harmless only if the pack's own state machine "
                                 "does not add shoot on top of static_idle"))
                if hb_names and "static_idle" in anims:
                    si = anims["static_idle"].get("bones") or {}
                    for hb in hb_names:
                        if hb not in si:
                            rep.warn("%s: static_idle has no %s channel - the arm "
                                     "would sit in its rest pose (crossed through "
                                     "the gun)" % (who, hb))
            gun_reports.append((who, gid, ix, gd, geo_info, anims, dp, datp))
            if not quiet:
                print("  gun %-22s model_type=%-6r bones=%s tris=%s anims=%d"
                      % (who, dsp.get("model_type"),
                         len(geo_info["bones"]) if geo_info else "?",
                         geo_info["tris"] if geo_info else "?",
                         len(anims)))

    if not gun_reports:
        rep.warn("no gun found under data/<ns>/index/guns/ - this pack only ships "
                 "attachments/ammo/blocks, which is legal")

    # ---- attachments ----------------------------------------------------
    att_index = {}
    for ns in ns_all:
        for n in pack.names:
            if not (n.startswith("data/%s/index/attachments/" % ns)
                    and n.endswith(".json")):
                continue
            aid = n.rsplit("/", 1)[1][:-5]
            ix = load_json(pack, n)
            att_index["%s:%s" % (ns, aid)] = (aid, ix, ns)
    for key, (aid, ix, ns) in sorted(att_index.items()):
        gun_geo = gun_reports[0][4] if gun_reports else None
        check_attachment(pack, key, ix, rep, gun_geo)
    if not quiet and att_index:
        print("  attachments: %s" % ", ".join(sorted(att_index)))

    # ---- tag chain ------------------------------------------------------
    for who, gid, ix, gd, geo_info, anims, dp, datp in gun_reports:
        allow_p = "data/%s/tacz_tags/attachments/allow_attachments/%s.json" % (
            who.split(":")[0], gid)
        if not pack.has(allow_p):
            if gd.get("allow_attachment_types"):
                rep.warn("%s: allow_attachment_types is set but %s is missing - "
                         "no attachment would ever be accepted"
                         % (who, allow_p))
            continue
        seen_types = set()
        unknown_tags = set()
        try:
            allow = load_json(pack, allow_p)
        except JsonFileError as e:
            rep.err("%s: %s" % (who, e))
            continue
        for ref in allow:
            if not isinstance(ref, str):
                rep.err("%s: allow_attachments entry %r is not a string"
                        % (who, ref))
                continue
            if not ref.startswith("#"):
                # A bare item id is legal (official vector45 lists
                # tacz:oem_stock_tactical and tacz:oem_stock_heavy like this).
                if ref in att_index:
                    seen_types.add(att_index[ref][1].get("type"))
                else:
                    unknown_tags.add(ref)
                continue
            tns, _, tname = ref[1:].partition(":")
            mapped = CROSS_TYPE.get(tname)
            if tns != who.split(":")[0]:
                # Legal and common: a pack may reference another pack's tags.
                # The files are not in this zip so they cannot be verified, but
                # the TYPE they stand for still has to be allowed by the gun.
                if mapped:
                    seen_types.add(mapped)
                else:
                    unknown_tags.add(ref)
                continue
            tp = "data/%s/tacz_tags/attachments/%s.json" % (tns, tname)
            if not resolve(pack, rep, who, tp, "tag %s" % ref):
                rep.err("%s: tag %s -> missing %s" % (who, ref, tp))
                continue
            try:
                ids = load_json(pack, tp)
            except JsonFileError as e:
                if ref not in rep.tag_seen:
                    rep.err("%s: %s" % (who, e))
                    rep.tag_seen.add(ref)
                continue
            first_use = ref not in rep.tag_seen
            rep.tag_seen.add(ref)
            if not ids and first_use:
                rep.err("%s: tag %s is empty - those attachments never appear"
                        % (who, ref))
            if mapped is None:
                unknown_tags.add(ref)
            for iid in ids:
                if iid not in att_index:
                    if iid.partition(":")[0] != tns:
                        # The tag aggregates another pack's attachments (the
                        # official #tacz:muzzle lists muzzles from several packs).
                        if first_use:
                            rep.note("%s: tag %s also lists %r from another "
                                     "namespace" % (who, ref, iid))
                        continue
                    alt = ref_index_lookup(pack, iid.partition(":")[0],
                                           "attachments", iid.partition(":")[2])
                    if alt is not None:
                        if first_use:
                            rep.note("%s: tag %s lists %r, indexed by another "
                                     "installed pack" % (who, ref, iid))
                        if mapped and alt.get("type") != mapped and first_use:
                            rep.err("%s: %r sits under tag %s (type %r) but its "
                                    "index type is %r"
                                    % (who, iid, tname, mapped, alt.get("type")))
                        continue
                    if first_use:
                        rep.err("%s: tag %s lists %r but the pack has no index "
                                "entry for it" % (who, ref, iid))
                elif mapped and att_index[iid][1].get("type") != mapped:
                    if first_use:
                        rep.err("%s: %r sits under tag %s (type %r) but its "
                                "index type is %r - the attachment would be "
                                "offered and then refused"
                                % (who, iid, tname, mapped,
                                   att_index[iid][1].get("type")))
        for ref in sorted(unknown_tags):
            rep.note("%s: %s names a tag with no known attachment type; the "
                     "type it stands for was not checked" % (who, ref))
        # Mountability is decided ONLY by allow_attachment_types
        # (AbstractGunItem.allowAttachmentType -> List.contains(AttachmentType));
        # the tag chain merely narrows the candidate list.  So a tag that offers
        # a type the gun does not allow is harmless clutter, not a break: the
        # slot never opens.  Official packs do this in over a hundred places.
        allowed = set(gd.get("allow_attachment_types") or [])
        for t in sorted(seen_types - allowed):
            rep.note("%s: allow_attachments offers type %r that "
                     "allow_attachment_types (%r) does not include - those "
                     "attachments simply never show up for this gun"
                     % (who, t, sorted(allowed)))
        for t in sorted(seen_types & set(POS_OF)):
            if geo_info and POS_OF[t] not in geo_info["bones"]:
                rep.warn("%s: tag exists for %r but the geo has no %s bone - the "
                         "attachment would be drawn at the model origin"
                         % (who, t, POS_OF[t]))
        if "extended_mag" in seen_types and geo_info:
            if not any(b.startswith(MAG_BONE_PREFIX) for b in geo_info["bones"]):
                # Official ammo-modifier tags live under extended_mag, so a gun
                # may legitimately accept "extended_mag" purely for fmj/hp.
                rep.warn("%s: 'extended_mag' is allowed but no bone name starts "
                         "with 'mag' - a real extended magazine would have "
                         "nowhere to live" % who)

    # ---- ammo chain -----------------------------------------------------
    for who, gid, ix, gd, geo_info, anims, dp, datp in gun_reports:
        check_ammo(pack, gd.get("ammo"), rep, who)

    # ---- blocks / misc pointers ----------------------------------------
    for n in pack.names:
        if n.startswith("data/") and n.endswith(".json") and "/index/" in n:
            try:
                obj = load_json(pack, n)
            except Exception as e:
                rep.err("%s: not valid json (%s)" % (n, e))
                continue
            if isinstance(obj, dict) and "display" in obj and isinstance(obj["display"], str):
                dpp = res_path(obj["display"], "display/attachments" if "attachments" in n else "display/guns")
                if not pack.has(dpp) and "attachments" not in n:
                    pass  # guns are handled above

    return rep, pack, gun_reports


def check_ammo(pack, ammo, rep, who):
    if not ammo or ":" not in ammo:
        rep.err("%s: gun data ammo %r is not a resource location" % (who, ammo))
        return
    ans, _, aid = ammo.partition(":")
    ai = "data/%s/index/ammo/%s.json" % (ans, aid)
    if not pack.has(ai):
        if pack.find(ai):
            # The ammo lives in another pack (every third-party pack points at
            # tacz:556x45 and friends).  It cannot be checked from here, and it
            # is the normal case.
            rep.note("%s: ammo %r comes from another pack - not checked" % (who, ammo))
            return
        rep.err("%s: ammo %r -> missing %s (TaCZ drops the whole gun index when "
                "its ammo does not exist)" % (who, ammo, ai))
        return
    try:
        ix = load_json(pack, ai)
    except JsonFileError as e:
        rep.err("%s: %s" % (who, e))
        return
    disp = ix.get("display") or ""
    dns = disp.partition(":")[0]
    if dns != ans:
        rep.err("%s: ammo index display %r is not in namespace %r"
                % (who, disp, ans))
    # display ids already end in "_display" (official: 556x45_display); do not
    # append another one, that was a real bug in an earlier validator.
    dp = "assets/%s/display/ammo/%s.json" % (dns, disp.partition(":")[2])
    if not resolve(pack, rep, who, dp, "ammo display"):
        rep.err("%s: ammo display -> missing %s" % (who, dp))
        return
    try:
        ad = load_json(pack, dp)
    except JsonFileError as e:
        rep.err("%s: %s" % (who, e))
        return
    # model + texture are optional: official 500mag ships a display with only
    # slot / shell / tracer_color and TaCZ falls back to a generic cartridge.
    for key, folder, ext, lvl in (("model", "geo_models", ".json", "note"),
                                  ("texture", "textures", ".png", "note"),
                                  ("slot", "textures", ".png", "err")):
        loc = ad.get(key)
        if not loc:
            (rep.err if lvl == "err" else rep.note)(
                "%s: ammo display lacks %r%s"
                % (who, key,
                   "" if lvl == "err" else " (TaCZ falls back to its default "
                                           "cartridge model)"))
        elif not resolve(pack, rep, who, res_path(loc, folder, ext),
                         "ammo " + key):
            rep.err("%s: ammo %s %r -> missing %s"
                    % (who, key, loc, res_path(loc, folder, ext)))
    sh = ad.get("shell") or {}
    for key, folder, ext in (("model", "geo_models", ".json"),
                             ("texture", "textures", ".png")):
        loc = sh.get(key)
        if not loc:
            rep.warn("%s: ammo shell lacks %r - no casing is ejected" % (who, key))
        elif not resolve(pack, rep, who, res_path(loc, folder, ext),
                         "ammo shell " + key):
            rep.err("%s: ammo shell %s %r -> missing %s"
                    % (who, key, loc, res_path(loc, folder, ext)))
    rp = "data/%s/recipes/ammo/%s.json" % (ans, aid)
    if not resolve(pack, rep, who, rp, "ammo recipe"):
        rep.warn("%s: ammo %r has no smith table recipe (%s)" % (who, ammo, rp))
    else:
        try:
            rec = load_json(pack, rp)
        except JsonFileError as e:
            rep.err("%s: %s" % (who, e))
            return
        res = rec.get("result") or {}
        if res.get("id") != ammo:
            rep.err("%s: ammo recipe result %r != %r" % (who, res.get("id"), ammo))
        if res.get("type") != "ammo":
            rep.err("%s: ammo recipe result type %r != 'ammo'"
                    % (who, res.get("type")))
        if rec.get("type") != "tacz:gun_smith_table_crafting":
            rep.err("%s: ammo recipe type %r is not tacz:gun_smith_table_crafting"
                    % (who, rec.get("type")))
        if not isinstance(res.get("count"), int) or res.get("count", 0) < 1:
            rep.err("%s: ammo recipe count %r is not a positive int"
                    % (who, res.get("count")))
        for m in rec.get("materials") or []:
            it = m.get("item") or {}
            if not (it.get("item") or it.get("tag")):
                rep.err("%s: ammo recipe material %r has neither item nor tag"
                        % (who, m))
    langs = {}
    for lg in ("en_us", "zh_cn"):
        lp = "assets/%s/lang/%s.json" % (ans, lg)
        if not resolve(pack, rep, who, lp, lg + " lang"):
            rep.warn("%s: no %s lang file (%s) - the ammo name shows raw"
                     % (who, lg, lp))
            continue
        try:
            langs[lg] = load_json(pack, lp)
        except JsonFileError as e:
            rep.err("%s: %s" % (who, e))
    if ix.get("name") and langs:
        have = [lg for lg, keys in langs.items() if ix["name"] in keys]
        if not have:
            rep.err("%s: no lang file defines %r - the item shows the raw key"
                    % (who, ix["name"]))
        elif len(have) != len(langs):
            rep.warn("%s: %r is only defined in %s" % (who, ix["name"], have))


# ---------------------------------------------------------------------------


BACKUP_HINTS = (".bak", ".dsh-backup", ".pre-", "~", ".orig")

# TaCZ ships a complete copy of tacz_default_gun inside its own jar and unpacks
# it at runtime (GunPackLoader scans the tacz/ folder *and* that copy).  Every
# pack that references tacz:xxx is therefore resolved against it, even when the
# user never installed tacz_default_gun as a folder.
BUILTIN_PREFIX = "assets/tacz/custom/tacz_default_gun/"


def builtin_pack(path):
    """The copy of tacz_default_gun that lives inside the TaCZ jar, or None.

    Works out the game instance from the usual layout <instance>/tacz/<pack>
    and looks for the TaCZ jar in <instance>/mods.  Returns None whenever the
    layout is anything else - this is a convenience, never a requirement.
    """
    tacz_dir = os.path.dirname(os.path.abspath(path))
    if os.path.basename(tacz_dir).lower() != "tacz":
        return None
    mods = os.path.join(os.path.dirname(tacz_dir), "mods")
    if not os.path.isdir(mods):
        return None
    for n in sorted(os.listdir(mods)):
        low = n.lower()
        if not low.endswith(".jar") or "tacz" not in low:
            continue
        if "mesh" in low:
            continue
        p = os.path.join(mods, n)
        try:
            with zipfile.ZipFile(p) as z:
                if BUILTIN_PREFIX + "gunpack.meta.json" not in z.namelist():
                    continue
            return Pack(p, prefix=BUILTIN_PREFIX)
        except Exception:
            continue
    return None


def sibling_packs(path, extra=()):
    """Every other pack installed next to *path*.

    A resource reference is resolved by TaCZ against the union of every pack in
    tacz/ plus the copy it unpacks from its own jar, so a pack that points at
    tacz:m4a1 (clips), tacz:shell/12g_shell (geo) or another pack's namespace is
    correct even though the file is not in its own zip.  Treating those as
    errors produced hundreds of false positives on real packs.

    Returns a list of Pack objects, never raising: a pack we cannot open simply
    does not contribute references.
    """
    out = []
    me = os.path.abspath(path)
    cands = list(extra)
    d = os.path.dirname(me)
    if d and os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            if os.path.abspath(p) == me:
                continue
            low = n.lower()
            if any(h in low for h in BACKUP_HINTS):
                continue
            if n.endswith(".zip") or os.path.isdir(p):
                cands.append(p)
    for c in cands:
        try:
            if os.path.abspath(c) == me:
                continue
            pk = Pack(c)
            if pk.names:
                out.append(pk)
        except Exception:
            continue
    try:
        bp = builtin_pack(me)
        if bp is not None:
            out.append(bp)
    except Exception:
        pass
    return out


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in argv
    no_refs = "--no-refs" in argv
    jout = None
    if "--json" in argv:
        i = argv.index("--json")
        if i + 1 < len(argv):
            jout = argv[i + 1]
            args = [a for a in args if a != jout]
    if not args:
        print(__doc__)
        return 2
    worst = 0
    summary = []
    for path in args:
        if not os.path.exists(path):
            print("no such pack: %s" % path)
            worst = 2
            continue
        refs = () if no_refs else sibling_packs(path)
        rep, pack, guns = check_pack(path, quiet=quiet, refs=refs)
        if refs and not quiet:
            print("  (resolving cross-pack references against %d sibling pack(s))"
                  % len(refs))
        for w in rep.warns:
            print("WARN  " + w)
        for e in rep.errors:
            print("ERROR " + e)
        print("%-52s %d error(s), %d warning(s)"
              % (rep.label, len(rep.errors), len(rep.warns)))
        summary.append({"pack": path, "errors": rep.errors, "warns": rep.warns})
        if rep.errors:
            worst = 1
    if jout:
        with open(jout, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=1, ensure_ascii=False)
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))
