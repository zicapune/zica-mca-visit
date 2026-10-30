# =====================================================================
#  ZICA WORLD BUILDER 2  ·  Blender 5.2 LTS (also 4.4+)  ·  ZICA Pune
#  EVERYTHING in one script: Worlds, Image to World, Prop Factory, Walls & Surfaces
#
#    WORLDS   Neon City · Ancient Old Town · Island Lagoon · Desert Canyon · Snowy Peaks · Forest Valley
#    IMAGE    Photo to terrain · Painted map · Pixel mosaic · 3D postcard · Photo to city
#    PROPS    Ancient · Modern · War · Sci-fi (22 props, Wear/Detail/Scale/Seed sliders, "Whole set")
#    WALLS    Brick · Castle stone · Concrete · Old plaster · Wooden planks · Sci-fi panels (Damage, Grime)
#    RENDER   Preview / Normal / Good / Cinematic, live render view, preview inside the panel
#
#  RUN:  Scripting tab > New > paste > Run Script (Alt+P), then 3D Viewport > N > ZICA tab.
#        Or Edit > Preferences > Add-ons > Install from Disk.
#  Every slider rebuilds live when "Live update" is on. Everything is procedural: no downloads.
# =====================================================================
bl_info = {"name": 'ZICA World Builder 2', "author": "ZICA Pune", "version": (2, 1, 0), "blender": (4, 4, 0),
           "location": "View3D > Sidebar > ZICA", "category": "3D View",
           "description": 'EVERYTHING in one script: Worlds, Image to World, Prop Factory, Walls & Surfaces'}

import bpy, bmesh, math, random, os
from mathutils import Vector, noise
ZICA_TITLE = 'ZICA World Builder 2'
ZICA_MODULES = {'props', 'worlds', 'surfaces', 'image'}



# ---------------------------------------------------------------------------
#  CORE: scene helpers, materials, stage, camera, render quality
# ---------------------------------------------------------------------------
import bpy, bmesh, math, random, os
from mathutils import Vector, noise

WORLD_COLL, PROP_COLL, STAGE_COLL = 'ZICA World', 'ZICA Props', 'ZICA Stage'


# ---------- collections / objects -------------------------------------------
def get_coll(name, clear=False):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    elif c.name not in bpy.context.scene.collection.children:
        try:
            bpy.context.scene.collection.children.link(c)
        except Exception:
            pass
    if clear:
        for ob in list(c.objects):
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0:
                try:
                    if isinstance(data, bpy.types.Mesh): bpy.data.meshes.remove(data)
                    elif isinstance(data, bpy.types.Curve): bpy.data.curves.remove(data)
                    elif isinstance(data, bpy.types.Light): bpy.data.lights.remove(data)
                    elif isinstance(data, bpy.types.Camera): bpy.data.cameras.remove(data)
                except Exception:
                    pass
    return c


def purge_orphans():
    # remove Blender's default Cube / Light / Camera so they don't sit in the shot
    for nm in ('Cube', 'Light', 'Camera'):
        ob = bpy.data.objects.get(nm)
        if ob and not any(c.name.startswith('ZICA') for c in ob.users_collection):
            bpy.data.objects.remove(ob, do_unlink=True)
    for lib in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.curves, bpy.data.lights, bpy.data.cameras):
        for b in list(lib):
            if b.users == 0:
                try:
                    lib.remove(b)
                except Exception:
                    pass


def remove_colls(*names):
    for n in names:
        c = bpy.data.collections.get(n)
        if c:
            get_coll(n, clear=True)
            bpy.data.collections.remove(c)


def link(ob, coll):
    coll.objects.link(ob)
    return ob


def obj_from_bm(name, bm, coll, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if mat is not None:
        me.materials.append(mat)
    return link(bpy.data.objects.new(name, me), coll)


def instance(src, name, coll, loc, rot_z=0.0, scale=1.0):
    ob = bpy.data.objects.new(name, src.data)
    ob.location = loc
    ob.rotation_euler = (0, 0, rot_z)
    ob.scale = (scale, scale, scale) if not isinstance(scale, (tuple, list)) else scale
    return link(ob, coll)


def add_bevel(ob, width=0.02, segments=2):
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    try:
        m.harden_normals = True
    except Exception:
        pass
    return m


def add_subsurf(ob, levels=1):
    m = ob.modifiers.new('Smooth', 'SUBSURF')
    m.levels = levels
    m.render_levels = levels
    return m


# ---------- bmesh primitives ----------------------------------------------------
def bm_box(bm, cx, cy, cz, sx, sy, sz):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co = Vector((cx + v.co.x * sx, cy + v.co.y * sy, cz + v.co.z * sz))
    return r['verts']


def bm_cyl(bm, cx, cy, z0, z1, r1, r2=None, seg=24, cap=True):
    r2 = r1 if r2 is None else r2
    res = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=(z1 - z0))
    for v in res['verts']:
        v.co.x += cx; v.co.y += cy; v.co.z += (z0 + z1) / 2
    return res['verts']


def bm_sphere(bm, cx, cy, cz, r, sub=2, squash=1.0):
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    for v in res['verts']:
        v.co = Vector((cx + v.co.x, cy + v.co.y, cz + v.co.z * squash))
    return res['verts']


def bm_lathe(bm, profile, seg=40, cx=0.0, cy=0.0, cz=0.0):
    """profile: list of (radius, z) from bottom to top. Returns verts."""
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((cx + r * ca, cy + r * sa, cz + z)) for (r, z) in profile])
    n = len(profile)
    for i in range(seg):
        a, b = rings[i], rings[(i + 1) % seg]
        for k in range(n - 1):
            try:
                bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
            except ValueError:
                pass
    if profile[0][0] > 1e-4:
        try: bm.faces.new([rings[i][0] for i in reversed(range(seg))])
        except ValueError: pass
    if profile[-1][0] > 1e-4:
        try: bm.faces.new([rings[i][-1] for i in range(seg)])
        except ValueError: pass
    bmesh.ops.remove_doubles(bm, verts=[v for r in rings for v in r], dist=1e-5)
    return [v for r in rings for v in r if v.is_valid]


