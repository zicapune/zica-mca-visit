"""Builds the 3D scene from a picture, step by step.

build_steps() is a generator: every `yield` is a moment where the viewport can redraw and a
pop-up can explain what just happened. In presentation mode the runner waits between yields;
in fast mode (and in tests) it just runs straight through.
"""
import os, math, time
import numpy as np
import bpy
from mathutils import Vector, Quaternion, Euler
from . import imgops as io
from . import vision, analyze

COL = 'ZICA Image to 3D'
Y_NEAR = 5.0


# ------------------------------------------------------------------ image helpers
def load_rgb(path, long_side=1600):
    img = bpy.data.images.load(path, check_existing=True)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    rgb = np.flipud(px.reshape(h, w, 4))[..., :3].copy()
    if img.is_float or img.colorspace_settings.name.lower().startswith('linear'):
        rgb = io.lin_to_srgb(rgb)
    if max(w, h) > long_side:
        rgb = io.fit(rgb, long_side)
    return img, np.clip(rgb, 0, 1)


def make_image(name, arr, non_color=False):
    arr = np.clip(np.asarray(arr, np.float32), 0, 1)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, -1)
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), np.float32)], -1)
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
    img.pixels.foreach_set(np.flipud(arr).ravel())
    img.pack()
    return img


SCENE = 'ZICA Image to 3D'


def zscene(activate=False):
    """The add-on builds in its own scene, so the default cube / your own scene are never touched."""
    sc = bpy.data.scenes.get(SCENE)
    if sc is None:
        sc = bpy.data.scenes.new(SCENE)
    if activate:
        try:
            win = bpy.context.window or bpy.context.window_manager.windows[0]
            if win.scene != sc:
                win.scene = sc
        except Exception:
            pass
    return sc


def coll():
    c = bpy.data.collections.get(COL)
    if not c:
        c = bpy.data.collections.new(COL)
    sc = zscene()
    if c.name not in sc.collection.children:
        sc.collection.children.link(c)
    return c


def clear():
    c = bpy.data.collections.get(COL)
    if c:
        for o in list(c.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
    for coll_ in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.hair_curves):
        for d in list(coll_):
            if d.users == 0 and d.name.startswith('ZICA'):
                coll_.remove(d)
    for m in list(bpy.data.materials):
        if m.name.startswith('ZICA3D') and m.users == 0:
            bpy.data.materials.remove(m)
    for im in list(bpy.data.images):
        if im.name.startswith('ZICA3D') and im.users == 0:
            bpy.data.images.remove(im)


# ------------------------------------------------------------------ geometry
class Cam:
    def __init__(self, W, H, focal):
        self.W, self.H, self.f = W, H, focal
        if W >= H:
            self.tx = 18.0 / focal; self.tz = self.tx * H / W
        else:
            self.tz = 18.0 / focal; self.tx = self.tz * W / H

    def rays(self, u, v):
        """u, v arrays in 0..1 (v=0 top). Returns direction vectors with forward (Y) component = 1."""
        return np.stack([(2 * u - 1) * self.tx, np.ones_like(u), (1 - 2 * v) * self.tz], -1)


def disp_to_y(d, ratio):
    yf = Y_NEAR * ratio
    return 1.0 / (np.clip(d, 0, 1) * (1 / Y_NEAR - 1 / yf) + 1 / yf)


def grid_mesh(name, P, valid, UV, P0=None, back=None, tear=0.035, smooth=True):
    """P: (gh, gw, 3) positions; valid: (gh, gw) bool; UV: (gh, gw, 2).
    back: optional (P_back, P0_back) -> second surface with reversed faces (closed shell).
    Quads are dropped where depth jumps more than `tear` (so objects separate)."""
    gh, gw = valid.shape
    surfaces = [(P, P0, False)]
    if back is not None:
        surfaces.append((back[0], back[1], True))
    verts, verts0, uvs, faces = [], [], [], []
    off = 0
    for (PP, PP0, flip) in surfaces:
        idx = -np.ones((gh, gw), np.int64)
        n = int(valid.sum())
        idx[valid] = np.arange(n) + off
        verts.append(PP[valid]); uvs.append(UV[valid])
        verts0.append((PP0 if PP0 is not None else PP)[valid])
        a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
        ok = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
        Y = PP[..., 1]
        ys = np.stack([Y[:-1, :-1], Y[:-1, 1:], Y[1:, 1:], Y[1:, :-1]], -1)
        ok &= (ys.max(-1) / np.maximum(ys.min(-1), 1e-6)) < 1 + tear
        q = np.stack([a[ok], b[ok], c[ok], d[ok]], -1)
        if flip:
            q = q[:, ::-1]
        else:
            q = q[:, [0, 3, 2, 1]]   # counter-clockwise seen from the camera
        faces.append(q)
        off += n
    V = np.concatenate(verts); V0 = np.concatenate(verts0); U = np.concatenate(uvs); F = np.concatenate(faces)
    # drop unused vertices
    used = np.zeros(len(V), bool); used[F.ravel()] = True
    remap = -np.ones(len(V), np.int64); remap[used] = np.arange(used.sum())
    V, V0, U, F = V[used], V0[used], U[used], remap[F]
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    uvl = me.uv_layers.new(name='UVMap')
    li = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', li)
    uvl.data.foreach_set('uv', U[li].astype(np.float32).ravel())
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    coll().objects.link(ob)
    if back is not None:
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
        bm.to_mesh(me); bm.free()
        V0 = None   # vertex count changed; rebuild the flat key from rays
    # shape keys: Flat (the picture as a flat card) -> 3D
    ob.shape_key_add(name='Flat', from_mix=False)
    k3 = ob.shape_key_add(name='3D', from_mix=False)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    flat = co / np.maximum(co[:, 1:2], 1e-6) * FLAT_Y[0]
    ob.data.shape_keys.key_blocks['Flat'].data.foreach_set('co', flat.ravel())
    k3.data.foreach_set('co', co.ravel())
    k3.value = 1.0
    return ob


