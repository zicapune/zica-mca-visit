bl_info = {
    "name": "ZICA Image to 3D",
    "author": "ZICA Pune (Kothrud)",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar (N) > ZICA 3D",
    "description": "Turns any picture (photo or 2D art) into a 3D scene you can orbit: depth, cut-out, matte background, "
                   "materials, light, lens and a render-compare look-match loop. Runs offline.",
    "category": "3D View",
}

if "bpy" in locals():
    import importlib
    for _m in (imgops, vision, analyze, builder, lookmatch, overlay, runner, ui):  # noqa: F821
        importlib.reload(_m)
else:
    from . import imgops, vision, analyze, builder, lookmatch, overlay, runner, ui

import bpy  # noqa: E402


def register():
    ui.register()


def unregister():
    ui.unregister()
