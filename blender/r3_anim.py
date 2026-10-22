"""r3_anim.py - author the Bedrock 1.8.0 animation set for the rifle3 gun pack.

Everything here is written in TaCZ model space (the space r3_export_tacz.py
bakes into):  -Z muzzle, +Z butt, +Y up, +X the shooter's right.  Units are
TaCZ model units; 1 mm = 0.0524476 units.

The magazine does not drop straight down: its well is tilted 15.6 deg back, so
the real extraction axis is (0.268, 0, 0.963) in Blender mm space, which maps
to (0, -0.963, -0.268) here (down and towards the muzzle).

Timings are matched to assets/tacz/player_animator/rifle_default.player_animation.json
"reload_upper" (2.375 s) so the default first-person arms and this gun agree on
when the magazine leaves and when it goes back in.
"""
import json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'work', 'tacz')
K = 0.0524476          # model units per millimetre
OFFY = 12.0


def P(xmm, ymm, zmm):
    """Blender mm -> TaCZ model units (same mapping as the exporter)."""
    return [round(-ymm * K, 4), round(zmm * K + OFFY, 4), round((xmm - 345.0) * K, 4)]


# 165 mm of travel along the (tilted) magazine axis
MAG_FULL = [0.0, round(-0.963 * 165 * K, 4), round(-0.268 * 165 * K, 4)]   # (0, -8.334, -2.319)
BOLT_BACK = [0.0, 0.0, 1.57]      # 30 mm rearward
CATCH_IN = [-0.12, 0.0, 0.0]      # bolt catch pressed inwards
REL_IN = [0.17, 0.0, 0.0]         # magazine release pressed inwards

# ---- hand rig ------------------------------------------------------------
# TaCZ ships no hands inside the gun model: it registers a functional renderer
# for the bones named righthand_pos / lefthand_pos and draws the *vanilla
# player arms* at whatever world matrix those bones end up with.  So the only
# thing an animation has to say about the hands is the pose of righthand /
# lefthand - every official gun writes them into every animation, and a missing
# channel means "arm in its default pose", i.e. the hand not holding the gun.
#
# These are m4a1's values verbatim (a proven AR arm pose).  No position offset
# is needed: r3_export_tacz.py already slid the whole bone chain so that
# righthand_pos sits on the pistol grip and lefthand_pos under the handguard.
RH_ROT = [96.07, 8.95, -179.05]
LH_ROT = [96.9594, -29.1425, -146.85684]
HAND_SCALE = [1, 1.5, 1]

# Where the support hand has to travel to be ON the magazine, in the position
# channel's own units - and those units are MODEL UNITS, not blocks (the engine
# multiplies every keyframe by 0.0625 = 1/16 itself; see work/fk2.py).  Getting
# that wrong by a factor of 16 is exactly what made the first version read as a
# "force reload": the magazine slid out of the well while the hand sat still on
# the handguard.
#
# The value is NOT (magazine centre - lefthand_pos): the vanilla arm is drawn
# from lefthand_pos and reaches forward and down, so the anchor is not the
# visible hand.  The ground truth for the visible hand is the Hand_L glove mesh
# that is still in rifle3.blend, wrapped around the handguard:
#     glove   (animated) [ 0.436, 13.094, -13.497]   engine frame (work/attach.py)
#     magazine           [ 0.000, 17.245,  -2.360]
#     delta              [-0.436,  4.151,  11.137]
# = -8 mm across, -79 mm down, +212 mm towards the shooter.  The 212 mm is the
# handguard centre (x=157 mm) -> magazine centre (x=300 mm) distance PLUS the
# reach of the arm itself: the glove has to be evaluated under the animated
# pose, because every animation writes LH_ROT (97/-29/-147 deg) onto the
# lefthand bone and that swings the visible hand well forward of its rest spot.
# Comparing the REST pose against the magazine is what produced the wrong first
# answer.  Position channels map 1:1 onto world translation (work/chan_probe.py),
# so the required channel value is just this delta with Y negated.
HAND_GRAB = [-0.4356, -4.1511, 11.1370]


