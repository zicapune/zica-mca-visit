# ---------------------------------------------------------------------------
#  WORLDS: Neon City, Old Town, Island Lagoon, Desert Canyon, Snowy Peaks, Forest Valley
# ---------------------------------------------------------------------------

def terrain_material(name, pal, snow_line=None, slope_rock=0.75, water_z=0.0):
    """Height + slope blended ground: pal = dict(low, mid, high, rock, snow)."""
    m, N, L, P, out = new_mat(name)
    geo = N.new('ShaderNodeNewGeometry')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Position'], sep.inputs['Vector'])
    nsep = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Normal'], nsep.inputs['Vector'])
    co = obj_coords(N)
    nz = noise_tex(N, L, 0.08, 6, 0.6, co)
    # height bands with noisy edges
    hz = math_node(N, L, 'ADD', sep.outputs['Z'], math_node(N, L, 'MULTIPLY', nz.outputs['Fac'], 4.0))
    hr = math_node(N, L, 'SUBTRACT', hz, water_z)
    band = N.new('ShaderNodeMapRange'); band.inputs['From Min'].default_value = 0.0; band.inputs['From Max'].default_value = pal.get('top', 40.0)
    L.new(hr, band.inputs['Value'])
    r = ramp(N, L, band.outputs['Result'], [(0.0, pal['beach']), (0.04, pal['low']), (0.45, pal['mid']), (0.8, pal['high'])])
    col = r.outputs['Color']
    # rock on steep slopes
    slope = ramp(N, L, nsep.outputs['Z'], [(slope_rock - 0.08, (1, 1, 1)), (slope_rock + 0.05, (0, 0, 0))])
    fine = noise_tex(N, L, 1.5, 8, 0.65, co)
    rk = ramp(N, L, fine.outputs['Fac'], [(0.3, tuple(c * 0.6 for c in pal['rock'])), (0.75, pal['rock'])])
    col = mix_rgb(N, L, slope.outputs['Color'], col, rk.outputs['Color'])
    if snow_line is not None:
        sn = N.new('ShaderNodeMapRange'); sn.inputs['From Min'].default_value = snow_line - 3; sn.inputs['From Max'].default_value = snow_line + 3
        L.new(hz, sn.inputs['Value'])
        flat = ramp(N, L, nsep.outputs['Z'], [(0.55, (0, 0, 0)), (0.75, (1, 1, 1))])
        smask = math_node(N, L, 'MULTIPLY', sn.outputs['Result'], flat.outputs['Color'])
        col = mix_rgb(N, L, smask, col, (0.92, 0.94, 0.98, 1))
    L.new(col, P.inputs['Base Color'])
    P.inputs['Roughness'].default_value = 0.9
    L.new(bump(N, L, fine.outputs['Fac'], 0.4, 0.3), P.inputs['Normal'])
    return m


def water_material(deep=(0.01, 0.12, 0.16), clear=True):
    m, N, L, P, out = new_mat('ZICA Water')
    P.inputs['Base Color'].default_value = (*deep, 1)
    P.inputs['Roughness'].default_value = 0.04
    P.inputs['IOR'].default_value = 1.33
    if clear:
        P.inputs['Transmission Weight'].default_value = 0.9
    co = obj_coords(N)
    n = noise_tex(N, L, 0.6, 4, 0.5, co)
    L.new(bump(N, L, n.outputs['Fac'], 0.15, 0.4), P.inputs['Normal'])
    return m


def terrain_mesh(coll, size, res, hfunc, mat):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=res, y_segments=res, size=size / 2)
    for v in bm.verts:
        v.co.z = hfunc(v.co.x, v.co.y)
    ob = obj_from_bm('Terrain', bm, coll, mat, smooth=True)
    return ob


# ---- scatter assets (one mesh each, many linked copies) ---------------------------------
def asset_pine(coll, mat_leaf, mat_bark):
    bm = bmesh.new()
    bm_cyl(bm, 0, 0, 0, 1.2, 0.18, 0.12, 8)
    trunk = obj_from_bm('src Pine trunk', bm, coll, mat_bark)
    bm = bmesh.new()
    for i, (z, r) in enumerate(((1.0, 2.0), (2.6, 1.6), (4.0, 1.2), (5.2, 0.8))):
        bm_cyl(bm, 0, 0, z, z + 2.2, r, 0.05, 9)
    for v in bm.verts:
        v.co.x += noise.noise(v.co * 0.9) * 0.18; v.co.y += noise.noise(v.co * 1.1 + Vector((5, 5, 5))) * 0.18
    leaves = obj_from_bm('src Pine', bm, coll, mat_leaf)
    return _join(coll, 'src Pine tree', [trunk, leaves])


