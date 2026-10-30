# ---------------------------------------------------------------------------
#  WALL & SURFACE ENGINE (grown from the "Wall Engine 0.1" idea)
#  Real geometry, not just a texture: every brick / stone / plank is its own piece,
#  damage removes and chips them, rubble falls on the ground, grime runs down.
#   BRICK    running-bond bricks over mortar, missing / broken bricks, rubble
#   STONE    rough-cut castle stones of random sizes, moss at the base
#   CONCRETE cast concrete panels with form-tie holes, cracks, bitten edges + rebar
#   PLASTER  old plaster peeling off and revealing the brick underneath
#   WOOD     plank fence / barn wall, gaps, broken planks, nails
#   SCIFI    sci-fi hull panels with glowing light strips and bolts
# ---------------------------------------------------------------------------

SURF_COLL = 'ZICA Surfaces'

SURF_TYPES = [
    ('BRICK', 'Brick wall', 'Running-bond bricks over mortar; damage knocks bricks out'),
    ('STONE', 'Castle stone wall', 'Rough-cut stones of random sizes, moss at the base'),
    ('CONCRETE', 'Concrete wall', 'Cast panels, tie holes, cracks; damage bites the edges and shows rebar'),
    ('PLASTER', 'Old plaster on brick', 'Plaster peels away and reveals the bricks underneath'),
    ('WOOD', 'Wooden planks', 'Plank fence / barn wall with gaps, nails and broken planks'),
    ('SCIFI', 'Sci-fi panels', 'Hull panels with glowing strips, vents and bolts'),
]


def _grime(N, L, col, grime, height, co):
    """Darken the base of the wall and add vertical rain streaks. Returns new colour socket."""
    if grime <= 0.001:
        return col
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(co, sep.inputs['Vector'])
    base = math_node(N, L, 'DIVIDE', sep.outputs['Z'], max(height, 0.1) * 0.45)
    base = math_node(N, L, 'SUBTRACT', 1.0, base, clamp=True)
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (6.0, 1.0, 0.35); L.new(co, mp.inputs['Vector'])
    streak = noise_tex(N, L, 3.0, 4, 0.5, mp.outputs['Vector'])
    st = ramp(N, L, streak.outputs['Fac'], [(0.45, (0, 0, 0)), (0.75, (1, 1, 1))])
    m = math_node(N, L, 'MULTIPLY', st.outputs['Color'], 0.6)
    mask = math_node(N, L, 'MAXIMUM', base, m)
    mask = math_node(N, L, 'MULTIPLY', mask, grime * 0.85, clamp=True)
    return mix_rgb(N, L, mask, col, (0.05, 0.045, 0.035, 1), 'MULTIPLY')


