"""Understanding the picture: style, scene, materials, palette, light, lens, build plan.
Everything here is classic image maths (numpy) on top of the depth / cut-out / labels from vision.py.
"""
import numpy as np
from . import imgops as io

# ImageNet index ranges
FUR = [(151, 299), (330, 389)]           # dogs, wolves, cats, bears, rabbits, monkeys...
BIRD = [(7, 25), (80, 101), (127, 147)]
FOOD = [(923, 970)]                      # food, fruit, veg
ART = {917: 'comic book', 921: 'book jacket'}
PRETTY = {'kite': 'kite (bird of prey)', 'tabby': 'tabby cat', 'tiger cat': 'striped cat', 'Egyptian cat': 'Egyptian cat',
          'cloak': 'cloak / hooded robe', 'comic book': 'comic-book art', 'chocolate sauce': 'chocolate / cream dessert'}
CITY = {576, 449, 698, 497, 663, 580, 538, 562, 483, 409, 437, 671, 510, 724}


def _in(i, ranges):
    return any(a <= i < b for a, b in ranges)


def kelvin_name(rgb):
    r, g, b = rgb
    t = (r - b) / max(r + g + b, 1e-4)
    if t > 0.12:
        return 'warm (about 3200 K)'
    if t > 0.04:
        return 'slightly warm (about 4500 K)'
    if t < -0.08:
        return 'cool / blue (about 8000 K)'
    return 'neutral daylight (about 5600 K)'


