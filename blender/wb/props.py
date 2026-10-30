# ---------------------------------------------------------------------------
#  PROPS: ancient, modern, war, sci-fi.  Every prop = real-world size in metres,
#  sits on the floor at the origin, uses procedural materials (Wear slider = damage).
# ---------------------------------------------------------------------------

def prop_greek_column(c, w, sd, det):
    bm = bmesh.new()
    seg = 24 if det < 2 else 40
    # fluted shaft: radius wobbles around the circle
    rings, H, R = [], 3.2, 0.26
    nz = 18 if det < 3 else 36
    shaft = []
    for k in range(nz + 1):
        z = 0.32 + H * k / nz
        taper = 1 - 0.12 * (k / nz)
        ring = []
        for i in range(seg * 2):
            a = 2 * math.pi * i / (seg * 2)
            r = R * taper * (1 - 0.035 * (0.5 + 0.5 * math.cos(a * 20)))
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        shaft.append(ring)
    for k in range(nz):
        for i in range(seg * 2):
            j = (i + 1) % (seg * 2)
            bm.faces.new((shaft[k][i], shaft[k][j], shaft[k + 1][j], shaft[k + 1][i]))
    bm_box(bm, 0, 0, 0.08, 0.78, 0.78, 0.16)                       # plinth
    bm_lathe(bm, [(0.36, 0.16), (0.38, 0.2), (0.33, 0.26), (0.3, 0.32)], seg)   # base torus
    bm_lathe(bm, [(R * 0.88, 0.32 + H), (0.36, 0.32 + H + 0.12), (0.4, 0.32 + H + 0.18)], seg)   # echinus
    bm_box(bm, 0, 0, 0.32 + H + 0.26, 0.86, 0.86, 0.16)             # abacus
    ob = obj_from_bm('Greek column', bm, c, mat_lib('marble', w, seed=sd), smooth=False)
    add_bevel(ob, 0.01, 2)
    if w > 0.5:   # broken top
        for v in ob.data.vertices:
            if v.co.z > 2.9:
                v.co.z -= (w - 0.5) * 2.2 * (0.5 + 0.5 * math.sin(v.co.x * 9 + v.co.y * 7))
    return [ob]


def prop_amphora(c, w, sd, det):
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.08, 0.0), (0.1, 0.03), (0.07, 0.08), (0.16, 0.2), (0.24, 0.38), (0.25, 0.48), (0.2, 0.6),
            (0.09, 0.72), (0.065, 0.8), (0.07, 0.86), (0.09, 0.88), (0.06, 0.9)]
    bm_lathe(bm, prof, 48 if det > 1 else 28)
    for side in (-1, 1):   # handles
        pts = [Vector((side * (0.06 + 0.13 * math.sin(math.pi * t)), 0, 0.84 - 0.26 * t)) for t in [i / 12 for i in range(13)]]
        bm_tube(bm, pts, 0.018, 10)
    ob = obj_from_bm('Amphora', bm, c, mat_lib('terracotta', w, seed=sd), smooth=True)
    add_subsurf(ob, 1)
    # painted band
    ob2 = obj_from_bm('Amphora band', _band(0.245, 0.43, 0.47), c, mat_lib('painted', 0.0, (0.03, 0.02, 0.02), sd), smooth=True)
    return [ob, ob2]


def _band(r, z0, z1):
    bm = bmesh.new()
    bm_lathe(bm, [(r, z0), (r + 0.004, (z0 + z1) / 2), (r, z1)], 48)
    return bm


