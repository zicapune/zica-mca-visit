# ---------------------------------------------------------------------------
#  IMAGE -> WORLD: four ways to turn a picture into 3D
#   TERRAIN  : brightness = height, the photo's own colours paint the land, low areas flood
#   MAP      : paint a map in any paint app. Blue = water, green = forest, yellow/brown = sand,
#              grey/black = city blocks (darker = taller), white = snowy mountains, red = roads
#   MOSAIC   : every pixel becomes a coloured block (3D pixel art / LEGO look)
#   POSTCARD : the photo itself becomes a 3D relief with a parallax camera move
#   CITY     : any photo becomes a city: bright = tall towers, the photo colours paint the buildings,
#              blue areas become water, green areas parks with trees, a street grid cuts through
# ---------------------------------------------------------------------------

def load_pixels(path, res):
    """Returns (w, h, grid) where grid[y][x] = (r, g, b) in 0..1, resampled to about `res` columns."""
    img = bpy.data.images.load(path, check_existing=True)
    W, H = img.size
    if W == 0 or H == 0:
        raise RuntimeError('Could not read the image')
    px = [0.0] * (W * H * 4)
    img.pixels.foreach_get(px)
    cols = max(8, min(res, W)); rows = max(8, int(cols * H / W))
    grid = []
    for j in range(rows):
        y0 = int(j * H / rows); y1 = max(y0 + 1, int((j + 1) * H / rows))
        row = []
        for i in range(cols):
            x0 = int(i * W / cols); x1 = max(x0 + 1, int((i + 1) * W / cols))
            r = g = b = 0.0; n = 0
            for yy in range(y0, y1, max(1, (y1 - y0) // 3)):
                for xx in range(x0, x1, max(1, (x1 - x0) // 3)):
                    k = (yy * W + xx) * 4
                    r += px[k]; g += px[k + 1]; b += px[k + 2]; n += 1
            row.append((r / n, g / n, b / n))
        grid.append(row)
    return cols, rows, grid, img


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def hsv(c):
    import colorsys
    return colorsys.rgb_to_hsv(*[max(0.0, min(1.0, v)) for v in c])


def blur(grid, passes=2):
    rows, cols = len(grid), len(grid[0])
    g = [row[:] for row in grid]
    for _ in range(passes):
        n = [[0.0] * cols for _ in range(rows)]
        for j in range(rows):
            for i in range(cols):
                s = 0.0; k = 0
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        jj, ii = j + dj, i + di
                        if 0 <= jj < rows and 0 <= ii < cols:
                            s += g[jj][ii]; k += 1
                n[j][i] = s / k
        g = n
    return g


def vcol_mesh(name, coll, cols, rows, size, height_fn, color_fn, mat):
    """Grid mesh with per-vertex height and a colour attribute 'Col'."""
    me = bpy.data.meshes.new(name)
    sx = size; sy = size * rows / cols
    verts, faces = [], []
    for j in range(rows):
        for i in range(cols):
            verts.append(((i / (cols - 1) - 0.5) * sx, (j / (rows - 1) - 0.5) * sy, height_fn(i, j)))
    for j in range(rows - 1):
        for i in range(cols - 1):
            a = j * cols + i
            faces.append((a, a + 1, a + cols + 1, a + cols))
    me.from_pydata(verts, [], faces)
    attr = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    for k in range(len(verts)):
        i, j = k % cols, k // cols
        attr.data[k].color = (*color_fn(i, j), 1.0)
    for p in me.polygons: p.use_smooth = True
    me.materials.append(mat)
    return link(bpy.data.objects.new(name, me), coll)


def vcol_material(name, rough=0.85, boost=1.0):
    m, N, L, P, out = new_mat(name)
    a = N.new('ShaderNodeAttribute'); a.attribute_name = 'Col'
    col = a.outputs['Color']
    if boost != 1.0:
        hs = N.new('ShaderNodeHueSaturation'); hs.inputs['Saturation'].default_value = boost
        L.new(col, hs.inputs['Color']); col = hs.outputs['Color']
    L.new(col, P.inputs['Base Color'])
    P.inputs['Roughness'].default_value = rough
    nz = noise_tex(N, L, 0.6, 8, 0.6, obj_coords(N))
    L.new(bump(N, L, nz.outputs['Fac'], 0.3, 0.2), P.inputs['Normal'])
    return m


def classify(c):
    """Map colour -> land type for MAP mode."""
    h, s, v = hsv(c)
    if v > 0.86 and s < 0.15: return 'SNOW'
    if v < 0.55 and s < 0.18: return 'CITY'
    if s < 0.15: return 'CITY' if v < 0.75 else 'SNOW'
    deg = h * 360
    if 190 <= deg <= 260: return 'WATER'
    if 75 <= deg < 170: return 'FOREST'
    if 28 <= deg < 75: return 'SAND'
    if deg < 15 or deg >= 330: return 'ROAD'
    if 15 <= deg < 28: return 'SAND'
    return 'GRASS'


def build_image_world(path, mode, s):
    get_coll(PROP_COLL, clear=True); get_coll(STAGE_COLL, clear=True)
    c = get_coll(WORLD_COLL, clear=True)
    purge_orphans(); _MAT_CACHE.clear()
    res = {'MOSAIC': s.img_res // 2}.get(mode, s.img_res)
    cols, rows, grid, img = load_pixels(bpy.path.abspath(path), res)
    size = 160.0
    sy = size * rows / cols
    H = s.img_height
    L_ = [[lum(grid[j][i]) for i in range(cols)] for j in range(rows)]
    rr = random.Random(s.seed)
    cell = size / cols
    target_z = 0.0

    if mode == 'TERRAIN':
        g = blur(L_, 2)
        if s.img_invert: g = [[1 - v for v in row] for row in g]
        water = s.img_water
        def hf(i, j):
            v = g[j][i]
            edge = min(i, j, cols - 1 - i, rows - 1 - j) / 4.0
            return (v ** 1.4) * H * min(1.0, edge) - (0 if edge >= 1 else (1 - edge) * 4)
        terr = vcol_mesh('Image terrain', c, cols, rows, size, hf, lambda i, j: grid[j][i], vcol_material('ZICA Image colours', 0.85, 1.15))
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size * 2)
        wo = obj_from_bm('Water', bm, c, water_material())
        wo.location.z = water * H
        if s.img_trees > 0:   # trees on greenish, gentle, above-water cells
            from_mat = flat_mat('ZICA Leaves', (0.1, 0.25, 0.06), 0.7); bark = flat_mat('ZICA Bark', (0.12, 0.07, 0.04), 0.9)
            tree = asset_broadleaf(c, from_mat, bark)
            n = 0
            for j in range(1, rows - 1):
                for i in range(1, cols - 1):
                    col = grid[j][i]
                    if col[1] > col[0] * 1.05 and col[1] > col[2] and hf(i, j) > water * H + 0.5 and rr.random() < s.img_trees * 0.5:
                        x = (i / (cols - 1) - 0.5) * size + rr.uniform(-cell / 2, cell / 2); y = (j / (rows - 1) - 0.5) * sy + rr.uniform(-cell / 2, cell / 2)
                        instance(tree, 'Tree', c, (x, y, hf(i, j) - 0.2), rr.uniform(0, 6.28), cell * rr.uniform(0.15, 0.3))
                        n += 1
                        if n > 2500: break
        target_z = H * 0.2
        add_sun(c, s.sun_height or 30, 220, 4.0)
        set_world((0.25, 0.45, 0.85), (0.9, 0.85, 0.75))
        orbit_camera(c, (0, 0, target_z), size * 0.75, H + size * 0.35, lens=32, sweep_deg=50)

    elif mode == 'MAP':
        kinds = [[classify(grid[j][i]) for i in range(cols)] for j in range(rows)]
        base_h = {'WATER': -1.2, 'SAND': 0.3, 'GRASS': 0.6, 'FOREST': 0.8, 'ROAD': 0.35, 'CITY': 0.5, 'SNOW': 1.0}
        # mountains: snow cells become peaks, distance from non-snow raises them
        hraw = [[base_h[kinds[j][i]] for i in range(cols)] for j in range(rows)]
        mount = [[(1.0 if kinds[j][i] == 'SNOW' else 0.0) for i in range(cols)] for j in range(rows)]
        mb = blur(mount, 4)
        hs_ = blur(hraw, 2)
        def hf(i, j):
            return hs_[j][i] * 1.5 + (mb[j][i] ** 1.5) * H * 1.2 + fbm(i * 0.15, j * 0.15, s.seed) * 0.6
        pal = {'WATER': (0.15, 0.25, 0.2), 'SAND': (0.82, 0.68, 0.45), 'GRASS': (0.25, 0.45, 0.12), 'FOREST': (0.12, 0.3, 0.07),
               'ROAD': (0.12, 0.12, 0.13), 'CITY': (0.3, 0.3, 0.32), 'SNOW': (0.92, 0.94, 0.97)}
        def cf(i, j):
            k = kinds[j][i]
            if k == 'SNOW' and hf(i, j) < H * 0.25: return (0.4, 0.38, 0.34)
            return pal[k]
        vcol_mesh('Map terrain', c, cols, rows, size, hf, cf, vcol_material('ZICA Map colours', 0.9))
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size * 2)
        wo = obj_from_bm('Water', bm, c, water_material()); wo.location.z = -0.2
        city = bmesh.new()
        tint = city.faces.layers.float.new('tint'); lit = city.faces.layers.float.new('lit')
        leaf = flat_mat('ZICA Leaves', (0.08, 0.22, 0.05), 0.7); bark = flat_mat('ZICA Bark', (0.12, 0.07, 0.04), 0.9)
        pine = asset_pine(c, flat_mat('ZICA Pine', (0.04, 0.13, 0.05), 0.8), bark); broad = asset_broadleaf(c, leaf, bark)
        nt = 0
        for j in range(rows):
            for i in range(cols):
                k = kinds[j][i]
                x = (i / (cols - 1) - 0.5) * size; y = (j / (rows - 1) - 0.5) * sy
                if k == 'CITY' and rr.random() < 0.85:
                    v = lum(grid[j][i])
                    hgt = cell * (1.5 + (1 - v) ** 2 * s.img_build * 9) * rr.uniform(0.6, 1.3)
                    vs = bm_box(city, x, y, hf(i, j) + hgt / 2, cell * 0.8, cell * 0.8, hgt)
                    tv, lv = rr.random(), rr.uniform(0.2, 0.6)
                    for f in {f for vv in vs for f in vv.link_faces}: f[tint] = tv; f[lit] = lv
                elif k == 'FOREST' and rr.random() < 0.3 + 0.6 * s.img_trees and nt < 4000:
                    src = pine if rr.random() < 0.5 else broad
                    instance(src, 'Tree', c, (x + rr.uniform(-cell / 2, cell / 2), y + rr.uniform(-cell / 2, cell / 2), hf(i, j) - 0.1),
                             rr.uniform(0, 6.28), cell * rr.uniform(0.12, 0.22))
                    nt += 1
        if len(city.verts):
            obj_from_bm('City blocks', city, c, window_facade_material('ZICA Map city', base=(0.35, 0.36, 0.38),
                                                                   lit_colors=((1.0, 0.8, 0.5), (0.7, 0.9, 1.0)), emit=2.0,
                                                                   floor_h=cell * 0.35, win_w=1 / (cell * 0.22), metal=0.1))
        else:
            city.free()
        add_sun(c, s.sun_height or 35, 210, 4.2)
        set_world((0.25, 0.45, 0.85), (0.9, 0.85, 0.75))
        orbit_camera(c, (0, 0, 0), size * 0.7, size * 0.45 + H, lens=32, sweep_deg=50)

    elif mode == 'MOSAIC':
        verts, faces, fcols = [], [], []
        CUBE_F = ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0))
        half = cell * 0.46
        stud = s.detail >= 2
        for j in range(rows):
            for i in range(cols):
                col = grid[j][i]
                hgt = 0.3 + lum(col) * H * 0.25
                x = (i / (cols - 1) - 0.5) * size; y = (j / (rows - 1) - 0.5) * sy
                b0 = len(verts)
                verts += [(x - half, y - half, 0), (x + half, y - half, 0), (x + half, y + half, 0), (x - half, y + half, 0),
                          (x - half, y - half, hgt), (x + half, y - half, hgt), (x + half, y + half, hgt), (x - half, y + half, hgt)]
                for f in CUBE_F:
                    faces.append(tuple(b0 + k for k in f)); fcols.append(col)
                if stud:
                    r_, n_ = cell * 0.28, 8
                    b1 = len(verts)
                    for k in range(n_):
                        a_ = 2 * math.pi * k / n_
                        verts.append((x + r_ * math.cos(a_), y + r_ * math.sin(a_), hgt))
                        verts.append((x + r_ * math.cos(a_), y + r_ * math.sin(a_), hgt + cell * 0.18))
                    for k in range(n_):
                        k2 = (k + 1) % n_
                        faces.append((b1 + 2 * k, b1 + 2 * k2, b1 + 2 * k2 + 1, b1 + 2 * k + 1)); fcols.append(col)
                    faces.append(tuple(b1 + 2 * k + 1 for k in range(n_))); fcols.append(col)
        me = bpy.data.meshes.new('Pixel mosaic')
        me.from_pydata(verts, [], faces)
        attr = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        flat = []
        for p, col in zip(me.polygons, fcols):
            flat += [col[0], col[1], col[2], 1.0] * p.loop_total
        attr.data.foreach_set('color', flat)
        m = vcol_material('ZICA Mosaic', 0.35, 1.1)
        me.materials.append(m)
        ob = link(bpy.data.objects.new('Pixel mosaic', me), c)
        add_bevel(ob, cell * 0.06, 1)
        add_sun(c, s.sun_height or 40, 210, 4.0)
        set_world((0.05, 0.06, 0.09), (0.15, 0.15, 0.18))
        orbit_camera(c, (0, 0, 0), size * 0.62, size * 0.5, lens=35, sweep_deg=40)

    elif mode == 'CITY':
        res2 = min(cols, 70)
        if res2 < cols:
            cols2, rows2 = res2, max(8, int(res2 * rows / cols))
            grid = [[grid[int(j * rows / rows2)][int(i * cols / cols2)] for i in range(cols2)] for j in range(rows2)]
            cols, rows = cols2, rows2
            sy = size * rows / cols; cell = size / cols
        block = 4   # a street every 4 cells
        bm = bmesh.new()
        tint = bm.faces.layers.float.new('tint'); lit = bm.faces.layers.float.new('lit')
        colr = []   # per face colour (filled after)
        leaf = flat_mat('ZICA Leaves', (0.08, 0.25, 0.05), 0.7); bark = flat_mat('ZICA Bark', (0.12, 0.07, 0.04), 0.9)
        broad = asset_broadleaf(c, leaf, bark)
        water_cells, park_cells = [], []
        H2 = H * s.img_build
        for j in range(rows):
            for i in range(cols):
                if i % block == 0 or j % block == 0:
                    continue   # street
                col = grid[j][i]; h_, s_, v_ = hsv(col)
                x = (i / (cols - 1) - 0.5) * size; y = (j / (rows - 1) - 0.5) * sy
                deg = h_ * 360
                if s_ > 0.25 and 185 <= deg <= 255 and v_ > 0.2:
                    water_cells.append((x, y)); continue
                if s_ > 0.25 and 70 <= deg < 170:
                    park_cells.append((x, y)); continue
                v = lum(col)
                hgt = cell * (0.6 + (v ** 1.8) * 7.0 * s.img_build) * rr.uniform(0.75, 1.25)
                if hgt < cell * 0.5: continue
                wdt = cell * rr.uniform(0.72, 0.9)
                vs = bm_box(bm, x, y, hgt / 2, wdt, wdt, hgt)
                fs = {f for vv in vs for f in vv.link_faces}
                tv, lv = rr.random(), rr.uniform(0.15, 0.55)
                for f in fs: f[tint] = tv; f[lit] = lv
                if hgt > cell * 4.5 and s.detail >= 2:   # setback crown on tall towers
                    vs2 = bm_box(bm, x, y, hgt + hgt * 0.08, wdt * 0.6, wdt * 0.6, hgt * 0.16)
                    for f in {f for vv in vs2 for f in vv.link_faces}: f[tint] = tv; f[lit] = lv
        me_ob = obj_from_bm('Photo city', bm, c, None)
        me = me_ob.data
        # paint every building with the colour of its pixel (lightened so it reads as facade)
        attr = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        flat = []
        for p in me.polygons:
            cx_, cy_ = p.center.x, p.center.y
            i = min(cols - 1, max(0, int(round((cx_ / size + 0.5) * (cols - 1)))))
            j = min(rows - 1, max(0, int(round((cy_ / sy + 0.5) * (rows - 1)))))
            r_, g_, b_ = grid[j][i]
            k = 0.15
            flat += [r_ * (1 - k) + 0.12 * k, g_ * (1 - k) + 0.12 * k, b_ * (1 - k) + 0.14 * k, 1.0] * p.loop_total
        attr.data.foreach_set('color', flat)
        mat = window_facade_material('ZICA Photo city', base=(0.3, 0.3, 0.32), lit_colors=((1.0, 0.82, 0.55), (0.75, 0.9, 1.0)),
                                     emit=1.6, floor_h=max(cell * 0.3, 0.6), win_w=1 / max(cell * 0.2, 0.4), metal=0.15)
        N_, L_n = mat.node_tree.nodes, mat.node_tree.links
        Pb = [n for n in N_ if n.type == 'BSDF_PRINCIPLED'][0]
        ca = N_.new('ShaderNodeAttribute'); ca.attribute_name = 'Col'
        L_n.new(ca.outputs['Color'], Pb.inputs['Base Color'])
        me.materials.append(mat)
        add_bevel(me_ob, cell * 0.02, 1)
        # ground with streets
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size * 0.62)
        gr = obj_from_bm('Streets', bm, c, mat_lib('concrete', 0.3, (0.16, 0.16, 0.17), s.seed)); gr.scale.y = sy / size
        if water_cells:
            bm = bmesh.new()
            for (x, y) in water_cells: bm_box(bm, x, y, -0.05, cell, cell, 0.1)
            obj_from_bm('Canals', bm, c, water_material())
        for (x, y) in park_cells[:1500]:
            if rr.random() < 0.6:
                instance(broad, 'Park tree', c, (x + rr.uniform(-cell / 3, cell / 3), y + rr.uniform(-cell / 3, cell / 3), 0), rr.uniform(0, 6.28), cell * rr.uniform(0.18, 0.3))
        elev = s.sun_height or 12
        add_sun(c, elev, 240, 3.5, (1.0, 0.8, 0.6))
        set_world((0.12, 0.2, 0.42), (1.0, 0.7, 0.45), 1.0)
        orbit_camera(c, (0, 0, cell * 2), size * 0.7, size * 0.42, lens=30, sweep_deg=55)

    else:   # POSTCARD
        g = blur(L_, 1)
        if s.img_invert: g = [[1 - v for v in row] for row in g]
        def hf(i, j):
            fg = (1 - j / (rows - 1)) * 0.6   # lower part of a photo is usually closer
            return (g[j][i] * 0.6 + fg) * H * 0.35
        ob = vcol_mesh('Photo relief', c, cols, rows, size, hf, lambda i, j: (1, 1, 1), bpy.data.materials.new('tmp'))
        bpy.data.materials.remove(ob.data.materials[0]); ob.data.materials.clear()
        m, N, L, P, out = new_mat('ZICA Photo')
        tx = N.new('ShaderNodeTexImage'); tx.image = img; tx.extension = 'EXTEND'
        uvm = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping')
        L.new(uvm.outputs['Generated'], mp.inputs['Vector']); L.new(mp.outputs['Vector'], tx.inputs['Vector'])
        L.new(tx.outputs['Color'], P.inputs['Emission Color']); L.new(tx.outputs['Color'], P.inputs['Base Color'])
        P.inputs['Emission Strength'].default_value = 0.6; P.inputs['Roughness'].default_value = 0.8
        ob.data.materials.append(m)
        ob.rotation_euler.x = math.radians(90)
        ob.location = (0, 0, sy / 2)
        add_sun(c, 45, 180, 2.0)
        set_world((0.02, 0.02, 0.03), (0.02, 0.02, 0.03))
        cam = orbit_camera(c, (0, 0, sy / 2), size * 1.15, sy / 2 - sy / 2 + 2, lens=40, start_deg=-14, sweep_deg=28)
    return c