def surface_material(kind, grime=0.3, wear=0.3, height=3.0, seed=0, tint=None):
    """Per-piece colour comes from the face attribute 'tint' (0..1) written by the generator."""
    m, N, L, P, out = new_mat('ZICA %s surface' % kind.title())
    co = obj_coords(N)
    at = N.new('ShaderNodeAttribute'); at.attribute_name = 'tint'
    tv = at.outputs['Fac']
    if kind == 'BRICK':
        tones = [(0.0, (0.2, 0.06, 0.035)), (0.5, (0.32, 0.11, 0.055)), (1.0, (0.4, 0.19, 0.1))]
    elif kind == 'STONE':
        tones = [(0.0, (0.16, 0.15, 0.13)), (0.5, (0.26, 0.24, 0.21)), (1.0, (0.34, 0.30, 0.25))]
    elif kind == 'WOOD':
        tones = [(0.0, (0.12, 0.07, 0.035)), (0.6, (0.22, 0.13, 0.06)), (1.0, (0.3, 0.22, 0.15))]
    elif kind == 'SCIFI':
        tones = [(0.0, (0.10, 0.11, 0.13)), (0.7, (0.2, 0.21, 0.24)), (1.0, (0.45, 0.32, 0.08))]
    elif kind == 'PLASTER':
        t = tint or (0.62, 0.55, 0.42)
        tones = [(0.0, tuple(c * 0.85 for c in t)), (1.0, t)]
    else:   # CONCRETE / MORTAR / GROUND
        t = tint or {'CONCRETE': (0.34, 0.33, 0.31), 'MORTAR': (0.3, 0.28, 0.25), 'GROUND': (0.12, 0.11, 0.095)}.get(kind, (0.4, 0.4, 0.4))
        tones = [(0.0, tuple(c * 0.8 for c in t)), (1.0, t)]
    r = ramp(N, L, tv, tones)
    nz = noise_tex(N, L, 5.0 if kind != 'WOOD' else 2.0, 10, 0.65, co)
    fine = noise_tex(N, L, 60.0, 4, 0.6, co)
    col = mix_rgb(N, L, 0.35, r.outputs['Color'], nz.outputs['Color'], 'OVERLAY')
    if kind == 'WOOD':
        mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, 0.08); L.new(co, mp.inputs['Vector'])
        w = N.new('ShaderNodeTexWave'); w.inputs['Scale'].default_value = 6.0; w.inputs['Distortion'].default_value = 6.0
        L.new(mp.outputs['Vector'], w.inputs['Vector'])
        grain = ramp(N, L, w.outputs['Fac'], [(0.0, (0.6, 0.6, 0.6)), (1.0, (1, 1, 1))])
        col = mix_rgb(N, L, 1.0, col, grain.outputs['Color'], 'MULTIPLY')
        col = mix_rgb(N, L, wear * 0.3, col, (0.3, 0.29, 0.27, 1), 'MIX')   # silver-grey weathering
    if kind in ('CONCRETE', 'PLASTER', 'STONE', 'MORTAR') and wear > 0.02:
        vor = N.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'
        vor.inputs['Scale'].default_value = 3.0
        dist_ = noise_tex(N, L, 2.0, 4, 0.6, co)
        warp = mix_rgb(N, L, 0.15, co, dist_.outputs['Color'], 'LINEAR_LIGHT')
        L.new(warp, vor.inputs['Vector'])
        line = ramp(N, L, vor.outputs['Distance'], [(0.0, (1, 1, 1)), (0.006 + wear * 0.01, (0, 0, 0))])
        patch = noise_tex(N, L, 1.2, 3, 0.5, co)
        pm = ramp(N, L, patch.outputs['Fac'], [(0.62 - wear * 0.25, (0, 0, 0)), (0.7 - wear * 0.25, (1, 1, 1))])
        fac = math_node(N, L, 'MULTIPLY', line.outputs['Color'], pm.outputs['Color'])
        fac = math_node(N, L, 'MULTIPLY', fac, min(1.0, 0.4 + wear), clamp=True)
        col = mix_rgb(N, L, fac, col, (0.05, 0.045, 0.04, 1))
    if kind == 'STONE':   # moss at the base, on top faces
        sep = N.new('ShaderNodeSeparateXYZ'); L.new(co, sep.inputs['Vector'])
        low = math_node(N, L, 'LESS_THAN', sep.outputs['Z'], height * 0.35)
        mz = noise_tex(N, L, 3.0, 6, 0.7, co)
        mm = ramp(N, L, mz.outputs['Fac'], [(0.5, (0, 0, 0)), (0.65, (1, 1, 1))])
        moss = math_node(N, L, 'MULTIPLY', low, mm.outputs['Color'])
        moss = math_node(N, L, 'MULTIPLY', moss, min(1.0, grime * 1.6))
        col = mix_rgb(N, L, moss, col, (0.12, 0.2, 0.05, 1))
    col = _grime(N, L, col, grime, height, co)
    L.new(col, P.inputs['Base Color'])
    rough = {'SCIFI': 0.35, 'WOOD': 0.8}.get(kind, 0.9)
    P.inputs['Roughness'].default_value = rough
    if kind == 'SCIFI':
        P.inputs['Metallic'].default_value = 0.7
    L.new(bump(N, L, math_node(N, L, 'ADD', nz.outputs['Fac'], math_node(N, L, 'MULTIPLY', fine.outputs['Fac'], 0.4)),
               0.25 if kind != 'SCIFI' else 0.05, 0.03), P.inputs['Normal'])
    return m


def _tinted_bm():
    bm = bmesh.new()
    return bm, bm.faces.layers.float.new('tint')