def prop_treasure_chest(c, w, sd, det):
    W, D, H = 0.9, 0.55, 0.45
    rr = random.Random(sd)
    bm = bmesh.new(); bm_box(bm, 0, 0, H / 2, W, D, H)
    body = obj_from_bm('Chest body', bm, c, mat_lib('wood', w, seed=sd)); add_bevel(body, 0.012, 2)
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=D / 2, radius2=D / 2, depth=W)
    transform_verts(res['verts'], rot=(0, math.pi / 2, 0))
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
    bm_box(bm, 0, -D / 2 - 0.01, -0.02, 0.1, 0.03, 0.12)               # lock plate
    for x in (-W * 0.36, W * 0.36):                                     # iron straps over the lid
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=D / 2 + 0.008, radius2=D / 2 + 0.008, depth=0.05)
        transform_verts(r['verts'], rot=(0, math.pi / 2, 0), loc=(x, 0, 0))
    for v in bm.verts:
        if v.co.z < -0.0001 and abs(v.co.y) < D / 2 - 0.02 and v.co.z < -0.05: v.co.z = -0.05
    transform_verts(bm.verts, loc=(0, -D / 2, 0))                       # hinge at the back edge
    lid = obj_from_bm('Chest lid', bm, c, mat_lib('wood', w, seed=sd + 1)); add_bevel(lid, 0.008, 2)
    lid.location = (0, D / 2, H)
    lid.rotation_euler.x = -math.radians(42) if det >= 2 else 0.0
    bm = bmesh.new()
    for x in (-W * 0.36, W * 0.36):
        bm_box(bm, x, 0, H / 2, 0.05, D + 0.012, H + 0.004)
    bm_box(bm, 0, -D / 2 - 0.01, H * 0.85, 0.1, 0.03, 0.14)
    bands = obj_from_bm('Chest iron', bm, c, mat_lib('steel', min(1, w + 0.3), seed=sd)); add_bevel(bands, 0.004, 1)
    bm = bmesh.new()
    n = 30 + det * 20
    for i in range(n):
        x, y = rr.uniform(-W * 0.42, W * 0.42), rr.uniform(-D * 0.4, D * 0.4)
        hgt = 0.06 * math.exp(-((x / (W * 0.3)) ** 2 + (y / (D * 0.3)) ** 2))
        v = bm_cyl(bm, 0, 0, -0.003, 0.003, 0.028, seg=16)
        transform_verts(v, rot=(rr.uniform(-.5, .5), rr.uniform(-.5, .5), 0), loc=(x, y, H - 0.01 + hgt + rr.uniform(0, 0.02)))
    for i in range(8 if det >= 2 else 0):     # a few coins spilled on the floor
        x, y = rr.uniform(-W * 0.6, W * 0.6), rr.uniform(-D * 1.2, -D * 0.6)
        v = bm_cyl(bm, 0, 0, -0.003, 0.003, 0.028, seg=16)
        transform_verts(v, rot=(rr.uniform(-.2, .2), rr.uniform(-.2, .2), 0), loc=(x, y, 0.004))
    coins = obj_from_bm('Gold coins', bm, c, mat_lib('gold', 0.05, seed=sd))
    return [body, lid, bands, coins]


def prop_torch(c, w, sd, det):
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0, 0.62, 0.022, 0.03, 12)
    handle = obj_from_bm('Torch handle', bm, c, mat_lib('darkwood', w, seed=sd)); add_subsurf(handle, 1)
    bm = bmesh.new(); bm_lathe(bm, [(0.02, 0.52), (0.05, 0.6), (0.055, 0.7), (0.045, 0.72)], 16)
    wrap = obj_from_bm('Torch wrap', bm, c, mat_lib('burlap', w, seed=sd), smooth=True)
    bm = bmesh.new(); bm_lathe(bm, [(0.0, 0.7), (0.05, 0.74), (0.045, 0.82), (0.025, 0.9), (0.0, 0.98)], 16)
    flame = obj_from_bm('Torch flame', bm, c, mat_lib('emissive', 0, (1.0, 0.45, 0.08), sd), smooth=True)
    add_subsurf(flame, 2)
    d = bpy.data.lights.new('Torch light', 'POINT'); d.energy = 60; d.color = (1, 0.55, 0.2); d.shadow_soft_size = 0.05
    lt = link(bpy.data.objects.new('Torch light', d), c); lt.location = (0, 0, 0.85)
    for o in (handle, wrap, flame, lt):
        o.rotation_euler.x = math.radians(18)
    return [handle, wrap, flame, lt]


def prop_round_shield(c, w, sd, det):
    bm = bmesh.new()
    bm_lathe(bm, [(0.0, 0.06), (0.15, 0.058), (0.36, 0.045), (0.42, 0.03), (0.44, 0.0), (0.0, 0.0)], 64)
    shield = obj_from_bm('Shield', bm, c, mat_lib('painted', w, (0.45, 0.06, 0.04), sd), smooth=True)
    bm = bmesh.new(); bm_torus(bm, 0, 0, 0.03, 0.44, 0.022, 64, 10)
    rim = obj_from_bm('Shield rim', bm, c, mat_lib('bronze', w, seed=sd), smooth=True)
    bm = bmesh.new(); bm_sphere(bm, 0, 0, 0.06, 0.09, 3, 0.55)
    boss = obj_from_bm('Shield boss', bm, c, mat_lib('bronze', w, seed=sd), smooth=True)
    for o in (shield, rim, boss):
        o.rotation_euler = (math.radians(80), 0, 0); o.location = (0, 0, 0.46)
    return [shield, rim, boss]