def bm_tube(bm, pts, r, seg=10, caps=True):
    """Smooth tube through a list of Vectors (handles, pipes, arms)."""
    pts = [Vector(p) for p in pts]
    rings = []
    for k, p in enumerate(pts):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        a = t.orthogonal().normalized(); b = t.cross(a).normalized()
        rr = r[k] if isinstance(r, (list, tuple)) else r
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * i / seg) + b * math.sin(2 * math.pi * i / seg)) * rr) for i in range(seg)])
    for k in range(len(rings) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    if caps:
        bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    return [v for r_ in rings for v in r_]


def bm_torus(bm, cx, cy, cz, R, r, seg=32, rseg=12, axis='Z'):
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(rseg):
            b = 2 * math.pi * j / rseg
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            if axis == 'X': x, y, z = z, y, x
            elif axis == 'Y': x, y, z = x, z, y
            ring.append(bm.verts.new((cx + x, cy + y, cz + z)))
        rings.append(ring)
    for i in range(seg):
        a, b = rings[i], rings[(i + 1) % seg]
        for j in range(rseg):
            bm.faces.new((a[j], b[j], b[(j + 1) % rseg], a[(j + 1) % rseg]))


def transform_verts(verts, rot=None, loc=None, scale=None):
    from mathutils import Matrix
    M = Matrix.Identity(4)
    if scale is not None:
        M = Matrix.Diagonal((*scale, 1)) @ M
    if rot is not None:
        M = Matrix.Rotation(rot[2], 4, 'Z') @ Matrix.Rotation(rot[1], 4, 'Y') @ Matrix.Rotation(rot[0], 4, 'X') @ M
    if loc is not None:
        M = Matrix.Translation(loc) @ M
    for v in verts:
        v.co = M @ v.co


# ---------- node helpers -------------------------------------------------------
def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (700, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (400, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return m, nt.nodes, nt.links, bsdf, out


def sock(node, name, kind=None):
    """Enabled input socket by name (Mix nodes have several sockets with one name)."""
    for s in node.inputs:
        if s.name == name and s.enabled and (kind is None or s.type == kind):
            return s
    return node.inputs[name]


def osock(node, name):
    for s in node.outputs:
        if s.name == name and s.enabled:
            return s
    return node.outputs[name]


def mix_rgb(N, L, fac, a, b, blend='MIX'):
    m = N.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = blend
    fs = sock(m, 'Factor', 'VALUE')
    if isinstance(fac, (int, float)): fs.default_value = fac
    else: L.new(fac, fs)
    A, B = sock(m, 'A', 'RGBA'), sock(m, 'B', 'RGBA')
    if isinstance(a, tuple): A.default_value = a
    else: L.new(a, A)
    if isinstance(b, tuple): B.default_value = b
    else: L.new(b, B)
    return osock(m, 'Result')


def noise_tex(N, L, scale, detail=6.0, rough=0.6, vec=None, dims='3D'):
    n = N.new('ShaderNodeTexNoise')
    n.noise_dimensions = dims
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    if vec is not None: L.new(vec, n.inputs['Vector'])
    return n


def ramp(N, L, src, stops, interp='LINEAR'):
    r = N.new('ShaderNodeValToRGB')
    r.color_ramp.interpolation = interp
    els = r.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (pos, col) in zip(els, stops):
        e.position = pos
        e.color = col if len(col) == 4 else (*col, 1)
    L.new(src, r.inputs['Fac'])
    return r


def math_node(N, L, op, a, b=None, clamp=False):
    m = N.new('ShaderNodeMath'); m.operation = op; m.use_clamp = clamp
    if isinstance(a, (int, float)): m.inputs[0].default_value = a
    else: L.new(a, m.inputs[0])
    if b is not None:
        if isinstance(b, (int, float)): m.inputs[1].default_value = b
        else: L.new(b, m.inputs[1])
    return m.outputs[0]


def bump(N, L, height, strength=0.3, distance=0.05, normal=None):
    b = N.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = distance
    L.new(height, b.inputs['Height'])
    if normal is not None: L.new(normal, b.inputs['Normal'])
    return b.outputs['Normal']


def obj_coords(N):
    t = N.new('ShaderNodeTexCoord')
    return t.outputs['Object']


# ---------- material library (procedural, no downloads) ----------------------------
_MAT_CACHE = {}


def mat_lib(kind, wear=0.3, color=None, seed=0):
    """Returns a procedural material. kind: wood, darkwood, painted, steel, rust, gold, bronze,
    stone, marble, terracotta, burlap, plastic, glass, emissive, leather, concrete, rubber, sand, cloth."""
    key = (kind, round(wear, 2), tuple(round(c, 3) for c in color) if color else None, seed)
    m0 = _MAT_CACHE.get(key)
    if m0 is not None and m0.name in bpy.data.materials:
        return m0
    m, N, L, P, out = new_mat('ZICA %s' % kind.title())
    co = obj_coords(N)
    rnd = random.Random(seed)
    if kind in ('wood', 'darkwood'):
        mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 1, 8)
        L.new(co, mp.inputs['Vector'])
        w = N.new('ShaderNodeTexWave'); w.wave_type = 'BANDS'; w.bands_direction = 'Z' if hasattr(w, 'bands_direction') else w.bands_direction
        w.inputs['Scale'].default_value = 3.0; w.inputs['Distortion'].default_value = 7.0; w.inputs['Detail'].default_value = 3.0
        L.new(mp.outputs['Vector'], w.inputs['Vector'])
        base = color or ((0.32, 0.17, 0.07) if kind == 'wood' else (0.12, 0.06, 0.03))
        r = ramp(N, L, w.outputs['Fac'], [(0.0, tuple(c * 0.55 for c in base)), (1.0, base)])
        dirt = noise_tex(N, L, 3.0, 8, 0.6, co)
        col = mix_rgb(N, L, wear * 0.6, r.outputs['Color'], (0.05, 0.04, 0.03, 1), 'MULTIPLY')
        L.new(col, P.inputs['Base Color'])
        rr = ramp(N, L, dirt.outputs['Fac'], [(0.3, (0.45,) * 3), (0.8, (0.8,) * 3)])
        L.new(rr.outputs['Color'], P.inputs['Roughness'])
        L.new(bump(N, L, w.outputs['Fac'], 0.2, 0.02), P.inputs['Normal'])
    elif kind in ('painted', 'panel', 'steel', 'rust', 'gold', 'bronze'):
        base = {'painted': color or (0.12, 0.16, 0.08), 'panel': color or (0.8, 0.8, 0.8), 'steel': (0.55, 0.56, 0.58), 'rust': (0.32, 0.12, 0.04),
                'gold': (1.0, 0.72, 0.28), 'bronze': (0.62, 0.38, 0.16)}[kind]
        metallic = 0.0 if kind in ('painted', 'panel') else (0.3 if kind == 'rust' else 1.0)
        rough = {'painted': 0.45, 'panel': 0.35, 'steel': 0.3, 'rust': 0.85, 'gold': 0.22, 'bronze': 0.35}[kind]
        nz = noise_tex(N, L, 4.0 + rnd.random(), 10, 0.65, co)
        fine = noise_tex(N, L, 40.0, 6, 0.6, co)
        # wear mask: where the noise passes a threshold set by the Wear slider
        wm = ramp(N, L, nz.outputs['Fac'], [(max(0.0, 0.72 - wear * 0.45), (0, 0, 0)), (min(1.0, 0.76 - wear * 0.45), (1, 1, 1))])
        under = (0.36, 0.13, 0.04, 1) if kind in ('painted', 'steel') else ((0.3, 0.31, 0.33, 1) if kind == 'panel' else (0.15, 0.1, 0.05, 1))
        col = mix_rgb(N, L, wm.outputs['Color'], (*base, 1), under)
        col2 = mix_rgb(N, L, 0.25, col, fine.outputs['Color'], 'OVERLAY')
        L.new(col2, P.inputs['Base Color'])
        met = mix_rgb(N, L, wm.outputs['Color'], (metallic,) * 3 + (1,), (0.9, 0.9, 0.9, 1) if kind == 'panel' else (0.2, 0.2, 0.2, 1))
        L.new(met, P.inputs['Metallic'])
        rg = mix_rgb(N, L, wm.outputs['Color'], (rough,) * 3 + (1,), (0.9, 0.9, 0.9, 1))
        L.new(rg, P.inputs['Roughness'])
        L.new(bump(N, L, fine.outputs['Fac'], 0.08 + wear * 0.2, 0.01), P.inputs['Normal'])
    elif kind in ('stone', 'marble', 'concrete', 'terracotta', 'sand'):
        base = {'stone': (0.42, 0.37, 0.30), 'marble': (0.85, 0.83, 0.78), 'concrete': (0.45, 0.44, 0.42),
                'terracotta': (0.62, 0.27, 0.12), 'sand': (0.80, 0.62, 0.38)}[kind]
        base = color or base
        nz = noise_tex(N, L, 6.0, 12, 0.7, co)
        vor = N.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = 4.0
        L.new(co, vor.inputs['Vector'])
        r = ramp(N, L, nz.outputs['Fac'], [(0.25, tuple(c * 0.7 for c in base)), (0.75, base)])
        dark = 0.2 if kind in ('stone', 'concrete') else 0.75 - wear * 0.35
        crack = ramp(N, L, vor.outputs['Distance'], [(0.0, (dark,) * 3), (0.015 + wear * 0.04, (1,) * 3)])
        col = mix_rgb(N, L, 1.0, r.outputs['Color'], crack.outputs['Color'], 'MULTIPLY')
        if kind == 'marble':
            w = N.new('ShaderNodeTexWave'); w.inputs['Scale'].default_value = 2.0; w.inputs['Distortion'].default_value = 12
            L.new(co, w.inputs['Vector'])
            vein = ramp(N, L, w.outputs['Fac'], [(0.0, (0.55, 0.53, 0.5)), (0.12, (1, 1, 1))])
            col = mix_rgb(N, L, 1.0, col, vein.outputs['Color'], 'MULTIPLY')
        L.new(col, P.inputs['Base Color'])
        P.inputs['Roughness'].default_value = 0.35 if kind == 'marble' else 0.85
        h = math_node(N, L, 'ADD', nz.outputs['Fac'], crack.outputs['Alpha'])
        L.new(bump(N, L, h, 0.35, 0.05), P.inputs['Normal'])
    elif kind in ('burlap', 'cloth', 'leather'):
        base = color or {'burlap': (0.42, 0.33, 0.2), 'cloth': (0.6, 0.12, 0.1), 'leather': (0.22, 0.11, 0.05)}[kind]
        if kind == 'leather':
            vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 60; L.new(co, vor.inputs['Vector'])
            hgt = vor.outputs['Distance']
        else:
            w1 = N.new('ShaderNodeTexWave'); w1.inputs['Scale'].default_value = 60; L.new(co, w1.inputs['Vector'])
            w2 = N.new('ShaderNodeTexWave'); w2.inputs['Scale'].default_value = 60; w2.bands_direction = 'Y'; L.new(co, w2.inputs['Vector'])
            hgt = math_node(N, L, 'MULTIPLY', w1.outputs['Fac'], w2.outputs['Fac'])
        nz = noise_tex(N, L, 3.0, 6, 0.6, co)
        r = ramp(N, L, nz.outputs['Fac'], [(0.3, tuple(c * 0.75 for c in base)), (0.8, base)])
        L.new(r.outputs['Color'], P.inputs['Base Color'])
        P.inputs['Roughness'].default_value = 0.9 if kind != 'leather' else 0.55
        L.new(bump(N, L, hgt, 0.25, 0.01), P.inputs['Normal'])
    elif kind in ('plastic', 'rubber'):
        base = color or ((0.85, 0.85, 0.82) if kind == 'plastic' else (0.02, 0.02, 0.02))
        P.inputs['Base Color'].default_value = (*base, 1)
        P.inputs['Roughness'].default_value = 0.35 if kind == 'plastic' else 0.8
    elif kind == 'glass':
        P.inputs['Base Color'].default_value = (*(color or (0.8, 0.9, 1.0)), 1)
        P.inputs['Roughness'].default_value = 0.03
        P.inputs['Transmission Weight'].default_value = 1.0
        P.inputs['IOR'].default_value = 1.45
    elif kind == 'emissive':
        c = color or (0.2, 0.9, 1.0)
        P.inputs['Base Color'].default_value = (*c, 1)
        P.inputs['Emission Color'].default_value = (*c, 1)
        P.inputs['Emission Strength'].default_value = 12.0
    _MAT_CACHE[key] = m
    return m


def flat_mat(name, color, rough=0.6, metal=0.0, emit=0.0):
    m, N, L, P, out = new_mat(name)
    P.inputs['Base Color'].default_value = (*color, 1)
    P.inputs['Roughness'].default_value = rough
    P.inputs['Metallic'].default_value = metal
    if emit:
        P.inputs['Emission Color'].default_value = (*color, 1)
        P.inputs['Emission Strength'].default_value = emit
    return m


# ---------- world / sky / sun -----------------------------------------------------
def set_world(top=(0.25, 0.45, 0.85), horizon=(0.85, 0.75, 0.6), strength=1.0, stars=False):
    w = bpy.data.worlds.get('ZICA Sky') or bpy.data.worlds.new('ZICA Sky')
    try:
        w.use_nodes = True
    except Exception:
        pass
    bpy.context.scene.world = w
    nt = w.node_tree; nt.nodes.clear(); N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputWorld'); out.location = (600, 0)
    bg = N.new('ShaderNodeBackground'); bg.location = (400, 0)
    bg.inputs['Strength'].default_value = strength
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs['Vector'])
    r = ramp(N, L, sep.outputs['Z'], [(0.45, horizon), (0.75, top)])
    col = r.outputs['Color']
    if stars:
        vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 400
        L.new(tc.outputs['Generated'], vor.inputs['Vector'])
        st = ramp(N, L, vor.outputs['Distance'], [(0.0, (1, 1, 1)), (0.04, (0, 0, 0))])
        col = mix_rgb(N, L, 1.0, col, st.outputs['Color'], 'ADD')
    L.new(col, bg.inputs['Color'])
    L.new(bg.outputs['Background'], out.inputs['Surface'])
    return w


def add_sun(coll, elevation_deg=35, azimuth_deg=40, energy=4.0, color=(1.0, 0.92, 0.82), angle_deg=1.5):
    d = bpy.data.lights.new('Sun', 'SUN'); d.energy = energy; d.color = color
    try: d.angle = math.radians(angle_deg)
    except Exception: pass
    ob = link(bpy.data.objects.new('Sun', d), coll)
    ob.rotation_euler = (math.radians(90 - elevation_deg), 0, math.radians(azimuth_deg))
    return ob


def area_light(coll, name, loc, target, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.size = size; d.color = color
    ob = link(bpy.data.objects.new(name, d), coll)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    try: ob.visible_camera = False
    except Exception: pass
    return ob


def fog_box(coll, size, z, density, color=(0.8, 0.85, 1.0)):
    if density <= 0: return None
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    ob = obj_from_bm('Atmosphere', bm, coll)
    ob.scale = size; ob.location.z = z
    m = bpy.data.materials.new('ZICA Atmosphere')
    try: m.use_nodes = True
    except Exception: pass
    N, L = m.node_tree.nodes, m.node_tree.links; N.clear()
    out = N.new('ShaderNodeOutputMaterial')
    vol = N.new('ShaderNodeVolumePrincipled')
    vol.inputs['Density'].default_value = density
    vol.inputs['Color'].default_value = (*color, 1)
    L.new(vol.outputs['Volume'], out.inputs['Volume'])
    ob.data.materials.append(m)
    ob.hide_select = True
    try: ob.visible_shadow = False
    except Exception: pass
    return ob


# ---------- camera ------------------------------------------------------------------
def fcurves_of(action):
    """F-curves for both old (<=4.3) and layered (4.4+/5.x) actions."""
    try:
        return list(action.fcurves)
    except AttributeError:
        pass
    out = []
    try:
        for layer in action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out.extend(cb.fcurves)
    except Exception:
        pass
    return out


def make_linear(ob, cyclic=False):
    ad = ob.animation_data
    if not ad or not ad.action: return
    for fc in fcurves_of(ad.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        if cyclic:
            try: fc.modifiers.new('CYCLES')
            except Exception: pass


def orbit_camera(coll, target, radius, height, lens=35, frames=240, start_deg=-35, sweep_deg=60, dof=True):
    """Camera on a slow arc around a target. Animated by rotating a pivot (works in every version)."""
    scene = bpy.context.scene
    pivot = link(bpy.data.objects.new('Camera pivot', None), coll)
    pivot.location = target
    cd = bpy.data.cameras.new('Camera'); cd.lens = lens; cd.clip_end = 50000; cd.clip_start = 0.05
    cam = link(bpy.data.objects.new('Camera', cd), coll)
    cam.parent = pivot
    cam.location = (0, -radius, height)
    tgt = link(bpy.data.objects.new('Camera aim', None), coll)
    tgt.location = target
    c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    if dof:
        cd.dof.use_dof = True; cd.dof.focus_object = tgt; cd.dof.aperture_fstop = 5.6
    scene.frame_start, scene.frame_end = 1, frames
    pivot.rotation_euler = (0, 0, math.radians(start_deg)); pivot.keyframe_insert('rotation_euler', index=2, frame=1)
    pivot.rotation_euler = (0, 0, math.radians(start_deg + sweep_deg)); pivot.keyframe_insert('rotation_euler', index=2, frame=frames)
    pivot.rotation_euler = (0, 0, math.radians(start_deg))
    scene.camera = cam
    scene.frame_set(1)
    return cam


def frame_objects_camera(coll, objs, stage_coll, lens=50, elev_deg=18, az_deg=-35, margin=1.25):
    """Static product-shot camera that fits a list of objects."""
    mins = Vector((1e9,) * 3); maxs = Vector((-1e9,) * 3)
    bpy.context.view_layer.update()
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            mins = Vector(map(min, mins, w)); maxs = Vector(map(max, maxs, w))
    centre = (mins + maxs) / 2
    size = max((maxs - mins).length, 0.3)
    fov = 2 * math.atan(36 / (2 * lens))
    dist = size * margin / (2 * math.tan(fov / 2))
    e, a = math.radians(elev_deg), math.radians(az_deg)
    loc = centre + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    cd = bpy.data.cameras.new('Camera'); cd.lens = lens; cd.clip_end = 5000; cd.clip_start = 0.01
    cam = link(bpy.data.objects.new('Camera', cd), stage_coll)
    cam.location = loc
    cam.rotation_euler = (centre - loc).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    return cam, centre, size


# ---------- render quality -------------------------------------------------------------
def set_engine(scene, want):
    for n in ({'EEVEE': ['BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'], 'CYCLES': ['CYCLES']}[want]):
        try:
            scene.render.engine = n
            return n
        except TypeError:
            continue


def try_gpu(scene):
    scene.cycles.device = 'CPU'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for t in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                prefs.compute_device_type = t
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type == t]
                if devs:
                    for d in devs: d.use = True
                    scene.cycles.device = 'GPU'
                    return t
            except Exception:
                continue
    except Exception:
        pass
    return 'CPU'


QUALITY = {
    'PREVIEW':   ('EEVEE',  1280, 720,  16,  'Fast look on any PC'),
    'NORMAL':    ('EEVEE',  1920, 1080, 64,  'Good-looking, renders in seconds'),
    'GOOD':      ('CYCLES', 1920, 1080, 96,  'Ray-traced, denoised'),
    'CINEMATIC': ('CYCLES', 3840, 2160, 256, '4K ray-traced still'),
}


def apply_quality(level):
    scene = bpy.context.scene
    eng, w, h, samples, _ = QUALITY[level]
    set_engine(scene, eng)
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.fps = 24
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    if eng == 'EEVEE':
        ee = scene.eevee
        for a, v in (('taa_render_samples', samples), ('taa_samples', 16), ('use_shadows', True),
                     ('use_raytracing', level != 'PREVIEW'), ('use_gtao', True), ('volumetric_tile_size', '8')):
            try: setattr(ee, a, v)
            except Exception: pass
    else:
        cy = scene.cycles
        cy.samples = samples
        cy.preview_samples = 32
        for a, v in (('use_denoising', True), ('use_preview_denoising', True), ('use_adaptive_sampling', True),
                     ('adaptive_threshold', 0.02), ('max_bounces', 8), ('transparent_max_bounces', 8)):
            try: setattr(cy, a, v)
            except Exception: pass
        try_gpu(scene)
    return level


def rendered_view():
    """Rendered shading + look through the camera in every 3D viewport (live preview)."""
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type != 'VIEW_3D': continue
            sp = area.spaces[0]
            try: sp.shading.type = 'RENDERED'
            except Exception: pass
            for reg in area.regions:
                if reg.type == 'WINDOW':
                    try:
                        with bpy.context.temp_override(window=win, area=area, region=reg):
                            if sp.region_3d.view_perspective != 'CAMERA':
                                bpy.ops.view3d.view_camera()
                    except Exception:
                        pass


PREVIEW_IMAGE = 'ZICA Preview'


def render_preview(percent=40):
    """Render a quick still into an image the panel can show."""
    scene = bpy.context.scene
    if scene.camera is None:
        return None
    path = os.path.join(bpy.app.tempdir or '/tmp', 'zica_preview.png')
    old = (scene.render.resolution_percentage, scene.render.filepath)
    scene.render.resolution_percentage = percent
    scene.render.filepath = path
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        scene.render.resolution_percentage, scene.render.filepath = old
    img = bpy.data.images.get(PREVIEW_IMAGE)
    if img is None:
        img = bpy.data.images.load(path)
        img.name = PREVIEW_IMAGE
    else:
        img.filepath = path
        img.reload()
    try:
        img.preview_ensure()
        img.preview.reload()
    except Exception:
        pass
    return img


def rng(seed):
    return random.Random(seed)


def fbm(x, y, seed=0.0, octaves=6, basis='PERLIN_ORIGINAL'):
    return noise.fractal(Vector((x + seed, y + seed * 1.7, 0)), 0.5, 2.0, octaves, noise_basis=basis)


def ridged(x, y, seed=0.0, octaves=5):
    v, amp, f = 0.0, 1.0, 1.0
    for _ in range(octaves):
        n = 1 - abs(noise.noise(Vector((x * f + seed, y * f - seed, 0))))
        v += n * n * amp
        amp *= 0.5; f *= 2.0
    return v


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


# ---------------------------------------------------------------------------
#  UI: sidebar panels (N > ZICA), sliders, live update, preview render
# ---------------------------------------------------------------------------
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty, PointerProperty)

_PENDING = {'world': False, 'prop': False, 'surf': False}


def _schedule(kind):
    if _PENDING[kind]:
        return
    _PENDING[kind] = True

    def run():
        _PENDING[kind] = False
        try:
            s = bpy.context.scene.zica
            # go through the operators: they belong to whichever ZICA script provides that tool
            if kind == 'world':
                if s.last_built == 'IMAGE': bpy.ops.zica.image_world(live=True)
                else: bpy.ops.zica.build_world(live=True)
            elif kind == 'surf': bpy.ops.zica.build_surface(live=True)
            else: bpy.ops.zica.build_prop(shelf=(s.last_built == 'SHELF'), live=True)
        except Exception as e:
            print('ZICA live update skipped:', e)
        return None
    bpy.app.timers.register(run, first_interval=0.35)


def _live_world(self, ctx):
    if self.live and self.last_built == 'WORLD': _schedule('world')


def _live_prop(self, ctx):
    if self.live and self.last_built in ('PROP', 'SHELF'): _schedule('prop')


def _live_image(self, ctx):
    if self.live and self.last_built == 'IMAGE' and self.img_path: _schedule('world')


def _live_surf(self, ctx):
    if self.live and self.last_built == 'SURF': _schedule('surf')


# Name tables are kept here (not taken from the modules) so every ZICA script registers
# exactly the same settings and they can all be loaded together.
WORLD_NAMES = [('CITY', 'Neon City', 'Night skyline, stepped towers, glowing windows, traffic'),
               ('OLDTOWN', 'Ancient Old Town', 'Sandstone houses, domes, temple with columns, market, town wall'),
               ('ISLAND', 'Island Lagoon', 'Tropical island, palms, beach, clear water, sunset'),
               ('DESERT', 'Desert Canyon', 'Dunes, terraced mesas, canyons, cacti, rocks'),
               ('SNOW', 'Snowy Peaks', 'Ridged mountains, snow line, pine forest, lake'),
               ('FOREST', 'Forest Valley', 'Rolling hills, river, dense mixed forest, haze')]
PROP_NAMES = {'ANCIENT': [('COLUMN', 'Greek column'), ('AMPHORA', 'Amphora'), ('CHEST', 'Treasure chest'), ('TORCH', 'Torch'),
                          ('SHIELD', 'Round shield'), ('SWORD', 'Sword')],
              'MODERN': [('CHAIR', 'Chair'), ('TABLE', 'Table'), ('DESKLAMP', 'Desk lamp'), ('STREETLAMP', 'Street lamp'),
                         ('LAPTOP', 'Laptop'), ('MUG', 'Coffee mug')],
              'WAR': [('SANDBAGS', 'Sandbag wall'), ('DRUM', 'Oil drum'), ('AMMO', 'Ammo crate'), ('JERRYCAN', 'Jerrycan'),
                      ('HEDGEHOG', 'Czech hedgehog'), ('HELMET', 'Helmet')],
              'SCIFI': [('CORE', 'Energy core'), ('CARGO', 'Cargo crate'), ('HOLO', 'Holo pillar'), ('DRONE', 'Drone')]}
SURF_NAMES = [('BRICK', 'Brick wall', 'Running-bond bricks over mortar; damage knocks bricks out'),
              ('STONE', 'Castle stone wall', 'Rough-cut stones of random sizes, moss at the base'),
              ('CONCRETE', 'Concrete wall', 'Cast panels, tie holes, cracks; damage bites the edges and shows rebar'),
              ('PLASTER', 'Old plaster on brick', 'Plaster peels away and reveals the bricks underneath'),
              ('WOOD', 'Wooden planks', 'Plank fence / barn wall with gaps, nails and broken planks'),
              ('SCIFI', 'Sci-fi panels', 'Hull panels with glowing strips, vents and bolts')]
_PROP_ITEMS = {k: [(a, b, '') for a, b in v] for k, v in PROP_NAMES.items()}


def _prop_items(self, ctx):
    return _PROP_ITEMS.get(self.prop_cat, _PROP_ITEMS['ANCIENT'])


def _clear_others(keep):
    if keep != 'SURF':
        remove_colls('ZICA Surfaces')


def _quality_update(self, ctx):
    apply_quality(self.quality)


class ZICA_Settings(bpy.types.PropertyGroup):
    quality: EnumProperty(name='Render quality', update=_quality_update, default='PREVIEW', items=[
        ('PREVIEW', 'Preview (EEVEE 720p)', QUALITY['PREVIEW'][4]),
        ('NORMAL', 'Normal (EEVEE 1080p)', QUALITY['NORMAL'][4]),
        ('GOOD', 'Good (Cycles 1080p)', QUALITY['GOOD'][4]),
        ('CINEMATIC', 'Cinematic (Cycles 4K)', QUALITY['CINEMATIC'][4])])
    live: BoolProperty(name='Live update', default=True, description='Rebuild automatically when you move a slider')
    last_built: StringProperty(default='')
    # worlds
    world_type: EnumProperty(name='World', items=WORLD_NAMES, default='ISLAND', update=_live_world)
    world_size: FloatProperty(name='Size', default=1.0, min=0.5, max=2.0, update=_live_world)
    density: FloatProperty(name='Density', default=0.6, min=0.0, max=1.0, subtype='FACTOR', update=_live_world)
    detail: IntProperty(name='Detail', default=2, min=1, max=3, description='1 fast, 3 most detailed', update=_live_world)
    seed: IntProperty(name='Seed', default=7, min=0, max=9999, description='Every number is a different world', update=_live_world)
    sun_height: FloatProperty(name='Sun height', default=0.0, min=0.0, max=80.0, description='0 = the world\'s own time of day', update=_live_world)
    fog: FloatProperty(name='Haze', default=0.5, min=0.0, max=1.0, subtype='FACTOR', update=_live_world)
    water: FloatProperty(name='Water level', default=0.0, min=-1.0, max=1.0, update=_live_world)
    # image -> world
    img_path: StringProperty(name='Image', subtype='FILE_PATH', update=_live_image)
    img_mode: EnumProperty(name='Mode', default='TERRAIN', update=_live_image, items=[
        ('TERRAIN', 'Photo to terrain', 'Bright = high, dark = low. The photo paints the land; low parts flood'),
        ('MAP', 'Painted map to world', 'Blue water, green forest, yellow sand, grey city, white mountains, red roads'),
        ('MOSAIC', 'Pixel mosaic', 'Every pixel becomes a coloured block (3D pixel art)'),
        ('POSTCARD', '3D postcard', 'The photo becomes a 3D relief with a parallax camera move'),
        ('CITY', 'Photo to city', 'Bright = tall towers, the photo paints the buildings, blue = canals, green = parks')])
    img_res: IntProperty(name='Resolution', default=120, min=32, max=256, update=_live_image)
    img_height: FloatProperty(name='Height', default=30.0, min=1.0, max=80.0, update=_live_image)
    img_water: FloatProperty(name='Water level', default=0.18, min=0.0, max=1.0, subtype='FACTOR', update=_live_image)
    img_build: FloatProperty(name='Building height', default=1.0, min=0.1, max=3.0, update=_live_image)
    img_trees: FloatProperty(name='Trees', default=0.5, min=0.0, max=1.0, subtype='FACTOR', update=_live_image)
    img_invert: BoolProperty(name='Invert height', default=False, update=_live_image)
    # props
    prop_cat: EnumProperty(name='Era', default='ANCIENT', update=_live_prop, items=[
        ('ANCIENT', 'Ancient', 'Columns, amphora, chest, torch, shield, sword'),
        ('MODERN', 'Modern', 'Chair, table, lamps, laptop, mug'),
        ('WAR', 'War', 'Sandbags, drums, ammo crate, jerrycan, hedgehog, helmet'),
        ('SCIFI', 'Sci-fi', 'Energy core, cargo crate, holo pillar, drone')])
    prop_item: EnumProperty(name='Prop', items=_prop_items, update=_live_prop)
    prop_wear: FloatProperty(name='Wear / damage', default=0.35, min=0.0, max=1.0, subtype='FACTOR', update=_live_prop)
    prop_seed: IntProperty(name='Seed', default=3, min=0, max=9999, update=_live_prop)
    prop_detail: IntProperty(name='Detail', default=2, min=1, max=3, update=_live_prop)
    prop_scale: FloatProperty(name='Scale', default=1.0, min=0.25, max=4.0, update=_live_prop)
    # wall & surface engine
    surf_type: EnumProperty(name='Surface', items=SURF_NAMES, default='BRICK', update=_live_surf)
    surf_width: FloatProperty(name='Width', default=6.0, min=1.0, max=20.0, unit='LENGTH', update=_live_surf)
    surf_height: FloatProperty(name='Height', default=3.0, min=0.8, max=8.0, unit='LENGTH', update=_live_surf)
    surf_thickness: FloatProperty(name='Thickness', default=0.25, min=0.05, max=1.0, unit='LENGTH', update=_live_surf)
    surf_detail: IntProperty(name='Detail', default=2, min=1, max=3, description='1 fast, 3 most detailed', update=_live_surf)
    surf_damage: FloatProperty(name='Damage', default=0.35, min=0.0, max=1.0, subtype='FACTOR', description='Holes, missing pieces, cracks, rubble', update=_live_surf)
    surf_grime: FloatProperty(name='Grime / moss', default=0.4, min=0.0, max=1.0, subtype='FACTOR', description='Dirt at the base, rain streaks, moss', update=_live_surf)
    surf_seed: IntProperty(name='Seed', default=4, min=0, max=9999, update=_live_surf)
    surf_variant: IntProperty(name='Colour variant', default=0, min=0, max=1, description='Plaster colour / sci-fi light colour', update=_live_surf)
    surf_angle: FloatProperty(name='Camera angle', default=0.6, min=-1.0, max=1.0, description='Swing the camera for a raking, cinematic angle', update=_live_surf)
    surf_light: EnumProperty(name='Lighting', default='DAY', update=_live_surf, items=[
        ('STUDIO', 'Studio', 'Three soft lights, dark background'),
        ('DAY', 'Daylight', 'Sun and blue sky'),
        ('NIGHT', 'Night', 'One warm street lamp, starry sky')])


def _do_world(s):
    _clear_others('WORLD')
    if s.last_built == 'IMAGE':
        build_image_world(s.img_path, s.img_mode, s)
    else:
        dict((k, f) for k, n, d, f in WORLD_TYPES)[s.world_type](s)
    apply_quality(s.quality)


def _do_surface(s):
    build_surface(s.surf_type, s)
    apply_quality(s.quality)


def _do_prop(s):
    _clear_others('PROP')
    build_props(s.prop_cat, s.prop_item, s.prop_wear, s.prop_seed, s.prop_detail, s.prop_scale, shelf=False)
    apply_quality(s.quality)


class ZICA_OT_build_world(bpy.types.Operator):
    bl_idname = 'zica.build_world'; bl_label = 'Build world'
    bl_description = 'Build the selected world (clears the previous one)'
    bl_options = {'REGISTER', 'UNDO'}

    live: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, ctx):
        s = ctx.scene.zica; s.last_built = 'WORLD'
        _do_world(s); (None if self.live else rendered_view())
        self.report({'INFO'}, 'World built. Move a slider to change it live.')
        return {'FINISHED'}


