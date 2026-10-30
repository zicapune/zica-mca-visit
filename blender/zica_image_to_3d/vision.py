"""Seeing the picture: depth, subject cut-out and object labels.

Smart vision = three free, open models run OFFLINE on your own PC with onnxruntime
(no API, no tokens, no internet after the one-time download):
  * Depth Anything V2 Small (Apache-2.0)      - how far every pixel is
  * IS-Net general use (Apache-2.0, via rembg) - which pixels are the subject
  * MobileNetV2 ImageNet (Apache-2.0, ONNX zoo) - what the picture probably shows
Without them the add-on falls back to classic image-processing guesses (worse, but works).
The bundled sample pictures carry their results pre-computed, so they always work.
"""
import os, sys, json, threading, subprocess
import numpy as np
from . import imgops as io

HERE = os.path.dirname(__file__)

MODELS = {
    'depth': ('depth_anything_v2_vits.onnx',
              'https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0/depth_anything_v2_vits.onnx', 99),
    'cutout': ('isnet-general-use.onnx',
               'https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx', 179),
    'labels': ('mobilenetv2-12.onnx',
               'https://media.githubusercontent.com/media/onnx/models/main/validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx', 14),
}


def models_dir():
    d = os.environ.get('ZICA_I3D_MODELS')
    if not d:
        try:
            import bpy
            d = os.path.join(bpy.utils.user_resource('DATAFILES', path='zica_image_to_3d', create=True), 'models')
        except Exception:
            d = os.path.join(os.path.expanduser('~'), '.zica_image_to_3d', 'models')
    os.makedirs(d, exist_ok=True)
    return d


def modules_dir():
    try:
        import bpy
        d = bpy.utils.user_resource('SCRIPTS', path='modules', create=True)
    except Exception:
        d = os.path.join(os.path.expanduser('~'), '.zica_image_to_3d', 'modules')
    os.makedirs(d, exist_ok=True)
    if d not in sys.path:
        sys.path.append(d)
    return d


def ort():
    modules_dir()
    try:
        import onnxruntime
        return onnxruntime
    except Exception:
        return None


def model_path(key):
    return os.path.join(models_dir(), MODELS[key][0])


def smart_status():
    """(ready, text)"""
    has_ort = ort() is not None
    have = [k for k in MODELS if os.path.exists(model_path(k)) and os.path.getsize(model_path(k)) > 1_000_000]
    if has_ort and len(have) == len(MODELS):
        return True, 'Smart vision ready (offline)'
    miss = []
    if not has_ort:
        miss.append('onnxruntime')
    miss += [k for k in MODELS if k not in have]
    return False, 'Missing: ' + ', '.join(miss)


# ---------------------------------------------------------------- one-time setup (thread)
SETUP = {'running': False, 'msg': '', 'done': False, 'error': ''}


