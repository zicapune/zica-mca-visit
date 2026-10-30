"""Sidebar panel (N -> ZICA 3D): five numbered steps, top to bottom."""
import os, json, glob
import bpy
from bpy.props import (StringProperty, EnumProperty, IntProperty, FloatProperty, BoolProperty,
                       FloatVectorProperty, PointerProperty)
from . import vision, analyze, builder, lookmatch, runner, overlay

HERE = os.path.dirname(__file__)
SAMPLES = os.path.join(HERE, 'samples')
PREV = {}
_ITEMS = []


def nice(fname):
    n = os.path.splitext(os.path.basename(fname))[0]
    n = n.split('-', 1)[1] if n[:2].isdigit() else n
    return n.replace('-', ' ').capitalize()


def previews():
    if 'p' not in PREV:
        from bpy.utils import previews as _pv
        PREV['p'] = _pv.new()
    return PREV['p']


def sample_items(self, context):
    if _ITEMS:
        return _ITEMS
    pc = previews()
    for i, f in enumerate(sorted(glob.glob(os.path.join(SAMPLES, '*.jpg')))):
        key = os.path.basename(f)
        if key not in pc:
            pc.load(key, f, 'IMAGE')
        _ITEMS.append((key, nice(f), 'Sample picture: ' + nice(f), pc[key].icon_id, i))
    return _ITEMS


def current_path(p):
    if p.source == 'FILE' and p.filepath:
        return bpy.path.abspath(p.filepath)
    return os.path.join(SAMPLES, p.sample)


def _changed(self, context):
    self.analysed = False
    self.analysis = ''


def _ref_update(self, context):
    cam = bpy.data.objects.get('ZICA Camera')
    if not cam:
        return
    cd = cam.data
    cd.show_background_images = self.ref_opacity > 0.001
    if not cd.background_images:
        bi = cd.background_images.new()
        bi.image = bpy.data.images.get('ZICA3D picture')
        bi.display_depth = 'FRONT'
        bi.frame_method = 'FIT'
    cd.background_images[0].alpha = self.ref_opacity


class ZICA3D_Props(bpy.types.PropertyGroup):
    source: EnumProperty(items=[('SAMPLE', 'Samples', 'Use one of the 10 sample pictures'),
                                ('FILE', 'Your picture', 'Use any JPG / PNG from your PC')],
                         default='SAMPLE', update=_changed)
    sample: EnumProperty(name='Sample', items=sample_items, update=_changed)
    filepath: StringProperty(name='Picture', subtype='FILE_PATH', update=_changed)
    analysed: BoolProperty(default=False)
    analysis: StringProperty(default='')
    style: EnumProperty(name='Style', items=[('AUTO', 'Auto', 'Use what was detected'),
                                             ('PHOTO', 'Photo', 'Treat as a photograph: real lighting, skin glow, bump'),
                                             ('ILLUSTRATION', '2D art', 'Treat as 2D art: flat colours, ink outline, paper grain')],
                        default='AUTO')
    fur: EnumProperty(name='Fur', items=[('AUTO', 'Auto', 'Grow fur if an animal was detected'), ('ON', 'On', ''), ('OFF', 'Off', '')],
                      default='AUTO')
    detail: IntProperty(name='Mesh detail', default=400, min=120, max=600,
                        description='Points along the long side of the picture. Higher = sharper 3D, slower')
    relief: FloatProperty(name='3D depth', default=1.0, min=0.3, max=2.0,
                          description='How strongly the picture pushes out into 3D')
    presentation: BoolProperty(name='Presentation mode', default=True,
                               description='Build slowly with animations and pop-up explanations (for an audience)')
    passes: IntProperty(name='Look-match passes', default=4, min=1, max=8,
                        description='How many render-compare-fix rounds to run')
    quality: EnumProperty(name='Quality', items=[('PREVIEW', 'Preview', 'EEVEE, 1280 px: seconds'),
                                                 ('NORMAL', 'Normal', 'EEVEE, 1920 px, ray tracing'),
                                                 ('GOOD', 'Good', 'Cycles 128 samples, 1920 px, denoised'),
                                                 ('CINEMATIC', 'Cinematic', 'Cycles 512 samples, 4K')], default='NORMAL')
    ref_opacity: FloatProperty(name='Original picture on top', default=0.0, min=0, max=1, subtype='FACTOR',
                               update=_ref_update, description='Fade the original picture over the camera view to compare')
    show_options: BoolProperty(default=False)
    show_smart: BoolProperty(default=False)
    pal0: FloatVectorProperty(subtype='COLOR_GAMMA', size=3, min=0, max=1)
    pal1: FloatVectorProperty(subtype='COLOR_GAMMA', size=3, min=0, max=1)
    pal2: FloatVectorProperty(subtype='COLOR_GAMMA', size=3, min=0, max=1)
    pal3: FloatVectorProperty(subtype='COLOR_GAMMA', size=3, min=0, max=1)
    pal4: FloatVectorProperty(subtype='COLOR_GAMMA', size=3, min=0, max=1)


