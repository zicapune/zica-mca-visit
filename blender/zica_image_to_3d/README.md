# ZICA Image to 3D (Blender add-on)

Turns a picture (photo or 2D art) into a 3D scene you can orbit, step by step, with pop-up explanations in the viewport.
Tested on Blender 5.2.3 LTS (should work on 4.2 and newer). No AI service, no tokens: it runs offline.

## Install (once)
1. Download `zica_image_to_3d.zip` (do not unzip it).
2. Blender → Edit → Preferences → Add-ons → the small arrow (top right) → **Install from Disk…** → pick the zip → tick **ZICA Image to 3D**.
3. In the 3D Viewport press **N** → tab **ZICA 3D**.

## Use it: five steps, top to bottom
1. **Pick a picture**: click the big thumbnail to choose one of the 10 samples, or switch to **Your picture**.
2. **What the code sees**: press **Analyse the picture**. The panel lists what it found: photo or 2D art (you can override), scene type, top guesses of what is in it, subject size, materials, palette, light direction and colour, lens, and the build plan.
3. **Build it in 3D**: keep **Presentation mode** on for an audience (animated, with pop-ups explaining each step). Off = fast build.
4. **Explore it**: Photo view (the exact picture), orbit buttons, Play (keyed orbit), Final / Clay / Wire views, and a slider that fades the original picture over the camera view to compare. Middle mouse orbits, the wheel zooms.
5. **Render**: Preview / Normal (EEVEE) or Good / Cinematic (Cycles), still or the 240-frame orbit video.

## How it works
| Step | What the code does |
|---|---|
| Depth | Depth Anything V2 Small (offline) estimates how far every pixel is |
| Subject | IS-Net cut-out mask finds the main subject |
| Labels | MobileNetV2 (ImageNet) guesses what the picture shows |
| Style | Photos carry camera noise even in smooth areas; digital 2D art is clean |
| Materials | Colour + position + texture rules: skin (subsurface glow), water (moving ripples), stone (bump), cloth (sheen), shiny spots (coat) |
| Light | Fits brightness against surface angle (normals from depth) to find where the light comes from; highlight colour gives its temperature |
| Lens | Compares sharpness of subject and background: a blurry background means a long lens and depth of field |
| 3D | Every pixel is pushed along its camera ray to its depth, so the camera still sees the exact picture; the surface tears where depth jumps; the subject gets a rounded back from its silhouette |
| Matte background | The holes behind the subject are painted from the surrounding colours, and the canvas is extended past the frame |
| Fur | Animals get thousands of hair strands on the silhouette, coloured from the photo |
| Look-match loop | Renders a small frame, compares it with the picture (CIE Lab colour difference), corrects brightness, colour, tint and the picture-vs-3D-light balance, repeats, keeps the best pass |

## Smart vision for your own pictures
The 10 samples carry their depth, cut-out and labels pre-computed, so they work immediately.
For your own pictures open **Smart vision** at the bottom of the panel → **Install Smart vision (one time)**. It installs onnxruntime into Blender and downloads three free open models (~290 MB) from GitHub. After that everything runs offline. Without it, your pictures still build, using classic image-processing guesses (noticeably weaker depth and cut-out).

## Honest limits
- One picture has no information about the back of anything. The add-on invents a rounded back and paints the hidden background, so it looks right from the front and up to roughly 15 to 25 degrees around. Beyond that you see the invented shell. This is a "3D photo" (2.5D), not a full 360° model.
- Full 360° models from one picture need large generative 3D models (e.g. TripoSR / Hunyuan3D) with a strong GPU; not included.
- The look-match loop fixes brightness, colour, tint and light balance; it cannot add detail that is not in the picture.
- Style detection and material regions are rules, not understanding: check the panel and override the style if it guessed wrong.

## Models and licences
Depth Anything V2 Small (Apache-2.0), IS-Net general use via rembg (Apache-2.0 / MIT), MobileNetV2 from the ONNX model zoo (Apache-2.0).
