# =====================================================================
#  ZICA PROP FACTORY  ·  Blender 5.2 LTS (also 4.4+)  ·  ZICA Pune
#  Game-ready style props: ancient, modern, war, sci-fi, with wear and damage
#
#    PROPS    Ancient · Modern · War · Sci-fi (22 props)
#    Sliders: Wear/damage, Detail, Scale, Seed.  "Whole set" lines a whole era up with labels
#    RENDER   Preview / Normal / Good / Cinematic, live render view, preview inside the panel
#
#  RUN:  Scripting tab > New > paste > Run Script (Alt+P), then 3D Viewport > N > ZICA tab.
#        Or Edit > Preferences > Add-ons > Install from Disk.
#  Every slider rebuilds live when "Live update" is on. Everything is procedural: no downloads.
# =====================================================================
bl_info = {"name": 'ZICA Prop Factory', "author": "ZICA Pune", "version": (2, 1, 0), "blender": (4, 4, 0),
           "location": "View3D > Sidebar > ZICA", "category": "3D View",
           "description": 'Game-ready style props: ancient, modern, war, sci-fi, with wear and damage'}

import bpy, bmesh, math, random, os
from mathutils import Vector, noise
ZICA_TITLE = 'ZICA Prop Factory'
ZICA_MODULES = {'props'}



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
