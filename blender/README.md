# ZICA Blender script library (Blender 5.2 LTS)

Tested on **Blender 5.2.3 LTS** (works on 4.4 and newer). Everything is procedural: no downloads, no internet.
For Blender 4.2 use the older `zica_world_builder_v1_blender4.py`.

## The scripts
| Script | Purpose | Inside |
|---|---|---|
| **`zica_world_builder_2.py`** (recommended) | Everything in one script, one sidebar tab | Worlds · Image to World · Prop Factory · Walls & Surfaces |
| `zica_worlds.py` | Landscapes and cities from code | Neon City · Ancient Old Town · Island Lagoon · Desert Canyon · Snowy Peaks · Forest Valley |
| `zica_image_to_world.py` | Turn any picture into 3D | Photo to terrain · Painted map · Pixel mosaic · 3D postcard · Photo to city |
| `zica_prop_factory.py` | Game-style props with wear | Ancient · Modern · War · Sci-fi (22 props) |
| `zica_wall_engine.py` | Real-geometry walls (grown from Wall Engine 0.1) | Brick · Castle stone · Concrete · Old plaster on brick · Wooden planks · Sci-fi panels |

The single scripts are the same tools as the big one, one panel each. You can run several of them together.

## Run it
1. Blender → **Scripting** tab → **New** → paste the script → **Run Script** (Alt+P).
2. Back in **Layout**, hover the 3D view, press **N**, open the **ZICA** tab.
3. Top panel: pick a render quality (start with **Preview**) and keep **Live update** on.

To keep it permanently: Edit → Preferences → Add-ons → Install from Disk → pick the .py → enable it. (Install either the big script or the single ones, not both.)

## Render quality (top panel)
| Preset | Engine | Size | Use it for |
|---|---|---|---|
| Preview | EEVEE | 1280×720 | Live sliders in class, any PC |
| Normal | EEVEE | 1920×1080 | Good-looking stills in seconds |
| Good | Cycles, denoised | 1920×1080 | Ray-traced stills |
| Cinematic | Cycles | 3840×2160 | Final 4K still |

**Live render view** looks through the camera with rendered shading. **Render preview** renders a small still and shows it inside the panel. **Render image** / **Animation** do the full render.

## Image to World: how it works
The script reads every pixel of your picture and decides what to build from it.
- **Photo to terrain**: brightness becomes height, the photo's own colours paint the land, the lowest parts flood with water, trees grow on green areas. (Version 1 only had this mode, which is why it only made mountains. A bright sky in a photo becomes a mountain range.) Best with aerial photos and landscapes.
- **Painted map to world**: the **colour** decides the land. Paint in MS Paint / Photoshop / phone: **blue** = water, **green** = forest, **yellow/brown** = sand, **grey/black** = city blocks (darker = taller), **white** = snowy mountains, **red** = roads. Click **Make sample map** to see it without painting anything.
- **Pixel mosaic**: every pixel becomes a coloured block (3D pixel art; Detail 2+ adds LEGO-style studs). Best with logos and pixel art.
- **3D postcard**: the picture itself becomes a 3D relief with a slow parallax camera move. Best with paintings and portraits.
- **Photo to city** (new): bright = tall towers, the photo's colours paint the buildings, blue areas become canals, green areas parks with trees, a street grid cuts through. Works with any photo.

## Walls & Surfaces (new)
Every brick, stone and plank is real geometry. Sliders: Width, Height, Thickness, **Damage** (impact holes, missing pieces, cracks, rubble, exposed rebar on concrete), **Grime / moss** (dirt at the base, rain streaks, moss on stone), Detail, Seed, Colour variant, Camera angle. Lighting: Studio, Daylight or Night (one warm street lamp).

## Props (22)
- **Ancient**: Greek column, Amphora, Treasure chest (opens at Detail 2+, gold coins), Torch, Round shield, Sword
- **Modern**: Chair, Table, Desk lamp, Street lamp, Laptop, Coffee mug
- **War**: Sandbag wall, Oil drum, Ammo crate, Jerrycan, Czech hedgehog, Helmet
- **Sci-fi**: Energy core, Cargo crate, Holo pillar, Drone

**Whole set** lines up a whole era with labels. **Wear** controls scratches, rust and cracks.

## Live demo order (5 minutes)
1. Quality **Preview** → **Worlds** → Island Lagoon → **Build world**. Drag **Seed**: a new island every number.
2. **Image to World** → **Make sample map**: "I painted this in Paint; Python built the world." Then Mode **Photo to city** with any photo.
3. **Walls & Surfaces** → Concrete → **Build surface**, drag **Damage** from 0 to 1.
4. **Props** → War → **Whole set**, drag **Wear**.
5. Quality **Good** → **Render preview** (appears in the panel) or **Render image**.

## For developers
The scripts are built from the modules in `wb/` (core, worlds, image_world, props, surfaces, ui): edit a module, then run `python3 wb/build.py`.