# ---- sound cues ----------------------------------------------------------
# Bedrock animations carry sound_effects keyframes and TaCZ plays them on the
# animation's own timeline (SoundEffectKeyframes / ObjectAnimationSoundChannel).
# Reusing the official m4a1 one-shots means the reload *sounds* right without
# shipping any audio in the pack.
SFX_RAISE = 'tacz:m4a1/m4a1_reload_empty_raise'
SFX_MAGOUT = 'tacz:m4a1/m4a1_reload_empty_magout'
SFX_MAGHIT = 'tacz:m4a1/m4a1_reload_empty_maghit'
SFX_MAGIN = 'tacz:m4a1/m4a1_reload_empty_magin'
SFX_CHARGE = 'tacz:m4a1/m4a1_reload_empty_charge'
SFX_END = 'tacz:m4a1/m4a1_reload_empty_end'
SFX_TAC_START = 'tacz:m4a1/m4a1_reload_tactical_start'
SFX_TAC_MAGOUT = 'tacz:m4a1/m4a1_reload_tactical_magout'
SFX_TAC_MAGHIT = 'tacz:m4a1/m4a1_reload_tactical_maghit'
SFX_TAC_MAGIN = 'tacz:m4a1/m4a1_reload_tactical_magin'
SFX_TAC_END = 'tacz:m4a1/m4a1_reload_tactical_end'
SFX_DRAW = 'tacz:m4a1/m4a1_draw'
SFX_PUTAWAY = 'tacz:m4a1/m4a1_put_away'
SFX_INSPECT_MAGOUT = 'tacz:m4a1/m4a1_inspect_magout'
SFX_INSPECT_MAGIN = 'tacz:m4a1/m4a1_inspect_magin'
SFX_INSPECT_RACK = 'tacz:m4a1/m4a1_inspect_rackon'
SFX_INSPECT_REL = 'tacz:m4a1/m4a1_inspect_rackrelase'
SFX_INSPECT_LIFT = 'tacz:m4a1/m4a1_inspect_lift'
SFX_INSPECT_END = 'tacz:m4a1/m4a1_inspect_end'
SFX_INSPECT_EMPTY_RACK = 'tacz:m4a1/m4a1_inspect_empty_rackcheck'
SFX_INSPECT_EMPTY_ON = 'tacz:m4a1/m4a1_inspect_empty_rackon'
SFX_INSPECT_EMPTY_END = 'tacz:m4a1/m4a1_inspect_empty_end'


def sfx(pairs):
    return {fmt(t): {'effect': e} for t, e in pairs}


def fmt(t):
    s = ('%.4f' % t).rstrip('0').rstrip('.')
    return s if s else '0'


def kf(keys, mode='catmullrom'):
    """keys: [(time, [x,y,z] or scalar)] -> Bedrock channel object."""
    out = {}
    for t, v in keys:
        out[fmt(t)] = {'post': v, 'lerp_mode': mode}
    return out


def mul(v, s):
    return [round(v[0] * s, 4), round(v[1] * s, 4), round(v[2] * s, 4)]


def add(a, b):
    return [round(a[0] + b[0], 4), round(a[1] + b[1], 4), round(a[2] + b[2], 4)]


def static_hands():
    """The arm pose every animation starts and ends on.

    Constant rotation/scale, zero position - the offset lives in the bone
    pivots (r3_export_tacz.py).  Returned as a fresh dict each call so callers
    can mutate it.
    """
    return {
        'righthand': {'rotation': list(RH_ROT), 'position': [0, 0, 0],
                      'scale': list(HAND_SCALE)},
        'lefthand': {'rotation': list(LH_ROT), 'position': [0, 0, 0],
                     'scale': list(HAND_SCALE)},
    }


# ---------------------------------------------------------------- magazine --
def mag_drop(t0, t1):
    """extract: s goes 0 -> 1 with quadratic acceleration (gravity)."""
    keys = [(0.0, [0, 0, 0]), (t0, [0, 0, 0])]
    n = 6
    for i in range(1, n + 1):
        u = i / float(n)
        keys.append((t0 + (t1 - t0) * u, mul(MAG_FULL, u * u)))
    return keys