def asset_broadleaf(coll, mat_leaf, mat_bark):
    bm = bmesh.new(); bm_cyl(bm, 0, 0, 0, 2.4, 0.22, 0.14, 8)
    trunk = obj_from_bm('src Tree trunk', bm, coll, mat_bark)
    bm = bmesh.new()
    for (x, y, z, r) in ((0, 0, 3.4, 1.7), (0.9, 0.3, 3.0, 1.2), (-0.8, -0.4, 3.1, 1.25), (0.2, -0.8, 3.8, 1.1), (-0.2, 0.7, 4.0, 1.0)):
        v = bm_sphere(bm, x, y, z, r, 2)
    for v in bm.verts:
        v.co += v.normal * noise.noise(v.co * 1.3) * 0.35
    crown = obj_from_bm('src Tree crown', bm, coll, mat_leaf, smooth=True)
    return _join(coll, 'src Broadleaf tree', [trunk, crown])


def asset_palm(coll, mat_leaf, mat_bark):
    bm = bmesh.new()
    pts = [Vector((0.35 * (t ** 2) * 2.2, 0, t * 6.0)) for t in [i / 10 for i in range(11)]]
    for i in range(10):
        v = bm_cyl(bm, 0, 0, 0, (pts[i + 1] - pts[i]).length, 0.2 - 0.008 * i, 0.19 - 0.008 * i, 8)
        d = pts[i + 1] - pts[i]
        ang = math.atan2(d.x, d.z)
        transform_verts(v, rot=(0, ang, 0), loc=pts[i])
    trunk = obj_from_bm('src Palm trunk', bm, coll, mat_bark)
    top = pts[-1]
    bm = bmesh.new()
    for k in range(9):
        a = 2 * math.pi * k / 9
        prev = None
        for j in range(8):
            t = j / 7
            p = top + Vector((math.cos(a) * 3.2 * t, math.sin(a) * 3.2 * t, 0.6 * math.sin(t * math.pi) - 1.6 * t * t))
            wdt = 0.55 * math.sin(math.pi * min(0.98, t + 0.05))
            side = Vector((-math.sin(a), math.cos(a), 0)) * wdt
            v1, v2 = bm.verts.new(p - side), bm.verts.new(p + side)
            if prev: bm.faces.new((prev[0], prev[1], v2, v1))
            prev = (v1, v2)
    fronds = obj_from_bm('src Palm fronds', bm, coll, mat_leaf, smooth=True)
    return _join(coll, 'src Palm tree', [trunk, fronds])


def asset_cactus(coll, mat):
    bm = bmesh.new()
    bm_cyl(bm, 0, 0, 0, 3.0, 0.32, 0.3, 10); bm_sphere(bm, 0, 0, 3.0, 0.3, 2)
    for side, h in ((1, 1.4), (-1, 1.9)):
        v = bm_cyl(bm, 0, 0, 0, 0.7, 0.2, 0.2, 8); transform_verts(v, rot=(0, side * math.pi / 2, 0), loc=(side * 0.4, 0, h))
        bm_cyl(bm, side * 0.75, 0, h, h + 1.0, 0.2, 0.18, 8); bm_sphere(bm, side * 0.75, 0, h + 1.0, 0.18, 1)
    return obj_from_bm('src Cactus', bm, coll, mat, smooth=True)


def asset_rock(coll, mat, seed):
    bm = bmesh.new(); bm_sphere(bm, 0, 0, 0.3, 1.0, 2)
    for v in bm.verts:
        v.co += v.co.normalized() * noise.noise(v.co * 1.6 + Vector((seed, 0, 0))) * 0.45
        v.co.z *= 0.6
    return obj_from_bm('src Rock', bm, coll, mat)


def _join(coll, name, objs):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    mats = []
    for o in objs:
        tmp = bmesh.new(); tmp.from_mesh(o.data)
        mi = len(mats); mats.append(o.data.materials[0] if o.data.materials else None)
        for f in tmp.faces: f.material_index = mi
        tm = bpy.data.meshes.new('tmp'); tmp.to_mesh(tm); tmp.free()
        bm.from_mesh(tm); bpy.data.meshes.remove(tm)
        sm = o.data.polygons[0].use_smooth if o.data.polygons else False
    for o in objs:
        d = o.data; bpy.data.objects.remove(o, do_unlink=True); bpy.data.meshes.remove(d)
    bm.to_mesh(me); bm.free()
    for mt in mats: me.materials.append(mt)
    for p in me.polygons: p.use_smooth = True
    ob = link(bpy.data.objects.new(name, me), coll)
    ob.hide_render = True; ob.hide_viewport = True
    return ob