def make_sample_map(path):
    """Paint a demo map (lake, river, forest, beach, city, roads, snowy range) and save it as PNG."""
    W = H = 256
    img = bpy.data.images.new('ZICA sample map', W, H, alpha=False)
    px = [0.0] * (W * H * 4)
    def put(x, y, col):
        if 0 <= x < W and 0 <= y < H:
            k = (y * W + x) * 4; px[k:k + 4] = [col[0], col[1], col[2], 1.0]
    WATER, FOREST, GRASS, SAND, CITY, ROAD, SNOW = (0.1, 0.35, 0.85), (0.1, 0.6, 0.15), (0.45, 0.8, 0.3), (0.95, 0.8, 0.4), (0.3, 0.3, 0.3), (0.85, 0.1, 0.1), (1, 1, 1)
    for y in range(H):
        for x in range(W):
            n = noise.noise(Vector((x * 0.03, y * 0.03, 0)))
            col = GRASS
            if n > 0.25: col = FOREST
            if y > 190 + n * 20: col = SNOW if (x * 7 + y * 3) % 5 else (0.85, 0.85, 0.85)
            rx = 120 + math.sin(y * 0.05) * 30
            if abs(x - rx) < 6 + n * 3 and y < 200: col = WATER
            if (x - 60) ** 2 + (y - 70) ** 2 < 900 + n * 300: col = WATER
            elif (x - 60) ** 2 + (y - 70) ** 2 < 1300 + n * 300: col = SAND
            if 150 < x < 235 and 30 < y < 130:
                col = CITY if ((x - 150) % 16 > 3 and (y - 30) % 16 > 3) else ROAD
                if (x + y) % 9 == 0: col = (0.15, 0.15, 0.15)
            put(x, y, col)
    img.pixels.foreach_set(px)
    img.filepath_raw = path; img.file_format = 'PNG'; img.save()
    return path