def mag_insert(t0, t1):
    """insert: s goes 1 -> 0, decelerating into the well."""
    keys = []
    n = 7
    for i in range(n + 1):
        u = i / float(n)
        s = (1.0 - u) ** 2
        keys.append((t0 + (t1 - t0) * u, mul(MAG_FULL, s)))
    return keys


# ------------------------------------------------------------------- reload --
def reload(empty=True):
    """The headline animation.  empty=True = bolt locked back, new mag, then
    the bolt catch drops the bolt; empty=False = tactical (round chambered)."""
    if empty:
        L = 2.375
        drop = (0.22, 0.50)
        back = 0.92
        insert = (0.92, 1.32)
        bolt_release = 1.78
        tilt_end = 2.05
    else:
        L = 2.2
        drop = (0.18, 0.42)
        back = 0.82
        insert = (0.82, 1.20)
        bolt_release = None
        tilt_end = 1.92

    bones = static_hands()

    # --- gun tilt -----------------------------------------------------------
    # Rolled to the SHOOTER'S RIGHT (Z negative), muzzle up (X negative), yawed
    # a touch to the left (Y negative) - the m4a1 pose: its reload_empty peaks
    # at [-19.6, -19.1, -22.2].  Rolling right turns the magwell towards the
    # left flank, which is where the (invisible) support hand comes from, so
    # the magazine drops away to the LEFT of the screen.  The first pass had
    # the sign the other way round: it leaned left and spat the magazine out
    # to the right, i.e. a mirror image of how an AR is actually reloaded.
    bones['root'] = {
        'rotation': kf([
            (0.0, [0, 0, 0]),
            (0.10, [-1.8, -1.8, -6]),
            (drop[0], [-5.0, -4.5, -13]),
            (drop[1], [-9.0, -8.0, -22]),
            (0.70, [-12.0, -11.0, -26]),
            (back, [-12.0, -11.0, -26]),
            (insert[1] + 0.05, [-9.0, -8.0, -20]),
            (tilt_end - 0.30, [-4.0, -3.5, -9]),
            (tilt_end, [0, 0, 0]),
            (L, [0, 0, 0]),
        ]),
        # translation follows m4a1: at its peak it sits at [-0.51, -0.39,
        # 0.08], i.e. towards screen-right (-X), up (-Y) and a hair towards the
        # shooter (+Z).
        'position': kf([
            (0.0, [0, 0, 0]),
            (drop[0], [-0.15, -0.10, 0.45]),
            (0.70, [-0.35, -0.20, 0.95]),
            (back, [-0.35, -0.20, 0.95]),
            (insert[1] + 0.05, [-0.20, -0.12, 0.55]),
            (tilt_end, [0, 0, 0]),
            (L, [0, 0, 0]),
        ]),
    }

    # --- magazine release button ------------------------------------------
    bones['mag_release'] = {
        'position': kf([
            (0.0, [0, 0, 0]),
            (drop[0] - 0.06, [0, 0, 0]),
            (drop[0] + 0.02, REL_IN),
            (drop[0] + 0.16, REL_IN),
            (drop[0] + 0.24, [0, 0, 0]),
            (L, [0, 0, 0]),
        ]),
    }

    # --- magazine: out, gone, back in, seated ------------------------------
    mpos = mag_drop(drop[0], drop[1]) + mag_insert(insert[0], insert[1])
    mpos.append((insert[1] + 0.06, [0, 0, 0]))
    mpos.append((L, [0, 0, 0]))
    bones['magazine'] = {
        'position': kf(mpos),
        'scale': kf([
            (0.0, [1, 1, 1]),
            (drop[1] - 0.04, [1, 1, 1]),
            (drop[1], [0, 0, 0]),
            (back - 0.04, [0, 0, 0]),
            (back, [1, 1, 1]),
            (L, [1, 1, 1]),
        ], mode='linear'),
    }

    # --- left hand: lets go of the handguard and carries the magazine ------
    # The magazine and the left hand are SIBLINGS under `gun` (see BONES in
    # r3_export_tacz.py), so animating only the magazine reads as a "force
    # reload": the mag floats out, swaps itself and floats back with nothing
    # touching it.  Official m4a1 avoids that structurally - its magazine is a
    # child of mag_and_lefthand - but reparenting ours would also make the
    # magazine drift with the hand in every other animation.
    #
    # So the hand gets the magazine's own translation plus the constant offset
    # between the hand anchor (lefthand_pos) and the magazine body centre.  Both
    # bones translate in `gun` space, so the offset is just added to the same
    # keyframe values: the two stay locked together for the whole carry.
    reach = (0.02, drop[0] - 0.04)
    carry_out = insert[1] + 0.06
    back_to_guard = min(L, carry_out + 0.22)
    hand = [(0.0, [0, 0, 0]), (reach[0], [0, 0, 0]), (reach[1], list(HAND_GRAB))]
    for t, v in mpos:
        if drop[0] <= t <= carry_out:
            hand.append((t, add(HAND_GRAB, v)))
    hand.append((carry_out, list(HAND_GRAB)))
    hand.append((back_to_guard, [0, 0, 0]))
    hand.append((L, [0, 0, 0]))
    hand.sort(key=lambda kv: kv[0])
    merged = []
    for t, v in hand:
        if merged and abs(merged[-1][0] - t) < 1e-6:
            merged[-1] = (t, v)
        else:
            merged.append((t, v))
    bones['lefthand'] = {
        'rotation': list(LH_ROT),
        'position': kf(merged),
        'scale': list(HAND_SCALE),
    }
    # --- bolt: locked back, then slammed home on the catch ------------------
    if empty:
        bones['bolt'] = {
            'position': kf([
                (0.0, BOLT_BACK),
                (bolt_release, BOLT_BACK),
                (bolt_release + 0.05, [0, 0, 0]),
                (L, [0, 0, 0]),
            ]),
        }
        bones['bolt_catch'] = {
            'position': kf([
                (0.0, [0, 0, 0]),
                (bolt_release - 0.10, [0, 0, 0]),
                (bolt_release - 0.03, CATCH_IN),
                (bolt_release + 0.10, CATCH_IN),
                (bolt_release + 0.20, [0, 0, 0]),
                (L, [0, 0, 0]),
            ]),
        }
    else:
        bones['bolt'] = {'position': kf([(0.0, [0, 0, 0]), (L, [0, 0, 0])])}

    if empty:
        sounds = sfx([
            (0.0, SFX_RAISE),
            (drop[0] + 0.02, SFX_MAGOUT),
            (drop[1], SFX_MAGHIT),
            (insert[1], SFX_MAGIN),
            (bolt_release, SFX_CHARGE),
            (min(L - 0.05, bolt_release + 0.30), SFX_END),
        ])
    else:
        sounds = sfx([
            (0.0, SFX_TAC_START),
            (drop[0] + 0.02, SFX_TAC_MAGOUT),
            (drop[1], SFX_TAC_MAGHIT),
            (insert[1], SFX_TAC_MAGIN),
            (min(L - 0.05, insert[1] + 0.45), SFX_TAC_END),
        ])
    return {'animation_length': L, 'bones': bones, 'sound_effects': sounds}