def P(context):
    return context.window_manager.zica3d


# ------------------------------------------------------------------ operators
class ZICA3D_OT_open(bpy.types.Operator):
    bl_idname = 'zica3d.open'
    bl_label = 'Open your picture'
    bl_description = 'Pick any JPG / PNG from your PC'
    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default='*.jpg;*.jpeg;*.png;*.webp;*.bmp;*.tif;*.tiff', options={'HIDDEN'})

    def execute(self, context):
        p = P(context)
        p.filepath = self.filepath
        p.source = 'FILE'
        pc = previews()
        if self.filepath not in pc:
            try:
                pc.load(self.filepath, self.filepath, 'IMAGE')
            except Exception:
                pass
        return bpy.ops.zica3d.analyze()

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class ZICA3D_OT_analyze(bpy.types.Operator):
    bl_idname = 'zica3d.analyze'
    bl_label = 'Analyse the picture'
    bl_description = 'Find depth, subject, style, materials, light and lens in the picture'

    def execute(self, context):
        p = P(context)
        path = current_path(p)
        if not os.path.exists(path):
            self.report({'ERROR'}, 'Picture not found')
            return {'CANCELLED'}
        overlay.toast('Analysing the picture', 'Depth, subject, style, materials, light and lens...', small=True)
        img, rgb = builder.load_rgb(path)
        vis = vision.see(rgb, os.path.splitext(path)[0] + '.npz')
        an = analyze.analyze(rgb, vis)
        an['source'] = vis['source']
        p.analysis = json.dumps(an)
        p.analysed = True
        for i, c in enumerate(an['palette'][:5]):
            setattr(p, 'pal%d' % i, c[:3])
        builder.S.cached = (path, rgb, vis, an)
        looks = ('Looks like: ' + ', '.join('%s %d%%' % (l[0], l[1]) for l in an['labels'][:2]) + '. ') if an['labels'] else ''
        overlay.toast('I see: %s, %s' % ('a photo' if an['style'] == 'photo' else '2D art', an['scene']),
                      looks + 'Light from %s, %s. Build plan is in the panel.' % (an['light']['vert'], an['light']['side']))
        return {'FINISHED'}


class ZICA3D_OT_build(bpy.types.Operator):
    bl_idname = 'zica3d.build'
    bl_label = 'Build it in 3D'
    bl_description = 'Turn the picture into a 3D scene, step by step'

    def execute(self, context):
        p = P(context)
        if runner.STATE['running']:
            self.report({'WARNING'}, 'Already building')
            return {'CANCELLED'}
        if not p.analysed:
            bpy.ops.zica3d.analyze()
        path = current_path(p)
        cached = getattr(builder.S, 'cached', None)
        if cached and cached[0] == path:
            _, rgb, vis, an = cached
        else:
            img, rgb = builder.load_rgb(path)
            vis = vision.see(rgb, os.path.splitext(path)[0] + '.npz'); an = analyze.analyze(rgb, vis)
        an = json.loads(json.dumps(an))
        opts = dict(detail=p.detail, style=p.style, fur=p.fur, relief=p.relief)
        p.ref_opacity = 0.0
        total = 9 + (1 if an['subject'] else 0) + (1 if (an['fur'] and p.fur != 'OFF') or p.fur == 'ON' else 0)
        gens = [builder.build_steps(path, opts, an, vis)]
        if p.passes > 0:
            gens.append(lookmatch.loop_steps(rgb, passes=p.passes))
        runner.start(gens, slow=p.presentation, total=total)
        return {'FINISHED'}


