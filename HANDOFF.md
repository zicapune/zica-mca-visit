# Brief for a Claude task linked to Chaitanya's PC

Deck: https://zicapune.github.io/zica-mca-visit/ — a presentation for MCA students of ASM IBMR (Audyogik Shikshan Mandal's Institute of Business Management and Research, Chinchwad) visiting ZICA Pune Kothrud on 30–31 Oct 2026.

## Your job
Read **only** `C:\Users\Chaitanya Jadkar\Desktop\ZICA-PPT\ppt-inbox` (the media extracted from an 88-slide PPT made for another college, plus `presentation.pdf`, the same PPT exported). Touch no other folder on the PC. The PC is slow: no heavy processing there. Copy the files into your cloud workspace and work there.

1. Open `presentation.pdf` first to learn which picture sat on which slide and what each section was (world art yesterday/today/tomorrow, AVGC industry, student work, Gen AI student work, renders, matte paintings, fun activities, studio visits).
2. Ignore slides that only made sense for the previous college and the AI-generated concept images, except as ideas for the AVGC story.
3. Pick the **best** student work only (about 20–30 pieces). Sort and title them well.
   - Images → `media/reel/NN-title.jpg` (1920 px long side, JPG quality ~80, under 600 KB). The number sets the order, the title shows on screen: `03-matte-painting-desert-city.jpg` shows as "Matte painting desert city".
   - Gen AI work: start the title with "Gen AI": `12-gen-ai-brand-reel-coffee.jpg`.
   - Videos → `media/reel/NN-title.mp4`, H.264 1080p, `-preset veryfast`, CRF 26, no audio unless it matters, 5–15 MB each, under 25 MB always.
4. Studio-visit photos → `media/visits/animation/`, `media/visits/vfx/`, `media/visits/gaming/`, `media/visits/uiux/` (`01-studio-name.jpg` …). Then set `SHOW_VISITS: true` in `assets/config.js`.
5. Fun activities → `media/fun/NN-title.jpg` (not wired into a slide yet; list them in the report).
6. Do not change slides, styles or scripts. Only add media and the visits flag.
7. Commit to `main` with a clear message, push, and write `media/INBOX-REPORT.md`: what you placed where, what you skipped and why, and AVGC-story ideas from the PDF.
8. Delete nothing on the PC. Never upload the raw PPT or the whole inbox to the repo (it's public).
