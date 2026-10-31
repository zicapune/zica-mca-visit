# =====================================================================
#  ZICA WORLDS  ·  Blender 5.2 LTS (also 4.4+)  ·  ZICA Pune
#  Landscapes and cities from code: island, desert, snow, forest, neon city, ancient old town
#
#    WORLDS   Neon City · Ancient Old Town · Island Lagoon · Desert Canyon · Snowy Peaks · Forest Valley
#    Sliders: Size, Density, Detail, Seed, Sun height, Haze, Water level
#    RENDER   Preview / Normal / Good / Cinematic, live render view, preview inside the panel
#
#  RUN:  Scripting tab > New > paste > Run Script (Alt+P), then 3D Viewport > N > ZICA tab.
#        Or Edit > Preferences > Add-ons > Install from Disk.
#  Every slider rebuilds live when "Live update" is on. Everything is procedural: no downloads.
# =====================================================================
bl_info = {"name": 'ZICA Worlds', "author": "ZICA Pune", "version": (2, 1, 0), "blender": (4, 4, 0),
           "location": "View3D > Sidebar > ZICA", "category": "3D View",
           "description": 'Landscapes and cities from code: island, desert, snow, forest, neon city, ancient old town'}

import bpy, bmesh, math, random, os
from mathutils import Vector, noise
ZICA_TITLE = 'ZICA Worlds'
ZICA_MODULES = {'worlds'}



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
    try:                                   # moving waves: 4D noise, W animated over the shot
        n.noise_dimensions = '4D'
        wv = n.inputs['W']
        wv.default_value = 0.0; wv.keyframe_insert('default_value', frame=1)
        wv.default_value = 3.0; wv.keyframe_insert('default_value', frame=360)
        for fc in fcurves_of(m.node_tree.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    except Exception:
        pass
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
    peak = max(h(x * size / 16, y * size / 16) for x in range(-7, 8) for y in range(-7, 8))
    trees = getattr(s, 'trees', s.density)
    n = int(trees * {'ISLAND': 900, 'DESERT': 220, 'SNOW': 900, 'FOREST': 1600}[kind] * (0.6 + 0.4 * s.detail))
    top = water + (peak - water) * getattr(s, 'tree_line', 0.7)      # trees stop at this height
    slope_max = getattr(s, 'tree_slope', 0.7)
    rocks = [asset_rock(c, rock_m, i) for i in range(3)]
    for r_ in rocks: r_.hide_render = True; r_.hide_viewport = True
    placed = 0
    if kind == 'ISLAND':
        palms = [asset_palm(c, palm_leaf, bark)]; broad = [asset_broadleaf(c, leaf, bark)]
        placed += scatter(c, palms, n // 3, size, h, lambda x, y, z, rr: (water + 0.4 < z < min(water + 4, top)) and slope_at(h, x, y) < slope_max * 0.7, s.seed)
        placed += scatter(c, broad, n, size, h, lambda x, y, z, rr: (water + 3 < z < top) and slope_at(h, x, y) < slope_max, s.seed + 1)
        scatter(c, rocks, int(n * 0.12), size, h, lambda x, y, z, rr: z > water - 0.5 and (z > top or slope_at(h, x, y) > slope_max), s.seed + 2, (0.6, 2.5))
    elif kind == 'DESERT':
        cac = [asset_cactus(c, flat_mat('ZICA Cactus', (0.15, 0.3, 0.12), 0.6))]
        placed += scatter(c, cac, n, size, h, lambda x, y, z, rr: slope_at(h, x, y) < slope_max * 0.35 and z < min(8, top), s.seed)
        scatter(c, rocks, n // 2, size, h, lambda x, y, z, rr: True, s.seed + 2, (0.6, 3.0))
    elif kind == 'SNOW':
        pines = [asset_pine(c, pine_leaf, bark)]
        placed += scatter(c, pines, n, size, h, lambda x, y, z, rr: (water + 1 < z < top) and slope_at(h, x, y) < slope_max * 0.85, s.seed)
        scatter(c, rocks, n // 4, size, h, lambda x, y, z, rr: z > water, s.seed + 2, (1.0, 4.0))
    else:
        pines = [asset_pine(c, pine_leaf, bark)]; broad = [asset_broadleaf(c, leaf, bark)]
        placed += scatter(c, pines + broad + broad, n, size, h, lambda x, y, z, rr: water + 0.6 < z < top and slope_at(h, x, y) < slope_max * 1.1, s.seed)
        scatter(c, rocks, n // 8, size, h, lambda x, y, z, rr: z > water - 1, s.seed + 2, (0.5, 2.2))
    bpy.context.scene['zica_info'] = 'Land read: water %.0f m, peak %.0f m. Trees grow up to %.0f m on slopes under %d deg: %d placed.' % (
        water, peak, top, round(math.degrees(math.atan(slope_max))), placed)
    elev, az, energy, scol = B['sun']
    add_sun(c, s.sun_height if s.sun_height else elev, az, energy, scol)
    set_world(*B['sky'], strength=1.0)
    fog_box(c, (size * 1.4, size * 1.4, 120), 40, 0.0015 * s.fog * (2 if kind == 'FOREST' else 1), B['fog'])
    shot(c, s, (0, 0, max(water, 0) + 2), size * (0.95 if kind == 'ISLAND' else 0.62),
         max(peak, 10) * 1.1 + size * (0.3 if kind == 'ISLAND' else 0.12),
         walk=lambda: terrain_flyover(c, size, h, water, peak))
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
    bpy.context.scene['zica_info'] = '%d x %d blocks, %d cars. Camera: %s.' % (BLOCKS, BLOCKS, int(20 + 40 * s.density), getattr(s, 'cam_move', 'ARC').lower())
    road_x = -HALF + PITCH * (BLOCKS // 2)          # centre line of the middle avenue
    shot(c, s, (0, 0, 35), HALF * 1.35, 30 + HALF * 0.12, lens=26, walk=lambda: city_walk(c, road_x, HALF))
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


# ---- camera moves -----------------------------------------------------------------------
def shot(c, s, target, radius, height, lens=30, walk=None):
    """ARC = slow arc, SPIN = full 360 turntable, WALK = cinematic walkthrough / flyover."""
    mode = getattr(s, 'cam_move', 'ARC')
    if mode == 'WALK' and walk is not None:
        walk()
    elif mode == 'SPIN':
        cam = orbit_camera(c, target, radius, height, lens=lens, frames=360, start_deg=-35, sweep_deg=360)
        make_linear(cam.parent)
    else:
        orbit_camera(c, target, radius, height, lens=lens, sweep_deg=60)


def _path_camera(c, pts, aims, lens, frames):
    """Camera that follows key points and looks at moving aim points."""
    scene = bpy.context.scene
    cd = bpy.data.cameras.new('Camera'); cd.lens = lens; cd.clip_end = 50000; cd.clip_start = 0.1
    cam = link(bpy.data.objects.new('Camera', cd), c)
    tgt = link(bpy.data.objects.new('Camera aim', None), c)
    con = cam.constraints.new('TRACK_TO'); con.target = tgt; con.track_axis = 'TRACK_NEGATIVE_Z'; con.up_axis = 'UP_Y'
    n = len(pts)
    for i, (p, a) in enumerate(zip(pts, aims)):
        f = 1 + round(i * (frames - 1) / (n - 1))
        cam.location = p; cam.keyframe_insert('location', frame=f)
        tgt.location = a; tgt.keyframe_insert('location', frame=f)
    scene.frame_start, scene.frame_end = 1, frames
    scene.camera = cam
    scene.frame_set(1)
    return cam


def city_walk(c, road_x, HALF):
    """Street-level run down the main avenue between the towers, then a crane up looking over the skyline."""
    y0, y1 = -HALF - 40, HALF * 0.5
    pts, aims = [], []
    for i in range(11):
        t = i / 10
        y = y0 + (y1 - y0) * t
        rise = (max(0, t - 0.65) / 0.35) ** 2
        z = 4.5 + 2.5 * math.sin(t * math.pi) + rise * 120
        x = road_x + math.sin(t * 6.0) * 1.0
        pts.append((x, y, z))
        aims.append((road_x + math.sin(t * 6.0 + 0.8) * 2, y + 60 + rise * 40, (z * 0.7 + 4) * (1 - rise) + 25 * rise))
    _path_camera(c, pts, aims, 22, 360)


def terrain_flyover(c, size, h, water, peak):
    """Low drone flight in from the sea, over the land, turning to keep the land in frame."""
    pts, aims = [], []
    R = size * 0.5
    for i in range(11):
        t = i / 10
        ang = math.radians(-120 + 150 * t)                 # curve around and across the land
        rad = R * (1.15 - 0.85 * math.sin(t * math.pi))
        x, y = math.cos(ang) * rad, math.sin(ang) * rad
        ground = max(h(x + dx, y + dy) for dx in (-10, 0, 10) for dy in (-10, 0, 10))
        z = max(ground, water) + 30 + 14 * math.sin(t * math.pi)
        pts.append((x, y, z))
        ahead = math.radians(-120 + 150 * min(1, t + 0.25))
        ax, ay = math.cos(ahead) * R * 0.35, math.sin(ahead) * R * 0.35
        aims.append((ax, ay, max(water, 0) + peak * 0.25))
    _path_camera(c, pts, aims, 24, 360)


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
    trees: FloatProperty(name='Trees', default=0.6, min=0.0, max=1.0, subtype='FACTOR', description='How many trees (they only grow where the land allows)', update=_live_world)
    tree_line: FloatProperty(name='Tree line', default=0.7, min=0.1, max=1.0, subtype='FACTOR', description='Highest point trees can grow (fraction of the peak height)', update=_live_world)
    tree_slope: FloatProperty(name='Max slope', default=0.7, min=0.15, max=1.5, description='Steeper ground than this stays bare rock', update=_live_world)
    cam_move: EnumProperty(name='Camera move', default='ARC', update=_live_world, items=[
        ('ARC', 'Slow arc', 'Gentle 60 degree arc'),
        ('SPIN', 'Spin 360', 'Full turn around the world, 15 s'),
        ('WALK', 'Walkthrough', 'City: street-level run down the avenue, then up over the skyline. Land: low drone flight')])
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


class ZICA_OT_cam_view(bpy.types.Operator):
    bl_idname = 'zica.cam_view'; bl_label = 'Camera view'
    bl_description = 'Look through the scene camera (Numpad 0)'

    def execute(self, ctx):
        for a in ctx.screen.areas:
            if a.type == 'VIEW_3D':
                a.spaces.active.region_3d.view_perspective = 'CAMERA'
                a.tag_redraw()
        return {'FINISHED'}


class ZICA_OT_play_cam(bpy.types.Operator):
    bl_idname = 'zica.play_cam'; bl_label = 'Play camera'
    bl_description = 'Look through the camera and play the camera move (press again or Esc to stop)'

    def execute(self, ctx):
        sc = ctx.scene
        if ctx.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
            return {'FINISHED'}
        bpy.ops.zica.cam_view()
        sc.frame_set(sc.frame_start)
        bpy.ops.screen.animation_play()
        return {'FINISHED'}


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
        terrain = s.world_type in ('ISLAND', 'DESERT', 'SNOW', 'FOREST')
        keys = ('world_size', 'density', 'detail', 'seed', 'sun_height', 'fog', 'water')
        if terrain:
            keys = ('world_size', 'trees', 'tree_line', 'tree_slope', 'detail', 'seed', 'sun_height', 'fog', 'water')
        for p in keys:
            c.prop(s, p, slider=p not in ('seed',))
        L_.prop(s, 'cam_move')
        L_.operator('zica.build_world', icon='WORLD')
        r = L_.row(align=True)
        r.operator('zica.play_cam', icon='PLAY')
        r.operator('zica.cam_view', icon='CAMERA_DATA')
        info = ctx.scene.get('zica_info')
        if info:
            b = L_.box().column(align=True)
            words, line = info.split(), ''
            for wd in words:
                if len(line) + len(wd) > 44:
                    b.label(text=line); line = wd
                else:
                    line = (line + ' ' + wd).strip()
            if line:
                b.label(text=line)


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
CLASSES = (ZICA_Settings, ZICA_OT_look, ZICA_OT_cam_view, ZICA_OT_play_cam, ZICA_OT_preview, ZICA_OT_render, ZICA_OT_render_anim, ZICA_PT_main) + \
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
