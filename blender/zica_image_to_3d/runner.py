"""Plays the build: turns builder/lookmatch events into pop-ups, animations and waits."""
import math, time
import bpy
from mathutils import Quaternion, Vector, Matrix
from . import overlay
from .builder import S, set_key

STATE = {'running': False, 'gen': None, 'step': 0, 'total': 0}


def views():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                yield area, area.spaces.active


def redraw():
    try:
        for area, _ in views():
            area.tag_redraw()
    except Exception:
        pass


def ease(t):
    return t * t * (3 - 2 * t)


def view_to(rot=None, loc=None, dist=None, persp='PERSP', shading=None):
    for area, sp in views():
        r3 = sp.region_3d
        if r3 is None:
            continue
        if persp:
            r3.view_perspective = persp
        if rot is not None:
            r3.view_rotation = rot
        if loc is not None:
            r3.view_location = loc
        if dist is not None:
            r3.view_distance = dist
        if shading:
            sp.shading.type = shading
        try:
            sp.lens = S.camera.data.lens          # same lens as the camera, so the view lines up with the photo
            sp.clip_start, sp.clip_end = 0.05, 1000
        except Exception:
            pass


def camera_view_rot():
    return Quaternion((1, 0, 0), math.pi / 2)


def handle(ev, live):
    """Generator of delays (seconds) for one event."""
    k = ev[0]
    if k == 'step':
        STATE['step'] += 1
        overlay.toast(ev[1], ev[2], step=STATE['step'], total=STATE['total'])
        yield 1.6 if live else 0.02
    elif k == 'info':
        overlay.toast(ev[1], '', small=True)
        if live:
            yield 0.6
    elif k == 'pause':
        if live:
            yield ev[1]
    elif k == 'view_side':
        if live:
            c = S.subject_center
            rot = camera_view_rot()
            side = Quaternion((0, 0, 1), math.radians(-38)) @ Quaternion((1, 0, 0), math.radians(-12))
            view_to(rot=side @ rot, loc=c, dist=c.length * 1.25, persp='PERSP', shading='MATERIAL')
            yield 0.4
    elif k == 'show_depth':
        objs, dur = ev[1], ev[2]
        if live and getattr(S, 'depth_img', None):
            overlay.toast('This is the depth map', 'White = near, black = far. Next, every pixel moves to its depth.', small=True)
            swaps = []
            for o in objs:
                for m in o.data.materials:
                    if m and m.get('zica3d'):
                        for n in m.node_tree.nodes:
                            if n.type == 'TEX_IMAGE' and n.image and n.image.name in ('ZICA3D picture', 'ZICA3D subject'):
                                swaps.append((n, n.image)); n.image = S.depth_img
                            elif n.type == 'TEX_IMAGE' and n.image and n.image.name == 'ZICA3D picture wide' and S.depth_wide:
                                swaps.append((n, n.image)); n.image = S.depth_wide
            redraw()
            yield dur
            for n, im in swaps:
                n.image = im
    elif k == 'animate_keys':
        objs, dur = ev[1], ev[2]
        if live:
            n = max(2, int(dur / 0.04))
            for i in range(n + 1):
                for o in objs:
                    set_key(o, ease(i / n))
                redraw()
                yield 0.04
        for o in objs:
            set_key(o, 1.0)
    elif k == 'paint_matte':
        mat, dur = ev[1], ev[2]
        node = mat.node_tree.nodes.get('ZPaint')
        fac = [s for s in node.inputs if s.identifier == 'Factor_Float'][0]
        if live:
            n = max(2, int(dur / 0.05))
            for i in range(n + 1):
                fac.default_value = ease(i / n)
                yield 0.05
        fac.default_value = 1.0
    elif k == 'relight':
        mats, bake, dur = ev[1], ev[2], ev[3]
        if live:
            n = max(2, int(dur / 0.05))
            for i in range(n + 1):
                t = ease(i / n)
                for m in mats:
                    nd = m.node_tree.nodes.get('ZBake')
                    if nd:
                        nd.outputs[0].default_value = 1.0 + (m.get('zbake', bake) - 1.0) * t
                yield 0.05
        for m in mats:
            nd = m.node_tree.nodes.get('ZBake')
            if nd:
                nd.outputs[0].default_value = m.get('zbake', bake)
    elif k == 'match':
        p, total, sc, msg = ev[1:]
        overlay.toast('Pass %d: match %d%%' % (p, round(sc)), msg, small=True, meter=sc / 100.0)
        yield 0.9 if live else 0.02
    elif k == 'done_build':
        c = S.subject_center
        if live:
            # swing back from the side view to the exact photo view
            from mathutils import Quaternion as Q
            start = None
            for _, sp in views():
                if sp.region_3d:
                    start = sp.region_3d.view_rotation.copy(); break
            if start is not None:
                n = 30
                for i in range(n + 1):
                    view_to(rot=start.slerp(camera_view_rot(), ease(i / n)), loc=c, dist=c.length, persp=None)
                    yield 0.03
        view_to(rot=camera_view_rot(), loc=c, dist=c.length, persp='PERSP', shading='MATERIAL')
        yield 0.3 if live else 0.0


def drive(gens, live):
    for g in gens:
        for ev in g:
            yield from handle(ev, live)


def start(gens, slow, total, on_done=None, sync=False):
    """slow = presentation mode (animations + pauses). sync = run now without timers (tests)."""
    STATE.update(running=True, step=0, total=total)
    it = drive(gens, slow)

    def tick():
        try:
            d = next(it)
            redraw()
            return max(0.01, d)
        except StopIteration:
            STATE['running'] = False
            redraw()
            if on_done:
                on_done()
            return None
        except Exception as e:
            STATE['running'] = False
            overlay.toast('Something went wrong', str(e)[:120])
            import traceback; traceback.print_exc()
            return None
    if not sync:
        bpy.app.timers.register(tick, first_interval=0.05)
    else:
        for _ in it:
            pass
        STATE['running'] = False
        if on_done:
            on_done()