def shoot():
    # NOTE: no hand channels here on purpose.  The default state machine runs
    # "shoot" as an ADDITIVE animation on the gun-kick track
    # (runAnimation("shoot", track, true, PLAY_ONCE_STOP, 0)), so every value in
    # it is *added* to whatever the base track (static_idle) already holds.  The
    # official m4a1 shoot carries root / m4a1_bolt / bullet_in_barrel / camera /
    # constraint only - never a hand.  Writing righthand/lefthand here (as the
    # first version did) doubles their 96 deg pose on every shot and the arms
    # flip wildly, which is exactly the "一开枪就上下翻飞" symptom.
    bones = {}
    bones['root'] = {
        'rotation': kf([
            (0.0, [0, 0, 0]), (0.0333, [1.2, 0, 0.7]), (0.0667, [-1.9, 0, -1.2]),
            (0.1, [-2.0, 0, -1.2]), (0.1333, [-0.9, 0, -0.35]), (0.1667, [0.2, 0, 0.5]),
            (0.2, [0.3, 0, 0.3]), (0.2667, [0.45, 0, -0.25]), (0.3333, [0.3, -0.13, 0.08]),
            (0.4, [0.18, -0.17, 0.17]), (0.5, [0.06, -0.07, -0.07]), (0.6333, [0, 0, 0]),
        ]),
        'position': kf([
            (0.0, [0, 0, 0]), (0.0333, [0, -0.02, 1.05]), (0.0667, [0, -0.05, 0.8]),
            (0.1, [0, -0.05, 0.4]), (0.1667, [0, -0.04, -0.01]), (0.2667, [0, -0.02, 0.06]),
            (0.3667, [0, 0, 0]), (0.6333, [0, 0, 0]),
        ]),
    }
    bones['bolt'] = {
        'position': kf([
            (0.0, [0, 0, 0]), (0.0333, BOLT_BACK), (0.0667, [0, 0, 0]), (0.6333, [0, 0, 0]),
        ], mode='linear'),
    }
    # the trigger pivots about Blender +Y, which the export maps to model -X;
    # a reflection flips the handedness, so the -18 deg pull becomes -18 on X
    bones['trigger'] = {
        'rotation': kf([
            (0.0, [0, 0, 0]), (0.0167, [-18, 0, 0]), (0.06, [-18, 0, 0]),
            (0.12, [0, 0, 0]), (0.6333, [0, 0, 0]),
        ], mode='linear'),
    }
    return {'animation_length': 0.6333, 'bones': bones}