def prop_sword(c, w, sd, det):
    bm = bmesh.new()
    L_ = 0.78
    pts = [(-0.028, 0), (0.028, 0), (0.024, L_ * 0.8), (0.0, L_), (-0.024, L_ * 0.8)]
    top = [bm.verts.new((x, 0.006, z)) for x, z in pts]; bot = [bm.verts.new((x, -0.006, z)) for x, z in pts]
    bm.faces.new(top); bm.faces.new(list(reversed(bot)))
    for i in range(len(pts)):
        j = (i + 1) % len(pts); bm.faces.new((top[i], top[j], bot[j], bot[i]))
    for v in bm.verts:
        if abs(v.co.x) > 0.02 and v.co.z < L_ * 0.8: v.co.y *= 0.2           # sharpened edges
    blade = obj_from_bm('Sword blade', bm, c, mat_lib('steel', w * 0.7, seed=sd))
    bm = bmesh.new(); bm_box(bm, 0, 0, -0.015, 0.22, 0.04, 0.03)
    guard = obj_from_bm('Sword guard', bm, c, mat_lib('bronze', w, seed=sd)); add_bevel(guard, 0.008, 2)
    bm = bmesh.new(); bm_cyl(bm, 0, 0, -0.2, -0.03, 0.018, 0.016, 12)
    grip = obj_from_bm('Sword grip', bm, c, mat_lib('leather', w, seed=sd)); add_subsurf(grip, 1)
    bm = bmesh.new(); bm_sphere(bm, 0, 0, -0.22, 0.03, 2)
    pommel = obj_from_bm('Sword pommel', bm, c, mat_lib('bronze', w, seed=sd), smooth=True)
    parts = [blade, guard, grip, pommel]
    for o in parts:
        o.location.z += 0.24
        o.rotation_euler.y = math.radians(-14)
    return parts


# ----- MODERN ------------------------------------------------------------------
def prop_chair(c, w, sd, det):
    bm = bmesh.new()
    for x in (-0.2, 0.2):
        for y in (-0.2, 0.2):
            bm_cyl(bm, x, y, 0, 0.45, 0.013, seg=12)
    for x in (-0.2, 0.2):
        bm_cyl(bm, x, 0.2, 0.45, 0.88, 0.013, seg=12)
    legs = obj_from_bm('Chair frame', bm, c, mat_lib('steel', w * 0.5, seed=sd), smooth=True)
    bm = bmesh.new(); bm_box(bm, 0, 0, 0.47, 0.46, 0.44, 0.035)
    seat = obj_from_bm('Chair seat', bm, c, mat_lib('wood', w, (0.55, 0.36, 0.2), sd)); add_bevel(seat, 0.012, 3)
    bm = bmesh.new(); v = bm_box(bm, 0, 0, 0, 0.46, 0.03, 0.26)
    transform_verts(v, rot=(math.radians(-8), 0, 0), loc=(0, 0.21, 0.74))
    back = obj_from_bm('Chair back', bm, c, mat_lib('wood', w, (0.55, 0.36, 0.2), sd)); add_bevel(back, 0.012, 3)
    return [legs, seat, back]


def prop_table(c, w, sd, det):
    bm = bmesh.new(); bm_box(bm, 0, 0, 0.74, 1.4, 0.8, 0.04)
    top = obj_from_bm('Table top', bm, c, mat_lib('wood', w, (0.5, 0.3, 0.15), sd)); add_bevel(top, 0.01, 3)
    bm = bmesh.new()
    for x in (-0.62, 0.62):
        for y in (-0.33, 0.33):
            bm_box(bm, x, y, 0.36, 0.05, 0.05, 0.72)
    legs = obj_from_bm('Table legs', bm, c, mat_lib('panel', w, (0.05, 0.05, 0.05), sd)); add_bevel(legs, 0.008, 2)
    return [top, legs]


def prop_desk_lamp(c, w, sd, det):
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0, 0.03, 0.11, 0.1, 32)
    base = obj_from_bm('Lamp base', bm, c, mat_lib('panel', w, (0.9, 0.55, 0.05), sd)); add_bevel(base, 0.006, 2)
    bm = bmesh.new()
    elbow = Vector((-0.11, 0, 0.33)); head = Vector((0.15, 0, 0.5))
    bm_tube(bm, [Vector((0, 0, 0.03)), elbow], 0.01, 10); bm_tube(bm, [elbow, head], 0.01, 10)
    bm_sphere(bm, elbow.x, elbow.y, elbow.z, 0.02, 2); bm_sphere(bm, 0, 0, 0.035, 0.022, 2)
    arm = obj_from_bm('Lamp arm', bm, c, mat_lib('steel', w, seed=sd), smooth=True)
    bm = bmesh.new(); v = bm_lathe(bm, [(0.025, 0.0), (0.04, 0.03), (0.09, 0.12), (0.085, 0.13)], 32)
    transform_verts(v, rot=(0, math.radians(130), 0), loc=(0.16, 0, 0.5))
    shade = obj_from_bm('Lamp shade', bm, c, mat_lib('panel', w, (0.9, 0.55, 0.05), sd), smooth=True)
    sh = shade.modifiers.new('Thickness', 'SOLIDIFY'); sh.thickness = 0.004
    bm = bmesh.new(); bm_sphere(bm, 0.2, 0, 0.45, 0.025, 2)
    bulb = obj_from_bm('Lamp bulb', bm, c, mat_lib('emissive', 0, (1, 0.85, 0.6), sd), smooth=True)
    d = bpy.data.lights.new('Lamp light', 'SPOT'); d.energy = 40; d.spot_size = math.radians(70); d.color = (1, 0.85, 0.65)
    lt = link(bpy.data.objects.new('Lamp light', d), c); lt.location = (0.2, 0, 0.44); lt.rotation_euler = (0, math.radians(40), 0)
    return [base, arm, shade, bulb, lt]