class ZICA_OT_image_world(bpy.types.Operator):
    bl_idname = 'zica.image_world'; bl_label = 'Image to world'
    bl_description = 'Turn the chosen image into a 3D world'
    bl_options = {'REGISTER', 'UNDO'}

    live: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, ctx):
        s = ctx.scene.zica
        if not s.img_path:
            self.report({'ERROR'}, 'Pick an image first (or click "Make sample map")'); return {'CANCELLED'}
        s.last_built = 'IMAGE'
        _do_world(s); (None if self.live else rendered_view())
        return {'FINISHED'}


class ZICA_OT_sample_map(bpy.types.Operator):
    bl_idname = 'zica.sample_map'; bl_label = 'Make sample map'
    bl_description = 'Paints a demo map (lake, river, forest, city, mountains) and uses it'

    def execute(self, ctx):
        s = ctx.scene.zica
        path = os.path.join(bpy.app.tempdir or '/tmp', 'zica_sample_map.png')
        make_sample_map(path)
        s.img_mode = 'MAP'; s.img_path = path
        s.last_built = 'IMAGE'; _do_world(s); rendered_view()
        return {'FINISHED'}


class ZICA_OT_build_prop(bpy.types.Operator):
    bl_idname = 'zica.build_prop'; bl_label = 'Build prop'
    bl_options = {'REGISTER', 'UNDO'}
    shelf: BoolProperty(default=False)
    live: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, ctx):
        s = ctx.scene.zica; s.last_built = 'PROP' if not self.shelf else 'SHELF'
        _clear_others('PROP')
        build_props(s.prop_cat, s.prop_item, s.prop_wear, s.prop_seed, s.prop_detail, s.prop_scale, shelf=self.shelf)
        apply_quality(s.quality)
        if not self.live: rendered_view()
        return {'FINISHED'}