def draw():
    bones = static_hands()
    bones['root'] = {
        'rotation': kf([
            (0.0, [0.8, -32.6, 34.0]), (0.1, [-0.9, -32.9, 26.1]), (0.2, [-1.5, -26.5, 17.6]),
            (0.3, [-0.2, -10.1, 10.8]), (0.4, [0.2, -1.7, 5.0]), (0.5, [0.05, -0.02, 0.15]),
            (0.6, [-0.01, -0.17, 0.96]), (0.7, [0, 0, 0]), (0.8, [0, 0, 0]),
        ]),
        'position': kf([
            (0.0, [-3.2, -5.6, 13.5]), (0.1, [-1.4, -3.2, 5.1]), (0.2, [-0.45, -1.5, 0.43]),
            (0.3, [-0.14, -0.69, -0.75]), (0.4, [-0.01, -0.38, -0.3]), (0.5, [-0.02, -0.21, 0.14]),
            (0.6, [-0.01, -0.02, -0.06]), (0.7, [0, 0, 0]), (0.8, [0, 0, 0]),
        ]),
    }
    return {'animation_length': 0.8, 'bones': bones,
            'sound_effects': sfx([(0.12, SFX_DRAW)])}


def put_away():
    bones = static_hands()
    bones['root'] = {
        'rotation': kf([
            (0.0, [0, 0, 0]), (0.15, [-0.5, -12, 9]), (0.30, [-1.0, -26, 21]),
            (0.4333, [0.8, -32.6, 34.0]),
        ]),
        'position': kf([
            (0.0, [0, 0, 0]), (0.15, [-0.4, -1.6, 1.8]), (0.30, [-1.4, -3.8, 7.0]),
            (0.4333, [-3.2, -5.6, 13.5]),
        ]),
    }
    return {'animation_length': 0.4333, 'bones': bones,
            'sound_effects': sfx([(0.02, SFX_PUTAWAY)])}


def static_idle():
    bones = static_hands()
    bones['root'] = {'rotation': [0, 0, 0], 'position': [0, 0, 0]}
    return {'animation_length': 0.0667, 'bones': bones}


def static_bolt_caught():
    bones = static_hands()
    bones['bolt'] = {'position': kf([(0.0, BOLT_BACK), (0.6667, BOLT_BACK)])}
    bones['bolt_catch'] = {
        'position': kf([
            (0.0, [0, 0, 0]), (0.1, CATCH_IN), (0.25, CATCH_IN), (0.4, [0, 0, 0]),
            (0.6667, [0, 0, 0]),
        ]),
    }
    return {'animation_length': 0.6667, 'bones': bones}