_BOX_F = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def _box_tint(bm, layer, cx, cy, cz, sx, sy, sz, t):
    """Fast axis-aligned box (much faster than bmesh.ops.create_cube for thousands of bricks)."""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    V = bm.verts.new
    vs = [V((cx - hx, cy - hy, cz - hz)), V((cx + hx, cy - hy, cz - hz)), V((cx + hx, cy + hy, cz - hz)), V((cx - hx, cy + hy, cz - hz)),
          V((cx - hx, cy - hy, cz + hz)), V((cx + hx, cy - hy, cz + hz)), V((cx + hx, cy + hy, cz + hz)), V((cx - hx, cy + hy, cz + hz))]
    for f in _BOX_F:
        bm.faces.new([vs[k] for k in f])[layer] = t
    return vs


def _slab(bm, layer, W, H, nx, nz, y0, y1, keep, tint_fn, z0=0.0):
    """One solid slab made of nx*nz cells, with cells removed where keep(i, j) is False.
    Only the outside faces are made, so it is fast and has no hidden inner faces."""
    ok = [[keep(i, j) for j in range(nz)] for i in range(nx)]
    F, B = {}, {}
    def vf(i, j):
        k = (i, j)
        if k not in F: F[k] = bm.verts.new((-W / 2 + W * i / nx, y0, z0 + H * j / nz))
        return F[k]
    def vb(i, j):
        k = (i, j)
        if k not in B: B[k] = bm.verts.new((-W / 2 + W * i / nx, y1, z0 + H * j / nz))
        return B[k]
    for i in range(nx):
        for j in range(nz):
            if not ok[i][j]: continue
            t = tint_fn(i, j)
            bm.faces.new((vf(i, j), vf(i + 1, j), vf(i + 1, j + 1), vf(i, j + 1)))[layer] = t
            bm.faces.new((vb(i, j + 1), vb(i + 1, j + 1), vb(i + 1, j), vb(i, j)))[layer] = t
            for (di, dj, a, b) in ((-1, 0, (i, j + 1), (i, j)), (1, 0, (i + 1, j), (i + 1, j + 1)),
                                   (0, -1, (i, j), (i + 1, j)), (0, 1, (i + 1, j + 1), (i, j + 1))):
                ii, jj = i + di, j + dj
                if 0 <= ii < nx and 0 <= jj < nz and ok[ii][jj]: continue
                bm.faces.new((vf(*a), vf(*b), vb(*b), vb(*a)))[layer] = t
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return F


def _hole_field(seed, damage, width, height):
    """Returns f(x, z) -> True where the wall is broken. A few big impact holes + edge bites."""
    rr = random.Random(seed * 13 + 1)
    holes = []
    for _ in range(int(damage * 4.0 + 0.5)):
        holes.append((rr.uniform(-width * 0.38, width * 0.38), rr.uniform(height * 0.25, height * 0.85), rr.uniform(0.25, 0.75) * (0.4 + damage)))
    top_bite = damage * 0.6

    def broken(x, z):
        for hx, hz, hr in holes:
            d = math.hypot(x - hx, (z - hz) * 1.2)
            if d < hr * (0.75 + 0.35 * noise.noise(Vector((x * 2.1 + seed, z * 2.1, 0.5)))):
                return True
        if top_bite > 0 and z > height - top_bite * (0.6 + 0.5 * noise.noise(Vector((x * 0.9 + seed, 0.3, 0)))):
            return True
        return False
    return broken


def _rubble(coll, mat, kind, seed, count, width, thickness, piece):
    if count <= 0: return None
    rr = random.Random(seed + 77)
    bm, lay = _tinted_bm()
    for _ in range(count):
        x = rr.uniform(-width * 0.5, width * 0.5)
        y = -thickness * 0.5 - abs(rr.gauss(0, 0.5))
        sx, sy, sz = piece[0] * rr.uniform(0.3, 1.0), piece[1] * rr.uniform(0.3, 1.0), piece[2] * rr.uniform(0.4, 1.0)
        vs = _box_tint(bm, lay, 0, 0, 0, sx, sy, sz, rr.random())
        transform_verts(vs, rot=(rr.uniform(-0.5, 0.5), rr.uniform(-0.5, 0.5), rr.uniform(0, 6.28)), loc=Vector((x, y, sz * 0.4)))
    ob = obj_from_bm('Rubble', bm, coll, mat)
    add_bevel(ob, min(piece) * 0.15, 1)
    return ob