def scatter(coll, srcs, count, size, hfunc, rule, seed, scale=(0.7, 1.3)):
    rr = random.Random(seed)
    placed, tries = 0, 0
    while placed < count and tries < count * 12:
        tries += 1
        x, y = rr.uniform(-size / 2, size / 2), rr.uniform(-size / 2, size / 2)
        z = hfunc(x, y)
        ok = rule(x, y, z, rr)
        if not ok: continue
        src = srcs[rr.randrange(len(srcs))] if isinstance(ok, bool) else ok
        instance(src, src.name[4:], coll, (x, y, z - 0.15), rr.uniform(0, 6.283), rr.uniform(*scale))
        placed += 1
    return placed


def slope_at(hfunc, x, y, e=1.0):
    dx = hfunc(x + e, y) - hfunc(x - e, y); dy = hfunc(x, y + e) - hfunc(x, y - e)
    return math.hypot(dx, dy) / (2 * e)


# ---- biomes ---------------------------------------------------------------------------
BIOMES = {
    'ISLAND': dict(sky=((0.22, 0.42, 0.85), (1.0, 0.72, 0.45)), sun=(14, 250, 4.5, (1.0, 0.75, 0.5)), fog=(1.0, 0.8, 0.65),
                   pal=dict(beach=(0.86, 0.74, 0.5), low=(0.16, 0.36, 0.08), mid=(0.12, 0.3, 0.07), high=(0.4, 0.38, 0.3), rock=(0.38, 0.34, 0.28), top=40)),
    'DESERT': dict(sky=((0.3, 0.55, 0.92), (0.95, 0.82, 0.62)), sun=(38, 120, 5.5, (1.0, 0.9, 0.75)), fog=(1.0, 0.85, 0.65),
                   pal=dict(beach=(0.78, 0.56, 0.32), low=(0.8, 0.58, 0.34), mid=(0.72, 0.42, 0.22), high=(0.62, 0.3, 0.16), rock=(0.55, 0.27, 0.14), top=45)),
    'SNOW': dict(sky=((0.25, 0.45, 0.82), (0.82, 0.88, 0.96)), sun=(22, 200, 4.0, (1.0, 0.93, 0.85)), fog=(0.85, 0.9, 1.0),
                 pal=dict(beach=(0.4, 0.38, 0.33), low=(0.17, 0.27, 0.12), mid=(0.3, 0.3, 0.27), high=(0.45, 0.45, 0.45), rock=(0.33, 0.33, 0.35), top=70)),
    'FOREST': dict(sky=((0.32, 0.5, 0.8), (0.95, 0.9, 0.78)), sun=(28, 70, 4.0, (1.0, 0.9, 0.75)), fog=(0.8, 0.88, 0.95),
                   pal=dict(beach=(0.38, 0.32, 0.2), low=(0.14, 0.3, 0.07), mid=(0.1, 0.24, 0.06), high=(0.25, 0.3, 0.12), rock=(0.35, 0.33, 0.3), top=30)),
}


def make_hfunc(kind, size, seed, water):
    so = seed * 13.37
    s = 1.0 / size
    if kind == 'ISLAND':
        def h(x, y):
            d = math.hypot(x, y) / (size * 0.45)
            isl = max(0.0, 1 - d ** 2.4)
            return (fbm(x * 3 * s, y * 3 * s, so, 4) * 9 + ridged(x * 1.6 * s, y * 1.6 * s, so, 3) * 16) * isl ** 1.3 - 5 + 6 * isl
    elif kind == 'DESERT':
        def sm(e0, e1, v):
            t = max(0.0, min(1.0, (v - e0) / (e1 - e0))); return t * t * (3 - 2 * t)
        def h(x, y):
            n = fbm(x * 1.3 * s, y * 1.3 * s, so + 5, 3) + fbm(x * 6 * s, y * 6 * s, so + 2, 2) * 0.04
            mesa = 22 * sm(0.06, 0.11, n) + 12 * sm(0.3, 0.34, n)          # flat-topped, terraced mesas
            dune = math.sin((x * 0.9 + y * 0.35) * 0.09 + fbm(x * 2 * s, y * 2 * s, so, 3) * 3) * 1.4 * (1 - sm(0.0, 0.08, n))
            return dune + mesa + fbm(x * 9 * s, y * 9 * s, so, 3) * 0.8 + 1
    elif kind == 'SNOW':
        def h(x, y):
            r = ridged(x * 1.7 * s, y * 1.7 * s, so, 4)
            valley = math.exp(-((x + y * 0.3) / (size * 0.2)) ** 2)
            return r * 26 + fbm(x * 4 * s, y * 4 * s, so, 4) * 4 - valley * 20 - 2
    else:   # FOREST
        def h(x, y):
            river = math.sin(y * 3.0 * s * math.pi / 2 + fbm(x * s, y * s, so) * 2) * size * 0.12
            rv = math.exp(-((x - river) / (size * 0.05)) ** 2)
            return fbm(x * 3 * s, y * 3 * s, so) * 12 + ridged(x * 1.5 * s, y * 1.5 * s, so) * 10 - rv * 9 + 2
    return h