class ZICA_OT_build_surface(bpy.types.Operator):
    bl_idname = 'zica.build_surface'; bl_label = 'Build surface'
    bl_description = 'Build the selected wall / surface (clears the previous one)'
    bl_options = {'REGISTER', 'UNDO'}

    live: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, ctx):
        s = ctx.scene.zica; s.last_built = 'SURF'
        _do_surface(s); (None if self.live else rendered_view())
        self.report({'INFO'}, 'Surface built. Drag Damage or Grime to see it change.')
        return {'FINISHED'}


class ZICA_OT_look(bpy.types.Operator):
    bl_idname = 'zica.look'; bl_label = 'Live render view'
    bl_description = 'Look through the camera with rendered shading'

    def execute(self, ctx):
        rendered_view(); return {'FINISHED'}


class ZICA_OT_preview(bpy.types.Operator):
    bl_idname = 'zica.preview'; bl_label = 'Render preview'
    bl_description = 'Quick still at 40% size, shown in this panel'

    def execute(self, ctx):
        img = render_preview(40)
        if img is None:
            self.report({'ERROR'}, 'No camera yet: build a world or a prop first'); return {'CANCELLED'}
        for a in ctx.screen.areas: a.tag_redraw()
        return {'FINISHED'}


class ZICA_OT_render(bpy.types.Operator):
    bl_idname = 'zica.render'; bl_label = 'Render image'
    bl_description = 'Full render at the chosen quality (opens the render window)'

    def execute(self, ctx):
        apply_quality(ctx.scene.zica.quality)
        bpy.ops.render.render('INVOKE_DEFAULT')
        return {'FINISHED'}