def prop_street_lamp(c, w, sd, det):
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0, 0.4, 0.14, 0.11, 24); bm_cyl(bm, 0, 0, 0.4, 4.2, 0.07, 0.05, 20)
    pole = obj_from_bm('Lamp post', bm, c, mat_lib('painted', w, (0.04, 0.05, 0.06), sd), smooth=True)
    bm = bmesh.new()
    pts = [Vector((0, 0, 4.0))] + [Vector((math.sin(t) * 0.55, 0, 4.2 + math.cos(t) * 0.3 - 0.3 + 0.2)) for t in [i / 10 * math.pi / 2 for i in range(11)]]
    bm_tube(bm, pts, 0.04, 12)
    arm = obj_from_bm('Lamp arm', bm, c, mat_lib('painted', w, (0.04, 0.05, 0.06), sd), smooth=True)
    bm = bmesh.new(); bm_lathe(bm, [(0.02, 0.0), (0.22, -0.08), (0.24, -0.14), (0.0, -0.14)], 32, 0.55, 0, 4.2)
    head = obj_from_bm('Lamp head', bm, c, mat_lib('painted', w, (0.04, 0.05, 0.06), sd), smooth=True)
    bm = bmesh.new(); bm_cyl(bm, 0.55, 0, 4.04, 4.07, 0.2, seg=32)
    glow = obj_from_bm('Lamp glow', bm, c, mat_lib('emissive', 0, (1, 0.8, 0.5), sd))
    d = bpy.data.lights.new('Street light', 'SPOT'); d.energy = 600; d.spot_size = math.radians(110); d.color = (1, 0.8, 0.55)
    lt = link(bpy.data.objects.new('Street light', d), c); lt.location = (0.55, 0, 4.0)
    return [pole, arm, head, glow, lt]


def prop_laptop(c, w, sd, det):
    bm = bmesh.new(); bm_box(bm, 0, 0, 0.009, 0.34, 0.24, 0.018)
    base = obj_from_bm('Laptop base', bm, c, mat_lib('steel', w * 0.3, seed=sd)); add_bevel(base, 0.006, 3)
    bm = bmesh.new()
    for i in range(12):
        for j in range(4):
            bm_box(bm, -0.135 + i * 0.0245, -0.02 + j * 0.026 - 0.03, 0.019, 0.02, 0.02, 0.002)
    keys = obj_from_bm('Laptop keys', bm, c, mat_lib('rubber', 0, seed=sd))
    bm = bmesh.new(); v = bm_box(bm, 0, 0, 0.115, 0.34, 0.008, 0.23)
    transform_verts(v, rot=(math.radians(-15), 0, 0), loc=(0, 0.125, 0.012))
    lid = obj_from_bm('Laptop lid', bm, c, mat_lib('steel', w * 0.3, seed=sd)); add_bevel(lid, 0.005, 3)
    bm = bmesh.new(); v = bm_box(bm, 0, -0.0045, 0.12, 0.31, 0.001, 0.19)
    transform_verts(v, rot=(math.radians(-15), 0, 0), loc=(0, 0.125, 0.012))
    scr = obj_from_bm('Laptop screen', bm, c, mat_lib('emissive', 0, (0.15, 0.55, 1.0), sd))
    scr.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 3
    return [base, keys, lid, scr]


def prop_mug(c, w, sd, det):
    bm = bmesh.new(); bm_lathe(bm, [(0.0, 0.0), (0.04, 0.0), (0.045, 0.005), (0.045, 0.1), (0.041, 0.1), (0.041, 0.008), (0.0, 0.008)], 48)
    mug = obj_from_bm('Mug', bm, c, mat_lib('plastic', w, (0.95, 0.4, 0.1), sd), smooth=True)
    bm = bmesh.new(); bm_torus(bm, 0.06, 0, 0.055, 0.028, 0.008, 24, 8, 'Y')
    handle = obj_from_bm('Mug handle', bm, c, mat_lib('plastic', w, (0.95, 0.4, 0.1), sd), smooth=True)
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0.08, 0.085, 0.04, seg=32)
    coffee = obj_from_bm('Coffee', bm, c, mat_lib('plastic', 0, (0.08, 0.035, 0.015), sd))
    return [mug, handle, coffee]