FLAT_Y = [Y_NEAR]
ORBIT = 12.0


def set_key(ob, v):
    if ob and ob.data and getattr(ob.data, 'shape_keys', None):
        ob.data.shape_keys.key_blocks['3D'].value = v


# ------------------------------------------------------------------ materials
def _out(node, ident):
    for s in node.outputs:
        if s.identifier == ident:
            return s
    return node.outputs[0]


def _inp(node, ident):
    for s in node.inputs:
        if s.identifier == ident or s.name == ident:
            return s
    raise KeyError(ident)


def surface_material(name, tex_img, reg_img, a, water_anim=False, bake=0.6):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    N.clear()
    out = N.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
    tex = N.new('ShaderNodeTexImage'); tex.image = tex_img; tex.extension = 'EXTEND'; tex.location = (-900, 200)
    tex.interpolation = 'Cubic'
    hs = N.new('ShaderNodeHueSaturation'); hs.name = 'ZLook'; hs.location = (-600, 200)
    L.new(tex.outputs['Color'], hs.inputs['Color'])
    gain = N.new('ShaderNodeMix'); gain.data_type = 'RGBA'; gain.blend_type = 'MULTIPLY'; gain.name = 'ZGain'
    gain.location = (-400, 200)
    _inp(gain, 'Factor_Float').default_value = 1.0
    L.new(hs.outputs['Color'], _inp(gain, 'A_Color'))
    _inp(gain, 'B_Color').default_value = (1, 1, 1, 1)
    col = _out(gain, 'Result_Color')
    em = N.new('ShaderNodeEmission'); em.location = (300, 300)
    L.new(col, em.inputs['Color'])
    bs = N.new('ShaderNodeBsdfPrincipled'); bs.location = (100, -100)
    L.new(col, bs.inputs['Base Color'])
    photo = a['style'] == 'photo'
    reg = N.new('ShaderNodeTexImage'); reg.image = reg_img; reg.extension = 'EXTEND'; reg.location = (-900, -300)
    sep = N.new('ShaderNodeSeparateColor'); sep.location = (-650, -300)
    L.new(reg.outputs['Color'], sep.inputs['Color'])

    def math(op, a_, b_, loc):
        n = N.new('ShaderNodeMath'); n.operation = op; n.location = loc
        for i, v in enumerate((a_, b_)):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]
    r1 = math('MULTIPLY', sep.outputs['Green'], -0.5, (-400, -200))
    rough = math('ADD', r1, 0.62 if photo else 0.8, (-250, -200))
    L.new(rough, bs.inputs['Roughness'])
    L.new(math('MULTIPLY', sep.outputs['Red'], 0.6, (-400, -320)), bs.inputs['Subsurface Weight'])
    bs.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.2)
    bs.inputs['Subsurface Scale'].default_value = 0.03
    L.new(math('MULTIPLY', sep.outputs['Green'], 0.45, (-400, -440)), bs.inputs['Coat Weight'])
    L.new(math('MULTIPLY', reg.outputs['Alpha'], 0.3, (-400, -560)), bs.inputs['Sheen Weight'])
    # surface bump from the picture's own detail (+ paper grain for 2D art)
    bw = N.new('ShaderNodeRGBToBW'); bw.location = (-600, -40)
    L.new(tex.outputs['Color'], bw.inputs['Color'])
    bump = N.new('ShaderNodeBump'); bump.location = (-150, -420)
    bump.inputs['Distance'].default_value = 0.004 if photo else 0.002
    L.new(math('ADD', math('MULTIPLY', sep.outputs['Blue'], 0.35, (-400, -680)), 0.04 if photo else 0.02, (-250, -680)),
          bump.inputs['Strength'])
    L.new(bw.outputs['Val'], bump.inputs['Height'])
    normal = bump.outputs['Normal']
    if not photo:
        nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; nz.location = (-400, -860)
        b2 = N.new('ShaderNodeBump'); b2.inputs['Strength'].default_value = 0.08; b2.location = (0, -700)
        L.new(nz.outputs['Fac'], b2.inputs['Height']); L.new(normal, b2.inputs['Normal'])
        normal = b2.outputs['Normal']
    if water_anim:
        nz = N.new('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'; nz.name = 'ZWaves'; nz.location = (-400, -1000)
        nz.inputs['Scale'].default_value = 60; nz.inputs['Detail'].default_value = 4
        w = nz.inputs['W']
        w.default_value = 0.0; w.keyframe_insert('default_value', frame=1)
        w.default_value = 6.0; w.keyframe_insert('default_value', frame=241)
        try:
            for fc in m.node_tree.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
        except Exception:
            pass
        b3 = N.new('ShaderNodeBump'); b3.location = (100, -900)
        L.new(nz.outputs['Fac'], b3.inputs['Height']); L.new(normal, b3.inputs['Normal'])
        L.new(math('MULTIPLY', sep.outputs['Green'], 0.5, (-150, -1000)), b3.inputs['Strength'])
        normal = b3.outputs['Normal']
    L.new(normal, bs.inputs['Normal'])
    mix = N.new('ShaderNodeMixShader'); mix.location = (600, 0); mix.name = 'ZMix'
    v = N.new('ShaderNodeValue'); v.name = 'ZBake'; v.label = 'Picture vs 3D light'; v.location = (300, 500)
    v.outputs[0].default_value = 1.0          # starts as the pure picture; 'relight' brings in 3D light
    m['zbake'] = bake
    L.new(v.outputs[0], mix.inputs['Fac'])
    L.new(bs.outputs['BSDF'], mix.inputs[1]); L.new(em.outputs['Emission'], mix.inputs[2])
    L.new(mix.outputs['Shader'], out.inputs['Surface'])
    m['zica3d'] = True
    return m


def flat_material(name, img, non_color=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; N.clear()
    t = N.new('ShaderNodeTexImage'); t.image = img; t.extension = 'EXTEND'
    e = N.new('ShaderNodeEmission'); o = N.new('ShaderNodeOutputMaterial')
    L.new(t.outputs['Color'], e.inputs['Color']); L.new(e.outputs['Emission'], o.inputs['Surface'])
    return m


def outline_material(rgb):
    m = bpy.data.materials.new('ZICA3D Ink outline'); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; N.clear()
    geo = N.new('ShaderNodeNewGeometry'); em = N.new('ShaderNodeEmission'); tr = N.new('ShaderNodeBsdfTransparent')
    mx = N.new('ShaderNodeMixShader'); o = N.new('ShaderNodeOutputMaterial')
    em.inputs['Color'].default_value = (*rgb, 1)
    L.new(geo.outputs['Backfacing'], mx.inputs['Fac'])
    L.new(em.outputs['Emission'], mx.inputs[1]); L.new(tr.outputs['BSDF'], mx.inputs[2])
    L.new(mx.outputs['Shader'], o.inputs['Surface'])
    m.use_backface_culling = False
    return m


def fur_material(bake):
    m = bpy.data.materials.new('ZICA3D Fur'); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; N.clear()
    at = N.new('ShaderNodeAttribute'); at.attribute_name = 'zcol'
    hs = N.new('ShaderNodeHueSaturation'); hs.name = 'ZLook'
    L.new(at.outputs['Color'], hs.inputs['Color'])
    gain = N.new('ShaderNodeMix'); gain.data_type = 'RGBA'; gain.blend_type = 'MULTIPLY'; gain.name = 'ZGain'
    _inp(gain, 'Factor_Float').default_value = 1.0
    L.new(hs.outputs['Color'], _inp(gain, 'A_Color')); _inp(gain, 'B_Color').default_value = (1, 1, 1, 1)
    hair = N.new('ShaderNodeBsdfHairPrincipled'); hair.parametrization = 'COLOR'
    L.new(_out(gain, 'Result_Color'), hair.inputs['Color'])
    hair.inputs['Roughness'].default_value = 0.35
    em = N.new('ShaderNodeEmission'); L.new(_out(gain, 'Result_Color'), em.inputs['Color'])
    mx = N.new('ShaderNodeMixShader'); mx.name = 'ZMix'
    v = N.new('ShaderNodeValue'); v.name = 'ZBake'; v.outputs[0].default_value = bake
    m['zbake'] = bake
    L.new(v.outputs[0], mx.inputs['Fac'])
    L.new(hair.outputs['BSDF'], mx.inputs[1]); L.new(em.outputs['Emission'], mx.inputs[2])
    o = N.new('ShaderNodeOutputMaterial'); L.new(mx.outputs['Shader'], o.inputs['Surface'])
    m['zica3d'] = True
    return m


def zica_materials():
    return [m for m in bpy.data.materials if m.get('zica3d') and m.users]


# ------------------------------------------------------------------ the build
class State:
    """Everything the steps share (kept on the module so the UI can read it)."""
    pass


S = State()


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def cam_to_world(v):
    """camera-space (x right, y up, z towards viewer) -> world (camera at origin looking +Y)."""
    return Vector((v[0], -v[2], v[1]))


def build_steps(path, opts, an=None, vis=None):
    """opts: dict(detail=320, style='AUTO'|'PHOTO'|'ILLUSTRATION', fur='AUTO'|'ON'|'OFF', relief=1.0,
    matte=True, loop=True, passes=5, outline=True). Yields (kind, ...) events for the runner."""
    t0 = time.time()
    scene = zscene(activate=True)
    yield ('step', 'Reading the picture', 'Loading every pixel into NumPy arrays (rows x columns x RGB).')
    img, rgb = load_rgb(path)
    H, W = rgb.shape[:2]
    cache = os.path.splitext(path)[0] + '.npz'
    if vis is None:
        vis = vision.see(rgb, cache)
    if an is None:
        an = analyze.analyze(rgb, vis)
    if opts.get('style', 'AUTO') != 'AUTO':
        an['style'] = 'photo' if opts['style'] == 'PHOTO' else 'illustration'
    photo = an['style'] == 'photo'
    fur = an['fur'] if opts.get('fur', 'AUTO') == 'AUTO' else opts['fur'] == 'ON'
    S.analysis = an; S.vis = vis; S.path = path
    S.border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).mean(0).tolist()
    clear()
    c = coll()

    cam = Cam(W, H, an['lens']['focal'])
    depth = io.blur(vis['depth'], max(1, W // 600))
    mask = vis['mask']
    subj = an['subject']
    ratio = an['ratio']
    relief = opts.get('relief', 1.0)

    # ---------- grid sampling
    N = int(opts.get('detail', 320))
    step = max(1.0, max(H, W) / N)
    gw, gh = int(W / step), int(H / step)
    gx = (np.arange(gw) + 0.5) / gw; gyy = (np.arange(gh) + 0.5) / gh
    U, V = np.meshgrid(gx, gyy)
    UV = np.stack([U, 1 - V], -1)
    R = cam.rays(U, V)
    D = io.resize(depth, gh, gw)
    M = io.resize(mask, gh, gw)
    Yall = disp_to_y(D, 1 + (ratio - 1) * relief)
    hard = M > 0.5
    if subj:
        FLAT_Y[0] = float(np.median(Yall[hard]))
    else:
        FLAT_Y[0] = float(np.median(Yall))
    yield ('info', 'Grid: %d x %d points = %s vertices per surface' % (gw, gh, format(gw * gh, ',')))

    # ---------- textures
    yield ('step', 'Separating subject and background',
           'Depth map (Depth Anything V2) + cut-out mask (IS-Net) tell us what is near and what is far.'
           if 'Smart' in vis['source'] else 'Depth and cut-out guessed from sharpness, colour and position.')
    tex_long = 1600
    rgb_t = io.fit(rgb, tex_long)
    th, tw = rgb_t.shape[:2]
    mask_t = io.resize(mask, th, tw)
    dep_t = io.resize(depth, th, tw)
    regmap = analyze.region_map(rgb, vis, an)
    reg_img = make_image('ZICA3D regions', regmap, non_color=True)
    pic_img = make_image('ZICA3D picture', rgb_t)

    # depth preview card (shown for a moment in presentation mode)
    S.depth_img = make_image('ZICA3D depth map', np.stack([dep_t] * 3, -1))
    S.depth_wide = None

    bake = 0.68 if photo else 0.82
    S.objects = {}

    # ---------- matte background (behind everything)
    near_g = (D > an['near_thr']) | hard
    near_t = io.resize(near_g.astype(np.float32), th, tw) > 0.5
    near_t = io.dilate(near_t, max(2, tw // 200))
    # margin: enough painted canvas that the orbit never sees past the edge
    far_y = float(Yall.max()) * 1.06 + 0.15
    half = min(cam.tx, cam.tz) * far_y
    # orbit angle: the far background may slide at most ~70% of its half-width
    S.orbit = float(np.clip(math.degrees(math.atan(0.7 * half / max(far_y - FLAT_Y[0], 1e-3))), 4.0, 12.0))
    shift = math.tan(math.radians(S.orbit + 6)) * (far_y - FLAT_Y[0])
    margin = float(np.clip(shift / max(half * 2, 1e-3) + 0.12, 0.2, 0.9))
    ox, oy = max(1, int(gw * margin)), max(1, int(gh * margin))
    mxf, myf = ox / gw, oy / gh
    pw, ph = int(round(tw * mxf)), int(round(th * myf))
    # 1) paint the holes inside the frame, 2) extend past the frame by mirroring (natural texture),
    #    softened more the further it gets from the frame edge
    wgt_in = (~near_t).astype(np.float32)
    if wgt_in.sum() < 50:
        wgt_in[:] = 1.0
    filled = io.push_pull(rgb_t, wgt_in)
    soft = io.blur(filled, max(2, tw // 120))
    hb = io.blur(1 - wgt_in, max(2, tw // 150))[..., None]
    filled = filled * (1 - hb) + soft * hb                        # painterly smoothing inside the painted areas
    matte = np.pad(filled, ((ph, ph), (pw, pw), (0, 0)), mode='symmetric')
    yy_, xx_ = np.mgrid[0:matte.shape[0], 0:matte.shape[1]]
    dx = np.maximum(np.maximum(pw - xx_, xx_ - (pw + tw - 1)), 0) / max(pw, 1)
    dy = np.maximum(np.maximum(ph - yy_, yy_ - (ph + th - 1)), 0) / max(ph, 1)
    far = np.clip(np.maximum(dx, dy), 0, 1)[..., None].astype(np.float32)
    matte = matte * (1 - far) + io.blur(matte, max(3, tw // 60)) * far
    wgt = np.pad(wgt_in, ((ph, ph), (pw, pw)), mode='constant', constant_values=1.0)
    holey = np.pad(rgb_t, ((ph, ph), (pw, pw), (0, 0)), mode='symmetric') * (1 - far) + far * matte
    holey[np.pad(wgt_in, ((ph, ph), (pw, pw)), mode='constant', constant_values=1.0) < 0.5] = np.array([0.05, 0.05, 0.06])
    matte_img = make_image('ZICA3D matte painting', matte)
    holey_img = make_image('ZICA3D matte holes', holey)
    # matte geometry: extended grid
    mgw, mgh = gw + 2 * ox, gh + 2 * oy
    mu = (np.arange(mgw) - ox + 0.5) / gw
    mv = (np.arange(mgh) - oy + 0.5) / gh
    MU, MV = np.meshgrid(mu, mv)
    Dfill = io.push_pull(D, (~near_g).astype(np.float32)) if (~near_g).sum() > 10 else D
    Dm = io.blur(np.pad(Dfill, ((oy, oy), (ox, ox)), mode='symmetric'), 2)
    Ym = disp_to_y(Dm, 1 + (ratio - 1) * relief) * 1.06 + 0.15
    far_floor = float(np.percentile(Yall[~near_g], 40)) if (~near_g).any() else float(Yall.max())
    Ym = np.maximum(Ym, far_floor * 1.02)
    Pm = cam.rays(MU, MV) * Ym[..., None]
    UVm = np.stack([(MU * tw + pw) / (tw + 2 * pw), 1 - (MV * th + ph) / (th + 2 * ph)], -1)
    matte_ob = grid_mesh('ZICA Matte background', Pm, np.ones((mgh, mgw), bool), UVm, tear=10)
    mm = surface_material('ZICA3D Matte', matte_img, reg_img, an, bake=min(1.0, bake + 0.25))
    # matte uses its own UV space; regions sampled from picture UV aren't aligned -> neutralise region map
    for n in mm.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image == reg_img:
            n.mute = True
    # show the holes first, then paint them (presentation)
    hole_tex = mm.node_tree.nodes.new('ShaderNodeTexImage'); hole_tex.image = holey_img; hole_tex.name = 'ZHoles'
    hole_tex.extension = 'EXTEND'
    mixh = mm.node_tree.nodes.new('ShaderNodeMix'); mixh.data_type = 'RGBA'; mixh.name = 'ZPaint'
    hs = mm.node_tree.nodes['ZLook']
    main_tex = [n for n in mm.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image == matte_img][0]
    mm.node_tree.links.new(hole_tex.outputs['Color'], _inp(mixh, 'A_Color'))
    mm.node_tree.links.new(main_tex.outputs['Color'], _inp(mixh, 'B_Color'))
    mm.node_tree.links.new(_out(mixh, 'Result_Color'), hs.inputs['Color'])
    _inp(mixh, 'Factor_Float').default_value = 0.0
    matte_ob.data.materials.append(mm)
    S.objects['matte'] = matte_ob

    # ---------- scene relief (everything except the subject), torn at depth jumps.
    # It continues ~12% past the frame (mirrored) so orbiting never shows its edge.
    sx, sy = max(1, int(gw * 0.12)), max(1, int(gh * 0.12))
    Dp = np.pad(D, ((sy, sy), (sx, sx)), mode='symmetric')
    validp = np.pad(~hard if subj else np.ones_like(hard), ((sy, sy), (sx, sx)), mode='constant', constant_values=True)
    up = (np.arange(gw + 2 * sx) - sx + 0.5) / gw
    vp = (np.arange(gh + 2 * sy) - sy + 0.5) / gh
    UP, VP = np.meshgrid(up, vp)
    Ps = cam.rays(UP, VP) * disp_to_y(Dp, 1 + (ratio - 1) * relief)[..., None]
    tpx, tpy = int(round(tw * sx / gw)), int(round(th * sy / gh))
    wide = np.pad(rgb_t, ((tpy, tpy), (tpx, tpx), (0, 0)), mode='symmetric')
    rh, rw = regmap.shape[:2]
    rpx, rpy = int(round(rw * sx / gw)), int(round(rh * sy / gh))
    reg_wide = np.pad(regmap, ((rpy, rpy), (rpx, rpx), (0, 0)), mode='symmetric')
    UVp = np.stack([(UP * tw + tpx) / (tw + 2 * tpx), 1 - (VP * th + tpy) / (th + 2 * tpy)], -1)
    water = bool(photo and 'water' in an['regions'])
    scene_ob = None
    if validp.sum() > 16:
        scene_ob = grid_mesh('ZICA Scene relief', Ps, validp, UVp, tear=0.015 + 0.006 * ratio)
        sm = surface_material('ZICA3D Scene', make_image('ZICA3D picture wide', wide),
                              make_image('ZICA3D regions wide', reg_wide, non_color=True), an, water_anim=water, bake=bake)
        scene_ob.data.materials.append(sm)
        S.objects['scene'] = scene_ob
        dw = np.pad(dep_t, ((tpy, tpy), (tpx, tpx)), mode='symmetric')
        S.depth_wide = make_image('ZICA3D depth map wide', np.stack([dw] * 3, -1))

    # ---------- subject: front from depth, rounded back from the silhouette
    subj_ob = None
    S.subject_center = Vector((0, FLAT_Y[0], 0))
    S.subject_size = 2 * cam.tx * FLAT_Y[0]
    if subj:
        hm = io.largest_component(hard, keep_frac=0.3)
        dt = io.dist_inside(hm, maxd=max(gw, gh))
        ys, xs = np.nonzero(hm)
        sw = (xs.max() - xs.min() + 1) / gw * 2 * cam.tx * FLAT_Y[0]
        sh = (ys.max() - ys.min() + 1) / gh * 2 * cam.tz * FLAT_Y[0]
        size = max(sw, sh)
        Yf = Yall.copy()
        rng = np.percentile(Yf[hm], 98) - np.percentile(Yf[hm], 2)
        target = np.clip(rng, 0.22 * min(sw, sh), 0.55 * min(sw, sh)) * relief * (1.0 if photo else 0.6)
        ymed = float(np.median(Yf[hm]))
        Yf = ymed + (Yf - ymed) * (target / max(rng, 1e-6))
        ring = hm & (dt <= 1.5)
        yedge = float(np.median(Yf[ring])) if ring.any() else ymed
        edge = max(2.0, 0.04 * max(gw, gh))
        wgt_e = np.clip((dt - 1) / edge, 0, 1); wgt_e = wgt_e * wgt_e * (3 - 2 * wgt_e)
        Yf = yedge + (Yf - yedge) * wgt_e
        dmax = max(np.percentile(dt[hm], 95), 1.0)
        T = (0.38 if photo else 0.22) * min(sw, sh) * relief * np.sqrt(np.clip((dt - 1) / dmax, 0, 1))
        Yb = np.maximum(Yf, yedge) + T + 0.002 * size * (dt > 1.5)   # the back always stays behind the front
        Pf = R * Yf[..., None]; Pb = R * Yb[..., None]
        # subject texture: grow subject colours outward so edges carry no background halo
        sub_w = (mask_t > 0.6).astype(np.float32)
        sub_rgb = io.push_pull(rgb_t, sub_w) if sub_w.sum() > 10 else rgb_t
        sub_img = make_image('ZICA3D subject', sub_rgb)
        subj_ob = grid_mesh('ZICA Subject', Pf, hm, UV, back=(Pb, None), tear=10)
        smat = surface_material('ZICA3D Subject', sub_img, reg_img, an, bake=bake)
        subj_ob.data.materials.append(smat)
        S.objects['subject'] = subj_ob
        S.subject_center = Vector(cam_to_world((0, 0, 0))) + Vector(
            (float(np.mean(Pf[hm][:, 0])), ymed, float(np.mean(Pf[hm][:, 2]))))
        S.subject_size = size
        S.sub = dict(hm=hm, dt=dt, Pf=Pf, Pb=Pb, rgb=sub_rgb, size=size, gw=gw, gh=gh)
        if not photo and opts.get('outline', False):
            ink = np.array(an['light']['shadow']) * 0.35
            om = outline_material(io.srgb_to_lin(ink).tolist())
            subj_ob.data.materials.append(om)
            sol = subj_ob.modifiers.new('Ink outline', 'SOLIDIFY')
            sol.thickness = -0.005 * size; sol.use_flip_normals = True; sol.material_offset = 1
            sol.use_rim = False

    # start everything flat (the picture), then animate into 3D
    for ob in (matte_ob, scene_ob, subj_ob):
        set_key(ob, 0.0)
    S.flat_card = True
    S.cam = cam

    # ---------- camera (matches the picture exactly from frame 1)
    cd = bpy.data.cameras.new('ZICA Camera'); cd.lens = an['lens']['focal']; cd.sensor_fit = 'AUTO'; cd.sensor_width = 36
    cd.clip_start = 0.05; cd.clip_end = 500
    camob = bpy.data.objects.new('ZICA Camera', cd); c.objects.link(camob)
    camob.rotation_euler = (math.pi / 2, 0, 0)
    scene.camera = camob
    scene.render.resolution_x, scene.render.resolution_y = (1920, int(1920 * H / W)) if W >= H else (int(1920 * W / H), 1920)
    scene.render.resolution_percentage = 50
    piv = bpy.data.objects.new('ZICA Orbit pivot', None); c.objects.link(piv)
    piv.location = S.subject_center
    camob.parent = piv
    from mathutils import Matrix
    camob.matrix_parent_inverse = Matrix.Translation(piv.location).inverted()
    S.camera = camob; S.pivot = piv

    yield ('view_side', None)
    yield ('show_depth', [o for o in (scene_ob, subj_ob) if o], 2.2)
    yield ('step', 'Lifting every pixel into 3D',
           'Each pixel is pushed along its camera ray to its depth: from the camera it still looks like the photo, from the side it is 3D.')
    yield ('animate_keys', [o for o in (matte_ob, scene_ob, subj_ob) if o], 1.8)
    if subj:
        yield ('step', 'Rounding the back of the subject',
               'Distance from the silhouette edge gives the thickness, so the back is round instead of a flat cut-out.')
    yield ('step', 'Painting the matte background',
           'The holes left behind the subject are filled from the surrounding colours (push-pull inpainting) and the canvas is extended %d%% past each edge.' % round(margin * 100))
    yield ('paint_matte', mm, 1.2)

    # ---------- materials
    mats = [l for l in an['plan'] if l.startswith('Materials')]
    yield ('step', 'Materials from the picture', mats[0] if mats else '')
    yield ('relight', zica_materials(), bake, 1.0)

    # ---------- fur
    if fur and subj:
        yield ('step', 'Growing fur', 'Thousands of hair strands on the silhouette, each coloured from the photo underneath.')
        for k in (0.35, 0.7, 1.0):
            make_fur(k, bake)
            yield ('pause', 0.25)

    # ---------- light
    ld = an['light']
    yield ('step', 'Matching the light',
           'Light comes from %s, %s; colour %s. Found by fitting brightness against surface angle.' % (ld['vert'], ld['side'], ld['temp']))
    make_lights(an)
    yield ('pause', 0.6)

    # ---------- lens + render settings
    lens = an['lens']
    cd.dof.use_dof = bool(lens['shallow'])
    cd.dof.focus_object = None
    cd.dof.focus_distance = (S.subject_center - camob.matrix_world.translation).length
    cd.dof.aperture_fstop = max(lens['fstop'] * 1.6, 2.0)
    yield ('step', 'Lens and camera',
           '%d mm lens%s. A gentle orbit is keyed on frames 1-240 (press Space).' % (
               lens['focal'], ', depth of field f/%.1f (the photo had a blurry background)' % cd.dof.aperture_fstop if lens['shallow'] else ''))
    turntable(piv)
    setup_render(scene, an)

    S.build_time = time.time() - t0
    yield ('done_build', None)


def make_fur(k, bake):
    sd = S.sub
    an = S.analysis
    old = bpy.data.objects.get('ZICA Fur')
    if old:
        cv = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if cv.users == 0:
            bpy.data.hair_curves.remove(cv)
    hm, dt, Pf, Pb = sd['hm'], sd['dt'], sd['Pf'], sd['Pb']
    rim = max(2.0, 0.09 * max(sd['gw'], sd['gh']))
    cand = np.argwhere(hm & (dt <= rim))
    if len(cand) == 0:
        return
    rng = np.random.default_rng(7)
    n = 26000
    pick = cand[rng.integers(0, len(cand), n)]
    jit = rng.random((n, 2)) - 0.5
    gy = np.clip(pick[:, 0] + jit[:, 0], 0, sd['gh'] - 1).astype(int)
    gx = np.clip(pick[:, 1] + jit[:, 1], 0, sd['gw'] - 1).astype(int)
    t = rng.random(n)
    side = t < 0.55
    root = np.where(side[:, None], Pb[gy, gx], Pf[gy, gx]) * 0.995
    root = root * (0.995 + 0.01 * rng.random((n, 1)))
    # outward direction in the picture plane = -gradient of the distance map
    gdy, gdx = np.gradient(io.blur(dt, 1.5))
    outv = np.stack([-gdx[gy, gx], np.zeros(n), gdy[gy, gx]], -1)   # picture x -> world x, picture down -> world -z
    outv /= np.linalg.norm(outv, axis=-1, keepdims=True) + 1e-6
    back = np.where(side[:, None], np.array([0, 1.0, 0]), np.array([0, -1.0, 0]))
    dirv = outv * 0.8 + back * 0.35 + rng.normal(0, 0.25, (n, 3))
    dirv /= np.linalg.norm(dirv, axis=-1, keepdims=True)
    L = sd['size'] * 0.022 * (0.5 + 0.6 * rng.random(n)) * k
    pts = 4
    P = np.zeros((n, pts, 3), np.float32)
    for i in range(pts):
        s_ = i / (pts - 1)
        P[:, i] = root + dirv * (L * s_)[:, None] + np.array([0, 0, -1.0]) * (L * 0.25 * s_ * s_)[:, None]
    cv = bpy.data.hair_curves.new('ZICA Fur')
    cv.add_curves([pts] * n)
    cv.position_data.foreach_set('vector', P.ravel())
    rad = cv.attributes.new('radius', 'FLOAT', 'POINT')
    rr = np.tile(np.linspace(1.0, 0.25, pts), n) * sd['size'] * 0.0011
    rad.data.foreach_set('value', rr.astype(np.float32))
    col = cv.attributes.new('zcol', 'FLOAT_COLOR', 'CURVE')
    H, W = sd['rgb'].shape[:2]
    py = np.clip(((gy + 0.5) / sd['gh'] * H).astype(int), 0, H - 1)
    px = np.clip(((gx + 0.5) / sd['gw'] * W).astype(int), 0, W - 1)
    c = io.srgb_to_lin(sd['rgb'][py, px]) * (0.85 + 0.3 * rng.random((n, 1)))
    col.data.foreach_set('color', np.concatenate([c, np.ones((n, 1))], -1).astype(np.float32).ravel())
    ob = bpy.data.objects.new('ZICA Fur', cv)
    coll().objects.link(ob)
    m = bpy.data.materials.get('ZICA3D Fur') or fur_material(min(1.0, bake + 0.12))
    cv.materials.append(m)
    S.objects['fur'] = ob


def make_lights(an):
    """Sun lights: their strength does not depend on scene size, so the look stays predictable."""
    c = coll()
    for n in ('ZICA Key light', 'ZICA Rim light'):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    ld = an['light']
    L = Vector(cam_to_world(ld['dir'])).normalized()
    ctr = S.subject_center
    dist = max(S.subject_size * 2.5, 2.0)
    col = tuple(float(x) for x in np.clip(np.array(ld['colour']) / max(max(ld['colour']), 1e-3), 0.35, 1))
    key = bpy.data.lights.new('ZICA Key light', 'SUN'); key.angle = math.radians(6)
    key.color = col
    key.energy = 2.4
    ko = bpy.data.objects.new('ZICA Key light', key); c.objects.link(ko)
    ko.location = ctr + L * dist
    look_at(ko, ctr)
    rim = bpy.data.lights.new('ZICA Rim light', 'SUN'); rim.angle = math.radians(10)
    rim.energy = 0.9; rim.color = col
    ro = bpy.data.objects.new('ZICA Rim light', rim); c.objects.link(ro)
    ro.location = ctr + Vector((-L.x * dist, dist * 0.8, max(L.z, 0.2) * dist))
    look_at(ro, ctr)
    sc = zscene()
    w = bpy.data.worlds.get('ZICA World') or bpy.data.worlds.new('ZICA World')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    fill = nt.nodes.new('ShaderNodeBackground'); seen = nt.nodes.new('ShaderNodeBackground')
    lp = nt.nodes.new('ShaderNodeLightPath'); mx = nt.nodes.new('ShaderNodeMixShader')
    sc_ = np.array(ld['shadow'])
    fill.inputs['Color'].default_value = (*io.srgb_to_lin(np.clip(sc_ * 1.4 + 0.08, 0, 1)).tolist(), 1)
    fill.inputs['Strength'].default_value = 1.0
    border = np.array(getattr(S, 'border', sc_))
    seen.inputs['Color'].default_value = (*io.srgb_to_lin(np.clip(border, 0, 1)).tolist(), 1)
    nt.links.new(lp.outputs['Is Camera Ray'], mx.inputs['Fac'])
    nt.links.new(fill.outputs['Background'], mx.inputs[1]); nt.links.new(seen.outputs['Background'], mx.inputs[2])
    nt.links.new(mx.outputs['Shader'], out.inputs['Surface'])
    S.key = ko; S.rim = ro


def turntable(piv):
    piv.animation_data_clear()
    o = getattr(S, 'orbit', ORBIT)
    for f, ang in ((1, 0), (60, o), (180, -o), (240, 0)):
        piv.rotation_euler = (0, 0, math.radians(ang))
        piv.keyframe_insert('rotation_euler', index=2, frame=f)
    try:
        for fc in piv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'SINE'
    except Exception:
        pass
    sc = zscene()
    sc.frame_start = 1
    sc.frame_end = 240
    sc.frame_set(1)


def setup_render(scene, an):
    scene.view_settings.view_transform = 'Standard'
    try:
        scene.view_settings.look = 'None'
    except Exception:
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0


def apply_quality(scene, q):
    """PREVIEW / NORMAL / GOOD / CINEMATIC"""
    eevee = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    long = {'PREVIEW': 1280, 'NORMAL': 1920, 'GOOD': 1920, 'CINEMATIC': 3840}[q]
    rx, ry = scene.render.resolution_x, scene.render.resolution_y
    s = long / max(rx, ry)
    scene.render.resolution_x, scene.render.resolution_y = int(rx * s) // 2 * 2, int(ry * s) // 2 * 2
    scene.render.resolution_percentage = 100
    if q in ('PREVIEW', 'NORMAL'):
        scene.render.engine = eevee
        try:
            scene.eevee.taa_render_samples = 32 if q == 'PREVIEW' else 96
            scene.eevee.use_raytracing = q == 'NORMAL'
        except Exception:
            pass
    else:
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 128 if q == 'GOOD' else 512
        scene.cycles.use_denoising = True
        try:
            scene.cycles.device = 'GPU' if bpy.context.preferences.addons['cycles'].preferences.has_active_device() else 'CPU'
        except Exception:
            pass