class ZICA_OT_render_anim(bpy.types.Operator):
    bl_idname = 'zica.render_anim'; bl_label = 'Render animation'
    bl_description = 'Render the camera move to video frames (set an output folder first)'

    def execute(self, ctx):
        bpy.ops.render.render('INVOKE_DEFAULT', animation=True)
        return {'FINISHED'}


class _Base:
    bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'ZICA'


class ZICA_PT_main(_Base, bpy.types.Panel):
    bl_label = ZICA_TITLE

    def draw(self, ctx):
        s = ctx.scene.zica; col = self.layout.column(align=True)
        col.prop(s, 'quality', text='')
        col.prop(s, 'live')
        row = col.row(align=True)
        row.operator('zica.look', icon='SHADING_RENDERED')
        row.operator('zica.preview', icon='IMAGE_DATA')
        row = col.row(align=True)
        row.operator('zica.render', icon='RENDER_STILL')
        row.operator('zica.render_anim', icon='RENDER_ANIMATION', text='Animation')
        img = bpy.data.images.get(PREVIEW_IMAGE)
        if img and img.preview:
            self.layout.template_icon(icon_value=img.preview.icon_id, scale=9)


class ZICA_PT_worlds(_Base, bpy.types.Panel):
    bl_label = 'Worlds'

    def draw(self, ctx):
        s = ctx.scene.zica; L_ = self.layout
        L_.prop(s, 'world_type', text='')
        c = L_.column(align=True)
        for p in ('world_size', 'density', 'detail', 'seed', 'sun_height', 'fog', 'water'):
            c.prop(s, p, slider=p not in ('seed',))
        L_.operator('zica.build_world', icon='WORLD')