# ----- WAR ---------------------------------------------------------------------
def prop_sandbags(c, w, sd, det):
    rr = random.Random(sd)
    bm = bmesh.new()
    for row in range(3):
        n = 5 - (row % 2)
        for i in range(n):
            x = (i - (n - 1) / 2) * 0.56 + rr.uniform(-0.02, 0.02)
            v = bm_box(bm, 0, 0, 0, 0.56, 0.32, 0.16)
            for vv in v:   # pinch the ends like a tied bag
                if abs(vv.co.x) > 0.2: vv.co.y *= 0.8; vv.co.z *= 0.75
            transform_verts(v, rot=(0, 0, rr.uniform(-0.07, 0.07)), loc=(x, rr.uniform(-0.02, 0.02), 0.08 + row * 0.145))
    ob = obj_from_bm('Sandbag wall', bm, c, mat_lib('burlap', w, seed=sd), smooth=True)
    add_subsurf(ob, 2)
    d = ob.modifiers.new('Lumps', 'DISPLACE')
    t = bpy.data.textures.new('Sandbag lumps', 'CLOUDS'); t.noise_scale = 0.12; d.texture = t; d.strength = 0.025
    return [ob]


def prop_oil_drum(c, w, sd, det):
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.285, 0.0), (0.29, 0.01), (0.29, 0.28), (0.297, 0.29), (0.29, 0.3), (0.29, 0.58), (0.297, 0.59),
            (0.29, 0.6), (0.29, 0.87), (0.285, 0.88), (0.27, 0.885), (0.0, 0.885)]
    bm_lathe(bm, prof, 48)
    drum = obj_from_bm('Oil drum', bm, c, mat_lib('painted', min(1, w + 0.15), (0.05, 0.18, 0.32), sd), smooth=True)
    bm = bmesh.new(); bm_cyl(bm, 0.15, 0.05, 0.885, 0.9, 0.03, seg=16)
    cap = obj_from_bm('Drum cap', bm, c, mat_lib('steel', w, seed=sd))
    return [drum, cap]


def prop_ammo_crate(c, w, sd, det):
    W, D, H = 0.75, 0.42, 0.36
    bm = bmesh.new(); bm_box(bm, 0, 0, H / 2, W, D, H)
    box = obj_from_bm('Ammo crate', bm, c, mat_lib('painted', w, (0.18, 0.2, 0.09), sd)); add_bevel(box, 0.01, 2)
    bm = bmesh.new()
    for x in (-W / 2 + 0.03, W / 2 - 0.03):
        bm_box(bm, x, 0, H / 2, 0.04, D + 0.02, H + 0.02)
    bm_box(bm, 0, 0, H + 0.005, W - 0.1, D * 0.98, 0.012)
    for x in (-0.2, 0.2):
        bm_box(bm, x, -D / 2 - 0.015, H * 0.75, 0.07, 0.02, 0.05)
    trim = obj_from_bm('Crate trim', bm, c, mat_lib('painted', min(1, w + 0.1), (0.14, 0.16, 0.07), sd)); add_bevel(trim, 0.006, 2)
    bm = bmesh.new()
    for side in (-1, 1):
        bm_torus(bm, side * (W / 2 + 0.03), 0, H * 0.6, 0.05, 0.008, 16, 6, 'X')
    handles = obj_from_bm('Crate handles', bm, c, mat_lib('steel', w, seed=sd), smooth=True)
    txt = bpy.data.curves.new('Crate stencil', 'FONT'); txt.body = '7.62 MM'; txt.size = 0.07; txt.align_x = 'CENTER'
    to = link(bpy.data.objects.new('Crate stencil', txt), c)
    to.location = (0, -D / 2 - 0.001, H * 0.35); to.rotation_euler = (math.radians(90), 0, 0)
    to.data.materials.append(mat_lib('painted', min(1, w + 0.2), (0.85, 0.8, 0.6), sd))
    return [box, trim, handles, to]


def prop_jerrycan(c, w, sd, det):
    bm = bmesh.new(); bm_box(bm, 0, 0, 0.235, 0.34, 0.165, 0.47)
    for v in bm.verts:
        if v.co.z > 0.4 and v.co.x < 0: v.co.z = 0.4 + (v.co.z - 0.4) * 0.3
    can = obj_from_bm('Jerrycan', bm, c, mat_lib('painted', w, (0.22, 0.24, 0.1), sd)); add_bevel(can, 0.025, 4)
    bm = bmesh.new()
    for y in (-0.083, 0.083):           # the X stamping
        for s in (-1, 1):
            v = bm_box(bm, 0, 0, 0, 0.42, 0.006, 0.02); transform_verts(v, rot=(0, s * math.radians(48), 0), loc=(0, y, 0.2))
    xs = obj_from_bm('Jerrycan X', bm, c, mat_lib('painted', w, (0.2, 0.22, 0.09), sd))
    bm = bmesh.new()
    for x in (-0.07, 0.0, 0.07):
        bm_box(bm, x, 0, 0.5, 0.025, 0.03, 0.06)
    bm_box(bm, 0, 0, 0.53, 0.18, 0.03, 0.02)
    bm_cyl(bm, 0.12, 0, 0.46, 0.53, 0.025, seg=16)
    handle = obj_from_bm('Jerrycan handles', bm, c, mat_lib('painted', w, (0.2, 0.22, 0.09), sd)); add_bevel(handle, 0.005, 2)
    return [can, xs, handle]


