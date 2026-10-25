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
| ? | Help |

Use **Chrome**, press **F**, then **P**. Projector set to "Extend", not "Duplicate", if you want the presenter window.

## Code Lab (slides 6–13)
Seven live demos. **Drag any amber number** in the code left/right with the mouse; the picture updates as you drag. The clicker plays each slide's planned changes, so it also works hands-free.
- Rigging and Flock: move the mouse over the picture (the arm follows it; the birds scatter from it).
- Image demo: upload `media/lab/photo.jpg` to use a real photo instead of the generated sunset.

## Backup
The original deck (before the Code Lab) is kept two ways: the folder `backup-v1/` (viewable at /zica-mca-visit/backup-v1/) and the branch `backup-v1-original`.

## Editing
Everything you'd normally change lives in **`assets/config.js`**: course software lists, durations, the Creative Quest link (QR appears automatically), calculator defaults, and the draft tag (`CURRICULUM_DRAFT: false` before you present).

Media uploads: see **`media/README.md`**.

## Files
- `index.html` — the 26 slides (speaker notes are in each slide's `<aside class="notes">`)
- `presenter.html` — presenter view (opened by P)
- `reel.html` — full-screen student work grid
- `assets/lab.js` — the Code Lab demos
- `assets/` — styles, engine, fonts (self-hosted, so the deck works offline)