def build_terrain_world(kind, s):
    """s: settings object with size, density, detail, seed, sun_height, fog, water."""
    scene = bpy.context.scene
    get_coll(PROP_COLL, clear=True); get_coll(STAGE_COLL, clear=True)
    c = get_coll(WORLD_COLL, clear=True)
    purge_orphans(); _MAT_CACHE.clear()
    B = BIOMES[kind]
    size = 260 * s.world_size
    res = (90, 160, 240)[s.detail - 1]
    water = s.water * 6 + (0 if kind != 'DESERT' else -30)
    h = make_hfunc(kind, size, s.seed, water)
    snow = 30 if kind == 'SNOW' else None
    terrain_mesh(c, size, res, h, terrain_material('ZICA Ground', B['pal'], snow, water_z=water))
    if kind != 'DESERT':
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size * 40)
        wo = obj_from_bm('Water', bm, c, water_material((0.01, 0.1, 0.13) if kind != 'SNOW' else (0.02, 0.07, 0.12)))
        wo.location.z = water
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size * 40)
        sb = obj_from_bm('Sea bed', bm, c, mat_lib('sand', 0.2, (0.36, 0.3, 0.2), s.seed))   # no hard edge where the terrain ends
        sb.location.z = water - 4.8
    else:
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size * 40)
        fl = obj_from_bm('Far sand', bm, c, mat_lib('sand', 0.2, seed=s.seed)); fl.location.z = -1
    src = get_coll('ZICA World')
    leaf = flat_mat('ZICA Leaves', (0.09, 0.22, 0.05), 0.7)
    pine_leaf = flat_mat('ZICA Pine needles', (0.04, 0.12, 0.05), 0.8)
    palm_leaf = flat_mat('ZICA Palm leaves', (0.18, 0.35, 0.08), 0.6)
    bark = flat_mat('ZICA Bark', (0.12, 0.07, 0.04), 0.9)
    rock_m = mat_lib('stone', 0.4, seed=s.seed)
    n = int(s.density * {'ISLAND': 500, 'DESERT': 160, 'SNOW': 600, 'FOREST': 1400}[kind] * (0.6 + 0.4 * s.detail))
    rocks = [asset_rock(c, rock_m, i) for i in range(3)]
    for r_ in rocks: r_.hide_render = True; r_.hide_viewport = True
    if kind == 'ISLAND':
        palms = [asset_palm(c, palm_leaf, bark)]; broad = [asset_broadleaf(c, leaf, bark)]
        scatter(c, palms, n // 3, size, h, lambda x, y, z, rr: (water + 0.4 < z < water + 4) and slope_at(h, x, y) < 0.5, s.seed)
        scatter(c, broad, n, size, h, lambda x, y, z, rr: (water + 3 < z < water + 22) and slope_at(h, x, y) < 0.7, s.seed + 1)
    elif kind == 'DESERT':
        cac = [asset_cactus(c, flat_mat('ZICA Cactus', (0.15, 0.3, 0.12), 0.6))]
        scatter(c, cac, n, size, h, lambda x, y, z, rr: slope_at(h, x, y) < 0.25 and z < 8, s.seed)
        scatter(c, rocks, n // 2, size, h, lambda x, y, z, rr: True, s.seed + 2, (0.6, 3.0))
    elif kind == 'SNOW':
        pines = [asset_pine(c, pine_leaf, bark)]
        scatter(c, pines, n, size, h, lambda x, y, z, rr: (water + 1 < z < 16) and slope_at(h, x, y) < 0.6, s.seed)
        scatter(c, rocks, n // 4, size, h, lambda x, y, z, rr: z > water, s.seed + 2, (1.0, 4.0))
    else:
        pines = [asset_pine(c, pine_leaf, bark)]; broad = [asset_broadleaf(c, leaf, bark)]
        scatter(c, pines + broad + broad, n, size, h, lambda x, y, z, rr: z > water + 0.6 and slope_at(h, x, y) < 0.8, s.seed)
        scatter(c, rocks, n // 8, size, h, lambda x, y, z, rr: z > water - 1, s.seed + 2, (0.5, 2.2))
    elev, az, energy, scol = B['sun']
    add_sun(c, s.sun_height if s.sun_height else elev, az, energy, scol)
    set_world(*B['sky'], strength=1.0)
    fog_box(c, (size * 1.4, size * 1.4, 120), 40, 0.0015 * s.fog * (2 if kind == 'FOREST' else 1), B['fog'])
    peak = max(h(x * size / 8, y * size / 8) for x in range(-3, 4) for y in range(-3, 4))
    if kind == 'ISLAND':   # pull back so the whole island, beach and lagoon are in the shot
        orbit_camera(c, (0, 0, max(water, 0) + 2), size * 0.95, max(peak, 10) * 1.1 + size * 0.3, lens=30, sweep_deg=50)
    else:
        orbit_camera(c, (0, 0, max(water, 0) + 4), size * 0.62, max(peak, 10) * 1.05 + size * 0.12, lens=30, sweep_deg=50)
    return c


# ---- Neon City -------------------------------------------------------------------------
def window_facade_material(name, base=(0.02, 0.025, 0.035), lit_colors=((1.0, 0.72, 0.38), (0.25, 0.95, 1.0), (1.0, 0.2, 0.75)),
                           emit=6.0, floor_h=3.2, win_w=0.55, metal=0.6):
    m, N, L, P, out = new_mat(name)
    P.inputs['Base Color'].default_value = (*base, 1)
    P.inputs['Metallic'].default_value = metal
    P.inputs['Roughness'].default_value = 0.3
    geo = N.new('ShaderNodeNewGeometry'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Position'], sep.inputs['Vector'])
    u = math_node(N, L, 'MULTIPLY', math_node(N, L, 'ADD', sep.outputs['X'], sep.outputs['Y']), win_w)
    v = math_node(N, L, 'MULTIPLY', sep.outputs['Z'], 1 / floor_h)
    pane = math_node(N, L, 'MULTIPLY', math_node(N, L, 'LESS_THAN', math_node(N, L, 'FRACT', u), 0.62),
                     math_node(N, L, 'LESS_THAN', math_node(N, L, 'FRACT', v), 0.55))
    cell = N.new('ShaderNodeCombineXYZ')
    L.new(math_node(N, L, 'FLOOR', u), cell.inputs['X']); L.new(math_node(N, L, 'FLOOR', v), cell.inputs['Y'])
    wn = N.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '3D'; L.new(cell.outputs['Vector'], wn.inputs['Vector'])
    at = N.new('ShaderNodeAttribute'); at.attribute_name = 'lit'
    on = math_node(N, L, 'LESS_THAN', wn.outputs['Value'], at.outputs['Fac'])
    tint = N.new('ShaderNodeAttribute'); tint.attribute_name = 'tint'
    stops = [(i / len(lit_colors), col) for i, col in enumerate(lit_colors)]
    cr = ramp(N, L, tint.outputs['Fac'], stops, 'CONSTANT')
    L.new(cr.outputs['Color'], P.inputs['Emission Color'])
    L.new(math_node(N, L, 'MULTIPLY', math_node(N, L, 'MULTIPLY', pane, on), emit), P.inputs['Emission Strength'])
    return m


def build_neon_city(s):
    get_coll(PROP_COLL, clear=True); get_coll(STAGE_COLL, clear=True)
    c = get_coll(WORLD_COLL, clear=True)
    purge_orphans(); _MAT_CACHE.clear()
    rr = random.Random(s.seed)
    BLOCKS = int(8 + 8 * s.world_size)
    BLOCK, ROAD = 14.0, 6.0
    PITCH = BLOCK + ROAD; HALF = BLOCKS * PITCH / 2
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=HALF + 60)
    ground = obj_from_bm('Wet asphalt', bm, c)
    m, N, L, P, out = new_mat('ZICA Wet asphalt')
    P.inputs['Base Color'].default_value = (0.012, 0.014, 0.02, 1)
    nz = noise_tex(N, L, 0.08, 4, 0.5, obj_coords(N))
    r = ramp(N, L, nz.outputs['Fac'], [(0.45, (0.06,) * 3), (0.6, (0.5,) * 3)])
    L.new(r.outputs['Color'], P.inputs['Roughness'])
    ground.data.materials.append(m)
    bm = bmesh.new()
    tint = bm.faces.layers.float.new('tint'); lit = bm.faces.layers.float.new('lit')
    roofs = bmesh.new()
    density = 0.4 + 0.6 * s.density
    for gx in range(BLOCKS):
        for gy in range(BLOCKS):
            if rr.random() > density + 0.25: continue
            cx = -HALF + PITCH * (gx + 0.5); cy = -HALF + PITCH * (gy + 0.5)
            d = Vector((cx, cy)).length / HALF
            for (tx, ty, sw) in ([(cx, cy, BLOCK)] if rr.random() < 0.4 else
                                 [(cx + sx * BLOCK / 4, cy + sy * BLOCK / 4, BLOCK / 2) for sx in (-1, 1) for sy in (-1, 1)]):
                w = sw * rr.uniform(0.6, 0.86); dp = sw * rr.uniform(0.6, 0.86)
                hgt = 8 + max(0, 1 - d) ** 2 * 140 * rr.uniform(0.3, 1.0) + rr.uniform(0, 12)
                tv, lv = rr.random(), rr.uniform(0.15, 0.55)
                tiers = 1 if s.detail == 1 else rr.choice((1, 2, 3))
                z0 = 0
                for t in range(tiers):                       # stepped skyscrapers
                    th = hgt * (0.6 if t == 0 and tiers > 1 else (0.25 if tiers > 1 else 1.0))
                    k = 1 - 0.18 * t
                    vs = bm_box(bm, tx, ty, z0 + th / 2, w * k, dp * k, th)
                    for f in {f for v_ in vs for f in v_.link_faces}:
                        f[tint] = tv; f[lit] = lv
                    z0 += th
                if s.detail >= 2:                             # rooftop units + antenna
                    bm_box(roofs, tx + w * 0.15, ty, z0 + 1.2, w * 0.3, dp * 0.3, 2.4)
                    if hgt > 90: bm_cyl(roofs, tx, ty, z0, z0 + 18, 0.25, 0.08, 6)
    towers = obj_from_bm('Towers', bm, c, window_facade_material('ZICA Neon facade'))
    if len(roofs.verts):
        obj_from_bm('Rooftops', roofs, c, mat_lib('concrete', 0.3, seed=s.seed))
    else:
        roofs.free()
    bm = bmesh.new()
    for i in range(BLOCKS + 1):
        rx = -HALF + PITCH * i - ROAD / 2
        for j in range(BLOCKS * 2):
            for (x, y) in ((rx, -HALF + j * PITCH / 2), (-HALF + j * PITCH / 2, rx)):
                bm_sphere(bm, x + 0.5, y + 0.5, 5.0, 0.35, 1)
    obj_from_bm('Street lights', bm, c, flat_mat('ZICA Street lamp', (1, 0.65, 0.3), emit=18))
    head = flat_mat('ZICA Headlights', (0.85, 0.92, 1.0), emit=30); tail = flat_mat('ZICA Taillights', (1.0, 0.08, 0.05), emit=30)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); me = bpy.data.meshes.new('Car'); bm.to_mesh(me); bm.free()
    me.materials.append(head)
    for k in range(int(20 + 40 * s.density)):
        car = link(bpy.data.objects.new('Car %02d' % k, me), c)
        car.material_slots[0].link = 'OBJECT'
        lane = rr.randint(1, BLOCKS - 1); along_x = k % 2 == 0
        road = -HALF + PITCH * lane - ROAD / 2 + (1.2 if rr.random() < .5 else -1.2)
        a, b = (-HALF - 20, HALF + 20) if rr.random() < .5 else (HALF + 20, -HALF - 20)
        car.material_slots[0].material = head if a < b else tail
        car.scale = (2.2, 1.0, 0.5)
        car.rotation_euler = (0, 0, 0 if along_x else math.pi / 2)
        f0 = rr.randint(-200, 0)
        for f, p in ((f0, a), (f0 + 260, b)):
            car.location = (p, road, 0.6) if along_x else (road, p, 0.6)
            car.keyframe_insert('location', frame=f)
        make_linear(car, cyclic=True)
    set_world((0.01, 0.012, 0.04), (0.06, 0.03, 0.08), 1.0, stars=True)
    moon = add_sun(c, 40, 30, 0.3, (0.6, 0.7, 1.0))
    fog_box(c, (HALF * 2.8, HALF * 2.8, 200), 100, 0.0022 * s.fog, (0.55, 0.62, 1.0))
    orbit_camera(c, (0, 0, 35), HALF * 1.35, 30 + HALF * 0.12, lens=26, sweep_deg=70)
    return c


# ---- Old Town (ancient) ------------------------------------------------------------------
def build_old_town(s):
    get_coll(PROP_COLL, clear=True); get_coll(STAGE_COLL, clear=True)
    c = get_coll(WORLD_COLL, clear=True)
    purge_orphans(); _MAT_CACHE.clear()
    rr = random.Random(s.seed)
    R = 70 * s.world_size
    so = s.seed * 7.1
    def h(x, y):
        d = math.hypot(x, y) / R
        return fbm(x * 0.02, y * 0.02, so) * 3 + max(0, d - 0.9) * 25
    terrain_mesh(c, R * 3, (80, 140, 200)[s.detail - 1], h,
                 terrain_material('ZICA Dust ground', dict(beach=(0.72, 0.6, 0.42), low=(0.68, 0.55, 0.36), mid=(0.6, 0.48, 0.3),
                                                           high=(0.5, 0.42, 0.3), rock=(0.5, 0.4, 0.3), top=30), None, water_z=-5))
    wall_m = mat_lib('stone', 0.35, (0.78, 0.66, 0.48), s.seed); plaster = mat_lib('concrete', 0.5, (0.86, 0.78, 0.64), s.seed + 1)
    roof_m = mat_lib('terracotta', 0.3, seed=s.seed); dome_m = mat_lib('painted', 0.25, (0.12, 0.35, 0.55), s.seed)
    wood = mat_lib('wood', 0.5, seed=s.seed); cloth_cols = [(0.7, 0.15, 0.1), (0.85, 0.6, 0.15), (0.15, 0.35, 0.55), (0.9, 0.85, 0.7)]
    houses, flat_roofs, domes, beams = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    n = int(60 + 140 * s.density)
    placed = []
    for i in range(n * 3):
        if len(placed) >= n: break
        a = rr.uniform(0, 2 * math.pi); rad = R * math.sqrt(rr.uniform(0.04, 0.85))
        x, y = math.cos(a) * rad, math.sin(a) * rad
        if abs(x) < 10 and abs(y) < 14: continue                           # temple square
        if abs(y) < 3.5 or abs(x) < 3: continue                            # main streets
        w, d, ht = rr.uniform(4, 8), rr.uniform(4, 8), rr.uniform(3, 7) * (1.3 if rad < R * 0.4 else 1)
        if any(abs(x - px) < (w + pw) / 2 + 1.2 and abs(y - py) < (d + pd) / 2 + 1.2 for px, py, pw, pd in placed): continue
        placed.append((x, y, w, d))
        z = h(x, y) - 0.5
        rot = rr.uniform(-0.15, 0.15)
        v = bm_box(houses, 0, 0, ht / 2, w, d, ht); transform_verts(v, rot=(0, 0, rot), loc=(x, y, z))
        if s.detail >= 2:   # doorway + windows as dark insets
            v = bm_box(beams, 0, -d / 2 - 0.02, 1.1, 1.0, 0.1, 2.2); transform_verts(v, rot=(0, 0, rot), loc=(x, y, z))
            for wx in (-w * 0.3, w * 0.3):
                v = bm_box(beams, wx, -d / 2 - 0.02, ht * 0.7, 0.7, 0.1, 0.8); transform_verts(v, rot=(0, 0, rot), loc=(x, y, z))
        if rr.random() < 0.18:
            v = bm_sphere(domes, 0, 0, ht, min(w, d) * 0.45, 3, 0.8); transform_verts(v, loc=(x, y, z))
        else:
            v = bm_box(flat_roofs, 0, 0, ht + 0.15, w + 0.3, d + 0.3, 0.3); transform_verts(v, rot=(0, 0, rot), loc=(x, y, z))
    obj_from_bm('Houses', houses, c, plaster)
    obj_from_bm('Roofs', flat_roofs, c, roof_m)
    obj_from_bm('Domes', domes, c, dome_m, smooth=True)
    obj_from_bm('Doors and windows', beams, c, flat_mat('ZICA Shadowed openings', (0.05, 0.035, 0.025), 0.9))
    # temple with columns
    tb = bmesh.new()
    bm_box(tb, 0, 0, 0.6, 16, 24, 1.2); bm_box(tb, 0, 0, 1.5, 14, 22, 0.6)
    bm_box(tb, 0, 0, 10.6, 15, 23, 1.2)
    for k in range(5): bm_box(tb, 0, -12.3 - k * 0.6, (1.2 - k * 0.24) / 2, 8, 0.6, 1.2 - k * 0.24)
    pv = [tb.verts.new(p) for p in ((-7.5, -11.5, 11.2), (7.5, -11.5, 11.2), (7.5, 11.5, 11.2), (-7.5, 11.5, 11.2), (0, -11.5, 14.5), (0, 11.5, 14.5))]
    tb.faces.new((pv[0], pv[1], pv[4])); tb.faces.new((pv[3], pv[5], pv[2])); tb.faces.new((pv[0], pv[4], pv[5], pv[3])); tb.faces.new((pv[1], pv[2], pv[5], pv[4]))
    obj_from_bm('Temple', tb, c, mat_lib('marble', 0.4, seed=s.seed))
    cb = bmesh.new()
    for i in range(6):
        for j in (-1, 1):
            bm_cyl(cb, -6.25 + i * 2.5, j * 10.5, 1.8, 10.0, 0.55, 0.48, 16)
    for j in range(1, 8):
        for i in (-1, 1):
            bm_cyl(cb, i * 6.25, -10.5 + j * 2.625, 1.8, 10.0, 0.55, 0.48, 16)
    cols = obj_from_bm('Temple columns', cb, c, mat_lib('marble', 0.4, seed=s.seed), smooth=True)
    # market stalls with cloth awnings along the main street
    for k in range(int(10 + 14 * s.density)):
        x = rr.choice((-1, 1)) * rr.uniform(12, R * 0.8); y = rr.choice((-2.6, 2.6))
        sb = bmesh.new()
        for px in (-1.1, 1.1):
            for py in (-0.8, 0.8): bm_cyl(sb, px, py, 0, 2.3, 0.05, seg=6)
        bm_box(sb, 0, 0, 0.9, 2.2, 1.6, 0.08)
        st = obj_from_bm('Stall %d' % k, sb, c, wood); st.location = (x, y, h(x, y))
        ab = bmesh.new(); v = bm_box(ab, 0, 0, 0, 2.6, 2.0, 0.03); transform_verts(v, rot=(math.radians(12), 0, 0), loc=(0, 0, 2.35))
        aw = obj_from_bm('Awning %d' % k, ab, c, mat_lib('cloth', 0.2, rr.choice(cloth_cols), k % 4))
        aw.location = (x, y, h(x, y))
    leaf = flat_mat('ZICA Palm leaves', (0.2, 0.35, 0.08), 0.6); bark = flat_mat('ZICA Bark', (0.2, 0.13, 0.07), 0.9)
    palm = asset_palm(c, leaf, bark)
    scatter(c, [palm], int(20 + 50 * s.density), R * 2, h,
            lambda x, y, z, rr2: math.hypot(x, y) > R * 0.6 or (abs(x) < 9 and abs(y) > 13 and abs(y) < 20), s.seed, (0.8, 1.3))
    # town wall ring
    wb = bmesh.new()
    segs = 48
    for i in range(segs):
        if i % 12 == 0: continue                                                   # gates
        a0, a1 = 2 * math.pi * i / segs, 2 * math.pi * (i + 1) / segs
        mid = (a0 + a1) / 2
        v = bm_box(wb, 0, 0, 0, 2 * math.pi * R * 0.95 / segs + 0.3, 1.6, 7)
        transform_verts(v, rot=(0, 0, mid + math.pi / 2), loc=(math.cos(mid) * R * 0.95, math.sin(mid) * R * 0.95, 3.5 + h(math.cos(mid) * R * .95, math.sin(mid) * R * .95) - 1))
        if i % 4 == 0:
            bm_cyl(wb, math.cos(mid) * R * 0.95, math.sin(mid) * R * 0.95, 0, 10, 2.2, 2.0, 16)
    obj_from_bm('Town wall', wb, c, wall_m)
    elev = s.sun_height if s.sun_height else 16
    add_sun(c, elev, 245, 4.5, (1.0, 0.78, 0.55))
    set_world((0.3, 0.45, 0.75), (1.0, 0.78, 0.55), 1.0)
    fog_box(c, (R * 4, R * 4, 80), 30, 0.002 * s.fog, (1.0, 0.85, 0.65))
    orbit_camera(c, (0, 0, 4), R * 1.15, R * 0.55, lens=30, sweep_deg=60)
    return c


WORLD_TYPES = [
    ('CITY', 'Neon City', 'Night skyline, stepped towers, glowing windows, traffic', build_neon_city),
    ('OLDTOWN', 'Ancient Old Town', 'Sandstone houses, domes, temple with columns, market, town wall', build_old_town),
    ('ISLAND', 'Island Lagoon', 'Tropical island, palms, beach, clear water, sunset', lambda s: build_terrain_world('ISLAND', s)),
    ('DESERT', 'Desert Canyon', 'Dunes, terraced mesas, canyons, cacti, rocks', lambda s: build_terrain_world('DESERT', s)),
    ('SNOW', 'Snowy Peaks', 'Ridged mountains, snow line, pine forest, lake', lambda s: build_terrain_world('SNOW', s)),
    ('FOREST', 'Forest Valley', 'Rolling hills, river, dense mixed forest, haze', lambda s: build_terrain_world('FOREST', s)),
]