def prop_tank_trap(c, w, sd, det):
    bm = bmesh.new()
    for axis in range(3):            # three steel L-angles crossing at the centre
        for (a_, b_) in ((0.16, 0.025), (0.025, 0.16)):
            size = [0, 0, 0]; size[axis] = 1.7
            o = [(axis + 1) % 3, (axis + 2) % 3]
            size[o[0]], size[o[1]] = a_, b_
            off = [0, 0, 0]; off[o[0]] = a_ / 2 - 0.0125; off[o[1]] = b_ / 2 - 0.0125
            bm_box(bm, off[0], off[1], off[2], *size)
    transform_verts(bm.verts, rot=(math.radians(35.26), 0, math.radians(45)))
    zmin = min(v.co.z for v in bm.verts)
    transform_verts(bm.verts, loc=(0, 0, -zmin))
    ob = obj_from_bm('Czech hedgehog', bm, c, mat_lib('rust' if w > 0.6 else 'painted', w, (0.15, 0.16, 0.14), sd)); add_bevel(ob, 0.006, 1)
    ob.rotation_euler.z = math.radians(15)
    return [ob]


def prop_helmet(c, w, sd, det):
    bm = bmesh.new()
    prof = [(0.0, 0.2), (0.07, 0.195), (0.13, 0.17), (0.165, 0.12), (0.18, 0.06), (0.19, 0.015), (0.215, 0.0), (0.21, -0.006)]
    bm_lathe(bm, prof, 48)
    for v in bm.verts:
        v.co.y *= 1.15
    hel = obj_from_bm('Helmet', bm, c, mat_lib('painted', w, (0.2, 0.22, 0.12), sd), smooth=True)
    so = hel.modifiers.new('Thickness', 'SOLIDIFY'); so.thickness = 0.006
    add_subsurf(hel, 1)
    hel.location.z = 0.01
    return [hel]


# ----- SCI-FI ------------------------------------------------------------------
def prop_energy_core(c, w, sd, det):
    bm = bmesh.new(); bm_lathe(bm, [(0.0, 0.0), (0.32, 0.0), (0.34, 0.06), (0.26, 0.12), (0.2, 0.14), (0.0, 0.14)], 8)
    base = obj_from_bm('Core base', bm, c, mat_lib('panel', w, (0.12, 0.13, 0.15), sd)); add_bevel(base, 0.01, 2)
    bm = bmesh.new(); bm_lathe(bm, [(0.0, 1.06), (0.2, 1.06), (0.26, 1.0), (0.2, 0.94), (0.0, 0.94)], 8)
    cap = obj_from_bm('Core cap', bm, c, mat_lib('panel', w, (0.12, 0.13, 0.15), sd)); add_bevel(cap, 0.01, 2)
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0.14, 0.94, 0.13, seg=32)
    glass = obj_from_bm('Core glass', bm, c, mat_lib('glass', 0, (0.7, 0.95, 1.0), sd), smooth=True)
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0.16, 0.92, 0.05, seg=16)
    glow = obj_from_bm('Core plasma', bm, c, mat_lib('emissive', 0, (0.1, 0.85, 1.0), sd), smooth=True)
    bm = bmesh.new()
    for i in range(4):
        a = i * math.pi / 2
        bm_box(bm, math.cos(a) * 0.16, math.sin(a) * 0.16, 0.54, 0.03, 0.03, 0.8)
    for z in (0.3, 0.54, 0.78):
        bm_torus(bm, 0, 0, z, 0.15, 0.012, 32, 6)
    frame = obj_from_bm('Core frame', bm, c, mat_lib('steel', w, seed=sd), smooth=True)
    d = bpy.data.lights.new('Core light', 'POINT'); d.energy = 80; d.color = (0.2, 0.85, 1.0)
    lt = link(bpy.data.objects.new('Core light', d), c); lt.location = (0, 0, 0.55)
    return [base, cap, glass, glow, frame, lt]


