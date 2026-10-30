"""Small numpy image toolkit (no PIL / OpenCV / scipy needed inside Blender)."""
import numpy as np


def resize(a, h, w):
    """Bilinear resize of HxW or HxWxC float array. Box-reduces first for big downscales."""
    a = np.asarray(a, dtype=np.float32)
    H, W = a.shape[:2]
    while H >= 2 * h and W >= 2 * w and H > 1 and W > 1:
        H2, W2 = H // 2, W // 2
        a = a[:H2 * 2, :W2 * 2]
        a = (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) * 0.25
        H, W = a.shape[:2]
    if (H, W) == (h, w):
        return a.copy()
    ys = np.clip((np.arange(h) + 0.5) * H / h - 0.5, 0, H - 1)
    xs = np.clip((np.arange(w) + 0.5) * W / w - 0.5, 0, W - 1)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
    y1 = np.minimum(y0 + 1, H - 1); x1 = np.minimum(x0 + 1, W - 1)
    wy = (ys - y0).astype(np.float32); wx = (xs - x0).astype(np.float32)
    if a.ndim == 3:
        wy = wy[:, None, None]; wx = wx[None, :, None]
    else:
        wy = wy[:, None]; wx = wx[None, :]
    top = a[y0][:, x0] * (1 - wx) + a[y0][:, x1] * wx
    bot = a[y1][:, x0] * (1 - wx) + a[y1][:, x1] * wx
    return (top * (1 - wy) + bot * wy).astype(np.float32)


def fit(a, long_side):
    H, W = a.shape[:2]
    s = long_side / max(H, W)
    return resize(a, max(2, int(round(H * s))), max(2, int(round(W * s))))


def blur(a, r):
    """Fast separable box blur (3 passes ~ gaussian). r in pixels."""
    r = int(max(1, r))
    out = np.asarray(a, dtype=np.float32)
    for _ in range(3):
        for ax in (0, 1):
            pad = [(0, 0)] * out.ndim
            pad[ax] = (r + 1, r)
            p = np.pad(out, pad, mode='edge')
            c = np.cumsum(p, axis=ax, dtype=np.float64)
            n = out.shape[ax]
            sl_hi = [slice(None)] * out.ndim; sl_lo = [slice(None)] * out.ndim
            sl_hi[ax] = slice(2 * r + 1, 2 * r + 1 + n); sl_lo[ax] = slice(0, n)
            out = ((c[tuple(sl_hi)] - c[tuple(sl_lo)]) / (2 * r + 1)).astype(np.float32)
    return out


def luma(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def srgb_to_lin(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def lin_to_srgb(c):
    c = np.clip(c, 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055).astype(np.float32)


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(-1); mn = rgb.min(-1); d = mx - mn + 1e-6
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    s = np.where(mx > 1e-4, (mx - mn) / (mx + 1e-6), 0)
    return h, s, mx


def rgb_to_lab(rgb):
    """sRGB 0..1 -> CIE Lab (D65)."""
    l = srgb_to_lin(rgb)
    x = l[..., 0] * 0.4124 + l[..., 1] * 0.3576 + l[..., 2] * 0.1805
    y = l[..., 0] * 0.2126 + l[..., 1] * 0.7152 + l[..., 2] * 0.0722
    z = l[..., 0] * 0.0193 + l[..., 1] * 0.1192 + l[..., 2] * 0.9505
    x /= 0.9505; z /= 1.089

    def f(t):
        return np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)
    fx, fy, fz = f(x), f(y), f(z)
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], -1).astype(np.float32)