class ZICA3D_OT_view(bpy.types.Operator):
    bl_idname = 'zica3d.view'
    bl_label = 'View'
    mode: EnumProperty(items=[('CAMERA', 'Photo view', 'Look through the camera: the exact picture'),
                              ('LEFT', 'Orbit left', ''), ('RIGHT', 'Orbit right', ''),
                              ('FINAL', 'Final', 'Materials and light'), ('CLAY', 'Clay', 'Only the 3D shapes'),
                              ('WIRE', 'Wireframe', 'Show the mesh'), ('PLAY', 'Play orbit', 'Play / stop the keyed camera orbit')])

    @classmethod
    def description(cls, context, props):
        return {'CAMERA': 'Look through the camera: the exact picture', 'LEFT': 'Swing the view around the subject',
                'RIGHT': 'Swing the view around the subject', 'FINAL': 'Show materials and light',
                'CLAY': 'Show only the 3D shapes (grey clay)', 'WIRE': 'Show the mesh wires',
                'PLAY': 'Play / stop the keyed camera orbit'}[props.mode]

    def execute(self, context):
        import math
        from mathutils import Quaternion
        c = getattr(builder.S, 'subject_center', None)
        if c is None:
            return {'CANCELLED'}
        for area, sp in runner.views():
            r3 = sp.region_3d
            if self.mode == 'CAMERA':
                r3.view_perspective = 'PERSP'
                r3.view_rotation = runner.camera_view_rot(); r3.view_location = c; r3.view_distance = c.length
                try:
                    sp.lens = builder.S.camera.data.lens
                except Exception:
                    pass
            elif self.mode in ('LEFT', 'RIGHT'):
                a = math.radians(-25 if self.mode == 'LEFT' else 25)
                r3.view_rotation = Quaternion((0, 0, 1), a) @ r3.view_rotation
                r3.view_location = c
            elif self.mode == 'FINAL':
                sp.shading.type = 'MATERIAL'; sp.overlay.show_wireframes = False
            elif self.mode == 'CLAY':
                sp.shading.type = 'SOLID'; sp.shading.color_type = 'SINGLE'; sp.shading.light = 'STUDIO'
                sp.overlay.show_wireframes = False
            elif self.mode == 'WIRE':
                sp.shading.type = 'SOLID'; sp.shading.color_type = 'TEXTURE'; sp.overlay.show_wireframes = True
            area.tag_redraw()
        if self.mode == 'PLAY':
            bpy.ops.screen.animation_play()
        return {'FINISHED'}


class ZICA3D_OT_render(bpy.types.Operator):
    bl_idname = 'zica3d.render'
    bl_label = 'Render'
    animation: BoolProperty(default=False)

    @classmethod
    def description(cls, context, props):
        return 'Render the 240-frame orbit as a video' if props.animation else 'Render a still with the chosen quality'

    def execute(self, context):
        sc = builder.zscene(activate=True)
        builder.apply_quality(sc, P(context).quality)
        sc.frame_set(1)
        if self.animation:
            sc.render.image_settings.file_format = 'FFMPEG'
            try:
                sc.render.ffmpeg.format = 'MPEG4'; sc.render.ffmpeg.codec = 'H264'
            except Exception:
                pass
            sc.render.filepath = '//zica_image_to_3d_orbit_'
            bpy.ops.render.render('INVOKE_DEFAULT', animation=True, scene=sc.name)
        else:
            bpy.ops.render.render('INVOKE_DEFAULT', scene=sc.name)
        return {'FINISHED'}


