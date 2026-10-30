# =====================================================================
#  ZICA WORLD BUILDER  —  one script, a few seconds, a whole world.
#  Blender 4.2 or newer (tested on 4.2 LTS).
#
#  HOW TO USE (live demo)
#   1. Blender → Scripting tab → Open this file → press Run Script (Alt+P).
#   2. In the 3D Viewport press N → open the "ZICA" tab on the right.
#   3. Click a world:  Neon City · Island Lagoon · Image → World
#   4. Optional: "Cinematic 4K settings" then F12 to render a still,
#      or "Fast preview" for a quick EEVEE look on a slow PC.
#
#  Every builder wipes the scene first, so you can click them in any order.
#  Everything is procedural: no downloads, no add-ons, no external files
#  (except the picture you choose for Image → World).
# =====================================================================

bl_info = {"name": "ZICA World Builder", "blender": (4, 2, 0), "category": "3D View"}

import bpy, bmesh, math, random
from mathutils import Vector, noise

# ---------------------------------------------------------------------
#  small helpers
# ---------------------------------------------------------------------

def wipe_scene():
    """Delete every object, mesh, material, light and camera so each world starts clean."""
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                 bpy.data.curves, bpy.data.images, bpy.data.node_groups):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)
    for c in list(bpy.context.scene.collection.children):
        bpy.data.collections.remove(c)


def new_collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def mesh_object(name, bm, coll=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me), coll)


def material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links


def shade_smooth(ob):
    for p in ob.data.polygons:
        p.use_smooth = True