def prop_cargo_crate(c, w, sd, det):
    S = 0.9
    bm = bmesh.new(); bm_box(bm, 0, 0, S / 2, S, S, S)
    box = obj_from_bm('Sci-fi crate', bm, c, mat_lib('panel', w, (0.85, 0.85, 0.82), sd)); add_bevel(box, 0.06, 3)
    bm = bmesh.new()
    for z in (0.06, S - 0.06):
        bm_box(bm, 0, 0, z, S + 0.02, S + 0.02, 0.08)
    for x in (-1, 1):
        for y in (-1, 1):
            bm_box(bm, x * S / 2, y * S / 2, S / 2, 0.1, 0.1, S + 0.02)
    trim = obj_from_bm('Crate frame', bm, c, mat_lib('panel', w, (0.1, 0.1, 0.11), sd)); add_bevel(trim, 0.012, 2)
    bm = bmesh.new(); bm_box(bm, 0, -S / 2 - 0.006, S * 0.55, S * 0.5, 0.01, 0.03); bm_box(bm, S * 0.3, -S / 2 - 0.006, S * 0.75, 0.06, 0.01, 0.06)
    strip = obj_from_bm('Crate light strip', bm, c, mat_lib('emissive', 0, (1.0, 0.45, 0.05), sd))
    return [box, trim, strip]


def prop_holo_pillar(c, w, sd, det):
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0, 0.12, 0.45, 0.4, 6)
    base = obj_from_bm('Holo base', bm, c, mat_lib('panel', w, (0.08, 0.09, 0.1), sd)); add_bevel(base, 0.01, 2)
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0.12, 0.14, 0.3, seg=6)
    ring = obj_from_bm('Holo emitter', bm, c, mat_lib('emissive', 0, (0.2, 1.0, 0.6), sd))
    bm = bmesh.new()
    v = bm_sphere(bm, 0, 0, 0.75, 0.28, 1)
    holo = obj_from_bm('Hologram', bm, c, mat_lib('emissive', 0, (0.2, 1.0, 0.6), sd))
    wf = holo.modifiers.new('Wire', 'WIREFRAME'); wf.thickness = 0.006
    holo.rotation_euler = (0.3, 0.2, 0.5)
    return [base, ring, holo]


def prop_drone(c, w, sd, det):
    bm = bmesh.new(); bm_sphere(bm, 0, 0, 0, 0.14, 3, 0.45)
    body = obj_from_bm('Drone body', bm, c, mat_lib('panel', w, (0.9, 0.9, 0.92), sd), smooth=True)
    bm = bmesh.new(); objs = [body]
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        v = bm_box(bm, 0, 0, 0, 0.3, 0.025, 0.02); transform_verts(v, rot=(0, 0, a), loc=(math.cos(a) * 0.15, math.sin(a) * 0.15, 0.01))
        bm_torus(bm, math.cos(a) * 0.3, math.sin(a) * 0.3, 0.03, 0.11, 0.008, 32, 6)
        bm_cyl(bm, math.cos(a) * 0.3, math.sin(a) * 0.3, 0.0, 0.05, 0.02, seg=12)
    arms = obj_from_bm('Drone arms', bm, c, mat_lib('panel', w, (0.1, 0.1, 0.11), sd), smooth=True)
    bm = bmesh.new(); bm_sphere(bm, 0, -0.12, -0.02, 0.035, 2)
    eye = obj_from_bm('Drone camera', bm, c, mat_lib('emissive', 0, (1.0, 0.15, 0.1), sd), smooth=True)
    for o in (body, arms, eye):
        o.location.z = 0.6
    return [body, arms, eye]


PROPS = {
    'ANCIENT': [('COLUMN', 'Greek column', prop_greek_column), ('AMPHORA', 'Amphora', prop_amphora),
                ('CHEST', 'Treasure chest', prop_treasure_chest), ('TORCH', 'Torch', prop_torch),
                ('SHIELD', 'Round shield', prop_round_shield), ('SWORD', 'Sword', prop_sword)],
    'MODERN': [('CHAIR', 'Chair', prop_chair), ('TABLE', 'Table', prop_table), ('DESKLAMP', 'Desk lamp', prop_desk_lamp),
               ('STREETLAMP', 'Street lamp', prop_street_lamp), ('LAPTOP', 'Laptop', prop_laptop), ('MUG', 'Coffee mug', prop_mug)],
    'WAR': [('SANDBAGS', 'Sandbag wall', prop_sandbags), ('DRUM', 'Oil drum', prop_oil_drum), ('AMMO', 'Ammo crate', prop_ammo_crate),
            ('JERRYCAN', 'Jerrycan', prop_jerrycan), ('HEDGEHOG', 'Czech hedgehog', prop_tank_trap), ('HELMET', 'Helmet', prop_helmet)],
    'SCIFI': [('CORE', 'Energy core', prop_energy_core), ('CARGO', 'Cargo crate', prop_cargo_crate),
              ('HOLO', 'Holo pillar', prop_holo_pillar), ('DRONE', 'Drone', prop_drone)],
}