def push_pull(img, w, iters_min=1):
    """Fill pixels where weight w==0 from their surroundings (multi-scale push-pull inpainting).
    img: HxWxC, w: HxW in 0..1. Returns filled image."""
    img = np.asarray(img, np.float32)
    w = np.asarray(w, np.float32)
    squeeze = img.ndim == 2
    if squeeze:
        img = img[..., None]
    levels = []
    ci, cw = img * w[..., None], w.copy()
    while min(cw.shape) > 2:
        levels.append((ci, cw))
        H, W = cw.shape
        H2, W2 = (H + 1) // 2, (W + 1) // 2
        pi = np.pad(ci, ((0, H2 * 2 - H), (0, W2 * 2 - W), (0, 0)), mode='edge')
        pw = np.pad(cw, ((0, H2 * 2 - H), (0, W2 * 2 - W)), mode='edge')
        si = pi[0::2, 0::2] + pi[1::2, 0::2] + pi[0::2, 1::2] + pi[1::2, 1::2]
        sw = pw[0::2, 0::2] + pw[1::2, 0::2] + pw[0::2, 1::2] + pw[1::2, 1::2]
        ci, cw = si / 4.0, sw / 4.0
    # coarsest: normalise
    if cw.sum() < 1e-6:
        col = np.zeros_like(ci)
    else:
        mean = ci.reshape(-1, ci.shape[-1]).sum(0) / cw.sum()
        col = np.where(cw[..., None] > 1e-6, ci / np.maximum(cw[..., None], 1e-6), mean)
    for li, lw in reversed(levels):
        H, W = lw.shape
        up = resize(col, H, W)
        norm = li / np.maximum(lw[..., None], 1e-6)
        a = np.clip(lw * 4.0, 0, 1)[..., None]
        col = norm * a + up * (1 - a)
    out = img * w[..., None] + col * (1 - w[..., None])
    return out[..., 0] if squeeze else out


def erode(m, n):
    m = m.copy()
    for _ in range(n):
        p = np.pad(m, 1, mode='constant')
        m = m & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m


def dilate(m, n):
    m = m.copy()
    for _ in range(n):
        p = np.pad(m, 1, mode='constant')
        m = m | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def dist_inside(m, maxd=200):
    """Approximate distance (in pixels) from each inside pixel to the mask edge."""
    m = m.astype(bool)
    d = np.zeros(m.shape, np.float32)
    cur = m.copy()
    for i in range(maxd):
        if not cur.any():
            break
        d += cur
        p = np.pad(cur, 1, mode='constant')
        cur = cur & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return blur(d, 1) * m


def _components(m, keep_frac):
    H, W = m.shape
    lab = np.where(m, np.arange(H * W).reshape(H, W) + 1, 0).astype(np.int64)
    for _ in range(4 * (H + W)):
        p = np.pad(lab, 1, mode='constant')
        nb = np.maximum.reduce([lab, p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
        nb = np.where(m, nb, 0)
        if np.array_equal(nb, lab):
            break
        lab = nb
    vals, counts = np.unique(lab[lab > 0], return_counts=True)
    if keep_frac:
        return np.isin(lab, vals[counts >= keep_frac * counts.max()])
    return lab == vals[np.argmax(counts)]


def largest_component(m, keep_frac=None):
    """Keep the largest 4-connected component (or every component at least keep_frac of the largest).
    Big masks are labelled on a small copy (fast, converges), then mapped back."""
    m = np.asarray(m, bool)
    if not m.any():
        return m
    H, W = m.shape
    f = int(np.ceil(max(H, W) / 160))
    if f <= 1:
        return _components(m, keep_frac)
    h2, w2 = -(-H // f), -(-W // f)
    pm = np.zeros((h2 * f, w2 * f), bool); pm[:H, :W] = m
    small = pm.reshape(h2, f, w2, f).any(axis=(1, 3))
    keep = _components(small, keep_frac)
    keep = dilate(keep, 1)
    big = np.repeat(np.repeat(keep, f, 0), f, 1)[:H, :W]
    return m & big


def otsu(v, bins=64):
    v = v[np.isfinite(v)].ravel()
    if v.size == 0:
        return 0.5
    hist, edges = np.histogram(v, bins=bins)
    hist = hist.astype(np.float64); c = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist); w1 = w0[-1] - w0
    m0 = np.cumsum(hist * c) / np.maximum(w0, 1)
    m1 = (np.sum(hist * c) - np.cumsum(hist * c)) / np.maximum(w1, 1)
    between = w0 * w1 * (m0 - m1) ** 2
    return float(c[np.argmax(between)])


def kmeans(px, k=5, iters=12, seed=1):
    rng = np.random.default_rng(seed)
    px = px.reshape(-1, px.shape[-1])
    if len(px) > 6000:
        px = px[rng.choice(len(px), 6000, replace=False)]
    cent = px[rng.choice(len(px), k, replace=False)]
    for _ in range(iters):
        d = ((px[:, None, :] - cent[None]) ** 2).sum(-1)
        a = d.argmin(1)
        for j in range(k):
            if (a == j).any():
                cent[j] = px[a == j].mean(0)
    counts = np.bincount(a, minlength=k)
    order = np.argsort(-counts)
    return cent[order], counts[order] / counts.sum()
