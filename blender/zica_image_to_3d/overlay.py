"""Pop-up messages drawn on top of the 3D viewport (they fade out by themselves)."""
import time
import bpy, blf, gpu
from gpu_extras.batch import batch_for_shader

TOASTS = []
_HANDLE = [None]
_TIMER = [False]
ACCENT = (1.0, 0.71, 0.28)


def toast(title, body='', step=None, total=None, small=False, meter=None):
    TOASTS.append(dict(title=title, body=body, t0=time.time(), dur=3.0 if small else 5.0,
                       step=step, total=total, small=small, meter=meter))
    del TOASTS[:-5]
    print('[ZICA Image to 3D]', title, '-', body)
    _ensure_timer()


def _ensure_timer():
    if _TIMER[0]:
        return
    _TIMER[0] = True

    def tick():
        try:
            for win in bpy.context.window_manager.windows:
                for a in win.screen.areas:
                    if a.type == 'VIEW_3D':
                        a.tag_redraw()
        except Exception:
            pass
        now = time.time()
        TOASTS[:] = [t for t in TOASTS if now - t['t0'] < t['dur'] + 0.6]
        if not TOASTS:
            _TIMER[0] = False
            return None
        return 0.05
    try:
        bpy.app.timers.register(tick, first_interval=0.05)
    except Exception:
        _TIMER[0] = False


def _rect(x, y, w, h, col):
    sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    b = batch_for_shader(sh, 'TRIS', {'pos': [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]}, indices=[(0, 1, 2), (0, 2, 3)])
    sh.uniform_float('color', col)
    b.draw(sh)


def _wrap(text, width, size):
    blf.size(0, size)
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if blf.dimensions(0, t)[0] > width and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def draw():
    if not TOASTS:
        return
    sc = bpy.context.preferences.system.ui_scale
    region = bpy.context.region
    now = time.time()
    gpu.state.blend_set('ALPHA')
    x0 = int(24 * sc)
    y = int(30 * sc)
    maxw = min(int(560 * sc), region.width - 2 * x0)
    for t in reversed(TOASTS):
        age = now - t['t0']
        a = min(1.0, age / 0.25) * (1.0 if age < t['dur'] else max(0.0, 1 - (age - t['dur']) / 0.6))
        if a <= 0:
            continue
        slide = (1 - min(1.0, age / 0.25)) * 20 * sc
        ts = int((15 if t['small'] else 20) * sc)
        bs = int(13 * sc)
        lines = _wrap(t['body'], maxw - 40 * sc, bs) if t['body'] else []
        h = int(ts + 22 * sc + len(lines) * (bs + 6 * sc) + (14 * sc if t['meter'] is not None else 0)
                + (16 * sc if t['step'] else 0))
        _rect(x0 - slide, y, maxw, h, (0.06, 0.06, 0.08, 0.86 * a))
        _rect(x0 - slide, y, 4 * sc, h, (*ACCENT, a))
        tx = x0 - slide + 18 * sc
        ty = y + h - ts - 8 * sc - (16 * sc if t['step'] else 0)
        if t['step']:
            blf.size(0, int(11 * sc)); blf.color(0, *ACCENT, a)
            lab = 'STEP %d / %d' % (t['step'], t['total']) if t['total'] else 'STEP %d' % t['step']
            blf.position(0, tx, ty + ts + 2 * sc, 0); blf.draw(0, lab)
        blf.size(0, ts); blf.color(0, 1, 1, 1, a)
        blf.position(0, tx, ty, 0); blf.draw(0, t['title'])
        blf.size(0, bs); blf.color(0, 0.82, 0.84, 0.88, a)
        ly = ty - bs - 10 * sc
        for ln in lines:
            blf.position(0, tx, ly, 0); blf.draw(0, ln)
            ly -= bs + 6 * sc
        if t['meter'] is not None:
            _rect(tx, y + 10 * sc, maxw - 40 * sc, 5 * sc, (1, 1, 1, 0.15 * a))
            _rect(tx, y + 10 * sc, (maxw - 40 * sc) * max(0, min(1, t['meter'])), 5 * sc, (*ACCENT, a))
        y += h + int((14 if t['step'] else 8) * sc)
    gpu.state.blend_set('NONE')


def register():
    if _HANDLE[0] is None:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    if _HANDLE[0] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], 'WINDOW')
        _HANDLE[0] = None
