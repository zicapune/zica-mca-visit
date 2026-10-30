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