def build_stage(coll, centre, size, warm=True):
    """Curved studio backdrop + 3 area lights."""
    R = max(size * 3, 3)
    bm = bmesh.new()
    prof = []
    for i in range(13):
        t = i / 12
        if t < 0.5: prof.append((-R + t * 2 * R, 0.0))
        else:
            a = (t - 0.5) * 2 * math.pi / 2
            prof.append((R * 0 + math.sin(a) * R * 0.5, (1 - math.cos(a)) * R * 0.5))
    rows = []
    for x in (-R * 1.5, R * 1.5):
        rows.append([bm.verts.new((x, y, z)) for y, z in prof])
    for k in range(len(prof) - 1):
        bm.faces.new((rows[0][k], rows[1][k], rows[1][k + 1], rows[0][k + 1]))
    bd = obj_from_bm('Studio backdrop', bm, coll, smooth=True)
    bd.location = (centre.x, centre.y + R * 0.3, 0)
    add_subsurf(bd, 2)
    m, N, L, P, out = new_mat('ZICA Studio floor')
    P.inputs['Base Color'].default_value = (0.08, 0.085, 0.1, 1) if warm else (0.6, 0.6, 0.62, 1)
    P.inputs['Roughness'].default_value = 0.55
    bd.data.materials.append(m)
    h = max(size, 0.4)
    area_light(coll, 'Key light', centre + Vector((-h * 1.6, -h * 1.8, h * 2.0)), centre, 90 * h * h, h * 1.2, (1.0, 0.9, 0.78))
    area_light(coll, 'Fill light', centre + Vector((h * 2.0, -h * 1.2, h * 0.8)), centre, 25 * h * h, h * 1.5, (0.75, 0.85, 1.0))
    area_light(coll, 'Rim light', centre + Vector((h * 0.6, h * 1.8, h * 1.6)), centre, 110 * h * h, h * 0.8, (1, 1, 1))
    set_world((0.03, 0.035, 0.05), (0.02, 0.02, 0.025), 1.0)


def build_props(cat, which, wear, seed, detail, scale=1.0, shelf=False):
    """which: prop key, or None with shelf=True = the whole category lined up with labels."""
    get_coll(WORLD_COLL, clear=True); get_coll(STAGE_COLL, clear=True)
    c = get_coll(PROP_COLL, clear=True)
    stage = get_coll(STAGE_COLL)
    purge_orphans(); _MAT_CACHE.clear()
    random.seed(seed)
    items = PROPS[cat] if shelf else [p for p in PROPS[cat] if p[0] == which]
    all_objs, x = [], 0.0
    sizes = []
    for key, label, fn in items:
        objs = fn(c, wear, seed, detail)
        bpy.context.view_layer.update()
        xs = [(ob.matrix_world @ Vector(cn)).x for ob in objs if ob.type in ('MESH', 'FONT') for cn in ob.bound_box]
        wdt = (max(xs) - min(xs)) if xs else 0.5
        if shelf:   # showcase: every prop scaled to a similar height so small items stay readable
            zs = [(ob.matrix_world @ Vector(cn)).z for ob in objs if ob.type == 'MESH' for cn in ob.bound_box]
            hgt = max(max(zs) - min(zs) if zs else 1.0, max(wdt, 0.1) * 0.85)
            k = 1.0 / hgt
            for ob in objs:
                if ob.parent is None:
                    ob.scale = ob.scale * k; ob.location = ob.location * k
                    if ob.type == 'LIGHT': ob.data.energy *= k * k
            wdt *= k
            for ob in objs:
                if ob.parent is None: ob.location.x += x + wdt / 2
            t = bpy.data.curves.new('Label ' + label, 'FONT'); t.body = label; t.size = 0.09; t.align_x = 'CENTER'
            to = link(bpy.data.objects.new('Label ' + label, t), stage)
            to.location = (x + wdt / 2, -0.5, 0.01); to.rotation_euler = (math.radians(75), 0, 0)
            to.data.materials.append(flat_mat('ZICA Label', (0.9, 0.7, 0.3), emit=1.5))
            x += wdt + 0.35
        for ob in objs:
            if ob.parent is None and not shelf:
                ob.scale = (ob.scale.x * scale, ob.scale.y * scale, ob.scale.z * scale)
                ob.location = ob.location * scale
        all_objs += objs
    if shelf:
        for ob in all_objs:
            if ob.parent is None: ob.location.x -= x / 2
        for ob in stage.objects:
            if ob.name.startswith('Label'): ob.location.x -= x / 2
    meshes = [o for o in all_objs if o.type in ('MESH', 'FONT')]
    cam, centre, size = frame_objects_camera(stage, meshes, stage, lens=50 if not shelf else 40,
                                             elev_deg=14 if shelf else 18, az_deg=0 if shelf else -32, margin=1.3 if not shelf else 1.12)
    build_stage(stage, centre, size)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 1
    return all_objs