def inspect():
    """Roll the gun over, then pull the charging handle back and let it fly."""
    bones = static_hands()
    bones['root'] = {
        'rotation': kf([
            (0.0, [0, 0, 0]), (0.35, [4, 26, -12]), (0.9, [4, 26, -12]),
            (1.35, [8, -28, 22]), (1.75, [8, -28, 22]), (2.1, [3, -12, 9]),
            (2.5, [0, 0, 0]),
        ]),
        'position': kf([
            (0.0, [0, 0, 0]), (0.35, [0, 0.5, 0.8]), (0.9, [0, 0.5, 0.8]),
            (1.35, [0, 0.3, 1.2]), (1.75, [0, 0.3, 1.2]), (2.1, [0, 0.1, 0.4]),
            (2.5, [0, 0, 0]),
        ]),
    }
    bones['charge_handle'] = {
        'position': kf([
            (0.0, [0, 0, 0]), (1.5, [0, 0, 0]), (1.62, [0, 0, 0.6]), (1.70, [0, 0, 0.6]),
            (1.74, [0, 0, 0]), (2.5, [0, 0, 0]),
        ], mode='linear'),
    }
    bones['bolt'] = {
        'position': kf([
            (0.0, [0, 0, 0]), (1.5, [0, 0, 0]), (1.62, [0, 0, 1.0]), (1.70, [0, 0, 1.0]),
            (1.74, [0, 0, 0]), (2.5, [0, 0, 0]),
        ], mode='linear'),
    }
    return {'animation_length': 2.5, 'bones': bones,
            'sound_effects': sfx([
                (0.20, SFX_INSPECT_LIFT),
                (1.10, SFX_INSPECT_MAGOUT),
                (1.35, SFX_INSPECT_MAGIN),
                (1.58, SFX_INSPECT_RACK),
                (1.72, SFX_INSPECT_REL),
                (2.30, SFX_INSPECT_END),
            ])}


def inspect_empty():
    """Same roll-over, but the bolt is already locked back and the charging
    handle is not touched - the state machine picks this one when the gun is
    dry (isNoAmmo -> inspect_empty)."""
    bones = static_hands()
    bones['root'] = {
        'rotation': kf([
            (0.0, [0, 0, 0]), (0.35, [6, 22, -14]), (0.9, [6, 22, -14]),
            (1.35, [10, -24, 20]), (1.75, [10, -24, 20]), (2.05, [3, -10, 8]),
            (2.35, [0, 0, 0]),
        ]),
        'position': kf([
            (0.0, [0, 0, 0]), (0.35, [0, 0.5, 0.9]), (0.9, [0, 0.5, 0.9]),
            (1.35, [0, 0.3, 1.3]), (1.75, [0, 0.3, 1.3]), (2.05, [0, 0.1, 0.4]),
            (2.35, [0, 0, 0]),
        ]),
    }
    bones['bolt'] = {'position': kf([(0.0, BOLT_BACK), (2.35, BOLT_BACK)])}
    return {'animation_length': 2.35, 'bones': bones,
            'sound_effects': sfx([
                (0.20, SFX_INSPECT_LIFT),
                (1.05, SFX_INSPECT_EMPTY_RACK),
                (1.20, SFX_INSPECT_EMPTY_ON),
                (2.15, SFX_INSPECT_EMPTY_END),
            ])}


# ---- baking --------------------------------------------------------------
# TaCZ's BedrockAnimation only knows loop / animation_length / bones /
# sound_effects, and every official pack bakes its channels onto the 1/30 s
# grid as *plain* [x, y, z] arrays.  A Bedrock keyframe object
# ({"post": [...], "lerp_mode": "catmullrom"}) is also parsed by TaCZ's
# AnimationKeyframesSerializer, but the plain array is the form that is proven
# to play in game, so we author sparsely and bake on export.
FPS = 30.0


