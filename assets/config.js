/* =====================================================================
   ZICA × ASM IBMR — deck config.js   ← the ONLY file you need to edit
   ===================================================================== */
window.DECK_CONFIG = {
  /* GitHub repo the media wall reads from (media/reel/ folder). */
  REPO: 'zicapune/zica-mca-visit',
  BRANCH: 'main',

  /* Logo: upload a transparent PNG/SVG to media/brand/ and keep this name. */
  LOGO: 'media/brand/logo.png',

  /* Creative Quest link. Leave '' → the last slide shows a QR placeholder.
     Paste the live URL here → a real QR code appears automatically. */
  QUEST_URL: 'https://zicapune.github.io/creative-quest/?src=mca_visit_qr',

  /* Admin mode: press M on any slide, enter the code, then ✕ on any photo/video
     moves it to the Archive (never deleted; restore any time from the Archive button). */
  ADMIN: {
    PIN: '1111',
    SUPABASE_URL: 'https://elrgbounsplqheblmvaa.supabase.co',
    SUPABASE_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVscmdib3Vuc3BscWhlYmxtdmFhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI5NTQyNTIsImV4cCI6MjEwODUzMDI1Mn0.UsIiV3Fy1UajAPBcXrLPj3gMpPfck2DuvGZ9FJCNZ_o'
  },

  /* Studio-visits slide: stays hidden until its photos/videos are uploaded to media/visits/… */
  SHOW_VISITS: false,

  /* true → small amber "draft" tag on the course slides. Off: lists below come
     from the ZICA Curriculum 2026–27 workbook. */
  CURRICULUM_DRAFT: false,

  /* Courses, longest first (that's the "plans" order on the comparison slide).
     Badge on top of each card: highlight:true → "Highly recommended", others → "Recommended".
     Add badge: '…' to any course to override its wording.
     Source: ZICA Curriculum 2026–27 (tabs PPAGAD, PPVFX, Prog in ADV MG, Prog in UI & UX).
     Every software name used below becomes a row; ✓ if the course has it, ✕ if not. */
  SOFTWARE_ORDER: [
    'Photoshop', 'Illustrator', 'Adobe XD', 'Figma', 'Notion',
    'Premiere Pro & Audition', 'After Effects', 'Element 3D',
    'Maya', 'Blender', 'Mixamo', 'Unreal Engine + Blueprints',
    'Nuke', 'SilhouetteFX', '3DEqualizer'
  ],
  COURSES: [
    { name: 'Game Art & Design', tier: 'Professional Program', months: 12, tagline: 'Build worlds people play in',
      software: ['Photoshop', 'Illustrator', 'After Effects', 'Blender', 'Mixamo', 'Unreal Engine + Blueprints'] },
    { name: 'Visual Effects', tier: 'Professional Program', months: 12, tagline: 'Make the impossible look filmed',
      software: ['Photoshop', 'Premiere Pro & Audition', 'Maya', 'After Effects', 'Nuke', 'SilhouetteFX', '3DEqualizer'] },
    { name: 'Adv. Motion Graphics', tier: 'Program', months: 6, tagline: 'Ads, reels, titles, explainers',
      software: ['Photoshop', 'Illustrator', 'Premiere Pro & Audition', 'After Effects', 'Element 3D'] },
    { name: 'UI & UX', tier: 'Program', months: 6, alt: { months: 12, tier: 'Professional Program' }, tagline: 'Fastest route to freelancing', highlight: true,
      software: ['Photoshop', 'Adobe XD', 'Notion', 'Figma'] }
  ],

  /* ASM IBMR hybrid offer — hidden view on the "Pick a path" slide.
     O (or click the small "Pick a path" tag) opens it · → rolls the months to the hybrid plan · → again = next slide
     R (or click "Minimum batch") shows/hides prices · ← / Esc closes.
     from = standard months, to = hybrid months (from Shikha ma'am's offer sheet). Prices in ₹. */
  ASM_OFFER: {
    kicker: 'Hybrid learning · what we recommend for ASM IBMR',
    title: 'Learn on your campus. And online.',
    sub: 'Same programs, rebuilt around your MCA timetable.',
    hours: '2 hrs',
    week: ['Campus', 'Campus', 'Online', 'Online', 'Online'],   // Mon → Fri
    minBatch: 5,
    rows: [
      { name: 'Game Art & Design', versions: [
        { tier: 'Professional Program', from: 12, to: 7, mrp: 170000, offer: 120000 } ] },
      { name: 'UI & UX', highlight: true, versions: [
        { tier: 'Professional Program', from: 12, to: 9, mrp: 150000, offer: 100000 },
        { tier: 'Program',              from: 6,  to: 3, mrp: 65000,  offer: 45000 } ] },
      { name: 'Digital Design & Marketing', versions: [
        { tier: 'Professional Program', from: 12, to: 8, mrp: 150000, offer: 100000 } ] }
    ]
  },

  /* UI/UX spotlight: the 12-month Professional Program adds these on top of the 6-month tools. */
  UIUX_UPGRADE: { months: 12, adds: ['Illustrator', 'Miro', 'FigJam', 'Framer'] },

  /* UI/UX spotlight slide: what students walk out with (from the 6-month syllabus). */
  UIUX_SHIPS: [
    'UX laws and heuristics, applied to real apps',
    'A clickable mobile app prototype in Adobe XD',
    'UX research documented in Notion',
    'A Figma design system with components and variables',
    'Micro-interactions, design specs and developer handoff'
  ],

  /* Side-hustle calculator defaults (₹/hr range from the Xflow 2026 rate card). */
  CALC: { hours: 10, rate: 1200, rateMin: 800, rateMax: 4000, hoursMax: 30,
    /* One chip per role; the clicker also steps through them in this order.
       Sources: Xflow India rate card 2026 (UI/UX, graphic, video); RocketBrush 2025 India 3D rates ($15–50/hr at ₹94 per $). */
    ROLES: [
      { name: 'UI/UX design',        min: 800,  max: 4000, start: 1200 },
      { name: 'Motion & video',      min: 500,  max: 3000, start: 1000 },
      { name: '3D & game art',       min: 1400, max: 4700, start: 1800 },
      { name: 'Graphic design',      min: 700,  max: 3000, start: 1000 }
    ] }
};
