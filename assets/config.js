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

  /* true → small amber "draft" tag on the course slides until the software
     lists below are confirmed. Set to false before you present. */
  CURRICULUM_DRAFT: true,

  /* Courses, longest first (that's the "plans" order on the comparison slide).
     Every software name used below becomes a row; ✓ if the course has it, ✕ if not. */
  SOFTWARE_ORDER: [
    'Photoshop', 'Illustrator', 'Figma', 'After Effects', 'Premiere Pro',
    'Blender', 'Maya', 'ZBrush', 'Substance Painter', 'Unreal Engine 5', 'Nuke', 'Houdini'
  ],
  COURSES: [
    { name: 'Game Art & Design', months: 12, tagline: 'Build worlds people play in',
      software: ['Photoshop', 'Illustrator', 'Blender', 'Maya', 'ZBrush', 'Substance Painter', 'Unreal Engine 5'] },
    { name: 'VFX', months: 12, tagline: 'Make the impossible look filmed',
      software: ['Photoshop', 'After Effects', 'Premiere Pro', 'Maya', 'Blender', 'Nuke', 'Houdini'] },
    { name: 'Motion Graphics', months: 6, tagline: 'Ads, reels, titles, explainers',
      software: ['Photoshop', 'Illustrator', 'After Effects', 'Premiere Pro', 'Blender'] },
    { name: 'UI/UX Design', months: 4, tagline: 'Fastest route to freelancing', highlight: true,
      software: ['Photoshop', 'Illustrator', 'Figma'] }
  ],

  /* UI/UX spotlight slide: what students walk out with. */
  UIUX_SHIPS: [
    'A full app redesign case study',
    'A responsive landing page, designed and handed off',
    'A clickable Figma prototype',
    'A reusable design system',
    'A portfolio that gets the first client'
  ],

  /* Side-hustle calculator defaults (₹/hr range from the Xflow 2026 rate card). */
  CALC: { hours: 10, rate: 1200, rateMin: 800, rateMax: 4000, hoursMax: 30 }
};