class ZICA_PT_image(_Base, bpy.types.Panel):
    bl_label = 'Image to World'

    def draw(self, ctx):
        s = ctx.scene.zica; L_ = self.layout
        L_.prop(s, 'img_mode', text='')
        L_.prop(s, 'img_path', text='')
        tips = {'TERRAIN': ('Bright pixels = high ground, dark = low.', 'The photo paints the land; low parts flood.'),
                'MAP': ('Paint a map: each COLOUR becomes a land type.', 'Try "Make sample map".'),
                'MOSAIC': ('Every pixel becomes a coloured block.', 'Best with logos and pixel art.'),
                'POSTCARD': ('The picture itself becomes a 3D relief.', 'Best with paintings and portraits.'),
                'CITY': ('Bright pixels = tall towers, colours paint them.', 'Blue = canals, green = parks.')}.get(s.img_mode, ())
        if tips:
            b = L_.box(); b.scale_y = 0.7
            for t in tips: b.label(text=t)
        c = L_.column(align=True)
        c.prop(s, 'img_res', slider=True); c.prop(s, 'img_height', slider=True)
        if s.img_mode == 'TERRAIN':
            c.prop(s, 'img_water', slider=True); c.prop(s, 'img_trees', slider=True); c.prop(s, 'img_invert')
        elif s.img_mode == 'MAP':
            c.prop(s, 'img_build', slider=True); c.prop(s, 'img_trees', slider=True)
            b = L_.box(); b.scale_y = 0.7
            for t in ('Blue = water   Green = forest', 'Yellow = sand   Grey/black = city', 'White = mountains   Red = roads'):
                b.label(text=t)
        elif s.img_mode == 'POSTCARD':
            c.prop(s, 'img_invert')
        elif s.img_mode == 'CITY':
            c.prop(s, 'img_build', slider=True)
        row = L_.row(align=True)
        row.operator('zica.image_world', icon='IMAGE_DATA')
        row.operator('zica.sample_map', icon='BRUSH_DATA')