def _setup_worker():
    try:
        if ort() is None:
            SETUP['msg'] = 'Installing onnxruntime into Blender (1-3 min)...'
            py = sys.executable
            subprocess.run([py, '-m', 'ensurepip', '--upgrade'], capture_output=True)
            r = subprocess.run([py, '-m', 'pip', 'install', '--upgrade', '--no-deps', '--target', modules_dir(), 'onnxruntime'],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError('pip failed: ' + (r.stderr or r.stdout)[-400:])
            import importlib
            importlib.invalidate_caches()
        import urllib.request
        for key, (fname, url, mb) in MODELS.items():
            dst = model_path(key)
            if os.path.exists(dst) and os.path.getsize(dst) > 1_000_000:
                continue
            SETUP['msg'] = 'Downloading %s model (%d MB)...' % (key, mb)
            tmp = dst + '.part'
            with urllib.request.urlopen(url) as resp, open(tmp, 'wb') as f:
                total = int(resp.headers.get('Content-Length') or mb * 1e6)
                got = 0
                while True:
                    b = resp.read(1 << 20)
                    if not b:
                        break
                    f.write(b); got += len(b)
                    SETUP['msg'] = 'Downloading %s model: %d%%' % (key, 100 * got // max(total, 1))
            os.replace(tmp, dst)
        SETUP['msg'] = 'Smart vision ready.'
        SETUP['done'] = True
    except Exception as e:
        SETUP['error'] = str(e)
        SETUP['msg'] = 'Setup failed: ' + str(e)[:160]
    SETUP['running'] = False


def start_setup():
    if SETUP['running']:
        return
    SETUP.update(running=True, done=False, error='', msg='Starting...')
    threading.Thread(target=_setup_worker, daemon=True).start()


# ---------------------------------------------------------------- model runners
_SESS = {}


def _session(key):
    o = ort()
    if o is None or not os.path.exists(model_path(key)):
        return None
    if key not in _SESS:
        so = o.SessionOptions()
        so.log_severity_level = 3
        _SESS[key] = o.InferenceSession(model_path(key), so, providers=['CPUExecutionProvider'])
    return _SESS[key]


MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def run_depth(rgb):
    s = _session('depth')
    if s is None:
        return None
    x = (io.resize(rgb, 518, 518) - MEAN) / STD
    out = s.run(None, {s.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
    d = io.resize(out.astype(np.float32), rgb.shape[0], rgb.shape[1])
    lo, hi = np.percentile(d, 0.5), np.percentile(d, 99.5)
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)   # 1 = near, 0 = far


def run_cutout(rgb):
    s = _session('cutout')
    if s is None:
        return None
    x = io.resize(rgb, 1024, 1024)
    x = (x / max(x.max(), 1e-6) - 0.5) / 1.0
    out = s.run(None, {s.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    out = (out - out.min()) / max(out.max() - out.min(), 1e-6)
    return io.resize(out.astype(np.float32), rgb.shape[0], rgb.shape[1])


_LABELS = None


def labels_list():
    global _LABELS
    if _LABELS is None:
        with open(os.path.join(HERE, 'imagenet_labels.txt'), encoding='utf-8') as f:
            _LABELS = [l.strip() for l in f]
    return _LABELS


def run_labels(rgb, top=5):
    s = _session('labels')
    if s is None:
        return None
    H, W = rgb.shape[:2]
    c = min(H, W)
    crop = rgb[(H - c) // 2:(H - c) // 2 + c, (W - c) // 2:(W - c) // 2 + c]
    x = (io.resize(crop, 224, 224) - MEAN) / STD
    out = s.run(None, {s.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
    p = np.exp(out - out.max()); p /= p.sum()
    idx = np.argsort(-p)[:top]
    L = labels_list()
    return [[int(i), L[i], float(p[i])] for i in idx]


# ---------------------------------------------------------------- classic fallbacks (no models)
def heuristic_depth(rgb):
    """Guess depth without a model: sharp/detailed areas and lower areas are nearer,
    the centre is a little nearer, flat bright areas at the top (sky) are far."""
    H, W = rgb.shape[:2]
    g = io.luma(rgb)
    lap = np.abs(g - io.blur(g, 2))
    sharp = io.blur(lap, max(4, W // 40))
    sharp = sharp / max(np.percentile(sharp, 98), 1e-6)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lower = yy / H
    centre = 1 - np.sqrt(((xx / W - 0.5) * 1.6) ** 2 + ((yy / H - 0.5) * 1.2) ** 2)
    d = 0.45 * np.clip(sharp, 0, 1) + 0.35 * lower + 0.2 * np.clip(centre, 0, 1)
    d = io.blur(d, max(3, W // 60))
    lo, hi = np.percentile(d, 1), np.percentile(d, 99)
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)


def heuristic_cutout(rgb):
    """Guess the subject: pixels whose colour differs from the picture's border colours,
    near the centre, kept as one blob."""
    small = io.fit(rgb, 160)
    h, w = small.shape[:2]
    lab = io.rgb_to_lab(small)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    cent, _ = io.kmeans(border, k=4)
    d = np.min(((lab[..., None, :] - cent[None, None]) ** 2).sum(-1), axis=-1) ** 0.5
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    prior = 1 - np.sqrt(((xx / w - 0.5) * 1.5) ** 2 + ((yy / h - 0.5) * 1.3) ** 2)
    s = io.blur(d / max(np.percentile(d, 98), 1e-6), 2) * (0.5 + 0.5 * np.clip(prior, 0, 1))
    m = s > io.otsu(s)
    m = io.dilate(io.erode(m, 2), 2)
    m = io.largest_component(m)
    m = io.blur(m.astype(np.float32), 1.5)
    return np.clip(io.resize(m, rgb.shape[0], rgb.shape[1]), 0, 1)


def see(rgb, cache=None):
    """Return dict(depth, mask, labels, source). Uses the cache (.npz next to sample pictures) first."""
    if cache and os.path.exists(cache):
        z = np.load(cache)
        H, W = rgb.shape[:2]
        meta = json.loads(str(z['meta']))
        return dict(depth=io.resize(z['depth'].astype(np.float32), H, W),
                    mask=io.resize(z['mask'].astype(np.float32) / 255.0, H, W),
                    labels=meta.get('labels') or [], source='Smart vision (pre-computed for this sample)')
    depth = cutout = labels = None
    try:
        depth = run_depth(rgb); cutout = run_cutout(rgb); labels = run_labels(rgb)
    except Exception as e:
        print('ZICA Image to 3D: model failed, using classic guesses:', e)
    smart = depth is not None and cutout is not None
    if depth is None:
        depth = heuristic_depth(rgb)
    if cutout is None:
        cutout = heuristic_cutout(rgb)
    return dict(depth=depth, mask=cutout, labels=labels or [],
                source='Smart vision (offline models)' if smart else 'Classic guesses (Smart vision not installed)')


def save_cache(path, v):
    """Used to pre-compute the bundled samples."""
    d = io.fit(v['depth'], 640); m = io.fit(v['mask'], 640)
    np.savez_compressed(path, depth=d.astype(np.float16), mask=(np.clip(m, 0, 1) * 255).astype(np.uint8),
                        meta=json.dumps({'labels': v['labels']}))