def _catmull(p0, p1, p2, p3, u):
    u2 = u * u
    u3 = u2 * u
    out = []
    for i in range(3):
        out.append(0.5 * ((2 * p1[i]) + (-p0[i] + p2[i]) * u
                          + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * u2
                          + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * u3))
    return out


def _sample(keys, t):
    """keys: sorted [(time, vec, mode)]; mode belongs to the left key."""
    if t <= keys[0][0]:
        return list(keys[0][1])
    if t >= keys[-1][0]:
        return list(keys[-1][1])
    for i in range(len(keys) - 1):
        t0, v0, mode = keys[i]
        t1, v1 = keys[i + 1][0], keys[i + 1][1]
        if t0 <= t <= t1:
            span = t1 - t0
            u = 0.0 if span <= 0 else (t - t0) / span
            if mode == 'linear' or len(keys) < 3:
                return [v0[k] + (v1[k] - v0[k]) * u for k in range(3)]
            p0 = keys[i - 1][1] if i > 0 else v0
            p3 = keys[i + 2][1] if i + 2 < len(keys) else v1
            val = _catmull(p0, v0, v1, p3, u)
            # Catmull-Rom overshoots whenever a segment starts or ends flat
            # (the magazine does: it sits still, then accelerates away).  Clamp
            # to the segment's own endpoints so a "hold" really holds.
            return [min(max(val[k], min(v0[k], v1[k])), max(v0[k], v1[k])) for k in range(3)]
    return list(keys[-1][1])


def bake_channel(ch, length):
    """sparse Bedrock channel -> plain-array channel sampled on the 1/30 grid."""
    if isinstance(ch, list):
        return ch                                  # already a static value
    if not ch:
        return [0, 0, 0]
    keys = []
    for ts, v in ch.items():
        v = v.get('post', v) if isinstance(v, dict) else v
        keys.append((float(ts), list(v), (ch[ts].get('lerp_mode') if isinstance(ch[ts], dict) else None) or 'catmullrom'))
    keys.sort(key=lambda k: k[0])

    times = []
    n = int(round(length * FPS))
    for i in range(n + 1):
        times.append(round(i / FPS, 4))
    if abs(times[-1] - length) > 1e-4:
        times.append(length)

    vals = [_sample(keys, t) for t in times]
    flat = all(max(abs(v[k] - vals[0][k]) for k in range(3)) < 1e-5 for v in vals)
    if flat:
        return [round(x, 4) for x in vals[0]]
    return {fmt(t): [round(x, 4) for x in v] for t, v in zip(times, vals)}


def bake(data):
    length = data['animation_length']
    bones = {}
    for bone, chans in data['bones'].items():
        bones[bone] = {ch: bake_channel(v, length) for ch, v in chans.items()}
    out = dict(data)
    out['bones'] = bones
    return out


ANIMS = {
    'static_idle': static_idle(),
    'static_bolt_caught': static_bolt_caught(),
    'shoot': shoot(),
    'draw': draw(),
    'put_away': put_away(),
    'inspect': inspect(),
    'inspect_empty': inspect_empty(),
    'reload_empty': reload(empty=True),
    'reload_tactical': reload(empty=False),
}


def main():
    geo = json.load(open(os.path.join(OUT, 'geo.json'), encoding='utf-8'))
    names = {b['name'] for b in geo['minecraft:geometry'][0]['bones']}

    bad = []
    for an, data in ANIMS.items():
        for bone in data['bones']:
            if bone not in names:
                bad.append((an, bone))
    if bad:
        raise SystemExit('animation references unknown bones: %s' % bad)

    baked = {name: bake(a) for name, a in ANIMS.items()}
    doc = {'format_version': '1.8.0', 'animations': baked}
    path = os.path.join(OUT, 'rifle3.animation.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
    print('wrote', path, os.path.getsize(path), 'bytes')
    for an, data in sorted(ANIMS.items()):
        print('  %-20s %5.4f s  bones: %s' % (an, data['animation_length'], ', '.join(sorted(data['bones']))))


if __name__ == '__main__':
    main()
