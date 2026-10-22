"""r3_mat.py — materials modelled on the reference sheet.

Key insight from sampling the reference:
  * hard-anodised aluminium = METALLIC 1.0, fairly rough (0.42-0.55), very dark base
  * the two greys differ mostly in VALUE, not in hue
  * every surface is bead-blasted, so roughness has fine variation and
    edges are slightly lighter (oxide wears thin there)

Everything is driven by a shared node group so the whole gun stays coherent.
"""
import bpy


def _principled(nt):
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None


def surf(name, base, rough=0.45, metal=1.0, spec=0.5, trans=0.0, ior=1.5,
         coat=0.0, emit=None, bump=0.0, bump_scale=2000.0,
         rough_var=0.0, rough_scale=60.0, edge_wear=0.0, edge_col=None,
         tint=(0.0, 0.0, 0.0), tint_scale=30.0, tint_strength=0.0):
    """Full PBR surface: bead-blast bump, roughness break-up, edge wear."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = _principled(nt)
    b.inputs['Base Color'].default_value = (*base, 1.0)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    if coat > 0:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = 0.12
    if trans > 0:
        b.inputs['Transmission Weight'].default_value = trans
        b.inputs['IOR'].default_value = ior
    if emit:
        b.inputs['Emission Color'].default_value = (*emit[:3], 1.0)
        b.inputs['Emission Strength'].default_value = emit[3]

    # ---- bead-blast micro bump
    if bump > 0:
        n = nt.nodes.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = bump_scale
        n.inputs['Detail'].default_value = 2.0
        n.inputs['Roughness'].default_value = 0.6
        bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump
        bp.inputs['Distance'].default_value = 0.00015
        nt.links.new(n.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])

    # ---- roughness break-up (machining / handling unevenness)
    if rough_var > 0:
        n2 = nt.nodes.new('ShaderNodeTexNoise')
        n2.inputs['Scale'].default_value = rough_scale
        n2.inputs['Detail'].default_value = 3.0
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[0].color = (rough - rough_var, ) * 3 + (1,)
        ramp.color_ramp.elements[1].position = 0.75
        ramp.color_ramp.elements[1].color = (rough + rough_var, ) * 3 + (1,)
        nt.links.new(n2.outputs['Fac'], ramp.inputs['Fac'])
        nt.links.new(ramp.outputs['Color'], b.inputs['Roughness'])

    # ---- large-scale tone variation (anodising is never perfectly even)
    if tint_strength > 0:
        n3 = nt.nodes.new('ShaderNodeTexNoise')
        n3.inputs['Scale'].default_value = tint_scale
        n3.inputs['Detail'].default_value = 2.0
        mix = nt.nodes.new('ShaderNodeMixRGB')
        mix.blend_type = 'MIX'
        mix.inputs['Fac'].default_value = tint_strength
        mix.inputs['Color1'].default_value = (*base, 1.0)
        mix.inputs['Color2'].default_value = (*tint, 1.0)
        # modulate the mix amount by noise so the variation is patchy
        nt.links.new(n3.outputs['Fac'], mix.inputs['Fac'])
        nt.links.new(mix.outputs['Color'], b.inputs['Base Color'])

    # ---- edge wear: convex geometry wears the anodising thin
    # NOTE: the Bevel node gives nicer results but is very expensive in Cycles
    # (~50x slower on this scene). Pointiness is a cheap mesh attribute, but its
    # range is narrow on low-poly meshes, so it is remapped AND scaled down.
    if edge_wear > 0:
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.interpolation = 'EASE'
        # narrow band: only genuinely convex tips pass. Small parts (rail teeth,
        # screws) hit high pointiness easily, so the window is kept tight and the
        # result is scaled down afterwards.
        ramp.color_ramp.elements[0].position = 0.512
        ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
        ramp.color_ramp.elements[1].position = 0.545
        ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
        nt.links.new(geo.outputs['Pointiness'], ramp.inputs['Fac'])
        # soften: the wear is a hint, not a white outline
        mult = nt.nodes.new('ShaderNodeMath')
        mult.operation = 'MULTIPLY'
        mult.inputs[1].default_value = min(0.30, edge_wear * 0.22)
        nt.links.new(ramp.outputs['Color'], mult.inputs[0])
        em = nt.nodes.new('ShaderNodeMixRGB')
        em.blend_type = 'MIX'
        em.inputs['Color1'].default_value = (*base, 1.0)
        em.inputs['Color2'].default_value = (*(edge_col or (0.30, 0.30, 0.31)), 1.0)
        nt.links.new(mult.outputs['Value'], em.inputs['Fac'])
        nt.links.new(em.outputs['Color'], b.inputs['Base Color'])
        # worn edges read slightly smoother (brighter specular streak)
        rmix = nt.nodes.new('ShaderNodeMixRGB')
        rmix.blend_type = 'MIX'
        w = max(0.06, rough - 0.13 * edge_wear)
        rmix.inputs['Color1'].default_value = (rough,) * 3 + (1,)
        rmix.inputs['Color2'].default_value = (w,) * 3 + (1,)
        nt.links.new(mult.outputs['Value'], rmix.inputs['Fac'])
        nt.links.new(rmix.outputs['Color'], b.inputs['Roughness'])
    return m


def build_materials():
    M = {}
    # handguard upper shell / magwell panel / cheek riser: hard anodised, mid grey
    # Tone calibrated against the sheet's tonal relationships (work/tonal.py):
    # the sheet's grey:black contrast is ~2.6:1 in sRGB, so the grey has to sit
    # well clear of the receiver rather than a shade above it.
    M['gray'] = surf('M_Gray', (0.105, 0.107, 0.104), rough=0.63, metal=1.0,
                     bump=0.16, bump_scale=2600.0, rough_var=0.09, rough_scale=48.0,
                     edge_wear=0.55, edge_col=(0.19, 0.19, 0.188),
                     tint=(0.078, 0.079, 0.077), tint_scale=26.0, tint_strength=0.55)

    # upper/lower receiver, rails: dark hard anodised
    # mid grey: sits between M_Gray (receiver plate) and M_Gray2 (handguard),
    # used for machined chamfers that catch light but must not read as paint.
    M['gray4'] = surf('M_Gray4', (0.072, 0.0735, 0.0715), rough=0.58, metal=1.0,
                      bump=0.16, bump_scale=2600.0, rough_var=0.08,
                      rough_scale=54.0, edge_wear=0.40,
                      edge_col=(0.15, 0.15, 0.148),
                      tint=(0.052, 0.053, 0.0515), tint_scale=26.0,
                      tint_strength=0.45)
    M['black'] = surf('M_Black', (0.0063, 0.0065, 0.0069), rough=0.52, metal=1.0,
                      bump=0.13, bump_scale=2600.0, rough_var=0.08, rough_scale=52.0,
                      edge_wear=0.50, edge_col=(0.115, 0.115, 0.118),
                      tint=(0.0062, 0.0064, 0.0069), tint_scale=30.0, tint_strength=0.5)

    # grip / stock frame / hand stop: filled nylon polymer
    M['poly'] = surf('M_Polymer', (0.0046, 0.0048, 0.0052), rough=0.66, metal=0.0,
                     spec=0.4, bump=0.42, bump_scale=5200.0,
                     rough_var=0.10, rough_scale=180.0,
                     edge_wear=0.30, edge_col=(0.055, 0.056, 0.058))

    # GRIP / handguard texture. The reference grip is NOT banded - it is a
    # smooth moulded border with a fine STIPPLE panel inside it. Modelling
    # stipple as geometry (a stack of rib prisms) produced visible horizontal
    # steps that read as a ladder, so the texture is a shader bump instead and
    # the only geometry left is the border frame.
    M['grip'] = surf('M_Grip', (0.0043, 0.0045, 0.0049), rough=0.72, metal=0.0,
                     spec=0.32, bump=0.0, rough_var=0.10, rough_scale=180.0)
    _mg = M['grip']
    _nt = _mg.node_tree
    _b = _principled(_nt)
    _vor = _nt.nodes.new('ShaderNodeTexVoronoi')
    _vor.feature = 'F1'
    _vor.inputs['Scale'].default_value = 2100.0
    _vor.inputs['Randomness'].default_value = 1.0
    _nz = _nt.nodes.new('ShaderNodeTexNoise')
    _nz.inputs['Scale'].default_value = 900.0
    _nz.inputs['Detail'].default_value = 4.0
    _mixb = _nt.nodes.new('ShaderNodeMixRGB')
    _mixb.blend_type = 'MULTIPLY'
    _mixb.inputs['Fac'].default_value = 0.55
    _nt.links.new(_vor.outputs['Distance'], _mixb.inputs['Color1'])
    _nt.links.new(_nz.outputs['Fac'], _mixb.inputs['Color2'])
    _bp = _nt.nodes.new('ShaderNodeBump')
    _bp.inputs['Strength'].default_value = 0.62
    _bp.inputs['Distance'].default_value = 0.00022
    _nt.links.new(_mixb.outputs['Color'], _bp.inputs['Height'])
    _nt.links.new(_bp.outputs['Normal'], _b.inputs['Normal'])

    # muzzle brake / optic / screws: dark phosphate steel
    M['steel'] = surf('M_Steel', (0.022, 0.0225, 0.024), rough=0.46, metal=1.0,
                      bump=0.09, bump_scale=3000.0, rough_var=0.07, rough_scale=70.0,
                      edge_wear=0.45, edge_col=(0.24, 0.24, 0.245))

    # butt pad: rubber
    M['rubber'] = surf('M_Rubber', (0.0090, 0.0090, 0.0095), rough=0.82, metal=0.0,
                       spec=0.25, bump=0.55, bump_scale=6000.0,
                       edge_wear=0.15, edge_col=(0.035, 0.035, 0.036))

    # MAGAZINE - OPAQUE GREY POLYMER, not transparent.
    # I had this as smoked polycarbonate and spent a long time making the
    # transmission believable. The user corrected it: the magazine in the
    # sheet is a solid GREY part; the pale look is just a light grey moulding,
    # not see-through. Making it opaque is also why it now reads correctly at
    # silhouette level - a transmissive shell never matches a solid one.
    # Value sits between the receiver black and the handguard grey, which is
    # exactly where the sheet puts it (~178 grey against ~47 receiver).
    M['mag'] = surf('M_Mag', (0.155, 0.158, 0.160), rough=0.50, metal=0.0,
                    spec=0.45, bump=0.20, bump_scale=3200.0,
                    rough_var=0.07, rough_scale=90.0,
                    edge_wear=0.35, edge_col=(0.26, 0.26, 0.265))

    # cartridge cases seen through the mag
    M['brass'] = surf('M_Cartridge', (0.44, 0.33, 0.12), rough=0.30, metal=1.0,
                      rough_var=0.05, rough_scale=120.0)

    # optic glass
    # Optic glass.  A transmissive shell with a mirror coat renders from the
    # FRONT as a flat white disc, because the coat reflects the studio
    # backdrop straight back at the camera.  Real coated optics read almost
    # black head-on with one hard specular pip, so the lens is modelled as a
    # dark dielectric with a thin clear coat instead of a window.
    M['glass'] = surf('M_Glass', (0.006, 0.008, 0.011), rough=0.26, metal=0.0,
                      spec=0.14, trans=0.0, coat=0.0)

    # optic body: anodised, slightly bluer than the receiver
    M['optic'] = surf('M_Optic', (0.020, 0.021, 0.024), rough=0.33, metal=1.0,
                      bump=0.10, bump_scale=2800.0, rough_var=0.06, rough_scale=64.0,
                      edge_wear=0.50, edge_col=(0.20, 0.20, 0.21))

    # SECOND GREY - a real finding, not a tweak.
    # The sheet does NOT use one grey. Measured with work/tonal.py:
    #   receiver side plate  x296-320 z-34..-20  -> 123.4
    #   handguard flank      x150-220 z0..20     -> 89.2
    #   stock cheek riser    x560-600 z0..20     -> 76.2
    # I had plate + handguard + cheek all on M_Gray; the ortho tonal report
    # showed the plate at ratio 1.02 (correct) while handguard and cheek both
    # read 1.35 (too bright). The handguard and cheek therefore get a darker
    # anodising of the same family, which also leaves the receiver plate as
    # the brightest grey - exactly the hierarchy the sheet shows.
    # MEASURED against the sheet: the handguard shell is the LIGHTEST grey on
    # the gun (sRGB ~142) - brighter even than the receiver's two-tone plate
    # (~123). The old value rendered at 100, which made the whole handguard
    # read as one dark mass and erased the three-band structure the sheet has.
    M['gray2'] = surf('M_Gray2', (0.118, 0.120, 0.1165), rough=0.62, metal=1.0,
                      bump=0.16, bump_scale=2600.0, rough_var=0.09, rough_scale=48.0,
                      edge_wear=0.40, edge_col=(0.22, 0.22, 0.215),
                      tint=(0.086, 0.088, 0.085), tint_scale=26.0, tint_strength=0.45)

    # mid-dark: the rib ladder sits BETWEEN the black channel and the bright
    # shell (sheet: ladder crests ~50 inside a ~30 channel). Using the shell
    # grey for the ribs made them render brighter than the shell itself.
    M['gray3'] = surf('M_Gray3', (0.0205, 0.0210, 0.0205), rough=0.55, metal=1.0,
                      bump=0.14, bump_scale=2800.0, rough_var=0.08, rough_scale=60.0,
                      edge_wear=0.35, edge_col=(0.075, 0.075, 0.074))

    # lower handguard shroud: darker than the receiver because its faces aim
    # down into the fill light. Measured target ~30 grey vs the receiver's ~47.
    M['shroud'] = surf('M_Shroud', (0.0042, 0.0043, 0.0045), rough=0.52, metal=1.0,
                       bump=0.18, bump_scale=2400.0, rough_var=0.07, rough_scale=64.0,
                       edge_wear=0.30, edge_col=(0.048, 0.048, 0.047))

    # hard black liner inside the handguard (kills bounce light)
    M['dark'] = surf('M_Dark', (0.006, 0.006, 0.0065), rough=0.88, metal=0.0, spec=0.08)
    return M