def analyze(rgb, vis):
    """rgb: HxWx3 sRGB 0..1. vis: dict(depth, mask, labels). Returns a plain dict (json-safe)."""
    small = io.fit(rgb, 256)
    h, w = small.shape[:2]
    dep = io.resize(vis['depth'], h, w)
    msk = io.resize(vis['mask'], h, w)
    H_, S_, V_ = io.rgb_to_hsv(small)
    g = io.luma(small)
    labels = vis.get('labels') or []
    top = labels[0] if labels else [-1, '', 0.0]

    # ---- style: photos carry camera noise even in their smoothest areas; digital 2D art is clean.
    s6 = io.fit(rgb, 640); g6 = io.luma(s6)
    hp = g6 - io.blur(g6, 1)
    lo6 = io.blur(g6, 4); gr6 = np.hypot(*np.gradient(lo6))
    noise = float(np.median(np.abs(hp)[gr6 < np.percentile(gr6, 40)]))
    kurt = float(np.mean(hp ** 4) / max(np.mean(hp ** 2) ** 2, 1e-12))
    hst = np.histogram(g6, 256, (0, 1))[0] / g6.size
    ent = float(-(hst[hst > 0] * np.log2(hst[hst > 0])).sum())
    q = (np.clip(s6, 0, 0.999) * 31).astype(int)
    cnt = np.sort(np.bincount((q[..., 0] * 1024 + q[..., 1] * 32 + q[..., 2]).ravel()))[::-1]
    top50 = float(cnt[:50].sum() / cnt.sum())
    ncol = int(np.searchsorted(np.cumsum(cnt) / cnt.sum(), 0.9)) + 1
    art_label = any(int(l[0]) in ART and l[2] > 0.3 for l in labels[:3])
    illus = noise < 0.0009 or art_label or (noise < 0.0016 and ent < 6.9 and kurt < 40 and top50 < 0.7)
    style = 'illustration' if illus else 'photo'
    flat = float((np.abs(hp) < 0.002).mean())

    # ---- subject confidence
    near_thr = io.otsu(dep)
    near = dep > near_thr
    hard = msk > 0.5
    cover = float(hard.mean())
    big = io.largest_component(hard, keep_frac=0.3) if hard.any() else hard
    soft = float(((msk > 0.15) & (msk < 0.85)).mean()) / max(cover, 1e-4)
    # a subject = a solid cut-out blob, mostly in the near half of the depth map
    near_share = float((hard & near).sum()) / max(hard.sum(), 1)
    subj_ok = 0.015 < cover < 0.8 and (soft < 0.35 or (soft < 0.45 and big.sum() > 0.9 * hard.sum())
                                       or (big.sum() > 0.55 * hard.sum() and near_share > 0.6 and soft < 0.9))

    # ---- material regions (colour + position + texture rules)
    yy = np.mgrid[0:h, 0:w][0] / h
    Y = 0.299 * small[..., 0] + 0.587 * small[..., 1] + 0.114 * small[..., 2]
    Cr = (small[..., 0] - Y) * 0.713 + 0.5
    Cb = (small[..., 2] - Y) * 0.564 + 0.5
    tex = io.blur(np.abs(g - io.blur(g, 1)), 2)
    skin = (Cr > 0.53) & (Cr < 0.70) & (Cb > 0.33) & (Cb < 0.50) & (Y > 0.18) & (S_ < 0.75) & (S_ > 0.12)
    skin &= (hard if subj_ok else near)
    sky = (dep < 0.1) & (tex < 0.035) & (((H_ > 185) & (H_ < 255) & (S_ > 0.2)) | ((S_ < 0.15) & (V_ > 0.75)) | (V_ < 0.06))
    sky = np.cumprod(sky, axis=0).astype(bool) | (sky & (dep < 0.03) & ~((V_ < 0.06) & (yy > 0.3)))   # must hang from the top
    water = (~sky) & (yy > 0.45) & (H_ > 140) & (H_ < 230) & (S_ > 0.1) & (~hard) & (dep > 0.1)
    foliage = (H_ > 65) & (H_ < 160) & (S_ > 0.3) & (V_ > 0.15)
    stone = (S_ < 0.2) & (tex > 0.025) & (V_ > 0.15) & (~skin)
    wood = (H_ > 12) & (H_ < 42) & (S_ > 0.3) & (S_ < 0.85) & (V_ < 0.55) & (V_ > 0.1) & (~skin) & (~hard if subj_ok else True)
    cloth = hard & (S_ > 0.45) & (tex < 0.03) & (~skin) if subj_ok else np.zeros_like(hard)
    gloss = (V_ > 0.85) & (S_ < 0.35) & (~sky) & (g > io.blur(g, 3) + 0.06)
    ti = int(top[0])
    fur = bool(_in(ti, FUR) and top[2] > 0.2)
    bird = bool(_in(ti, BIRD) or (ti == 21))   # 21 = kite (the bird)
    food = bool(_in(ti, FOOD))

    regions = {}
    # ---- scene type
    if style == 'illustration':
        scene = 'illustrated still life' if (food or ti in (968, 967, 966, 960, 504)) else 'character art'
    elif fur:
        scene = 'animal'
    elif bird:
        scene = 'bird in the sky'
    elif food:
        scene = 'still life'
    elif subj_ok and (skin & hard).mean() > 0.01 and cover > 0.12:
        scene = 'portrait'
    elif ti in CITY or (not subj_ok and dep.std() > 0.2):
        scene = 'street / city'
    elif sky.mean() > 0.35:
        scene = 'sky / landscape'
    else:
        scene = 'scene' if not subj_ok else 'object'

    if scene in ('street / city', 'still life', 'animal', 'bird in the sky'):
        skin = skin & False
    for name, m in (('skin', skin), ('sky', sky), ('water', water), ('foliage / leaves', foliage),
                    ('stone / concrete', stone), ('wood / brick', wood), ('cloth', cloth), ('shiny highlights', gloss)):
        p = float(m.mean())
        if p > 0.01:
            regions[name] = round(p * 100, 1)

    # ---- palette
    cent, share = io.kmeans(small.reshape(-1, 3), k=5)
    palette = [[float(c) for c in cent[i]] + [float(share[i])] for i in range(5)]

    # ---- light: fit brightness against surface angle (normals from depth), classic shape-from-shading
    dd = io.blur(dep, 2)
    gy, gx = np.gradient(dd)
    n = np.stack([-gx * 18, gy * 18, np.ones_like(dd)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    sel = (hard if subj_ok else near) & (g > 0.04) & (g < 0.96)
    lightdir = [-0.45, 0.55, 0.7]
    fit_ok = False
    if sel.sum() > 200:
        A = np.c_[np.ones(sel.sum()), n[sel]]
        coef, *_ = np.linalg.lstsq(A, g[sel], rcond=None)
        L = coef[1:]
        if np.linalg.norm(L) > 1e-3:
            L = L / np.linalg.norm(L)
            L[2] = max(L[2], 0.25)
            lightdir = list(L / np.linalg.norm(L)); fit_ok = True
    hi = g > np.percentile(g, 97)
    lo = g < np.percentile(g, 20)
    hcol = small[hi].mean(0) if hi.any() else np.array([1, 1, 1.0])
    lcol = small[lo].mean(0) if lo.any() else np.array([0.1, 0.1, 0.1])
    key_fill = float(np.clip((np.percentile(g, 90) + 0.02) / (np.percentile(g, 10) + 0.02), 1, 30))
    lx, ly = lightdir[0], lightdir[1]
    side = ('left' if lx < -0.25 else 'right' if lx > 0.25 else 'front')
    vert = ('above' if ly > 0.3 else 'below' if ly < -0.3 else 'eye level')
    mood = 'low-key (dark, dramatic)' if g.mean() < 0.28 else 'high-key (bright, soft)' if g.mean() > 0.62 else 'balanced'

    # ---- lens: how blurry is the background compared with the subject?
    fg = (hard if subj_ok else near)
    bg = ~io.dilate(fg, 3)
    detail = np.abs(g - io.blur(g, 1))
    sharp_fg = float(detail[fg].mean()) if fg.any() else 0.0
    sharp_bg = float(detail[bg].mean()) if bg.any() else sharp_fg
    blur_ratio = sharp_bg / max(sharp_fg, 1e-5)
    shallow = style == 'photo' and blur_ratio < 0.55
    fstop = float(np.interp(blur_ratio, [0.1, 0.55, 1.0], [1.4, 4.0, 11.0]))
    focal = {'portrait': 85, 'animal': 85, 'still life': 70, 'bird in the sky': 70, 'street / city': 35,
             'sky / landscape': 35, 'character art': 50, 'illustrated still life': 60}.get(scene, 50)
    ratio = {'portrait': 1.8, 'animal': 2.0, 'still life': 2.2, 'bird in the sky': 3.0, 'street / city': 3.5,
             'sky / landscape': 4.0, 'character art': 1.7, 'illustrated still life': 1.9}.get(scene, 2.5)

    plan = []
    if subj_ok:
        plan.append('Cut out the subject and give it a rounded 3D back')
    plan.append('Lift every pixel to its depth along the camera rays')
    plan.append('Tear the surface where depth jumps (so objects separate)')
    plan.append('Paint a matte background behind everything (fills the gaps)')
    mats = []
    if 'skin' in regions and style == 'photo':
        mats.append('skin: subsurface glow')
    if 'water' in regions:
        mats.append('water: moving ripples + reflections')
    if 'stone / concrete' in regions:
        mats.append('stone: bump from texture')
    if 'cloth' in regions:
        mats.append('cloth: soft sheen')
    if 'shiny highlights' in regions:
        mats.append('shiny spots: glossy coat')
    if style == 'illustration':
        mats.append('flat 2D colours kept, paper grain')
    if fur:
        mats.append('fur strands grown on the edges')
    plan.append('Materials: ' + (', '.join(mats) if mats else 'photo colours + surface bump'))
    plan.append('Light from %s, %s; lens %d mm%s' % (vert, side, focal, (', f/%.1f blur' % fstop) if shallow else ''))
    plan.append('Render, compare with the picture, fix, repeat (look-match loop)')

    return dict(
        style=style, flat=round(flat * 100), colours=ncol, noise=round(noise * 1e4, 1), scene=scene,
        labels=[[PRETTY.get(l[1], l[1]), round(l[2] * 100)] for l in labels[:3]],
        subject=bool(subj_ok), cover=round(cover * 100), regions=regions, palette=palette,
        light=dict(dir=[float(x) for x in lightdir], fit=fit_ok, side=side, vert=vert,
                   colour=[float(x) for x in hcol], shadow=[float(x) for x in lcol],
                   temp=kelvin_name(hcol), contrast=round(key_fill, 1), mood=mood),
        lens=dict(focal=focal, fstop=round(fstop, 1), shallow=bool(shallow), blur_ratio=round(blur_ratio, 2)),
        fur=fur, bird=bird, ratio=ratio, plan=plan, near_thr=float(near_thr),
        brightness=round(float(g.mean()) * 100),
    )


def region_map(rgb, vis, a, size=512):
    """RGBA texture driving the materials: R skin, G gloss/water, B bump strength, A cloth sheen."""
    small = io.fit(rgb, size)
    h, w = small.shape[:2]
    dep = io.resize(vis['depth'], h, w)
    msk = io.resize(vis['mask'], h, w)
    H_, S_, V_ = io.rgb_to_hsv(small)
    g = io.luma(small)
    yy = np.mgrid[0:h, 0:w][0] / h
    Y = 0.299 * small[..., 0] + 0.587 * small[..., 1] + 0.114 * small[..., 2]
    Cr = (small[..., 0] - Y) * 0.713 + 0.5
    Cb = (small[..., 2] - Y) * 0.564 + 0.5
    tex = io.blur(np.abs(g - io.blur(g, 1)), 2)
    photo = a['style'] == 'photo'
    skin = ((Cr > 0.53) & (Cr < 0.70) & (Cb > 0.33) & (Cb < 0.50) & (Y > 0.18) & (S_ > 0.12) & (S_ < 0.75)).astype(np.float32)
    if a['subject']:
        skin *= (msk > 0.5)
    if not photo or a['scene'] in ('still life', 'animal', 'bird in the sky', 'street / city'):
        skin *= 0.0 if not photo else 0.3
    water = ((yy > 0.45) & (H_ > 140) & (H_ < 230) & (S_ > 0.1) & (dep > 0.05) & (msk < 0.5)).astype(np.float32)
    gloss = np.clip(water + ((V_ > 0.9) & (S_ < 0.35)).astype(np.float32) * 0.6, 0, 1)
    if a['scene'] in ('still life', 'illustrated still life'):
        gloss = np.clip(gloss + 0.35 * (msk > 0.5), 0, 1)       # fruit / glass is glossy
    bump = np.clip(tex * 12, 0, 1) * (0.4 if photo else 0.15)
    cloth = ((S_ > 0.45) & (tex < 0.03) & (msk > 0.5)).astype(np.float32) * (1 - skin)
    rm = np.stack([io.blur(skin, 2), io.blur(gloss, 2), bump, io.blur(cloth, 2)], -1)
    return np.clip(rm, 0, 1)
