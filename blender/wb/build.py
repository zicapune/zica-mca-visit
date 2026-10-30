"""Builds the ZICA Blender scripts from the modules in this folder.
   python3 build.py   ->  ../zica_world_builder_2.py (everything) + 4 focused scripts."""
import os
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.dirname(HERE)

VARIANTS = [
    ('zica_world_builder_2.py', 'ZICA World Builder 2', ['worlds', 'image', 'props', 'surfaces'],
     'EVERYTHING in one script: Worlds, Image to World, Prop Factory, Walls & Surfaces',
     ['WORLDS   Neon City · Ancient Old Town · Island Lagoon · Desert Canyon · Snowy Peaks · Forest Valley',
      'IMAGE    Photo to terrain · Painted map · Pixel mosaic · 3D postcard · Photo to city',
      'PROPS    Ancient · Modern · War · Sci-fi (22 props, Wear/Detail/Scale/Seed sliders, "Whole set")',
      'WALLS    Brick · Castle stone · Concrete · Old plaster · Wooden planks · Sci-fi panels (Damage, Grime)']),
    ('zica_worlds.py', 'ZICA Worlds', ['worlds'],
     'Landscapes and cities from code: island, desert, snow, forest, neon city, ancient old town',
     ['WORLDS   Neon City · Ancient Old Town · Island Lagoon · Desert Canyon · Snowy Peaks · Forest Valley',
      'Sliders: Size, Density, Detail, Seed, Sun height, Haze, Water level']),
    ('zica_image_to_world.py', 'ZICA Image to World', ['image'],
     'Turn any picture into 3D: terrain, painted map, pixel mosaic, 3D postcard, photo city',
     ['IMAGE    Photo to terrain · Painted map to world · Pixel mosaic · 3D postcard · Photo to city',
      'Sliders: Resolution, Height, Water level, Trees, Building height, Invert']),
    ('zica_prop_factory.py', 'ZICA Prop Factory', ['props'],
     'Game-ready style props: ancient, modern, war, sci-fi, with wear and damage',
     ['PROPS    Ancient · Modern · War · Sci-fi (22 props)',
      'Sliders: Wear/damage, Detail, Scale, Seed.  "Whole set" lines a whole era up with labels']),
    ('zica_wall_engine.py', 'ZICA Wall & Surface Engine', ['surfaces'],
     'Real-geometry walls: brick, castle stone, concrete, old plaster, wood planks, sci-fi panels',
     ['WALLS    Brick · Castle stone · Concrete · Old plaster on brick · Wooden planks · Sci-fi panels',
      'Sliders: Width, Height, Thickness, Damage, Grime/moss, Detail, Seed, Colour variant, Camera angle',
      'Lighting: Studio · Daylight · Night']),
]
LIB = {'worlds': ['worlds'], 'image': ['worlds', 'image_world'], 'props': ['props'], 'surfaces': ['surfaces']}


def header(title, mods, desc, lines):
    bar = '# ' + '=' * 69
    return '\n'.join([
        bar,
        '#  %s  ·  Blender 5.2 LTS (also 4.4+)  ·  ZICA Pune' % title.upper(),
        '#  ' + desc,
        '#',
        *['#    ' + l for l in lines],
        '#    RENDER   Preview / Normal / Good / Cinematic, live render view, preview inside the panel',
        '#',
        '#  RUN:  Scripting tab > New > paste > Run Script (Alt+P), then 3D Viewport > N > ZICA tab.',
        '#        Or Edit > Preferences > Add-ons > Install from Disk.',
        '#  Every slider rebuilds live when "Live update" is on. Everything is procedural: no downloads.',
        bar,
        'bl_info = {"name": %r, "author": "ZICA Pune", "version": (2, 1, 0), "blender": (4, 4, 0),' % title,
        '           "location": "View3D > Sidebar > ZICA", "category": "3D View",',
        '           "description": %r}' % desc,
        '',
        'import bpy, bmesh, math, random, os',
        'from mathutils import Vector, noise',
        'ZICA_TITLE = %r' % title,
        'ZICA_MODULES = %r' % set(mods),
        '', ''])


def read(n):
    return open(os.path.join(HERE, n + '.py')).read()


for fname, title, mods, desc, lines in VARIANTS:
    parts = [header(title, mods, desc, lines), read('core')]
    seen = []
    for m in mods:
        for lib in LIB[m]:
            if lib not in seen:
                seen.append(lib); parts.append(read(lib))
    parts.append(read('ui'))
    open(os.path.join(OUT, fname), 'w').write('\n\n'.join(parts))
    print('built', fname, sum(len(p) for p in parts) // 1024, 'KB', seen)
