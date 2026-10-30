"""Look-match loop: render a small frame, compare it with the picture, correct, repeat.
No AI: plain colour science (CIE Lab difference) and simple feedback rules."""
import os, tempfile, math
import numpy as np
import bpy
from . import imgops as io
from .builder import S, zica_materials, zscene


def render_small(scene, long=220, spp=20):
    r = scene.render
    keep = (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath,
            r.image_settings.file_format, scene.cycles.samples, scene.cycles.use_denoising)
    rx, ry = r.resolution_x, r.resolution_y
    s = long / max(rx, ry)
    r.engine = 'CYCLES'
    r.resolution_x, r.resolution_y = max(8, int(rx * s)), max(8, int(ry * s))
    r.resolution_percentage = 100
    scene.cycles.samples = spp
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    path = os.path.join(tempfile.gettempdir(), 'zica3d_match.png')
    r.filepath = path
    r.image_settings.file_format = 'PNG'
    scene.frame_set(1)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath,
     r.image_settings.file_format, scene.cycles.samples, scene.cycles.use_denoising) = keep
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return np.flipud(px.reshape(h, w, 4))[..., :3].copy()


def score(ref, ren):
    a, b = io.rgb_to_lab(ref), io.rgb_to_lab(ren)
    de = float(np.sqrt(((a - b) ** 2).sum(-1)).mean())
    return max(0.0, 100.0 - de * 2.0), de, a, b


def set_param(name, value):
    for m in zica_materials():
        nt = m.node_tree
        if name == 'sat':
            n = nt.nodes.get('ZLook')
            if n:
                n.inputs['Saturation'].default_value = value
        elif name == 'gain':
            n = nt.nodes.get('ZGain')
            if n:
                for s in n.inputs:
                    if s.identifier == 'B_Color':
                        s.default_value = (*value, 1)
        elif name == 'bake':
            n = nt.nodes.get('ZBake')
            if n:
                n.outputs[0].default_value = float(np.clip(m.get('zbake', 0.6) + value, 0, 1))


def loop_steps(ref_rgb, passes=5):
    scene = zscene()
    yield ('step', 'Look-match loop',
           'Render a small frame -> compare every pixel with the picture (CIE Lab colour difference) -> correct -> repeat.')
    sat, gain, bake_off = 1.0, np.ones(3), 0.0
    ex = 0.0
    best = None
    S.match_history = []
    for p in range(1, passes + 1):
        ren = render_small(scene)
        ref = io.resize(ref_rgb, ren.shape[0], ren.shape[1])
        sc, de, la, lb = score(ref, ren)
        S.match_history.append(round(sc, 1))
        if best is None or sc > best[0]:
            best = (sc, ex, sat, gain.copy(), bake_off)
        # --- corrections
        msgs = []
        yr, yn = io.luma(io.srgb_to_lin(ref)).mean(), io.luma(io.srgb_to_lin(ren)).mean()
        dex = float(np.clip(math.log2(max(yr, 1e-4) / max(yn, 1e-4)), -1.2, 1.2))
        if abs(dex) > 0.03:
            ex += dex * 0.9; msgs.append('brightness %+d%%' % round((2 ** (dex * 0.9) - 1) * 100))
        cr = np.hypot(la[..., 1], la[..., 2]).mean() / max(np.hypot(lb[..., 1], lb[..., 2]).mean(), 1e-3)
        if abs(cr - 1) > 0.03:
            sat = float(np.clip(sat * cr ** 0.9, 0.4, 2.0)); msgs.append('colour %+d%%' % round((cr - 1) * 100))
        mr, mn = io.srgb_to_lin(ref).reshape(-1, 3).mean(0), io.srgb_to_lin(ren).reshape(-1, 3).mean(0)
        cast = (mr / max(mr.mean(), 1e-4)) / np.maximum(mn / max(mn.mean(), 1e-4), 1e-4)
        if np.abs(cast - 1).max() > 0.03:
            gain = np.clip(gain * cast ** 0.8, 0.5, 2.0); msgs.append('tint fixed')
        cref, cren = la[..., 0].std(), lb[..., 0].std()
        if cren < cref * 0.92:
            bake_off = min(bake_off + 0.08, 0.4); msgs.append('more picture detail')
        elif cren > cref * 1.1:
            bake_off = max(bake_off - 0.08, -0.4); msgs.append('softer 3D shading')
        yield ('match', p, passes, sc, ', '.join(msgs) if msgs else 'no change needed')
        if p == passes or (p > 1 and abs(S.match_history[-1] - S.match_history[-2]) < 0.4 and sc > 85):
            break
        scene.view_settings.exposure = ex
        set_param('sat', sat); set_param('gain', tuple(gain)); set_param('bake', bake_off)
    # keep the best settings found
    sc, ex, sat, gain, bake_off = best
    scene.view_settings.exposure = ex
    set_param('sat', sat); set_param('gain', tuple(gain)); set_param('bake', bake_off)
    S.match = round(sc, 1)
    yield ('step', 'Match: %d%%' % round(sc), 'Best pass kept. Now orbit with the middle mouse button and zoom with the wheel.')