def build_surface(kind, s):
    remove_colls(PROP_COLL, STAGE_COLL)
    get_coll(WORLD_COLL, clear=True)
    c = get_coll(SURF_COLL, clear=True)
    purge_orphans(); _MAT_CACHE.clear()
    W, H, T = s.surf_width, s.surf_height, s.surf_thickness
    dmg, grime, det, seed = s.surf_damage, s.surf_grime, s.surf_detail, s.surf_seed
    rr = random.Random(seed)
    broken = _hole_field(seed, dmg, W, H) if dmg > 0.02 else (lambda x, z: False)
    made = []

    def mortar_slab(name='Mortar', kind_='MORTAR', inset=0.012, holes=False):
        bm, lay = _tinted_bm()
        nx, nz = (max(4, int(W / 0.1)), max(4, int(H / 0.1))) if holes else (1, 1)
        _slab(bm, lay, W, H, nx, nz, -T / 2 + inset, T / 2 - inset,
              (lambda i, j: not broken(-W / 2 + (i + 0.5) * W / nx, (j + 0.5) * H / nz)) if holes else (lambda i, j: True),
              lambda i, j: 0.5)
        return obj_from_bm(name, bm, c, surface_material(kind_, grime, dmg, H, seed))

    if kind in ('BRICK', 'PLASTER'):
        bw, bh, gap = 0.215, 0.065, 0.01
        bm, lay = _tinted_bm()
        rows = int(H / (bh + gap)); cols = int(W / (bw + gap)) + 2
        for j in range(rows):
            off = (bw + gap) / 2 if j % 2 else 0.0
            z = j * (bh + gap) + bh / 2
            for i in range(cols):
                x = -W / 2 + i * (bw + gap) + off
                x0, x1 = max(x - bw / 2, -W / 2), min(x + bw / 2, W / 2)
                if x1 - x0 < 0.03: continue
                if kind == 'BRICK' and broken((x0 + x1) / 2, z):
                    continue
                if kind == 'BRICK' and dmg > 0 and rr.random() < dmg * 0.02:   # single loose bricks
                    continue
                push = rr.uniform(-0.004, 0.004) + (rr.uniform(0, 0.02) * dmg if rr.random() < dmg * 0.3 else 0)
                vs = _box_tint(bm, lay, (x0 + x1) / 2, -push, z, x1 - x0, T, bh, rr.random())
                if dmg > 0.1 and rr.random() < dmg * 0.25:
                    cxx = Vector(((x0 + x1) / 2, -push, z))
                    for v in vs: v.co -= cxx
                    transform_verts(vs, rot=(0, rr.uniform(-0.08, 0.08) * dmg, rr.uniform(-0.06, 0.06) * dmg))
                    for v in vs: v.co += cxx
        bricks = obj_from_bm('Bricks', bm, c, surface_material('BRICK', grime, dmg, H, seed))
        add_bevel(bricks, 0.006 if det > 1 else 0.004, 2 if det > 1 else 1)
        made.append(bricks)
        made.append(mortar_slab('Mortar', 'MORTAR', 0.012, holes=(kind == 'BRICK')))
        if kind == 'PLASTER':
            # plaster skin in front: a grid of tiles; peeled where noise < threshold
            res = 0.05 if det >= 3 else (0.075 if det == 2 else 0.12)
            nx, nz = int(W / res), int(H / res)
            bm, lay = _tinted_bm()
            thr = 1.0 - dmg * 1.25
            def pkeep(i, j):
                x = -W / 2 + (i + 0.5) * W / nx; z = (j + 0.5) * H / nz
                n = noise.fractal(Vector((x * 0.9 + seed, z * 0.9, 0.3)), 0.5, 2.0, 4) * 0.5 + 0.5 + (1 - z / H) * 0.15 * dmg
                return n <= thr
            Fv = _slab(bm, lay, W, H, nx, nz, -T / 2 - 0.022, -T / 2 + 0.002, pkeep,
                       lambda i, j: 0.5 + 0.5 * noise.noise(Vector((i * 0.2, j * 0.2, seed))))
            for v in Fv.values():   # wavy hand-trowelled surface
                v.co.y -= noise.noise(Vector((v.co.x * 2 + seed, v.co.z * 2, 1.0))) * 0.004 * det
            pl = obj_from_bm('Plaster', bm, c, surface_material('PLASTER', grime, dmg, H, seed,
                                                                tint=(0.62, 0.55, 0.42) if s.surf_variant == 0 else (0.42, 0.55, 0.6)))
            made.append(pl)
        piece = (bw, T, bh)
        mat = surface_material('BRICK', grime, dmg, H, seed)
    elif kind == 'STONE':
        bm, lay = _tinted_bm()
        z = 0.0
        while z < H - 0.05:
            rh = rr.uniform(0.22, 0.42) if det > 1 else rr.uniform(0.3, 0.5)
            rh = min(rh, H - z)
            x = -W / 2
            while x < W / 2 - 0.05:
                sw = min(rr.uniform(0.35, 0.8), W / 2 - x)
                cx, cz = x + sw / 2, z + rh / 2
                if not broken(cx, cz):
                    g = 0.025
                    vs = _box_tint(bm, lay, cx, rr.uniform(-0.02, 0.02), cz, sw - g, T + rr.uniform(0, 0.06), rh - g, rr.random())
                    if det >= 2:   # rough, rounded silhouette: jitter the corners
                        for v in vs:
                            v.co.x += rr.uniform(-0.012, 0.012); v.co.z += rr.uniform(-0.012, 0.012); v.co.y += rr.uniform(-0.015, 0.015)
                x += sw
            z += rh
        st = obj_from_bm('Stones', bm, c, surface_material('STONE', grime, dmg, H, seed))
        add_bevel(st, 0.03 if det > 1 else 0.02, 3 if det > 2 else 2)
        if det >= 3: add_subsurf(st, 1)
        made += [st, mortar_slab('Mortar', 'MORTAR', 0.05, holes=True)]
        piece = (0.4, T * 0.6, 0.25)
        mat = surface_material('STONE', grime, dmg, H, seed)
    elif kind == 'CONCRETE':
        res = 0.05 if det >= 3 else (0.08 if det == 2 else 0.14)
        nx, nz = int(W / res), int(H / res)
        bm, lay = _tinted_bm()
        panel_w = 1.2
        def ckeep(i, j):
            return not broken(-W / 2 + (i + 0.5) * W / nx, (j + 0.5) * H / nz)
        def ctint(i, j):
            x = -W / 2 + (i + 0.5) * W / nx
            pan = int((x + W / 2) / panel_w)
            return 0.45 + ((pan * 37 % 11) / 11.0) * 0.4
        Fv = _slab(bm, lay, W, H, nx, nz, -T / 2, T / 2, ckeep, ctint)
        for v in Fv.values():
            v.co.y -= noise.noise(Vector((v.co.x * 3 + seed, v.co.z * 3, 0))) * 0.006 * det
        wall = obj_from_bm('Concrete', bm, c, surface_material('CONCRETE', grime, dmg, H, seed))
        made.append(wall)
        # form-tie holes and panel seams
        bm, lay = _tinted_bm()
        x = -W / 2 + panel_w
        while x < W / 2 - 0.1:
            _box_tint(bm, lay, x, -T / 2, H / 2, 0.012, 0.01, H, 0.0)
            x += panel_w
        seams = obj_from_bm('Panel seams', bm, c, flat_mat('ZICA Seam', (0.05, 0.05, 0.05), 0.9)) if len(bm.verts) else None
        dark = bmesh.new()
        for i in range(int(W / 0.6)):
            for j in range(int(H / 0.6)):
                hx, hz = -W / 2 + 0.3 + i * 0.6, 0.3 + j * 0.6
                if not broken(hx, hz):
                    vs = bm_cyl(dark, 0, 0, -0.008, 0.008, 0.016, seg=10)
                    transform_verts(vs, rot=(math.pi / 2, 0, 0), loc=Vector((hx, -T / 2, hz)))
        if len(dark.verts):
            obj_from_bm('Tie holes', dark, c, flat_mat('ZICA Tie hole', (0.03, 0.03, 0.03), 0.9))
        else:
            dark.free()
        # exposed rebar inside broken areas
        if dmg > 0.15:
            reb = bmesh.new()
            for zz in [0.2 + k * 0.25 for k in range(int(H / 0.25))]:
                xs = [x_ for x_ in [(-W / 2 + q * 0.05) for q in range(int(W / 0.05))] if broken(x_, zz)]
                if len(xs) > 3:
                    bm_tube(reb, [Vector((xs[0] - 0.05, 0, zz)), Vector((xs[-1] + 0.05, rr.uniform(-0.05, 0.02), zz + rr.uniform(-0.03, 0.03)))], 0.007, 6)
            for xx in [(-W / 2 + 0.3 + k * 0.25) for k in range(int(W / 0.25))]:
                zs = [z_ for z_ in [(q * 0.05) for q in range(int(H / 0.05))] if broken(xx, z_)]
                if len(zs) > 3:
                    bm_tube(reb, [Vector((xx, 0.01, zs[0] - 0.05)), Vector((xx + rr.uniform(-0.03, 0.03), rr.uniform(-0.08, 0.0), zs[-1] + 0.05))], 0.007, 6)
            if len(reb.verts):
                made.append(obj_from_bm('Rebar', reb, c, mat_lib('rust', 0.8, None, seed), smooth=True))
            else:
                reb.free()
        piece = (0.25, 0.18, 0.15)
        mat = surface_material('CONCRETE', grime, dmg, H, seed)
    elif kind == 'WOOD':
        bm, lay = _tinted_bm()
        x = -W / 2
        nails = bmesh.new()
        while x < W / 2 - 0.05:
            pw = rr.uniform(0.11, 0.18)
            gap = 0.008 + dmg * rr.uniform(0, 0.03)
            cx = x + pw / 2
            ph = H
            if dmg > 0 and rr.random() < dmg * 0.35:   # broken plank: shorter, jagged
                ph = H * rr.uniform(0.35, 0.85)
            if not (dmg > 0.5 and rr.random() < (dmg - 0.5) * 0.4):
                vs = _box_tint(bm, lay, cx, 0, ph / 2, pw - gap, T * 0.4, ph, rr.random())
                tops = sorted(vs, key=lambda v: v.co.z)[-4:]
                if ph < H:   # jagged break
                    for k, v in enumerate(tops):
                        v.co.z += rr.uniform(-0.12, 0.05)
                elif det >= 2:   # pointed fence top
                    for v in tops:
                        v.co.z -= abs(v.co.x - cx) * 0.6
                for zz in (0.25 * H, 0.75 * H):
                    if zz < ph and det >= 2:
                        for dx in (-pw * 0.25, pw * 0.25):
                            vn = bm_cyl(nails, 0, 0, -0.003, 0.003, 0.007, seg=8)
                            transform_verts(vn, rot=(math.pi / 2, 0, 0), loc=Vector((cx + dx, -T * 0.2 - 0.002, zz)))
            x += pw
        planks = obj_from_bm('Planks', bm, c, surface_material('WOOD', grime, dmg, H, seed))
        add_bevel(planks, 0.004, 1)
        made.append(planks)
        if len(nails.verts):
            obj_from_bm('Nails', nails, c, mat_lib('rust', 0.6, None, seed), smooth=True)
        else:
            nails.free()
        bm, lay = _tinted_bm()
        for zz in (0.25 * H, 0.75 * H):
            _box_tint(bm, lay, 0, T * 0.3, zz, W, T * 0.25, 0.09, 0.3)
        for xx in [-W / 2 + 0.05 + k * 2.0 for k in range(int(W / 2.0) + 1)]:
            _box_tint(bm, lay, xx, T * 0.45, H / 2 - 0.1, 0.09, 0.09, H + 0.2, 0.2)
        made.append(obj_from_bm('Rails and posts', bm, c, surface_material('WOOD', grime, dmg * 0.5, H, seed + 1)))
        piece = (0.14, 0.02, 0.5)
        mat = surface_material('WOOD', grime, dmg, H, seed)
    else:   # SCIFI
        pw, ph = 1.0, 0.75
        bm, lay = _tinted_bm()
        strips = bmesh.new()
        nx, nz = max(1, round(W / pw)), max(1, round(H / ph))
        pw, ph = W / nx, H / nz
        for i in range(nx):
            for j in range(nz):
                cx, cz = -W / 2 + (i + 0.5) * pw, (j + 0.5) * ph
                if broken(cx, cz) and dmg > 0.4: continue
                depth = T * (0.85 + 0.15 * rr.random())
                vs = _box_tint(bm, lay, cx, (T - depth) / 2, cz, pw - 0.025, depth, ph - 0.025, 0.85 if rr.random() < 0.15 else rr.random() * 0.7)
                if det >= 2:   # inset frame
                    _box_tint(bm, lay, cx, -depth / 2 + (T - depth) / 2 - 0.01, cz, pw * 0.7, 0.02, ph * 0.6, rr.random() * 0.7)
                if rr.random() < 0.35:
                    bm_box(strips, cx, -T / 2 - 0.012, cz + ph * 0.33 if rr.random() < 0.5 else cz - ph * 0.33, pw * 0.6, 0.012, 0.02)
                if det >= 2:
                    for dx in (-1, 1):
                        for dz in (-1, 1):
                            vb = bm_cyl(bm, 0, 0, -0.006, 0.006, 0.012, seg=8)
                            transform_verts(vb, rot=(math.pi / 2, 0, 0), loc=Vector((cx + dx * (pw / 2 - 0.05), -T / 2 - 0.01, cz + dz * (ph / 2 - 0.05))))
                            for f in {f for v in vb for f in v.link_faces}: f[lay] = 1.0
        hull = obj_from_bm('Hull panels', bm, c, surface_material('SCIFI', grime * 0.5, dmg, H, seed))
        add_bevel(hull, 0.008, 2 if det > 1 else 1)
        made.append(hull)
        if len(strips.verts):
            col = (0.2, 0.9, 1.0) if s.surf_variant == 0 else (1.0, 0.35, 0.1)
            made.append(obj_from_bm('Light strips', strips, c, mat_lib('emissive', 0, col, seed)))
        else:
            strips.free()
        made.append(mortar_slab('Back plate', 'CONCRETE', 0.08))
        piece = (0.3, 0.05, 0.2)
        mat = surface_material('SCIFI', grime, dmg, H, seed)

    # ground + rubble
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=max(W, H) * 1.6)
    g = obj_from_bm('Ground', bm, c, surface_material('GROUND', grime, 0.5, H, seed + 3))
    g.location.y = -max(W, H) * 0.4
    if dmg > 0.15:
        _rubble(c, mat, kind, seed, int(dmg * 60 * (W / 6)), W, T, piece)
    # light and camera
    light = s.surf_light
    if light == 'STUDIO':
        tgt = Vector((0, 0, H * 0.5))
        area_light(c, 'Key light', (-W * 0.6, -H * 1.4, H * 1.4), tgt, 55 * H * H, W * 0.6, (1.0, 0.86, 0.7))
        area_light(c, 'Fill light', (W * 0.9, -H * 0.9, H * 0.7), tgt, 18 * H * H, W * 0.6, (0.7, 0.82, 1.0))
        area_light(c, 'Rim light', (0, H * 0.8, H * 1.2), tgt, 40 * H * H, W * 0.5)
        set_world((0.06, 0.065, 0.08), (0.04, 0.04, 0.05))
    elif light == 'DAY':
        add_sun(c, 34, -40, 3.2, (1.0, 0.9, 0.78))
        set_world((0.2, 0.36, 0.7), (0.55, 0.55, 0.55), 0.7)
    else:   # NIGHT: one warm lamp and a cold sky
        set_world((0.01, 0.015, 0.04), (0.02, 0.025, 0.05), 1.0, stars=True)
        d = bpy.data.lights.new('Street lamp', 'POINT'); d.energy = 380 * (H / 3) ** 2; d.color = (1.0, 0.62, 0.28)
        try: d.shadow_soft_size = 0.15
        except Exception: pass
        lo = link(bpy.data.objects.new('Street lamp', d), c); lo.location = (-W * 0.3, -H * 0.7, H * 1.0)
        add_sun(c, 25, 140, 0.15, (0.6, 0.7, 1.0))
    cd = bpy.data.cameras.new('Camera'); cd.lens = 35; cd.clip_end = 5000
    cam = link(bpy.data.objects.new('Camera', cd), c)
    dist = max(W * 1.2, H * 2.3)
    cam.location = (W * 0.18 * s.surf_angle, -dist, H * 0.55)
    aim = Vector((W * 0.05 * s.surf_angle, 0, H * 0.45))
    cam.rotation_euler = (aim - cam.location).to_track_quat('-Z', 'Y').to_euler()
    if abs(s.surf_angle) > 0.01:   # orbit a little for a more cinematic, raking angle
        piv = link(bpy.data.objects.new('Camera pivot', None), c)
        piv.location = (0, 0, 0); cam.parent = piv
        piv.rotation_euler.z = math.radians(-28 * s.surf_angle)
    bpy.context.scene.camera = cam
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 1
    for ob in made:
        ob['zica_generator'] = 'Wall & Surface Engine'
    return c
