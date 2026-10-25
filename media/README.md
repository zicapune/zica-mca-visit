# Media folder

Upload through GitHub: open the folder → **Add file → Upload files**. Keep each file **under 25 MB** (the website upload limit).

| Put this | Here | Named |
|---|---|---|
| Your logo (transparent PNG) | `media/brand/` | `logo.png` |
| Opening video for slide 1 (muted, loops) | `media/` | `hero.mp4` |
| Student work: videos and images | `media/reel/` | `01-title.mp4`, `02-title.jpg`, `03-another-title.mp4` … |
| YouTube / Shorts links | `media/reel/` | `youtube.txt` (one per line, see below) |

**Numbers decide the order.** `01-robot-short.mp4` shows as "Robot short", first in the grid. Images: jpg, png, webp. Videos: mp4 (H.264), webm.

**youtube.txt** — one link per line, number + title, then a `|`, then the link:

```
04 Car chase VFX | https://youtu.be/XXXXXXXXXXX
07 Game trailer | https://www.youtube.com/shorts/XXXXXXXXXXX
```

The first 7 items show on the "Made by students" slide; all of them show on `reel.html`.

**Compress big videos** (free, HandBrake): Preset *Fast 1080p30*, then Video → RF 24–26. A 1-minute reel lands around 15–20 MB.

**Offline (laptop, no internet):** the grid reads the folder list from GitHub. If you ever run the deck from a downloaded copy, add `media/reel/manifest.json` listing the file names, e.g. `["01-robot-short.mp4","02-poster.jpg"]`.