class ZICA_PT_props(_Base, bpy.types.Panel):
    bl_label = 'Props'

    def draw(self, ctx):
        s = ctx.scene.zica; L_ = self.layout
        L_.prop(s, 'prop_cat', expand=True)
        L_.prop(s, 'prop_item', text='')
        c = L_.column(align=True)
        for p in ('prop_wear', 'prop_detail', 'prop_scale', 'prop_seed'):
            c.prop(s, p, slider=p != 'prop_seed')
        row = L_.row(align=True)
        row.operator('zica.build_prop', icon='MESH_MONKEY').shelf = False
        row.operator('zica.build_prop', text='Whole set', icon='OUTLINER_COLLECTION').shelf = True


class ZICA_PT_surfaces(_Base, bpy.types.Panel):
    bl_label = 'Walls & Surfaces'

    def draw(self, ctx):
        s = ctx.scene.zica; L_ = self.layout
        L_.prop(s, 'surf_type', text='')
        c = L_.column(align=True)
        for p in ('surf_width', 'surf_height', 'surf_thickness'):
            c.prop(s, p)
        c = L_.column(align=True)
        for p in ('surf_damage', 'surf_grime', 'surf_detail', 'surf_seed', 'surf_variant', 'surf_angle'):
            c.prop(s, p, slider=p not in ('surf_seed',))
        L_.prop(s, 'surf_light', expand=True)
        L_.operator('zica.build_surface', icon='MOD_BUILD')


_MODULE_CLASSES = {
    'worlds': (ZICA_OT_build_world, ZICA_PT_worlds),
    'image': (ZICA_OT_image_world, ZICA_OT_sample_map, ZICA_PT_image),
    'props': (ZICA_OT_build_prop, ZICA_PT_props),
    'surfaces': (ZICA_OT_build_surface, ZICA_PT_surfaces),
}
CLASSES = (ZICA_Settings, ZICA_OT_look, ZICA_OT_preview, ZICA_OT_render, ZICA_OT_render_anim, ZICA_PT_main) + \
    tuple(c for k in ('worlds', 'image', 'props', 'surfaces') if k in ZICA_MODULES for c in _MODULE_CLASSES[k])


def register():
    for c in CLASSES:
        try: bpy.utils.unregister_class(c)
        except Exception: pass
        bpy.utils.register_class(c)
    bpy.types.Scene.zica = PointerProperty(type=ZICA_Settings)


def unregister():
    del bpy.types.Scene.zica
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)


if __name__ == '__main__':
    register()
    print(ZICA_TITLE + ' ready: 3D Viewport > N > ZICA tab')
