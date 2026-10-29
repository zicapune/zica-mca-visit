# ZICA × ASM IBMR — MCA industrial visit deck

Live: **https://zicapune.github.io/zica-mca-visit/** · Student reel: **/reel.html**

## Presenting
| Key | Does |
|---|---|
| → / Space / PgDn (clicker) | Next build or slide |
| ← / PgUp | Back |
| F | Fullscreen |
| P | Presenter window: notes, next slide, timer. Drag it to your laptop screen, deck on the projector |
| T | Hide/show the timeline |
| B | Blackout |
| number + Enter | Jump to slide |
| , . / [ ] | Student-work carousel: back, next / slower, faster |
| M | Admin mode (OTP 1111): ✕ archives a media item, Archive → Restore brings it back |
| ? | Help |

Use **Chrome**, press **F**, then **P**. Projector set to "Extend", not "Duplicate", if you want the presenter window.

## Code Lab (slides 9–16)
Seven live demos. **Drag any amber number** in the code left/right with the mouse; the picture updates as you drag. The clicker plays each slide's planned changes, so it also works hands-free.
- Rigging and Flock: move the mouse over the picture (the arm follows it; the birds scatter from it).
- Image demo: upload `media/lab/photo.jpg` to use a real photo instead of the generated sunset.

## Backup
The original deck (before the Code Lab) is kept two ways: the folder `backup-v1/` (viewable at /zica-mca-visit/backup-v1/) and the branch `backup-v1-original`.

## Team slides
Names, titles and photo file names are in `index.html` between the comments `✏️ TEAM SLIDES — EDIT HERE ONLY`. Change only the text inside the `pname`, `prole` and `pbio` tags. A name in [square brackets] shows an amber Draft tag until replaced.

## Editing
Everything you'd normally change lives in **`assets/config.js`**: course software lists, durations, the Creative Quest link (QR appears automatically), calculator defaults, and the draft tag (`CURRICULUM_DRAFT: false` before you present).

Media uploads: see **`media/README.md`**.

## Files
- `index.html` — the slides (31, plus the studio-visits slide when `SHOW_VISITS` is on) (speaker notes are in each slide's `<aside class="notes">`)
- `presenter.html` — presenter view (opened by P)
- `reel.html` — full-screen student work grid
- `assets/lab.js` — the Code Lab demos
- `assets/` — styles, engine, fonts (self-hosted, so the deck works offline)

## Blender demo
`blender/zica_world_builder.py` — run once in Blender 4.2+, then N → ZICA tab. See `blender/README.md`.

Visitors: MCA students of ASM IBMR (Audyogik Shikshan Mandal's Institute of Business Management and Research, Chinchwad).