def set_engine(scene, want):
    """Pick an engine name this Blender version accepts."""
    names = {'EEVEE': ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'], 'CYCLES': ['CYCLES']}[want]
    for n in names:
        try:
            scene.render.engine = n
            return n
        except TypeError:
            continue


def view_through_camera():
    """Rendered shading + look through the camera in every 3D viewport."""
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                sp = area.spaces[0]
                try:
                    sp.shading.type = 'RENDERED'
                except Exception:
                    pass
                for reg in area.regions:
                    if reg.type == 'WINDOW':
                        try:
                            with bpy.context.temp_override(window=win, area=area, region=reg):
                                bpy.ops.view3d.view_camera()
                        except Exception:
                            pass


def base_render_settings(scene, frames=240):
    scene.frame_start, scene.frame_end = 1, frames
    scene.render.fps = 24
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        try:
            scene.view_settings.view_transform = 'Filmic'
        except Exception:
            pass
    set_engine(scene, 'EEVEE')
    ee = scene.eevee
    for attr, val in (('use_raytracing', True), ('use_shadows', True), ('taa_render_samples', 32),
                      ('use_bloom', True), ('use_gtao', True), ('use_ssr', True), ('volumetric_tile_size', '8')):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass


def add_glare_compositor(scene, strength=0.6):
    """Soft bloom/glare in the compositor (works for EEVEE and Cycles, all 4.x versions)."""
    try:
        scene.use_nodes = True
        nt = scene.node_tree
        nt.nodes.clear()
        rl = nt.nodes.new('CompositorNodeRLayers')
        gl = nt.nodes.new('CompositorNodeGlare')
        gl.glare_type = 'FOG_GLOW'
        gl.quality = 'MEDIUM'
        gl.threshold = 0.9
        try:
            gl.mix = -1 + strength
        except Exception:
            pass
        out = nt.nodes.new('CompositorNodeComposite')
        nt.links.new(rl.outputs['Image'], gl.inputs['Image'])
        nt.links.new(gl.outputs['Image'], out.inputs['Image'])
        rl.location, gl.location, out.location = (-300, 0), (0, 0), (300, 0)
    except Exception as e:
        print('Compositor glare skipped:', e)


def camera_rig(path_points, target_points, frames, lens=32, coll=None, dof_target=None):
    """Camera that follows keyframed positions and always looks at a moving empty."""
    cam_data = bpy.data.cameras.new('Camera')
    cam_data.lens = lens
    cam_data.clip_end = 60000
    cam = link(bpy.data.objects.new('Camera', cam_data), coll)
    tgt = link(bpy.data.objects.new('Camera target', None), coll)
    tgt.empty_display_size = 2
    con = cam.constraints.new('TRACK_TO')
    con.target = tgt
    con.track_axis, con.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'
    n = len(path_points)
    for i, (p, t) in enumerate(zip(path_points, target_points)):
        f = 1 + round((frames - 1) * i / max(1, n - 1))
        cam.location = p
        tgt.location = t
        cam.keyframe_insert('location', frame=f)
        tgt.keyframe_insert('location', frame=f)
    for ob in (cam, tgt):
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'
                    kp.easing = 'AUTO'
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = dof_target or tgt
    cam_data.dof.aperture_fstop = 4.0
    bpy.context.scene.camera = cam
    return cam, tgt


def fog_box(coll, size, z, density, color):
    """Atmospheric haze inside a large invisible box (renders in EEVEE and Cycles)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    ob = mesh_object('Atmosphere', bm, coll)
    ob.scale = size
    ob.location.z = z
    m, N, L = material('Atmosphere')
    N.remove(N['Principled BSDF'])
    vol = N.new('ShaderNodeVolumePrincipled')
    vol.inputs['Density'].default_value = density
    vol.inputs['Color'].default_value = color
    L.new(vol.outputs['Volume'], N['Material Output'].inputs['Volume'])
    ob.data.materials.append(m)
    ob.hide_select = True
    try:
        ob.visible_shadow = False
    except Exception:
        pass
    return ob


def world_shader(name):
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    w.use_nodes = True
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (400, 0)
    return w, nt, out


# =====================================================================
#  WORLD 1 · NEON CITY  (night, wet streets, glowing windows, traffic)
# =====================================================================

def build_neon_city(seed=7):
    random.seed(seed)
    wipe_scene()
    scene = bpy.context.scene
    base_render_settings(scene, 240)
    coll = new_collection('Neon City')

    BLOCKS, BLOCK, ROAD = 16, 14.0, 6.0          # 16 x 16 city blocks
    PITCH = BLOCK + ROAD
    HALF = BLOCKS * PITCH / 2

    # --- ground: wet asphalt (dark, glossy, reflects the neon) ------------------
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=HALF + 40)
    ground = mesh_object('Wet asphalt', bm, coll)
    m, N, L = material('Wet asphalt')
    bsdf = N['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.01, 0.012, 0.018, 1)
    bsdf.inputs['Roughness'].default_value = 0.12
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.6
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.45, 0.6
    ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.05, 1)
    ramp.color_ramp.elements[1].color = (0.5, 0.5, 0.5, 1)
    L.new(nz.outputs['Fac'], ramp.inputs['Fac'])
    L.new(ramp.outputs['Color'], bsdf.inputs['Roughness'])          # puddles = smoother patches
    ground.data.materials.append(m)

    # --- all towers in ONE mesh (fast), each tower gets a random 'tint' value ----------
    bm = bmesh.new()
    tint = bm.faces.layers.float.new('tint')
    lit = bm.faces.layers.float.new('lit')
    heights = []
    for gx in range(BLOCKS):
        for gy in range(BLOCKS):
            cx = -HALF + PITCH * (gx + 0.5)
            cy = -HALF + PITCH * (gy + 0.5)
            d = Vector((cx, cy)).length / HALF                         # 0 centre → 1 edge
            # 1 to 4 towers per block, taller towards the centre
            n_t = random.choice((1, 1, 2, 4))
            sub = BLOCK / (2 if n_t == 4 else 1)
            spots = [(cx, cy)] if n_t == 1 else (
                [(cx - BLOCK / 4, cy), (cx + BLOCK / 4, cy)] if n_t == 2 else
                [(cx + sx * BLOCK / 4, cy + sy * BLOCK / 4) for sx in (-1, 1) for sy in (-1, 1)])
            for (tx, ty) in spots:
                w = (sub if n_t != 2 else BLOCK / 2) * random.uniform(0.62, 0.86)
                dpt = (sub if n_t != 2 else BLOCK) * random.uniform(0.62, 0.86)
                h = 6 + (1 - d) ** 2 * 120 * random.uniform(0.35, 1.0) + abs(noise.noise(Vector((tx * .03, ty * .03, 0)))) * 30
                heights.append(h)
                res = bmesh.ops.create_cube(bm, size=1.0)
                vs = res['verts']
                for v in vs:
                    v.co.x = tx + v.co.x * w
                    v.co.y = ty + v.co.y * dpt
                    v.co.z = (v.co.z + 0.5) * h
                tval, lval = random.random(), random.uniform(0.12, 0.5)
                for f in {f for v in vs for f in v.link_faces}:
                    f[tint] = tval
                    f[lit] = lval
    towers = mesh_object('Towers', bm, coll)

    # tower material: glass-and-concrete facade + emissive window grid in world space
    m, N, L = material('Neon facade')
    N.clear()
    out = N.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
    bsdf = N.new('ShaderNodeBsdfPrincipled'); bsdf.location = (600, 0)
    bsdf.inputs['Base Color'].default_value = (0.02, 0.025, 0.035, 1)
    bsdf.inputs['Metallic'].default_value = 0.6
    bsdf.inputs['Roughness'].default_value = 0.25
    geo = N.new('ShaderNodeNewGeometry'); geo.location = (-900, 0)
    sep = N.new('ShaderNodeSeparateXYZ'); sep.location = (-700, 0)
    L.new(geo.outputs['Position'], sep.inputs['Vector'])
    # window grid in world space: u runs along every wall, v climbs the floors
    add = N.new('ShaderNodeMath'); add.operation = 'ADD'; add.location = (-500, 60)
    L.new(sep.outputs['X'], add.inputs[0]); L.new(sep.outputs['Y'], add.inputs[1])
    u = N.new('ShaderNodeMath'); u.operation = 'MULTIPLY'; u.inputs[1].default_value = 0.55; u.location = (-320, 120)
    L.new(add.outputs['Value'], u.inputs[0])
    v = N.new('ShaderNodeMath'); v.operation = 'MULTIPLY'; v.inputs[1].default_value = 1 / 3.2; v.location = (-320, -20)
    L.new(sep.outputs['Z'], v.inputs[0])
    def frac_less(src, edge, y):
        fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; fr.location = (-140, y)
        L.new(src.outputs['Value'], fr.inputs[0])
        lt = N.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; lt.inputs[1].default_value = edge; lt.location = (20, y)
        L.new(fr.outputs['Value'], lt.inputs[0])
        return lt
    wu, wv = frac_less(u, 0.62, 140), frac_less(v, 0.55, -20)
    pane = N.new('ShaderNodeMath'); pane.operation = 'MULTIPLY'; pane.location = (180, 60)
    L.new(wu.outputs['Value'], pane.inputs[0]); L.new(wv.outputs['Value'], pane.inputs[1])
    # only some windows are lit: random value per window cell vs the tower's 'lit' share
    fu = N.new('ShaderNodeMath'); fu.operation = 'FLOOR'; fu.location = (-140, -200); L.new(u.outputs['Value'], fu.inputs[0])
    fv = N.new('ShaderNodeMath'); fv.operation = 'FLOOR'; fv.location = (-140, -300); L.new(v.outputs['Value'], fv.inputs[0])
    cell = N.new('ShaderNodeCombineXYZ'); cell.location = (20, -250)
    L.new(fu.outputs['Value'], cell.inputs['X']); L.new(fv.outputs['Value'], cell.inputs['Y'])
    wn = N.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '3D'; wn.location = (180, -250)
    L.new(cell.outputs['Vector'], wn.inputs['Vector'])
    attr_lit = N.new('ShaderNodeAttribute'); attr_lit.attribute_name = 'lit'; attr_lit.location = (180, -440)
    less = N.new('ShaderNodeMath'); less.operation = 'LESS_THAN'; less.location = (360, -300)
    L.new(wn.outputs['Value'], less.inputs[0]); L.new(attr_lit.outputs['Fac'], less.inputs[1])
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.location = (360, -100)
    L.new(pane.outputs['Value'], mul.inputs[0]); L.new(less.outputs['Value'], mul.inputs[1])
    # tower tint picks warm white, cyan or magenta windows
    attr_t = N.new('ShaderNodeAttribute'); attr_t.attribute_name = 'tint'; attr_t.location = (-120, 300)
    cr = N.new('ShaderNodeValToRGB'); cr.location = (80, 300)
    els = cr.color_ramp.elements
    els[0].position, els[0].color = 0.0, (1.0, 0.72, 0.38, 1)
    els[1].position, els[1].color = 0.55, (0.25, 0.95, 1.0, 1)
    e3 = els.new(0.8); e3.color = (1.0, 0.2, 0.75, 1)
    cr.color_ramp.interpolation = 'CONSTANT'
    L.new(attr_t.outputs['Fac'], cr.inputs['Fac'])
    L.new(cr.outputs['Color'], bsdf.inputs['Emission Color'])
    emi_strength = N.new('ShaderNodeMath'); emi_strength.operation = 'MULTIPLY'; emi_strength.location = (420, -100)
    emi_strength.inputs[1].default_value = 6.0
    L.new(mul.outputs['Value'], emi_strength.inputs[0])
    L.new(emi_strength.outputs['Value'], bsdf.inputs['Emission Strength'])
    L.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    towers.data.materials.append(m)

    # --- rooftop beacons and street lights (one mesh each) --------------------
    m_red, Nr, _ = material('Beacon red')
    Nr['Principled BSDF'].inputs['Emission Color'].default_value = (1, 0.05, 0.05, 1)
    Nr['Principled BSDF'].inputs['Emission Strength'].default_value = 25
    m_lamp, Nl, _ = material('Street lamp')
    Nl['Principled BSDF'].inputs['Emission Color'].default_value = (1, 0.65, 0.3, 1)
    Nl['Principled BSDF'].inputs['Emission Strength'].default_value = 18

    bm = bmesh.new()
    for i in range(BLOCKS + 1):
        rx = -HALF + PITCH * i - ROAD / 2
        for j in range(BLOCKS * 2):
            for (x, y) in ((rx, -HALF + j * PITCH / 2), (-HALF + j * PITCH / 2, rx)):
                r = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.35)
                for v in r['verts']:
                    v.co += Vector((x + 0.5, y + 0.5, 5.0))
    lamps = mesh_object('Street lights', bm, coll)
    lamps.data.materials.append(m_lamp)

    # --- traffic: 36 glowing cars driving the avenues (looping) ------------------
    m_head, Nh, _ = material('Headlights')
    Nh['Principled BSDF'].inputs['Emission Color'].default_value = (0.8, 0.9, 1.0, 1)
    Nh['Principled BSDF'].inputs['Emission Strength'].default_value = 30
    m_tail, Nt, _ = material('Taillights')
    Nt['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.08, 0.05, 1)
    Nt['Principled BSDF'].inputs['Emission Strength'].default_value = 30
    car_mesh = None
    for k in range(36):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        if car_mesh is None:
            me = bpy.data.meshes.new('Car'); bm.to_mesh(me); bm.free(); car_mesh = me
        else:
            bm.free()
        if not car_mesh.materials:
            car_mesh.materials.append(m_head)
        car = link(bpy.data.objects.new(f'Car {k:02d}', car_mesh), coll)
        car.scale = (2.2, 1.0, 0.5)
        car.material_slots[0].link = 'OBJECT'          # each car can have its own light colour
        lane = random.randint(1, BLOCKS - 1)
        along_x = k % 2 == 0
        road = -HALF + PITCH * lane - ROAD / 2 + (1.2 if random.random() < .5 else -1.2)
        start, end = (-HALF - 20, HALF + 20) if random.random() < .5 else (HALF + 20, -HALF - 20)
        car.material_slots[0].material = m_head if start < end else m_tail
        f0 = random.randint(-200, 0)
        for f, s in ((f0, start), (f0 + 260, end)):
            car.location = (s, road, 0.6) if along_x else (road, s, 0.6)
            car.rotation_euler = (0, 0, 0 if along_x else math.pi / 2)
            car.keyframe_insert('location', frame=f)
        for fc in car.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
            fc.modifiers.new('CYCLES')

    # --- night sky + thin fog --------------------------------------------------
    w, nt, out = world_shader('Neon night')
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.004, 0.006, 0.02, 1)
    bg.inputs['Strength'].default_value = 1.0
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    # fog lives in a big box over the city (a world-wide volume would also swallow the sky)
    fog_box(coll, size=(HALF * 2.6, HALF * 2.6, 180), z=90, density=0.0025, color=(0.55, 0.62, 1.0, 1))

    moon = bpy.data.lights.new('Moon', 'SUN'); moon.energy = 0.25; moon.color = (0.6, 0.7, 1.0)
    mo = link(bpy.data.objects.new('Moon', moon), coll); mo.rotation_euler = (math.radians(50), 0, math.radians(30))

    # --- camera: drop from the sky and glide down an avenue ---------------------
    avenue = -HALF + PITCH * (BLOCKS // 2) - ROAD / 2
    path = [(-HALF * 1.1, -HALF * 1.1, 160), (-HALF * 0.6, avenue - 20, 70), (-HALF * 0.2, avenue, 18), (HALF * 0.35, avenue, 9)]
    look = [(0, 0, 20), (0, avenue, 25), (HALF * 0.4, avenue, 20), (HALF, avenue, 30)]
    camera_rig(path, look, 240, lens=28, coll=coll)
    add_glare_compositor(scene, 0.75)
    scene.frame_set(1)
    view_through_camera()
    print('Neon City: %d towers, tallest %.0f m' % (len(heights), max(heights)))


# =====================================================================
#  WORLD 2 · ISLAND LAGOON  (terrain from noise, real water, forest, sunset)
# =====================================================================

def terrain_height(x, y, size, seed_off):
    p = Vector((x * 0.012 + seed_off, y * 0.012 + seed_off, 0))
    h = noise.fractal(p, 0.5, 2.0, 6, noise_basis='PERLIN_ORIGINAL')        # rolling hills
    ridge = 1 - abs(noise.noise(p * 0.7))                                  # sharp ridges
    d = Vector((x, y)).length / (size * 0.5)
    island = max(0.0, 1 - d ** 2.2)                                        # sea around the edges
    return (h * 18 + ridge ** 3 * 38) * island - 6


def build_island_lagoon(seed=11):
    random.seed(seed)
    wipe_scene()
    scene = bpy.context.scene
    base_render_settings(scene, 240)
    coll = new_collection('Island Lagoon')
    SIZE, RES = 400.0, 200
    off = seed * 13.37

    # --- terrain mesh ---------------------------------------------------------
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=RES, y_segments=RES, size=SIZE / 2)
    for v in bm.verts:
        v.co.z = terrain_height(v.co.x, v.co.y, SIZE, off)
    bm.normal_update()
    terrain = mesh_object('Terrain', bm, coll)
    shade_smooth(terrain)

    # terrain shader: colour by height and slope (sand → grass → rock → snow)
    m, N, L = material('Terrain')
    bsdf = N['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.85
    geo = N.new('ShaderNodeNewGeometry')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Position'], sep.inputs['Vector'])
    jitter = N.new('ShaderNodeTexNoise'); jitter.inputs['Scale'].default_value = 0.15
    mr = N.new('ShaderNodeMath'); mr.operation = 'MULTIPLY_ADD'
    mr.inputs[1].default_value = 4.0
    L.new(jitter.outputs['Fac'], mr.inputs[0]); L.new(sep.outputs['Z'], mr.inputs[2])
    rng = N.new('ShaderNodeMapRange')
    rng.inputs['From Min'].default_value, rng.inputs['From Max'].default_value = -6, 42
    L.new(mr.outputs['Value'], rng.inputs['Value'])
    ramp = N.new('ShaderNodeValToRGB'); E = ramp.color_ramp.elements
    E[0].position, E[0].color = 0.10, (0.70, 0.62, 0.42, 1)    # wet sand
    E[1].position, E[1].color = 0.20, (0.13, 0.30, 0.07, 1)    # grass
    for pos, col in ((0.45, (0.09, 0.20, 0.05, 1)), (0.62, (0.30, 0.27, 0.24, 1)), (0.86, (0.92, 0.94, 0.97, 1))):
        e = E.new(pos); e.color = col
    L.new(rng.outputs['Result'], ramp.inputs['Fac'])
    # steep slopes show rock regardless of height
    sepn = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Normal'], sepn.inputs['Vector'])
    steep = N.new('ShaderNodeMapRange')
    steep.inputs['From Min'].default_value, steep.inputs['From Max'].default_value = 0.75, 0.6
    L.new(sepn.outputs['Z'], steep.inputs['Value'])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs[7].default_value = (0.24, 0.22, 0.2, 1)
    L.new(steep.outputs['Result'], mix.inputs['Factor'])
    L.new(ramp.outputs['Color'], mix.inputs[6])
    L.new(mix.outputs[2], bsdf.inputs['Base Color'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35
    fine = N.new('ShaderNodeTexNoise'); fine.inputs['Scale'].default_value = 4.0; fine.inputs['Detail'].default_value = 8
    L.new(fine.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    terrain.data.materials.append(m)

    # --- water: clear, shallow turquoise near the shore, rippling -------------
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=SIZE * 60)      # reaches the horizon
    water = mesh_object('Lagoon water', bm, coll)
    water.location.z = 0.0
    m, N, L = material('Lagoon water')
    b = N['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.02, 0.35, 0.42, 1)
    b.inputs['Roughness'].default_value = 0.03
    b.inputs['IOR'].default_value = 1.333
    try:
        b.inputs['Transmission Weight'].default_value = 0.92
    except KeyError:
        b.inputs['Transmission'].default_value = 0.92
    wave = N.new('ShaderNodeTexWave'); wave.inputs['Scale'].default_value = 0.35; wave.inputs['Distortion'].default_value = 6
    wn = N.new('ShaderNodeTexNoise'); wn.inputs['Scale'].default_value = 2.5
    mx = N.new('ShaderNodeMath'); mx.operation = 'ADD'
    L.new(wave.outputs['Fac'], mx.inputs[0]); L.new(wn.outputs['Fac'], mx.inputs[1])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.12
    L.new(mx.outputs['Value'], bump.inputs['Height']); L.new(bump.outputs['Normal'], b.inputs['Normal'])
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    water.data.materials.append(m)
    # animate the ripples
    mapping = N.new('ShaderNodeMapping'); tc = N.new('ShaderNodeTexCoord')
    L.new(tc.outputs['Object'], mapping.inputs['Vector']); L.new(mapping.outputs['Vector'], wave.inputs['Vector']); L.new(mapping.outputs['Vector'], wn.inputs['Vector'])
    mapping.inputs['Location'].default_value = (0, 0, 0); mapping.inputs['Location'].keyframe_insert('default_value', frame=1)
    mapping.inputs['Location'].default_value = (6, 3, 0); mapping.inputs['Location'].keyframe_insert('default_value', frame=240)

    # --- forest: 600 trees as linked duplicates of one tree (cheap) ----------
    tm, TN, _ = material('Pine needles'); TN['Principled BSDF'].inputs['Base Color'].default_value = (0.03, 0.14, 0.04, 1)
    bm_, BN, _ = material('Bark'); BN['Principled BSDF'].inputs['Base Color'].default_value = (0.12, 0.07, 0.04, 1)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.25, radius2=0.18, depth=1.4,
                          matrix=__import__('mathutils').Matrix.Translation((0, 0, 0.7)))
    for i, (r, z) in enumerate(((1.6, 2.2), (1.25, 3.3), (0.85, 4.3))):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=9, radius1=r, radius2=0.0, depth=1.9,
                              matrix=__import__('mathutils').Matrix.Translation((0, 0, z)))
    tree_me = bpy.data.meshes.new('Pine'); bm.to_mesh(tree_me); bm.free()
    tree_me.materials.append(bm_); tree_me.materials.append(tm)
    for p in tree_me.polygons:
        p.material_index = 0 if p.center.z < 1.45 else 1
    forest = new_collection('Forest')
    placed = 0
    tries = 0
    while placed < 600 and tries < 9000:
        tries += 1
        x, y = random.uniform(-SIZE * .42, SIZE * .42), random.uniform(-SIZE * .42, SIZE * .42)
        z = terrain_height(x, y, SIZE, off)
        if not (2.0 < z < 24.0):
            continue
        dz = abs(terrain_height(x + 1, y, SIZE, off) - z) + abs(terrain_height(x, y + 1, SIZE, off) - z)
        if dz > 1.1:                                            # no trees on cliffs
            continue
        t = bpy.data.objects.new('Pine', tree_me)
        s = random.uniform(0.7, 1.5)
        t.location, t.scale, t.rotation_euler.z = (x, y, z - 0.2), (s, s, s * random.uniform(.9, 1.3)), random.uniform(0, 6.28)
        forest.objects.link(t)
        placed += 1

    # --- sunset sky + matching sun --------------------------------------------
    w, nt, out = world_shader('Sunset sky')
    sky = nt.nodes.new('ShaderNodeTexSky')
    try:
        sky.sky_type = 'NISHITA'
        sky.sun_elevation = math.radians(6)
        sky.sun_rotation = math.radians(215)
        sky.altitude = 200
        sky.air_density, sky.dust_density = 1.2, 2.5
    except Exception:
        pass
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.35
    nt.links.new(sky.outputs['Color'], bg.inputs['Color']); nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    sun = bpy.data.lights.new('Sun', 'SUN'); sun.energy = 3.5; sun.color = (1.0, 0.62, 0.38); sun.angle = math.radians(1.5)
    so = link(bpy.data.objects.new('Sun', sun), coll)
    so.rotation_euler = (math.radians(84), 0, math.radians(215 - 180))
    # (no fog box here: the Nishita sky already has its own atmosphere)

    # --- drone flight over the lagoon to the peak -------------------------------
    peak = max(terrain.data.vertices, key=lambda v: v.co.z).co.copy()
    # sweep around the island over the sea, always above the hills, slowly descending
    path, look = [], []
    for k in range(7):
        a = math.radians(200 + 22 * k)
        r = SIZE * (0.62 - 0.03 * k)
        path.append((math.cos(a) * r, math.sin(a) * r, 70 - 6 * k))
        look.append((peak.x * 0.6, peak.y * 0.6, peak.z * 0.45))
    camera_rig(path, look, 240, lens=24, coll=coll)
    add_glare_compositor(scene, 0.4)
    scene.frame_set(1)
    view_through_camera()
    print('Island Lagoon: %d trees, peak %.1f m' % (placed, peak.z))


# =====================================================================
#  WORLD 3 · IMAGE → WORLD  (any photo or painting becomes a 3D landscape)
#  Brightness becomes height, the picture's own colours paint the ground,
#  dark areas fill with water.
# =====================================================================

def build_world_from_image(path, seed=3):
    random.seed(seed)
    img = bpy.data.images.load(path, check_existing=False)
    W, H = img.size
    if W == 0 or H == 0:
        raise RuntimeError('Could not read that image')
    wipe_scene()
    img = bpy.data.images.load(path, check_existing=False)       # re-load: wipe removed it
    scene = bpy.context.scene
    base_render_settings(scene, 240)
    coll = new_collection('Image World')

    RES = 220                                                      # grid detail (keep ≤ 260 on slow PCs)
    aspect = W / H
    gx, gy = (RES, max(2, int(RES / aspect))) if aspect >= 1 else (max(2, int(RES * aspect)), RES)
    px = list(img.pixels)                                          # flat RGBA floats, bottom row first
    def sample(u, v):
        x = min(W - 1, int(u * (W - 1))); y = min(H - 1, int(v * (H - 1)))
        i = (y * W + x) * 4
        return px[i], px[i + 1], px[i + 2]

    SIZE_X = 200.0
    SIZE_Y = SIZE_X / aspect
    HEIGHT = 42.0
    bm = bmesh.new()
    col_layer = bm.loops.layers.color.new('Picture')
    verts = []
    lum_grid = []
    for j in range(gy + 1):
        row = []
        for i in range(gx + 1):
            u, v = i / gx, j / gy
            r, g, b = sample(u, v)
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            lum_grid.append(lum)
            # soften with a little blur from neighbours for smooth hills
            z = (lum ** 1.25) * HEIGHT - 3.0
            vtx = bm.verts.new(((u - .5) * SIZE_X, (v - .5) * SIZE_Y, z))
            row.append((vtx, (r, g, b)))
        verts.append(row)
    for j in range(gy):
        for i in range(gx):
            a, b_, c, d = verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]
            f = bm.faces.new((a[0], b_[0], c[0], d[0]))
            for loop, src in zip(f.loops, (a, b_, c, d)):
                r, g, b2 = src[1]
                loop[col_layer] = (r, g, b2, 1.0)
    # gentle smoothing so it reads as terrain, not as pixels
    bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.6, use_axis_z=True)
    bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.6, use_axis_z=True)
    bm.normal_update()
    land = mesh_object('Picture landscape', bm, coll)
    shade_smooth(land)

    m, N, L = material('Picture ground')
    bsdf = N['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.7
    attr = N.new('ShaderNodeVertexColor'); attr.layer_name = 'Picture'
    hsv = N.new('ShaderNodeHueSaturation'); hsv.inputs['Saturation'].default_value = 1.45; hsv.inputs['Value'].default_value = 0.95
    L.new(attr.outputs['Color'], hsv.inputs['Color']); L.new(hsv.outputs['Color'], bsdf.inputs['Base Color'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.3
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3
    L.new(nz.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    land.data.materials.append(m)

    # water fills the darkest valleys
    lum_sorted = sorted(lum_grid)
    sea = (lum_sorted[int(len(lum_sorted) * 0.22)] ** 1.25) * HEIGHT - 3.0 + 0.4
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=max(SIZE_X, SIZE_Y))
    water = mesh_object('Water', bm, coll); water.location.z = sea
    wm, WN, WL = material('Water')
    wb = WN['Principled BSDF']
    wb.inputs['Base Color'].default_value = (0.02, 0.18, 0.28, 1); wb.inputs['Roughness'].default_value = 0.04
    try:
        wb.inputs['Transmission Weight'].default_value = 0.85
    except KeyError:
        wb.inputs['Transmission'].default_value = 0.85
    wave = WN.new('ShaderNodeTexWave'); wave.inputs['Scale'].default_value = 0.5; wave.inputs['Distortion'].default_value = 5
    wbump = WN.new('ShaderNodeBump'); wbump.inputs['Strength'].default_value = 0.1
    WL.new(wave.outputs['Fac'], wbump.inputs['Height']); WL.new(wbump.outputs['Normal'], wb.inputs['Normal'])
    try:
        wm.surface_render_method = 'BLENDED'
    except Exception:
        pass
    water.data.materials.append(wm)

    # golden-hour light
    w, nt, out = world_shader('Image world sky')
    sky = nt.nodes.new('ShaderNodeTexSky')
    try:
        sky.sky_type = 'NISHITA'; sky.sun_elevation = math.radians(14); sky.sun_rotation = math.radians(140)
    except Exception:
        pass
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.3
    nt.links.new(sky.outputs['Color'], bg.inputs['Color']); nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    sun = bpy.data.lights.new('Sun', 'SUN'); sun.energy = 4; sun.color = (1, 0.8, 0.6)
    so = link(bpy.data.objects.new('Sun', sun), coll); so.rotation_euler = (math.radians(70), 0, math.radians(-40))

    # orbit around the new world
    R = max(SIZE_X, SIZE_Y) * 0.75
    path = [(math.cos(a) * R, math.sin(a) * R, 55 - 20 * k / 6) for k, a in enumerate([math.radians(-110 + 30 * t) for t in range(7)])]
    look = [(0, 0, 4)] * len(path)
    camera_rig(path, look, 240, lens=30, coll=coll)
    add_glare_compositor(scene, 0.35)
    scene.frame_set(1)
    view_through_camera()
    print('Image → World: %d × %d grid' % (gx, gy))


# =====================================================================
#  RENDER PRESETS
# =====================================================================

def preset_cinematic_4k():
    """Cycles, 4K UHD, medium quality that a normal PC can finish."""
    sc = bpy.context.scene
    set_engine(sc, 'CYCLES')
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 3840, 2160, 100
    cy = sc.cycles
    for attr, val in (('samples', 96), ('use_adaptive_sampling', True), ('adaptive_threshold', 0.03),
                      ('use_denoising', True), ('max_bounces', 6), ('diffuse_bounces', 2), ('glossy_bounces', 3),
                      ('transmission_bounces', 6), ('volume_bounces', 0), ('caustics_reflective', False),
                      ('caustics_refractive', False), ('use_fast_gi', False)):
        try:
            setattr(cy, attr, val)
        except Exception:
            pass
    try:
        cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    # use the GPU when Blender can find one
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                prefs.compute_device_type = backend
                prefs.get_devices()
                if any(d.type != 'CPU' for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    cy.device = 'GPU'
                    break
            except Exception:
                continue
    except Exception:
        pass
    sc.render.use_motion_blur = True
    sc.render.image_settings.file_format = 'PNG'
    print('Cinematic 4K preset set: Cycles, 96 samples + denoise.')


def preset_fast_preview():
    """EEVEE, 1080p: for a slow PC or a quick look."""
    sc = bpy.context.scene
    set_engine(sc, 'EEVEE')
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
    try:
        sc.eevee.taa_render_samples = 32
    except Exception:
        pass
    view_through_camera()


# =====================================================================
#  UI: a "ZICA" tab in the 3D viewport sidebar (press N)
# =====================================================================

class ZICA_OT_city(bpy.types.Operator):
    bl_idname, bl_label, bl_description = 'zica.neon_city', 'Neon City', 'Build a neon city at night'
    def execute(self, ctx):
        build_neon_city(); return {'FINISHED'}


class ZICA_OT_island(bpy.types.Operator):
    bl_idname, bl_label, bl_description = 'zica.island', 'Island Lagoon', 'Build an island with water, forest and a sunset'
    def execute(self, ctx):
        build_island_lagoon(); return {'FINISHED'}


class ZICA_OT_image(bpy.types.Operator):
    bl_idname, bl_label, bl_description = 'zica.image_world', 'Image → World', 'Pick a picture; it becomes a 3D landscape'
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_image: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    def invoke(self, ctx, event):
        ctx.window_manager.fileselect_add(self); return {'RUNNING_MODAL'}
    def execute(self, ctx):
        try:
            build_world_from_image(self.filepath)
        except Exception as e:
            self.report({'ERROR'}, str(e)); return {'CANCELLED'}
        return {'FINISHED'}


class ZICA_OT_cine(bpy.types.Operator):
    bl_idname, bl_label, bl_description = 'zica.cinematic', 'Cinematic 4K settings', 'Cycles, 4K, medium quality; then press F12'
    def execute(self, ctx):
        preset_cinematic_4k(); return {'FINISHED'}


class ZICA_OT_fast(bpy.types.Operator):
    bl_idname, bl_label, bl_description = 'zica.fast', 'Fast preview (EEVEE)', 'Quick look on a slower PC'
    def execute(self, ctx):
        preset_fast_preview(); return {'FINISHED'}


class ZICA_PT_panel(bpy.types.Panel):
    bl_label = 'ZICA World Builder'
    bl_space_type, bl_region_type, bl_category = 'VIEW_3D', 'UI', 'ZICA'
    def draw(self, ctx):
        col = self.layout.column(align=True)
        col.scale_y = 1.6
        col.operator('zica.neon_city', icon='LIGHT_AREA')
        col.operator('zica.island', icon='WORLD')
        col.operator('zica.image_world', icon='IMAGE_DATA')
        self.layout.separator()
        col = self.layout.column(align=True)
        col.operator('zica.fast', icon='SHADING_RENDERED')
        col.operator('zica.cinematic', icon='RENDER_STILL')
        self.layout.label(text='Then F12 = still, Ctrl+F12 = animation')


CLASSES = (ZICA_OT_city, ZICA_OT_island, ZICA_OT_image, ZICA_OT_cine, ZICA_OT_fast, ZICA_PT_panel)


def register():
    for c in CLASSES:
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
        bpy.utils.register_class(c)


if __name__ == '__main__':
    register()
    print('ZICA World Builder ready: 3D Viewport → N → ZICA tab')
