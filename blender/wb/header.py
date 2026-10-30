# =====================================================================
#  ZICA WORLD BUILDER 2  ·  Blender 5.2 LTS (also 4.4+)
#  One script → a whole toolkit in the sidebar (3D Viewport → N → ZICA):
#    WORLDS   Neon City · Ancient Old Town · Island Lagoon · Desert Canyon · Snowy Peaks · Forest Valley
#    IMAGE    Photo → terrain · Painted map → world · Pixel mosaic · 3D postcard
#    PROPS    Ancient · Modern · War · Sci-fi (22 props, Wear/Detail/Scale/Seed sliders, "Whole set")
#    RENDER   Preview / Normal / Good / Cinematic, live render view, preview inside the panel
#
#  RUN:  Scripting tab → New → paste → Run Script (Alt+P)      or install as an add-on.
#  Every slider rebuilds live when "Live update" is on.  Everything is procedural: no downloads.
# =====================================================================
bl_info = {"name": "ZICA World Builder 2", "author": "ZICA Pune", "version": (2, 0, 0), "blender": (4, 4, 0),
           "location": "View3D > Sidebar > ZICA", "category": "3D View",
           "description": "Procedural worlds, image-to-world and props with live sliders and render presets"}

import bpy, bmesh, math, random, os
from mathutils import Vector, noise
