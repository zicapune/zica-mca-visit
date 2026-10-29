# ZICA World Builder (Blender 4.2+)

1. Download `zica_world_builder.py` (button "Download raw file" on GitHub).
2. Blender → **Scripting** tab → **Open** → pick the file → **Run Script** (Alt+P).
3. Back in the 3D Viewport press **N** → tab **ZICA**:
   - **Neon City**: 500+ towers, glowing windows, traffic, fog, fly-through camera.
   - **Island Lagoon**: noise terrain, snow peaks, 600 trees, clear water, sunset, drone orbit.
   - **Image → World**: pick any photo or painting; brightness becomes height, its colours paint the land, the darkest valleys fill with water.
   - **Fast preview (EEVEE)**: quick look on a slow PC.
   - **Cinematic 4K settings**: Cycles, 3840×2160, 96 samples + denoiser, GPU if found. Then **F12** for a still, **Ctrl+F12** for the 10-second animation.

Each button wipes the scene first. Build time: about 3 s (city), under 1 s (island, image). Tested on Blender 4.2.0.
Test renders: `preview-neon-city.png`, `preview-island.png` (low-res, low samples).
