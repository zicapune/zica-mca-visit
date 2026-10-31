# =====================================================================
#  ZICA WALL & SURFACE ENGINE  ·  Blender 5.2 LTS (also 4.4+)  ·  ZICA Pune
#  Real-geometry walls: brick, castle stone, concrete, old plaster, wood planks, sci-fi panels
#
#    WALLS    Brick · Castle stone · Concrete · Old plaster on brick · Wooden planks · Sci-fi panels
#    Sliders: Width, Height, Thickness, Damage, Grime/moss, Detail, Seed, Colour variant, Camera angle
#    Lighting: Studio · Daylight · Night
#    RENDER   Preview / Normal / Good / Cinematic, live render view, preview inside the panel
#
#  RUN:  Scripting tab > New > paste > Run Script (Alt+P), then 3D Viewport > N > ZICA tab.
#        Or Edit > Preferences > Add-ons > Install from Disk.
#  Every slider rebuilds live when "Live update" is on. Everything is procedural: no downloads.
# =====================================================================
bl_info = {"name": 'ZICA Wall & Surface Engine', "author": "ZICA Pune", "version": (2, 1, 0), "blender": (4, 4, 0),
           "location": "View3D > Sidebar > ZICA", "category": "3D View",
           "description": 'Real-geometry walls: brick, castle stone, concrete, old plaster, wood planks, sci-fi panels'}

import bpy, bmesh, math, random, os
from mathutils import Vector, noise
ZICA_TITLE = 'ZICA Wall & Surface Engine'
ZICA_MODULES = {'surfaces'}



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