class ZICA3D_OT_smart(bpy.types.Operator):
    bl_idname = 'zica3d.smart_setup'
    bl_label = 'Install Smart vision (one time)'
    bl_description = ('Downloads onnxruntime + 3 free offline models (~290 MB) so YOUR pictures get real depth, cut-out '
                      'and labels. Needs internet once; after that everything runs offline. Samples work without it')

    def execute(self, context):
        vision.start_setup()

        def poll():
            for a in context.screen.areas if context.screen else []:
                a.tag_redraw()
            return 0.5 if vision.SETUP['running'] else None
        bpy.app.timers.register(poll, first_interval=0.5)
        return {'FINISHED'}


# ------------------------------------------------------------------ panel
def step_header(layout, n, text, done=False, active=True):
    r = layout.row()
    r.active = active
    r.label(text='%s  %s' % (n, text), icon='CHECKMARK' if done else 'NONE')


class ZICA3D_PT_main(bpy.types.Panel):
    bl_label = 'ZICA Image to 3D'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ZICA 3D'

    def draw(self, context):
        try:
            self._draw(context)
        except Exception as e:      # never lose the whole panel to one bad line
            self.layout.label(text='Panel error: %s' % e, icon='ERROR')

    def _draw(self, context):
        p = P(context)
        L = self.layout
        an = json.loads(p.analysis) if p.analysed and p.analysis else None
        built = bool(bpy.data.objects.get('ZICA Camera'))
        busy = runner.STATE['running']

        # 1 ------------------------------------------------ pick
        b = L.box()
        step_header(b, '1', 'Pick a picture', done=True)
        r = b.row(align=True); r.prop(p, 'source', expand=True)
        if p.source == 'SAMPLE':
            b.template_icon_view(p, 'sample', show_labels=True, scale=7.0, scale_popup=6.0)
            b.label(text=nice(p.sample) if p.sample else '')
        else:
            pc = previews()
            fp = bpy.path.abspath(p.filepath) if p.filepath else ''
            if fp and fp in pc:
                b.template_icon(icon_value=pc[fp].icon_id, scale=7.0)
            b.operator('zica3d.open', icon='FILEBROWSER', text='Choose picture...' if not fp else os.path.basename(fp))

        # 2 ------------------------------------------------ analyse
        b = L.box()
        step_header(b, '2', 'What the code sees', done=bool(an))
        if not an:
            b.operator('zica3d.analyze', icon='VIEWZOOM')
        else:
            col = b.column(align=True)
            st = 'Photo' if an['style'] == 'photo' else '2D illustration'
            why = ' (camera noise found)' if an['style'] == 'photo' else ' (clean flat colours)'
            r = col.row(); r.label(text='Style: ' + st + why, icon='IMAGE_DATA')
            r = col.row(); r.label(text='Treat as'); r.prop(p, 'style', text='')
            col.label(text='Scene: ' + an['scene'], icon='SCENE_DATA')
            if an['labels']:
                col.label(text='Looks like: ' + ', '.join('%s %d%%' % (l[0], l[1]) for l in an['labels'][:3]), icon='VIEWZOOM')
            col.label(text=('Subject found: %d%% of the frame' % an['cover']) if an['subject'] else 'No single subject: whole scene in layers',
                      icon='USER' if an['subject'] else 'RENDERLAYERS')
            if an['regions']:
                col.label(text='Materials: ' + ', '.join('%s %d%%' % (k, v) for k, v in list(an['regions'].items())[:4]), icon='MATERIAL')
            r = col.row(align=True)
            r.label(text='Palette', icon='COLOR')
            for i in range(5):
                r.prop(p, 'pal%d' % i, text='')
            ld = an['light']
            col.label(text='Light: from %s, %s, %s' % (ld['vert'], ld['side'], ld['temp']), icon='LIGHT_SUN')
            col.label(text='Mood: %s, contrast %.0f:1' % (ld['mood'], ld['contrast']), icon='SHADING_RENDERED')
            ln = an['lens']
            col.label(text='Lens: %d mm%s' % (ln['focal'], ', f/%.1f, background blur found' % ln['fstop'] if ln['shallow'] else ''), icon='CAMERA_DATA')
            col.label(text='Vision: ' + an.get('source', ''), icon='INFO')
            pb = b.box().column(align=True)
            pb.label(text='How it will be built:')
            for i, l in enumerate(an['plan'], 1):
                pb.label(text='%d. %s' % (i, l))
            b.operator('zica3d.analyze', icon='FILE_REFRESH', text='Analyse again')

        # 3 ------------------------------------------------ build
        b = L.box()
        step_header(b, '3', 'Build it in 3D', done=built and not busy, active=bool(an))
        b.prop(p, 'presentation', icon='TIME')
        r = b.row(); r.scale_y = 2.0; r.enabled = not busy
        r.operator('zica3d.build', icon='MOD_SOLIDIFY', text='Building...' if busy else 'Build it in 3D')
        b.prop(p, 'show_options', icon='TRIA_DOWN' if p.show_options else 'TRIA_RIGHT', text='Options', emboss=False)
        if p.show_options:
            c2 = b.column(align=True)
            c2.prop(p, 'detail'); c2.prop(p, 'relief'); c2.prop(p, 'passes')
            c2.prop(p, 'fur')

        # 4 ------------------------------------------------ explore
        b = L.box()
        step_header(b, '4', 'Explore it', active=built)
        if built:
            r = b.row(align=True)
            r.operator('zica3d.view', text='Photo view', icon='CAMERA_DATA').mode = 'CAMERA'
            r.operator('zica3d.view', text='', icon='TRIA_LEFT').mode = 'LEFT'
            r.operator('zica3d.view', text='', icon='TRIA_RIGHT').mode = 'RIGHT'
            r.operator('zica3d.view', text='Play', icon='PLAY').mode = 'PLAY'
            r = b.row(align=True)
            r.operator('zica3d.view', text='Final', icon='MATERIAL').mode = 'FINAL'
            r.operator('zica3d.view', text='Clay', icon='SHADING_SOLID').mode = 'CLAY'
            r.operator('zica3d.view', text='Wire', icon='SHADING_WIRE').mode = 'WIRE'
            b.prop(p, 'ref_opacity', slider=True)
            m = getattr(builder.S, 'match', None)
            if m is not None:
                b.label(text='Look-match: %d%%  (passes: %s)' % (round(m), ' > '.join(str(int(x)) for x in builder.S.match_history)),
                        icon='CHECKMARK')
            b.label(text='Mouse: middle-drag orbit, wheel zoom, Shift+middle pan', icon='MOUSE_MMB')

        # 5 ------------------------------------------------ render
        b = L.box()
        step_header(b, '5', 'Render', active=built)
        b.prop(p, 'quality', expand=True)
        r = b.row(align=True); r.enabled = built
        r.operator('zica3d.render', text='Render image', icon='RENDER_STILL').animation = False
        r.operator('zica3d.render', text='Render orbit video', icon='RENDER_ANIMATION').animation = True

        # smart vision
        b = L.box()
        ready, txt = vision.smart_status()
        b.prop(p, 'show_smart', emboss=False, icon='TRIA_DOWN' if p.show_smart else 'TRIA_RIGHT',
               text='Smart vision: ' + ('ready' if ready else 'not installed'))
        if p.show_smart:
            c3 = b.column(align=True)
            c3.label(text='Offline models for YOUR pictures (samples work without).')
            c3.label(text=txt)
            if vision.SETUP['msg']:
                c3.label(text=vision.SETUP['msg'], icon='INFO')
            if not ready:
                r = c3.row(); r.enabled = not vision.SETUP['running']
                r.operator('zica3d.smart_setup', icon='IMPORT')


CLASSES = (ZICA3D_Props, ZICA3D_OT_open, ZICA3D_OT_analyze, ZICA3D_OT_build, ZICA3D_OT_view,
           ZICA3D_OT_render, ZICA3D_OT_smart, ZICA3D_PT_main)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.zica3d = PointerProperty(type=ZICA3D_Props)
    overlay.register()


def unregister():
    overlay.unregister()
    del bpy.types.WindowManager.zica3d
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    if 'p' in PREV:
        from bpy.utils import previews as _pv
        _pv.remove(PREV.pop('p'))
    _ITEMS.clear()
