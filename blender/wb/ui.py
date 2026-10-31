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
