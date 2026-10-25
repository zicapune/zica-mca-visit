/* =====================================================================
   lab.js — the Code Lab: seven live demos.
   Every amber number in the code can be dragged left/right with the mouse.
   The clicker (→) plays each slide's preset changes, so it works hands-free.
   Loaded before deck.js; deck.js picks up window.LAB_HOOKS.
   ===================================================================== */
(function () {
  'use strict';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var KW = /\b(for|let|const|function|if|return|void|vec2|vec3|float|in|of|new)\b/g;

  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function ease(t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

  /* ---------- code rendering with draggable numbers ---------- */
  function highlight(line) {
    var ci = line.indexOf('//'), code = ci > -1 ? line.slice(0, ci) : line, cm = ci > -1 ? line.slice(ci) : '';
    var h = esc(code)
      .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="n">$1</span>')
      .replace(KW, '<span class="k">$1</span>')
      .replace(/\b([a-zA-Z_]\w*)(?=\()/g, '<span class="f">$1</span>');
    h = h.replace(/§(\w+)§/g, '<span class="scrub" data-p="$1" title="Drag left or right"></span>');
    return h + (cm ? '<span class="c">' + esc(cm) + '</span>' : '');
  }

  function Lab(def) {
    var P = {}, spans = [], tweens = {}, raf = 0, inited = false, slide, t0 = performance.now();
    Object.keys(def.params).forEach(function (k) { P[k] = def.params[k].v; });
    var api = { P: P, dirty: true };

    function fmt(k) { var d = def.params[k]; return d.dec ? P[k].toFixed(d.dec) : String(Math.round(P[k])); }
    function paint() { spans.forEach(function (s) { s.textContent = fmt(s.dataset.p); }); }
    function set(k, v) { var d = def.params[k]; P[k] = clamp(v, d.min, d.max); if (!d.dec) P[k] = d.int ? Math.round(P[k]) : P[k]; api.dirty = true; }

    function tweenTo(target, dur) {
      Object.keys(target).forEach(function (k) {
        if (!(k in def.params)) { api[k] = target[k]; return; }
        tweens[k] = { from: P[k], to: target[k], t0: performance.now(), dur: reduce ? 1 : (dur || 1400) };
      });
    }
    function presetFor(st) {
      var o = {};
      Object.keys(def.params).forEach(function (k) { o[k] = def.params[k].v; });
      Object.keys(def.view || {}).forEach(function (k) { o[k] = def.view[k]; });
      for (var i = 1; i <= st; i++) Object.assign(o, (def.presets || {})[i] || {});
      return o;
    }

    function init() {
      inited = true;
      var pre = slide.querySelector('.lab-code');
      pre.innerHTML = def.code.map(highlight).join('\n');
      spans = Array.prototype.slice.call(pre.querySelectorAll('.scrub'));
      spans.forEach(function (s) {
        var d = def.params[s.dataset.p];
        s.addEventListener('pointerdown', function (e) {
          e.preventDefault(); s.setPointerCapture(e.pointerId);
          var x0 = e.clientX, v0 = P[s.dataset.p];
          delete tweens[s.dataset.p];
          document.body.classList.add('scrubbing');
          spans.forEach(function (o) { if (o.dataset.p === s.dataset.p) o.classList.add('live'); });
          function mv(ev) {
            var scale = stageScale();
            set(s.dataset.p, v0 + ((ev.clientX - x0) / scale) / (d.px || 6) * (d.step || 1));
            paint(); if (def.onParam) def.onParam(api, s.dataset.p);
          }
          function up() {
            s.removeEventListener('pointermove', mv); s.removeEventListener('pointerup', up);
            document.body.classList.remove('scrubbing');
            spans.forEach(function (o) { o.classList.remove('live'); });
          }
          s.addEventListener('pointermove', mv); s.addEventListener('pointerup', up);
        });
      });
      api.canvas = slide.querySelector('.lab-view canvas');
      api.hud = slide.querySelector('.lab-hud');
      def.init(api);
      paint();
    }

    function frame(now) {
      Object.keys(tweens).forEach(function (k) {
        var tw = tweens[k], p = Math.min(1, (now - tw.t0) / tw.dur);
        set(k, lerp(tw.from, tw.to, ease(p)));
        if (p >= 1) { P[k] = tw.to; delete tweens[k]; }
      });
      if (Object.keys(tweens).length) paint();
      def.frame(api, (now - t0) / 1000);
      raf = requestAnimationFrame(frame);
    }

    return {
      enter: function (s) {
        slide = s;
        if (!inited) init();
        cancelAnimationFrame(raf); raf = requestAnimationFrame(frame);
      },
      leave: function () { cancelAnimationFrame(raf); raf = 0; },
      step: function (s, st) {
        if (!inited) { slide = s; init(); }
        tweenTo(presetFor(st), def.tween);
        var say = s.querySelector('.lab-say');
        if (say && say.dataset.say) {
          var arr = JSON.parse(say.dataset.say), txt = arr[Math.min(st, arr.length - 1)];
          if (say.textContent !== txt) { say.textContent = txt; say.classList.remove('pop'); void say.offsetWidth; say.classList.add('pop'); }
        }
      }
    };
  }

  function stageScale() {
    var m = (document.getElementById('stage').style.transform || '').match(/scale\(([\d.]+)\)/);
    return m ? +m[1] : 1;
  }

  /* hi-dpi 2D canvas helper: draws in CSS pixels */
  function ctx2d(cv, k) {
    k = k || 1.5;
    var w = cv.clientWidth || 880, h = cv.clientHeight || 620;
    cv.width = Math.round(w * k); cv.height = Math.round(h * k);
    var c = cv.getContext('2d'); c.setTransform(k, 0, 0, k, 0, 0);
    return { c: c, w: w, h: h };
  }

  function mouseOn(api) {
    api.mouse = { x: 0, y: 0, t: -1e9 };
    api.canvas.addEventListener('pointermove', function (e) {
      var r = api.canvas.getBoundingClientRect();
      api.mouse.x = (e.clientX - r.left) / r.width * api.W;
      api.mouse.y = (e.clientY - r.top) / r.height * api.H;
      api.mouse.t = performance.now();
    });
  }
  function mouseFresh(api) { return performance.now() - api.mouse.t < 2500; }

  var H = {};

  /* =====================================================================
     1 · An image is a 2D array  (Texture)
     ===================================================================== */
  H['lab-img'] = Lab({
    params: {
      C: { v: 1, min: -4, max: 12, step: 1, px: 14, int: true },
      N: { v: 0, min: -2, max: 2, step: 1, px: 18, int: true }
    },
    view: { zoom: 0 },
    presets: { 1: { zoom: 1 }, 2: { zoom: 0, C: 8, N: -1 }, 3: { C: 1, N: 1 } },
    code: [
      '// a photo = rows × columns of numbers (0–255)',
      'const kernel = [',
      '  [§N§, §N§, §N§],',
      '  [§N§, §C§, §N§],',
      '  [§N§, §N§, §N§]',
      '];',
      'for (let y = 1; y < H - 1; y++)',
      '  for (let x = 1; x < W - 1; x++)',
      '    out[y][x] = sum3x3(img, x, y, kernel);'
    ],
    init: function (api) {
      var g = ctx2d(api.canvas, 1); api.c = g.c; api.W = g.w; api.H = g.h;
      var SW = 360, SH = Math.round(SW * g.h / g.w);
      api.SW = SW; api.SH = SH;
      var src = document.createElement('canvas'); src.width = SW; src.height = SH;
      api.src = src; api.out = document.createElement('canvas'); api.out.width = SW; api.out.height = SH;
      paintScene(src.getContext('2d'), SW, SH);
      api.srcData = src.getContext('2d').getImageData(0, 0, SW, SH);
      // a photo of yours wins if you upload media/lab/photo.jpg
      var img = new Image();
      img.onload = function () {
        var sx = src.getContext('2d'), r = Math.max(SW / img.width, SH / img.height);
        sx.drawImage(img, (SW - img.width * r) / 2, (SH - img.height * r) / 2, img.width * r, img.height * r);
        api.srcData = sx.getImageData(0, 0, SW, SH); api.dirty = true; findFocus(api);
      };
      img.src = 'media/lab/photo.jpg';
      api.zoomV = 0; findFocus(api);
    },
    frame: function (api) {
      var c = api.c, W = api.W, Hh = api.H, SW = api.SW, SH = api.SH;
      if (api.dirty) { convolve(api); api.dirty = false; }
      api.zoomV += ((api.zoom || 0) - api.zoomV) * 0.06;
      var z = api.zoomV, cols = 12, rows = Math.round(cols * Hh / W);
      var fx = api.fx, fy = api.fy;              // zoom focus: the most contrasty spot
      var cw = lerp(SW, cols, Math.pow(z, 0.35)), ch = cw * Hh / W;
      var x0 = clamp(fx - cw / 2, 0, SW - cw), y0 = clamp(fy - ch / 2, 0, SH - ch);
      c.imageSmoothingEnabled = z < 0.02;
      c.fillStyle = '#000'; c.fillRect(0, 0, W, Hh);
      c.drawImage(api.out, x0, y0, cw, ch, 0, 0, W, Hh);
      if (z > 0.75) {
        var a = (z - 0.75) / 0.25, px = W / cw;
        var d = api.outData.data;
        c.font = '600 ' + Math.round(px * 0.3) + 'px "JetBrains Mono", monospace';
        c.textAlign = 'center'; c.textBaseline = 'middle';
        for (var yy = Math.floor(y0); yy < y0 + ch; yy++) for (var xx = Math.floor(x0); xx < x0 + cw; xx++) {
          var i = (yy * SW + xx) * 4, L = Math.round(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]);
          var sx = (xx - x0 + 0.5) * px, sy = (yy - y0 + 0.5) * px;
          c.globalAlpha = a * 0.35; c.strokeStyle = '#000'; c.strokeRect((xx - x0) * px, (yy - y0) * px, px, px);
          c.globalAlpha = a; c.fillStyle = L > 140 ? '#0d0e13' : '#eceef4'; c.fillText(L, sx, sy);
        }
        c.globalAlpha = 1;
      }
      api.hud.textContent = z > 0.75 ? 'One square = one pixel. The number is its brightness.'
        : SW + ' × ' + SH + ' pixels = ' + (SW * SH).toLocaleString('en-IN') + ' numbers per colour channel';
    }
  });

  function findFocus(api) {
    // pick the spot with the strongest edges near the middle, so the zoomed numbers visibly change
    var d = api.srcData.data, SW = api.SW, SH = api.SH, best = -1, bx = SW / 2, by = SH / 2;
    function L(x, y) { var i = (y * SW + x) * 4; return 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]; }
    for (var y = Math.round(SH * .25); y < SH * .75; y += 3) for (var x = Math.round(SW * .25); x < SW * .75; x += 3) {
      var g = 0;
      for (var k = -4; k <= 4; k += 2) g += Math.abs(L(x + k, y - 4) - L(x + k, y + 4)) + Math.abs(L(x - 4, y + k) - L(x + 4, y + k));
      if (g > best) { best = g; bx = x; by = y; }
    }
    api.fx = bx; api.fy = by;
  }

  function convolve(api) {
    var SW = api.SW, SH = api.SH, s = api.srcData.data;
    var C = api.P.C, N = api.P.N, sum = C + 8 * N, div = sum > 0 ? sum : 1;
    var out = api.outData || (api.outData = api.out.getContext('2d').createImageData(SW, SH)), o = out.data;
    for (var y = 0; y < SH; y++) for (var x = 0; x < SW; x++) {
      var i = (y * SW + x) * 4;
      for (var ch = 0; ch < 3; ch++) {
        var acc = s[i + ch] * C;
        if (N !== 0) {
          for (var dy = -1; dy <= 1; dy++) for (var dx = -1; dx <= 1; dx++) {
            if (!dx && !dy) continue;
            var xx = clamp(x + dx, 0, SW - 1), yy = clamp(y + dy, 0, SH - 1);
            acc += s[(yy * SW + xx) * 4 + ch] * N;
          }
        }
        o[i + ch] = acc / div;
      }
      o[i + 3] = 255;
    }
    api.out.getContext('2d').putImageData(out, 0, 0);
  }

  function paintScene(c, W, Hh) {
    var sky = c.createLinearGradient(0, 0, 0, Hh);
    sky.addColorStop(0, '#1b1440'); sky.addColorStop(.45, '#c2410c'); sky.addColorStop(.62, '#ffb547'); sky.addColorStop(.63, '#2b1a2e'); sky.addColorStop(1, '#0d0e13');
    c.fillStyle = sky; c.fillRect(0, 0, W, Hh);
    var sun = c.createRadialGradient(W * .62, Hh * .4, 0, W * .62, Hh * .4, Hh * .32);
    sun.addColorStop(0, '#fff3d6'); sun.addColorStop(.28, '#ffd27a'); sun.addColorStop(.3, 'rgba(255,181,71,.55)'); sun.addColorStop(1, 'rgba(255,122,26,0)');
    c.fillStyle = sun; c.fillRect(0, 0, W, Hh);
    var layers = [['#3a1f3d', .52, 18], ['#26172b', .58, 26], ['#140f1a', .64, 34]];
    layers.forEach(function (L, li) {
      c.fillStyle = L[0]; c.beginPath(); c.moveTo(0, Hh);
      for (var x = 0; x <= W; x += 4) {
        var y = Hh * L[1] - (Math.sin(x * .021 + li * 2) * .5 + Math.sin(x * .053 + li) * .3 + Math.sin(x * .11 + li * 4) * .2 + .4) * L[2] * 1.4;
        c.lineTo(x, y);
      }
      c.lineTo(W, Hh); c.closePath(); c.fill();
    });
    // water reflection
    c.fillStyle = 'rgba(255,181,71,.35)';
    for (var r = 0; r < 14; r++) { var y = Hh * .7 + r * 6, w = 70 - r * 4; c.fillRect(W * .62 - w / 2 + Math.sin(r) * 6, y, w, 2); }
    // a wireframe cube on the shore — this is a 3D school after all
    c.strokeStyle = '#5ce1e6'; c.lineWidth = 1.5;
    var cx = W * .2, cy = Hh * .76, s = 26;
    c.strokeRect(cx, cy - s, s, s); c.strokeRect(cx + 10, cy - s - 8, s, s);
    c.beginPath(); c.moveTo(cx, cy - s); c.lineTo(cx + 10, cy - s - 8); c.moveTo(cx + s, cy - s); c.lineTo(cx + s + 10, cy - s - 8);
    c.moveTo(cx, cy); c.lineTo(cx + 10, cy - 8); c.moveTo(cx + s, cy); c.lineTo(cx + s + 10, cy - 8); c.stroke();
  }

  /* =====================================================================
     2 · Recursion grows a tree  (Model)
     ===================================================================== */
  H['lab-tree'] = Lab({
    params: {
      ANGLE: { v: 22, min: 0, max: 120, step: 1, px: 4 },
      SHRINK: { v: 0.72, min: 0.5, max: 0.8, step: 0.01, px: 6, dec: 2 },
      DEPTH: { v: 1, min: 1, max: 13, step: 1, px: 16, dec: 0 }
    },
    presets: { 1: { DEPTH: 11 }, 2: { ANGLE: 88, SHRINK: 0.7 }, 3: { ANGLE: 22, SHRINK: 0.74, DEPTH: 12 } },
    tween: 2200,
    code: [
      'function branch(len, depth) {',
      '  if (depth === 0) return;          // base case',
      '  drawLine(len);',
      '  turn(+§ANGLE§); branch(len * §SHRINK§, depth - 1);',
      '  turn(-§ANGLE§ * 2); branch(len * §SHRINK§, depth - 1);',
      '  turn(+§ANGLE§);',
      '}',
      'branch(150, §DEPTH§);'
    ],
    init: function (api) { var g = ctx2d(api.canvas); api.c = g.c; api.W = g.w; api.H = g.h; },
    frame: function (api, t) {
      var c = api.c, W = api.W, Hh = api.H, P = api.P;
      c.clearRect(0, 0, W, Hh);
      var full = Math.floor(P.DEPTH), frac = P.DEPTH - full, maxD = Math.ceil(P.DEPTH - 1e-6);
      var sway = reduce ? 0 : Math.sin(t * 1.3) * 2.2;
      var len0 = Hh * 0.26;
      c.lineCap = 'round';
      function br(x, y, a, len, d, k) {
        if (d === 0) return;
        var level = maxD - d;                       // 0 = trunk
        var grow = (d === 1 && frac > 0) ? frac : 1;
        var x2 = x + Math.cos(a) * len * grow, y2 = y + Math.sin(a) * len * grow;
        var u = maxD > 1 ? level / (maxD - 1) : 0;
        c.strokeStyle = 'rgb(' + Math.round(lerp(255, 92, u)) + ',' + Math.round(lerp(181, 225, u)) + ',' + Math.round(lerp(71, 230, u)) + ')';
        c.lineWidth = Math.max(0.6, (d / maxD) * 12);
        c.beginPath(); c.moveTo(x, y); c.lineTo(x2, y2); c.stroke();
        if (grow < 1) return;
        var A = (P.ANGLE + sway * (level / 4)) * Math.PI / 180;
        br(x2, y2, a + A, len * P.SHRINK, d - 1, k);
        br(x2, y2, a - A, len * P.SHRINK, d - 1, k);
      }
      br(W / 2, Hh - 30, -Math.PI / 2, len0, maxD, 0);
      var n = Math.pow(2, Math.round(P.DEPTH)) - 1;
      api.hud.textContent = 'One function. It calls itself ' + n.toLocaleString('en-IN') + ' times.';
    }
  });

  /* =====================================================================
     3 · Noise makes worlds  (Environment)
     ===================================================================== */
  var perm = (function () {
    var p = [], i; for (i = 0; i < 256; i++) p[i] = i;
    var s = 1337; for (i = 255; i > 0; i--) { s = (s * 16807) % 2147483647; var j = s % (i + 1), t = p[i]; p[i] = p[j]; p[j] = t; }
    return p.concat(p);
  })();
  function fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); }
  var G8 = [[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0], [0, 1], [0, -1]];
  function grad(h, x, y) { var g = G8[h & 7]; return g[0] * x + g[1] * y; }
  function noise2(x, y) {
    var X = Math.floor(x) & 255, Y = Math.floor(y) & 255; x -= Math.floor(x); y -= Math.floor(y);
    var u = fade(x), v = fade(y), A = perm[X] + Y, B = perm[X + 1] + Y;
    return lerp(lerp(grad(perm[A], x, y), grad(perm[B], x - 1, y), u), lerp(grad(perm[A + 1], x, y - 1), grad(perm[B + 1], x - 1, y - 1), u), v);
  }
  function fbm(x, y) { return noise2(x, y) * .6 + noise2(x * 2.1, y * 2.1) * .28 + noise2(x * 4.3, y * 4.3) * .12; }

  H['lab-noise'] = Lab({
    params: {
      SEED: { v: 7, min: 0, max: 999, step: 1, px: 2 },
      SCALE: { v: 0.07, min: 0.02, max: 0.2, step: 0.005, px: 6, dec: 3 },
      HEIGHT: { v: 26, min: 0, max: 60, step: 1, px: 5 },
      SPEED: { v: 0, min: 0, max: 0.6, step: 0.02, px: 8, dec: 2 }
    },
    presets: { 1: { SEED: 412 }, 2: { SPEED: 0.25 } },
    tween: 3200,
    code: [
      'for (let z = 0; z < 56; z++)',
      '  for (let x = 0; x < 80; x++) {',
      '    let h = noise(x * §SCALE§ + §SEED§, (z + t) * §SCALE§);',
      '    vertex(x, h * §HEIGHT§, z);',
      '    paint(h < 0 ? "water" : h < 0.45 ? "grass" : "snow");',
      '  }',
      't += §SPEED§;        // fly forward'
    ],
    init: function (api) { var g = ctx2d(api.canvas, 1.25); api.c = g.c; api.W = g.w; api.H = g.h; api.off = 0; },
    frame: function (api) {
      var c = api.c, W = api.W, Hh = api.H, P = api.P;
      api.off += P.SPEED;
      var GX = 80, GZ = 56, cx = W / 2, hor = Hh * 0.30, f = 560, camH = 34, zc = 7;
      var sky = c.createLinearGradient(0, 0, 0, Hh);
      sky.addColorStop(0, '#141a2e'); sky.addColorStop(.32, '#3a2a4a'); sky.addColorStop(.33, '#0d0e13'); sky.addColorStop(1, '#0d0e13');
      c.fillStyle = sky; c.fillRect(0, 0, W, Hh);
      var hs = [], zi, xi, fl = Math.floor(api.off), fr = api.off - fl;
      for (zi = 0; zi <= GZ; zi++) { hs[zi] = []; for (xi = 0; xi <= GX; xi++) hs[zi][xi] = fbm(xi * P.SCALE + P.SEED * 0.73, (zi + fl) * P.SCALE + P.SEED * 0.31); }
      function proj(xi, zi, h) {
        var X = (xi - GX / 2) * 1.0, Z = (GZ - zi) - fr + zc, Y = Math.max(h, 0) * P.HEIGHT;
        return [cx + X * f / Z, hor + (camH - Y) * f / Z * 0.42];
      }
      for (zi = GZ - 1; zi >= 0; zi--) {          // far → near (painter's algorithm)
        for (xi = 0; xi < GX; xi++) {
          var h = (hs[zi][xi] + hs[zi][xi + 1] + hs[zi + 1][xi] + hs[zi + 1][xi + 1]) / 4;
          var p1 = proj(xi, zi, hs[zi][xi]), p2 = proj(xi + 1, zi, hs[zi][xi + 1]), p3 = proj(xi + 1, zi + 1, hs[zi + 1][xi + 1]), p4 = proj(xi, zi + 1, hs[zi + 1][xi]);
          var slope = (hs[zi][xi + 1] - hs[zi][xi]) * 3 + (hs[zi + 1][xi] - hs[zi][xi]) * 2;
          var sh = clamp(0.75 + slope * 2.2, 0.35, 1.25), col;
          if (h < 0) col = [29 + h * 30, 78 + h * 40, 107 + h * 40];
          else if (h < 0.05) col = [201, 163, 107];
          else if (h < 0.3) col = [79, 138 - h * 80, 75];
          else if (h < 0.45) col = [107, 98, 88];
          else col = [236, 238, 244];
          var fog = clamp(zi / GZ, 0, 1);
          var r = lerp(col[0] * sh, 20, fog * fog), g = lerp(col[1] * sh, 22, fog * fog), b = lerp(col[2] * sh, 36, fog * fog);
          c.fillStyle = 'rgb(' + (r | 0) + ',' + (g | 0) + ',' + (b | 0) + ')';
          c.beginPath(); c.moveTo(p1[0], p1[1]); c.lineTo(p2[0], p2[1]); c.lineTo(p3[0], p3[1]); c.lineTo(p4[0], p4[1]); c.closePath(); c.fill();
        }
      }
      api.hud.textContent = 'World #' + Math.round(P.SEED) + '  ·  ' + (GX * GZ).toLocaleString('en-IN') + ' heights from one function';
    }
  });

  /* =====================================================================
     4 · Rigging is maths  (Rig) — FABRIK inverse kinematics
     ===================================================================== */
  H['lab-ik'] = Lab({
    params: {
      SEGMENTS: { v: 3, min: 2, max: 16, step: 1, px: 14, int: true },
      LENGTH: { v: 130, min: 30, max: 200, step: 1, px: 2 }
    },
    presets: { 1: { SEGMENTS: 14, LENGTH: 38 } },
    code: [
      '// FABRIK inverse kinematics, every frame',
      'const N = §SEGMENTS§, L = §LENGTH§;',
      'joint[N] = target;',
      'for (let i = N - 1; i >= 0; i--)   // reach',
      '  joint[i] = pull(joint[i + 1], joint[i], L);',
      'joint[0] = base;',
      'for (let i = 1; i <= N; i++)       // stay on base',
      '  joint[i] = pull(joint[i - 1], joint[i], L);'
    ],
    init: function (api) {
      var g = ctx2d(api.canvas); api.c = g.c; api.W = g.w; api.H = g.h; mouseOn(api);
      api.J = []; api.tgt = { x: g.w / 2, y: g.h / 3 };
    },
    frame: function (api, t) {
      var c = api.c, W = api.W, Hh = api.H, P = api.P, n = Math.round(P.SEGMENTS), L = P.LENGTH;
      var base = { x: W / 2, y: Hh - 70 }, J = api.J, i, k;
      while (J.length < n + 1) J.push({ x: base.x, y: base.y - J.length * L });
      J.length = n + 1;
      var goal = mouseFresh(api) ? api.mouse : { x: W / 2 + Math.sin(t * 0.9) * W * 0.36, y: Hh * 0.42 + Math.sin(t * 1.7) * Hh * 0.26 };
      api.tgt.x += (goal.x - api.tgt.x) * 0.2; api.tgt.y += (goal.y - api.tgt.y) * 0.2;
      function pull(a, b) { var dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1; return { x: a.x + dx / d * L, y: a.y + dy / d * L }; }
      for (k = 0; k < 4; k++) {
        J[n] = { x: api.tgt.x, y: api.tgt.y };
        for (i = n - 1; i >= 0; i--) J[i] = pull(J[i + 1], J[i]);
        J[0] = { x: base.x, y: base.y };
        for (i = 1; i <= n; i++) J[i] = pull(J[i - 1], J[i]);
      }
      c.clearRect(0, 0, W, Hh);
      // floor grid
      c.strokeStyle = 'rgba(92,225,230,.12)'; c.lineWidth = 1;
      for (i = 0; i < W; i += 40) { c.beginPath(); c.moveTo(i, 0); c.lineTo(i, Hh); c.stroke(); }
      for (i = 0; i < Hh; i += 40) { c.beginPath(); c.moveTo(0, i); c.lineTo(W, i); c.stroke(); }
      // base
      c.fillStyle = '#2b2f42'; c.beginPath(); c.roundRect(base.x - 70, base.y - 6, 140, 40, 10); c.fill();
      // bones
      c.lineCap = 'round';
      for (i = 0; i < n; i++) {
        var w = lerp(30, 8, i / Math.max(1, n - 1));
        c.strokeStyle = i % 2 ? '#ff7a1a' : '#ffb547'; c.lineWidth = w;
        c.beginPath(); c.moveTo(J[i].x, J[i].y); c.lineTo(J[i + 1].x, J[i + 1].y); c.stroke();
      }
      for (i = 0; i <= n; i++) { c.fillStyle = '#0d0e13'; c.strokeStyle = '#5ce1e6'; c.lineWidth = 3; c.beginPath(); c.arc(J[i].x, J[i].y, i === 0 ? 14 : 7, 0, 7); c.fill(); c.stroke(); }
      // target
      c.save(); c.translate(api.tgt.x, api.tgt.y); c.rotate(Math.PI / 4); c.strokeStyle = '#eceef4'; c.lineWidth = 2.5; c.strokeRect(-11, -11, 22, 22); c.restore();
      api.hud.textContent = mouseFresh(api) ? 'Following your mouse' : n + ' bones, solved ' + Math.round(60 * 4) + ' times a second. Move the mouse here to take control.';
    }
  });

  /* =====================================================================
     5 · One curve = "smooth"  (Animate / UI)
     ===================================================================== */
  function bezier(x1, y1, x2, y2) {
    function bx(t) { return 3 * x1 * t * (1 - t) * (1 - t) + 3 * x2 * t * t * (1 - t) + t * t * t; }
    function by(t) { return 3 * y1 * t * (1 - t) * (1 - t) + 3 * y2 * t * t * (1 - t) + t * t * t; }
    return function (x) { var lo = 0, hi = 1, m; for (var i = 0; i < 24; i++) { m = (lo + hi) / 2; if (bx(m) < x) lo = m; else hi = m; } return by((lo + hi) / 2); };
  }
  H['lab-ease'] = Lab({
    params: {
      X1: { v: 0, min: 0, max: 1, step: 0.01, px: 4, dec: 2 },
      Y1: { v: 0, min: -0.6, max: 2, step: 0.01, px: 4, dec: 2 },
      X2: { v: 1, min: 0, max: 1, step: 0.01, px: 4, dec: 2 },
      Y2: { v: 1, min: -0.6, max: 2, step: 0.01, px: 4, dec: 2 }
    },
    presets: { 1: { X1: 0.16, Y1: 1, X2: 0.3, Y2: 1 }, 2: { X1: 0.34, Y1: 1.56, X2: 0.64, Y2: 1 } },
    tween: 900,
    code: [
      '.card {',
      '  transition: transform 0.9s',
      '    cubic-bezier(§X1§, §Y1§, §X2§, §Y2§);',
      '}',
      '.card.open {',
      '  transform: translateX(480px);',
      '}'
    ],
    init: function (api) { var g = ctx2d(api.canvas); api.c = g.c; api.W = g.w; api.H = g.h; },
    frame: function (api, t) {
      var c = api.c, W = api.W, Hh = api.H, P = api.P;
      var fn = bezier(P.X1, P.Y1, P.X2, P.Y2);
      var cyc = 3.2, u = (t % cyc) / cyc, dir, p;      // 0.9s go, hold, 0.9s back, hold
      if (u < .28) { p = fn(u / .28); dir = 1; } else if (u < .5) { p = 1; dir = 0; } else if (u < .78) { p = 1 - fn((u - .5) / .28); dir = -1; } else { p = 0; dir = 0; }
      var lin = u < .28 ? u / .28 : u < .5 ? 1 : u < .78 ? 1 - (u - .5) / .28 : 0;
      c.clearRect(0, 0, W, Hh);
      // graph
      var gx = 40, gy = 50, gs = 250;
      c.strokeStyle = '#2b2f42'; c.lineWidth = 1.5; c.strokeRect(gx, gy, gs, gs);
      c.strokeStyle = 'rgba(141,147,168,.4)'; c.setLineDash([6, 6]); c.beginPath(); c.moveTo(gx, gy + gs); c.lineTo(gx + gs, gy); c.stroke(); c.setLineDash([]);
      c.strokeStyle = '#ffb547'; c.lineWidth = 4; c.beginPath();
      for (var i = 0; i <= 60; i++) { var x = i / 60; var y = fn(x); i ? c.lineTo(gx + x * gs, gy + gs - y * gs) : c.moveTo(gx + x * gs, gy + gs - y * gs); }
      c.stroke();
      var h1 = [gx + P.X1 * gs, gy + gs - P.Y1 * gs], h2 = [gx + P.X2 * gs, gy + gs - P.Y2 * gs];
      c.strokeStyle = '#5ce1e6'; c.lineWidth = 2; c.beginPath(); c.moveTo(gx, gy + gs); c.lineTo(h1[0], h1[1]); c.moveTo(gx + gs, gy); c.lineTo(h2[0], h2[1]); c.stroke();
      [h1, h2].forEach(function (h) { c.fillStyle = '#5ce1e6'; c.beginPath(); c.arc(h[0], h[1], 8, 0, 7); c.fill(); });
      c.fillStyle = '#8d93a8'; c.font = '500 18px "JetBrains Mono", monospace'; c.fillText('time →', gx + gs - 70, gy + gs + 28);
      c.save(); c.translate(gx - 14, gy + 80); c.rotate(-Math.PI / 2); c.fillText('position →', 0, 0); c.restore();
      // lanes
      function lane(y, prog, label, accent) {
        var x0 = 340, x1 = W - 40 - 170;
        c.fillStyle = '#15171f'; c.beginPath(); c.roundRect(x0 - 10, y - 10, x1 - x0 + 190, 150, 20); c.fill();
        c.fillStyle = '#8d93a8'; c.font = '600 20px "Bricolage Grotesque", sans-serif'; c.fillText(label, x0 + 8, y + 22);
        var x = lerp(x0, x1, prog);
        c.fillStyle = accent ? '#eceef4' : '#2b2f42'; c.beginPath(); c.roundRect(x, y + 40, 170, 90, 16); c.fill();
        c.fillStyle = accent ? '#ff7a1a' : '#4a4f66'; c.beginPath(); c.roundRect(x + 16, y + 58, 40, 40, 12); c.fill();
        c.fillStyle = accent ? '#c7cad6' : '#3a3f55'; c.fillRect(x + 68, y + 64, 80, 9); c.fillRect(x + 68, y + 82, 50, 9);
      }
      lane(90, lin, 'linear', false);
      lane(300, p, 'your curve', true);
      c.fillStyle = '#ffb547'; c.beginPath(); c.arc(gx + (u < .28 ? u / .28 : u < .5 ? 1 : u < .78 ? (u - .5) / .28 : 0) * gs, gy + gs - (dir === -1 ? 1 - p : p) * gs, 9, 0, 7); c.fill();
      var name = (P.Y1 > 1.05) ? 'springy overshoot' : (P.X1 < .2 && P.Y1 > .8) ? 'ease-out: how premium apps feel' : (Math.abs(P.X1) < .02 && Math.abs(P.Y1) < .02 && P.X2 > .98 && P.Y2 > .98) ? 'linear: robotic' : 'custom curve';
      api.hud.textContent = name;
    }
  });

  /* =====================================================================
     6 · Shaders paint every pixel  (Light / Render) — WebGL
     ===================================================================== */
  H['lab-shader'] = Lab({
    params: {
      FREQ: { v: 8, min: 1, max: 40, step: 0.5, px: 5, dec: 1 },
      SPEED: { v: 1, min: 0, max: 8, step: 0.1, px: 5, dec: 1 },
      GLOW: { v: 1, min: 0.2, max: 3, step: 0.05, px: 5, dec: 2 }
    },
    presets: { 1: { FREQ: 14 }, 2: { SPEED: 4, GLOW: 1.1 } },
    code: [
      'void main() {          // runs for EVERY pixel',
      '  vec2 uv = pixelPosition();',
      '  for (float i = 0.0; i < 3.0; i++) {',
      '    uv = fract(uv * 1.5) - 0.5;  // repeat',
      '    float d = length(uv);',
      '    d = sin(d * §FREQ§ + time * §SPEED§) / §FREQ§;',
      '    color += palette(i + time) * §GLOW§ * 0.01 / abs(d);',
      '  }',
      '}'
    ],
    init: function (api) {
      var cv = api.canvas, w = cv.clientWidth || 880, h = cv.clientHeight || 620;
      cv.width = w; cv.height = h; api.W = w; api.H = h;
      var gl = cv.getContext('webgl', { antialias: false, preserveDrawingBuffer: true });
      if (!gl) { api.hud.textContent = 'WebGL is off in this browser'; return; }
      var vs = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
      var fs = [
        'precision mediump float;uniform vec2 res;uniform float time,FREQ,SPEED,GLOW;',
        'vec3 palette(float t){return vec3(.5)+vec3(.5)*cos(6.28318*(t+vec3(.0,.33,.67)));}',
        'void main(){vec2 uv=(gl_FragCoord.xy*2.-res)/res.y;vec2 uv0=uv;vec3 col=vec3(0.);',
        'for(float i=0.;i<3.;i++){uv=fract(uv*1.5)-.5;float d=length(uv)*exp(-length(uv0));',
        'vec3 c=palette(length(uv0)+i*.4+time*.25);d=sin(d*FREQ+time*SPEED)/FREQ;d=abs(d);d=pow(GLOW*.01/d,1.2);col+=c*d;}',
        'gl_FragColor=vec4(col,1.);}'
      ].join('');
      function sh(type, src) { var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; }
      var pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(pr); gl.useProgram(pr);
      var b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
      var loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      api.gl = gl; api.u = {}; ['res', 'time', 'FREQ', 'SPEED', 'GLOW'].forEach(function (n) { api.u[n] = gl.getUniformLocation(pr, n); });
      api.fps = 60; api.last = performance.now();
    },
    frame: function (api, t) {
      var gl = api.gl; if (!gl) return;
      var now = performance.now(), dt = now - api.last; api.last = now; api.fps = api.fps * 0.95 + (1000 / Math.max(1, dt)) * 0.05;
      gl.viewport(0, 0, api.W, api.H);
      gl.uniform2f(api.u.res, api.W, api.H); gl.uniform1f(api.u.time, t);
      gl.uniform1f(api.u.FREQ, api.P.FREQ); gl.uniform1f(api.u.SPEED, api.P.SPEED); gl.uniform1f(api.u.GLOW, api.P.GLOW);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      var runs = Math.round(api.W * api.H * Math.min(api.fps, 120) / 1e6);
      api.hud.textContent = (api.W * api.H).toLocaleString('en-IN') + ' pixels × ' + Math.round(api.fps) + ' fps ≈ ' + runs + ' million runs a second';
    }
  });

  /* =====================================================================
     7 · Three rules = a flock  (VFX / crowds) — boids
     ===================================================================== */
  H['lab-boids'] = Lab({
    params: {
      SEPARATE: { v: 1.6, min: 0, max: 4, step: 0.05, px: 4, dec: 1 },
      ALIGN: { v: 1.0, min: 0, max: 3, step: 0.05, px: 4, dec: 1 },
      GATHER: { v: 1.0, min: 0, max: 3, step: 0.05, px: 4, dec: 1 }
    },
    presets: { 1: { ALIGN: 0, GATHER: 0 }, 2: { ALIGN: 1.4, GATHER: 2.6, SEPARATE: 1.2 } },
    tween: 900,
    code: [
      'for (const bird of flock) {',
      '  bird.velocity += separation(bird) * §SEPARATE§  // avoid',
      '                 + alignment(bird)  * §ALIGN§  // match',
      '                 + cohesion(bird)   * §GATHER§; // stick',
      '  bird.position += bird.velocity;',
      '}'
    ],
    init: function (api) {
      var g = ctx2d(api.canvas, 1.25); api.c = g.c; api.W = g.w; api.H = g.h; mouseOn(api);
      api.B = [];
      for (var i = 0; i < 240; i++) { var a = Math.random() * 7; api.B.push({ x: Math.random() * g.w, y: Math.random() * g.h, vx: Math.cos(a) * 2, vy: Math.sin(a) * 2, k: i % 5 === 0 }); }
    },
    frame: function (api) {
      var c = api.c, W = api.W, Hh = api.H, P = api.P, B = api.B, n = B.length, i, j;
      var R = 70, RS = 24, fleeOn = mouseFresh(api);
      for (i = 0; i < n; i++) {
        var b = B[i], ax = 0, ay = 0, cx = 0, cy = 0, sx = 0, sy = 0, cnt = 0;
        for (j = 0; j < n; j++) {
          if (i === j) continue;
          var o = B[j], dx = o.x - b.x, dy = o.y - b.y;
          if (dx > W / 2) dx -= W; else if (dx < -W / 2) dx += W;
          if (dy > Hh / 2) dy -= Hh; else if (dy < -Hh / 2) dy += Hh;
          var d2 = dx * dx + dy * dy;
          if (d2 < R * R) {
            cnt++; ax += o.vx; ay += o.vy; cx += dx; cy += dy;
            if (d2 < RS * RS) { var d = Math.sqrt(d2) || 1; sx -= dx / d * (RS - d) / RS; sy -= dy / d * (RS - d) / RS; }
          }
        }
        if (cnt) {
          b.vx += ((ax / cnt - b.vx) * 0.05) * P.ALIGN + (cx / cnt) * 0.0009 * P.GATHER + sx * 0.25 * P.SEPARATE;
          b.vy += ((ay / cnt - b.vy) * 0.05) * P.ALIGN + (cy / cnt) * 0.0009 * P.GATHER + sy * 0.25 * P.SEPARATE;
        }
        b.vx += (Math.random() - .5) * 0.12; b.vy += (Math.random() - .5) * 0.12;
        if (fleeOn) { var mx = b.x - api.mouse.x, my = b.y - api.mouse.y, md = Math.hypot(mx, my); if (md < 140) { b.vx += mx / md * 0.6; b.vy += my / md * 0.6; } }
        var sp = Math.hypot(b.vx, b.vy), mxs = 3.6, mns = 1.6;
        if (sp > mxs) { b.vx *= mxs / sp; b.vy *= mxs / sp; } else if (sp < mns) { b.vx *= mns / sp; b.vy *= mns / sp; }
      }
      c.fillStyle = 'rgba(13,14,19,.28)'; c.fillRect(0, 0, W, Hh);
      for (i = 0; i < n; i++) {
        var q = B[i]; q.x = (q.x + q.vx + W) % W; q.y = (q.y + q.vy + Hh) % Hh;
        var a = Math.atan2(q.vy, q.vx);
        c.save(); c.translate(q.x, q.y); c.rotate(a);
        c.fillStyle = q.k ? '#5ce1e6' : '#ffb547';
        c.beginPath(); c.moveTo(9, 0); c.lineTo(-6, 4.5); c.lineTo(-3, 0); c.lineTo(-6, -4.5); c.closePath(); c.fill();
        c.restore();
      }
      api.hud.textContent = n + ' birds, 3 rules, nobody in charge' + (fleeOn ? '  ·  your mouse is a hawk' : '');
    }
  });

  window.LAB_HOOKS = H;
})();
