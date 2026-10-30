/* =====================================================================
   deck.js — slide engine for the ZICA × ASM IBMR deck
   ===================================================================== */
(function () {
  'use strict';
  var CFG = window.DECK_CONFIG || {};
  var stage = document.getElementById('stage');
  // slides switched off in config.js (e.g. data-show-if="SHOW_VISITS") are removed before anything counts them
  Array.prototype.slice.call(document.querySelectorAll('.slide[data-show-if]')).forEach(function (el) {
    if (!(window.DECK_CONFIG || {})[el.getAttribute('data-show-if')]) el.parentNode.removeChild(el);
  });
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var N = slides.length;
  var cur = 0, step = 0, entered = -1;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var ICON_Y = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7"/></svg>';
  var ICON_X = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7L7 17"/></svg>';

  /* ---------- fit 1920×1080 to the window ---------- */
  function fit() {
    var s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = 'translate(-50%, -50%) scale(' + s + ')';
  }
  window.addEventListener('resize', fit);
  fit();

  /* ---------- brand ---------- */
  (function () {
    var brand = $('#brand'), img = $('img', brand);
    if (!CFG.LOGO) return;
    img.onload = function () { img.hidden = false; brand.classList.remove('no-logo'); };
    img.src = CFG.LOGO;
  })();
  if (CFG.CURRICULUM_DRAFT) document.body.classList.add('draft');

  /* ---------- steps ---------- */
  function maxStep(i) {
    var m = 0;
    $$('[data-step]', slides[i]).forEach(function (e) { m = Math.max(m, +e.dataset.step); });
    return m;
  }

  /* ---------- timeline ---------- */
  var tl = $('#timeline'), tlHead = $('#tlHead'), tlFill = $('#tlFill');
  slides.forEach(function (s, i) {
    var x = (i / (N - 1)) * 100;
    var k = document.createElement('div');
    k.className = 'tl-key'; k.style.left = x + '%'; k.title = (i + 1) + ' · ' + (s.dataset.title || '');
    k.addEventListener('click', function (e) { e.stopPropagation(); go(i, 0); });
    tl.appendChild(k);
  });
  var keys = $$('.tl-key', tl);
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function updateTimeline() {
    var ms = maxStep(cur);
    var frac = ms ? step / (ms + 1) : 0;
    var x = cur === N - 1 ? 100 : ((cur + frac) / (N - 1)) * 100;
    tlHead.style.left = x + '%';
    tlFill.style.width = x + '%';
    tlHead.dataset.f = 'F ' + pad(cur + 1) + ' / ' + N;
    keys.forEach(function (k, i) { k.classList.toggle('done', i <= cur); });
  }

  /* ---------- render ---------- */
  function render() {
    slides.forEach(function (s, i) {
      s.classList.toggle('active', i === cur);
      s.classList.toggle('past', i < cur);
      s.setAttribute('aria-hidden', i === cur ? 'false' : 'true');
    });
    var sl = slides[cur];
    $$('[data-step]', sl).forEach(function (e) { e.classList.toggle('on', +e.dataset.step <= step); });
    if (entered !== cur) { entered = cur; onEnter(cur); }
    onStep(cur, step);
    updateTimeline();
    syncVideos();
    try { sessionStorage.setItem('deck-pos', JSON.stringify([cur, step])); } catch (e) {}
    broadcast();
  }

  function hookNav(d) { var h = hooks[slides[cur].dataset.hook]; return !!(h && h.nav && h.nav(d)); }
  function next() {
    if (hookNav(1)) return;
    if (step < maxStep(cur)) { step++; render(); }
    else if (cur < N - 1) { cur++; step = 0; render(); }
  }
  function prev() {
    if (hookNav(-1)) return;
    if (step > 0) { step--; render(); }
    else if (cur > 0) { cur--; step = maxStep(cur); render(); }
  }
  function go(i, s) {
    cur = Math.max(0, Math.min(N - 1, i)); step = Math.max(0, Math.min(maxStep(cur), s || 0)); render();
  }

  /* ---------- keyboard ---------- */
  var numBuf = '';
  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA') && /Arrow|Home|End|Page/.test(e.key)) return;
    if (t && t.tagName === 'INPUT' && t.type !== 'range') return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key;
    var hk = hooks[slides[cur].dataset.hook];
    if (hk && hk.key && hk.key(k)) { e.preventDefault(); return; }
    if (k === 'ArrowRight' || k === 'PageDown' || k === ' ' || k === 'ArrowDown' || (k === 'Enter' && !numBuf)) { e.preventDefault(); next(); }
    else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'ArrowUp' || k === 'Backspace') { e.preventDefault(); prev(); }
    else if (k === 'Home') go(0);
    else if (k === 'End') go(N - 1);
    else if (/^[0-9]$/.test(k)) { numBuf += k; clearTimeout(numBuf.t); }
    else if (k === 'Enter' && numBuf) { go(parseInt(numBuf, 10) - 1); numBuf = ''; }
    else if (k === 'f' || k === 'F') toggleFS();
    else if (k === 't' || k === 'T') tl.classList.toggle('hidden');
    else if (k === 'p' || k === 'P') openPresenter();
    else if (k === 'b' || k === 'B') stage.style.opacity = stage.style.opacity === '0' ? '1' : '0';
    else if (k === '?' || k === 'h' || k === 'H') $('#help').classList.toggle('show');
    else if (k === 'm' || k === 'M') adminGate();
    else if (k === 'Escape') $('#help').classList.remove('show');
  });
  // give arrow keys back to the deck after using a slider
  stage.addEventListener('pointerdown', function (e) {
    if (!e.target.closest('input, a, button') && document.activeElement && document.activeElement.blur) document.activeElement.blur();
  });

  function toggleFS() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
    else document.exitFullscreen && document.exitFullscreen();
  }

  // hide cursor when idle
  var idle;
  document.addEventListener('mousemove', function () {
    document.body.classList.remove('hide-cursor');
    clearTimeout(idle); idle = setTimeout(function () { document.body.classList.add('hide-cursor'); }, 2200);
  });

  /* ---------- presenter window ---------- */
  var bc = 'BroadcastChannel' in window ? new BroadcastChannel('zica-deck') : null;
  function broadcast() {
    if (!bc) return;
    var sl = slides[cur], nx = slides[cur + 1];
    var notes = $('.notes', sl);
    bc.postMessage({
      type: 'state', cur: cur, step: step, maxStep: maxStep(cur), total: N,
      title: sl.dataset.title || '', notes: notes ? notes.textContent.trim() : '',
      nextTitle: step < maxStep(cur) ? '(build ' + (step + 1) + ' of ' + maxStep(cur) + ' on this slide)' : (nx ? nx.dataset.title : 'End'),
      titles: slides.map(function (s) { return s.dataset.title || ''; })
    });
  }
  if (bc) bc.onmessage = function (m) {
    var d = m.data || {};
    if (d.type === 'cmd') {
      if (d.cmd === 'next') next();
      else if (d.cmd === 'prev') prev();
      else if (d.cmd === 'goto') go(d.n, 0);
      else if (d.cmd === 'hello') broadcast();
    }
  };
  function openPresenter() { window.open('presenter.html', 'zica-presenter', 'width=1100,height=720'); }

  /* ---------- video slots ---------- */
  $$('.vslot[data-video]').forEach(function (slot) {
    var v = document.createElement('video');
    v.muted = true; v.loop = true; v.playsInline = true; v.preload = 'auto';
    v.addEventListener('loadeddata', function () { slot.classList.add('has-video'); });
    v.src = slot.dataset.video;
    slot.insertBefore(v, slot.firstChild);
  });
  function syncVideos() {
    slides.forEach(function (s, i) {
      $$('video', s).forEach(function (v) {
        if (i === cur && (v.closest('.vslot') || v.dataset.autoplay)) { var p = v.play(); if (p && p.catch) p.catch(function () {}); }
        else if (i !== cur) v.pause();
      });
    });
  }

  /* ---------- count-ups ---------- */
  function countUp(el) {
    var to = +el.dataset.count, from = +(el.dataset.from || 0), t0 = performance.now(), dur = reduce ? 1 : 1400;
    (function tick(t) {
      var p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 4);
      var v = Math.round(from + (to - from) * e);
      el.textContent = el.dataset.fmt === 'in' ? v.toLocaleString('en-IN') : v;
      if (p < 1) requestAnimationFrame(tick);
    })(t0);
  }

  /* =====================================================================
     Slide hooks
     ===================================================================== */
  var hooks = {};
  function onEnter(i) {
    var s = slides[i];
    clearInterval(ambTimer);
    $$('[data-count]', s).forEach(countUp);
    var h = hooks[s.dataset.hook];
    if (h && h.enter) h.enter(s);
    // stop loops on other slides
    Object.keys(hooks).forEach(function (k) { if (k !== s.dataset.hook && hooks[k].leave) hooks[k].leave(); });
  }
  function onStep(i, st) {
    var s = slides[i], h = hooks[s.dataset.hook];
    if (h && h.step) h.step(s, st);
  }

  /* ---- 1 · torus: wireframe → rendered, drawn live ---- */
  hooks.open = (function () {
    var cv = $('#torus'), ctx = cv.getContext('2d'), raf = 0, mix = 0, target = 0, t0 = performance.now();
    var label = $('#renderLabel');
    var U = 56, V = 22, R = 1, r = 0.42, verts = [];
    for (var i = 0; i < U; i++) for (var j = 0; j < V; j++) {
      var u = i / U * Math.PI * 2, v = j / V * Math.PI * 2;
      verts.push([(R + r * Math.cos(v)) * Math.cos(u), (R + r * Math.cos(v)) * Math.sin(u), r * Math.sin(v), Math.cos(v) * Math.cos(u), Math.cos(v) * Math.sin(u), Math.sin(v)]);
    }
    function rot(p, a, b) {
      var x = p[0], y = p[1], z = p[2];
      var y1 = y * Math.cos(a) - z * Math.sin(a), z1 = y * Math.sin(a) + z * Math.cos(a);
      var x2 = x * Math.cos(b) + z1 * Math.sin(b), z2 = -x * Math.sin(b) + z1 * Math.cos(b);
      return [x2, y1, z2];
    }
    var light = (function () { var l = [-0.5, -0.7, -0.6], m = Math.hypot(l[0], l[1], l[2]); return [l[0] / m, l[1] / m, l[2] / m]; })();
    function frame(now) {
      var t = (now - t0) / 1000;
      mix += (target - mix) * 0.06;
      var a = 0.62 + Math.sin(t * 0.35) * 0.22, b = t * 0.4;
      var W = cv.width, H = cv.height, sc = 300, cz = 3.4;
      var P = verts.map(function (p) {
        var q = rot(p, a, b), n = rot([p[3], p[4], p[5]], a, b), z = q[2] + cz, f = 720 / z;
        return { x: W / 2 + q[0] * f * sc / 300, y: H / 2 + q[1] * f * sc / 300, z: z, n: n };
      });
      ctx.clearRect(0, 0, W, H);
      var quads = [];
      for (var i = 0; i < U; i++) for (var j = 0; j < V; j++) {
        var a0 = i * V + j, a1 = ((i + 1) % U) * V + j, a2 = ((i + 1) % U) * V + (j + 1) % V, a3 = i * V + (j + 1) % V;
        quads.push([P[a0], P[a1], P[a2], P[a3]]);
      }
      quads.forEach(function (q) { q.z = (q[0].z + q[1].z + q[2].z + q[3].z) / 4; });
      quads.sort(function (m, n) { return n.z - m.z; });
      quads.forEach(function (q) {
        var nx = (q[0].n[0] + q[2].n[0]) / 2, ny = (q[0].n[1] + q[2].n[1]) / 2, nz = (q[0].n[2] + q[2].n[2]) / 2;
        var facing = nz < 0.15;
        ctx.beginPath(); ctx.moveTo(q[0].x, q[0].y); ctx.lineTo(q[1].x, q[1].y); ctx.lineTo(q[2].x, q[2].y); ctx.lineTo(q[3].x, q[3].y); ctx.closePath();
        if (mix > 0.01) {
          var d = Math.max(0, nx * light[0] + ny * light[1] + nz * light[2]); d = 0.18 + 0.82 * d;
          var spec = Math.pow(d, 22);
          var rim = Math.pow(1 - Math.min(1, Math.abs(nz)), 3);
          var rr = Math.round(20 + 235 * d * d + 60 * spec + 40 * rim), gg = Math.round(8 + 150 * d * d * d + 120 * spec + 200 * rim), bb = Math.round(6 + 30 * d + 140 * spec + 210 * rim);
          ctx.globalAlpha = mix;
          ctx.fillStyle = 'rgb(' + Math.min(255, rr) + ',' + Math.min(255, gg) + ',' + Math.min(255, bb) + ')';
          ctx.fill();
        }
        if (mix < 0.99) {
          ctx.globalAlpha = (1 - mix) * (facing ? 0.75 : 0.18);
          ctx.strokeStyle = '#5ce1e6'; ctx.lineWidth = 1.2; ctx.stroke();
        }
      });
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(frame);
    }
    return {
      enter: function () { cancelAnimationFrame(raf); if (!$('#s-open .vslot').classList.contains('has-video')) raf = requestAnimationFrame(frame); },
      leave: function () { cancelAnimationFrame(raf); raf = 0; },
      step: function (s, st) {
        target = st >= 1 ? 1 : 0;
        label.innerHTML = st >= 1 ? '<b>rendered</b> live in JavaScript, ' + (U * V) + ' faces' : 'wireframe';
      }
    };
  })();
  // the cold open gets one build: the render
  (function () { var c = $('#s-open .copy'); var m = document.createElement('i'); m.dataset.step = '1'; m.className = 'fade'; c.appendChild(m); })();

  /* ---- 3 · spreadsheet → viewport ---- */
  hooks.story = (function () {
    var built = false;
    function build() {
      var sh = $('#sheet'), cols = ['', 'A', 'B', 'C', 'D', 'E'], h = '';
      cols.forEach(function (c) { h += '<div class="hd">' + c + '</div>'; });
      var rows = [['Q1 sales', '1,240', '980', '1,410', '=SUM(B2:D2)'], ['Q2 sales', '1,310', '1,050', '1,390', '=SUM(B3:D3)'], ['Payroll', '420', '420', '435', ''], ['Rent', '90', '90', '90', ''], ['Stationery', '12', '9', '14', ''], ['', '', '', '', ''], ['', '', '', '', ''], ['', '', '', '', ''], ['', '', '', '', ''], ['', '', '', '', '']];
      rows.forEach(function (r, i) { h += '<div class="hd">' + (i + 2) + '</div>'; r.forEach(function (c) { h += '<div>' + c + '</div>'; }); });
      sh.innerHTML = h;
    }
    return {
      enter: function () { if (!built) { build(); built = true; } },
      step: function (s, st) { $('#monitor').classList.toggle('rendered', st >= 1); }
    };
  })();

  /* ---- 4 · code types, cubes drop ---- */
  hooks.code = (function () {
    var SEG = [
      ['k', 'import'], ['', ' bpy\n\n'],
      ['k', 'for'], ['', ' i '], ['k', 'in'], ['', ' '], ['f', 'range'], ['', '('], ['n', '12'], ['', '):\n'],
      ['', '    h = '], ['n', '1'], ['', ' + (i * '], ['n', '7'], ['', ' % '], ['n', '5'], ['', ')\n'],
      ['', '    bpy.ops.mesh.'], ['f', 'primitive_cube_add'], ['', '(\n'],
      ['', '        location=(i * '], ['n', '2'], ['', ', '], ['n', '0'], ['', ', h / '], ['n', '2'], ['', '),\n'],
      ['', '        scale=('], ['n', '0.9'], ['', ', '], ['n', '0.9'], ['', ', h / '], ['n', '2'], ['', '))\n\n'],
      ['c', '# 12 buildings. One loop.']
    ];
    var total = SEG.reduce(function (a, s) { return a + s[1].length; }, 0);
    var pre = $('#typed'), box = $('#cubes'), timer = 0, cubeTimer = 0, done = false, cubes = [];
    function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
    function draw(n) {
      var out = '', left = n;
      for (var i = 0; i < SEG.length && left > 0; i++) {
        var t = SEG[i][1].slice(0, left); left -= t.length;
        out += SEG[i][0] ? '<span class="' + SEG[i][0] + '">' + esc(t) + '</span>' : esc(t);
      }
      pre.innerHTML = out + '<span class="caret"></span>';
    }
    function buildCubes() {
      // dimetric projection of the 12 boxes the code makes
      var A = 20 * Math.PI / 180, ca = Math.cos(A), sa = Math.sin(A), S = 38;
      function P(X, Y, Z) { return [(X - Y) * ca * S, (X + Y) * sa * S - Z * S]; }
      var polys = [], minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
      for (var i = 0; i < 12; i++) {
        var h = 1 + (i * 7 % 5), x0 = i * 2 - 0.9, x1 = i * 2 + 0.9, y0 = -0.9, y1 = 0.9;
        var top = [P(x0, y0, h), P(x1, y0, h), P(x1, y1, h), P(x0, y1, h)];
        var left = [P(x0, y1, 0), P(x1, y1, 0), P(x1, y1, h), P(x0, y1, h)];
        var right = [P(x1, y0, 0), P(x1, y1, 0), P(x1, y1, h), P(x1, y0, h)];
        [top, left, right].forEach(function (f) { f.forEach(function (p) { minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]); minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]); }); });
        polys.push([left, right, top]);
      }
      var pts = function (f) { return f.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' '); };
      var svg = '<svg viewBox="' + (minX - 10) + ' ' + (minY - 10) + ' ' + (maxX - minX + 20) + ' ' + (maxY - minY + 20) + '" aria-hidden="true">';
      polys.forEach(function (p) {
        svg += '<g class="cube"><polygon points="' + pts(p[0]) + '" fill="#ff7a1a"/><polygon points="' + pts(p[1]) + '" fill="#a9460a"/><polygon points="' + pts(p[2]) + '" fill="#ffc874"/></g>';
      });
      box.innerHTML = svg + '</svg>';
      cubes = $$('.cube', box);
    }
    function dropCubes() {
      var k = 0;
      clearInterval(cubeTimer);
      cubeTimer = setInterval(function () { if (k >= cubes.length) return clearInterval(cubeTimer); cubes[k++].classList.add('in'); }, reduce ? 1 : 140);
    }
    function finish() { clearInterval(timer); draw(total); done = true; dropCubes(); }
    return {
      enter: function () {
        if (!cubes.length) buildCubes();
        done = false; clearInterval(timer); clearInterval(cubeTimer); clearTimeout(this._d);
        cubes.forEach(function (c) { c.classList.remove('in'); });
        var n = 0; draw(0);
        this._d = setTimeout(function () {
          timer = setInterval(function () { n += 2; if (n >= total) finish(); else draw(n); }, reduce ? 1 : 28);
        }, 500);
      },
      step: function (s, st) { if (st >= 1 && !done) finish(); },
      leave: function () { clearInterval(timer); clearInterval(cubeTimer); }
    };
  })();

  /* ---- 5 · pipeline lights up in order ---- */
  hooks.pipe = (function () {
    var timers = [];
    return {
      enter: function () {
        var nodes = $$('#pipe .stage-n');
        timers.forEach(clearTimeout); timers = [];
        nodes.forEach(function (n) { n.classList.remove('lit'); });
        nodes.forEach(function (n, i) { timers.push(setTimeout(function () { n.classList.add('lit'); }, reduce ? 0 : 500 + i * 420)); });
      },
      leave: function () { timers.forEach(clearTimeout); }
    };
  })();

  /* ---- 8 · plans (from config) ---- */
  hooks.plans = (function () {
    var built = false;
    return {
      enter: function () {
        if (built) return; built = true;
        var order = CFG.SOFTWARE_ORDER || [];
        var used = order.filter(function (sw) { return (CFG.COURSES || []).some(function (c) { return c.software.indexOf(sw) !== -1; }); });
        var html = '';
        (CFG.COURSES || []).forEach(function (c, i) {
          html += '<div class="plan' + (c.highlight ? ' hi' : '') + '"' + (i ? ' data-step="' + i + '"' : '') + '>' +
            '<div class="pill' + (c.highlight ? '' : ' soft') + '">' + (c.badge || (c.highlight ? 'Highly recommended' : 'Recommended')) + '</div>' +
            (c.tier && !c.alt ? '<div class="tier">' + c.tier + ' in</div>' : (c.alt ? '<div class="tier">Two ways to learn</div>' : '')) +
            '<div class="pn">' + c.name + '</div>' +
            (c.alt ? '<div class="dur two"><div><b>' + c.months + '</b><span>months</span><i>' + c.tier + '</i></div><div><b>' + c.alt.months + '</b><span>months</span><i>' + c.alt.tier + '</i></div></div>' : '<div class="dur"><b>' + c.months + '</b><span>months</span></div>') +
            '<div class="tg">' + (c.tagline || '') + '</div><ul>';
          used.forEach(function (sw) {
            var has = c.software.indexOf(sw) !== -1;
            html += '<li class="' + (has ? 'y' : 'x') + '">' + (has ? ICON_Y : ICON_X) + sw + '</li>';
          });
          html += '</ul></div>';
        });
        $('#plans').innerHTML = html;
        render(); // pick up the new data-step elements
      },
      step: function (sl, st) {
        PB.mode(st);
        $$('#plans .plan').forEach(function (p, i) { p.classList.toggle('focus', i === st); });
      },
      leave: function () { PB.stop(); offerClose(); },
      nav: function (d) {
        if (!OF.open) return false;
        if (d > 0) {
          if (!OF.hyb) { offerHybrid(true); return true; }
          offerClose(); cur = Math.min(N - 1, cur + 1); step = 0; render(); return true;   // straight to the next slide
        }
        if (OF.hyb) { offerHybrid(false); return true; }
        offerClose(); return true;
      },
      key: function (k) {
        if (k === 'o' || k === 'O') { OF.open ? offerClose() : offerOpen(); return true; }
        if (!OF.open) return false;
        if (k === 'r' || k === 'R') { offerMoney(); return true; }
        if (k === 'Escape') { offerClose(); return true; }
        return false;
      }
    };
  })();

  /* ASM hybrid offer: hidden view on "Pick a path" (O to open, → hybrid months, → next slide, R prices) */
  var OF = { open: false, hyb: false, built: false };
  function inr(n) { return '₹' + Number(n).toLocaleString('en-IN'); }
  function offerBuild() {
    var o = CFG.ASM_OFFER, el = $('#offer');
    if (!o || !el) return null;
    if (OF.built) return el;
    var DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
    var I_CAMPUS = '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 21h18M5 21V9l7-5 7 5v12"/><path d="M9 21v-6h6v6"/></svg>';
    var I_ONLINE = '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="12" rx="1"/><path d="M8 20h8M12 16v4"/><circle cx="12" cy="10" r="2.2"/></svg>';
    var MAX = 12, rows = [];
    o.rows.forEach(function (r) { r.versions.forEach(function (v, j) { rows.push({ r: r, v: v, first: j === 0, n: r.versions.length }); }); });
    var h = '<div class="o-head"><div class="o-kick">' + o.kicker + '</div><div class="o-title">' + o.title + '</div><div class="o-sub">' + o.sub + '</div></div>' +
      '<div class="o-rows"><div class="o-axis"><span></span><span>Months of learning</span><span></span><span></span></div>';
    rows.forEach(function (x, i) {
      var v = x.v, tr = '';
      for (var k = 0; k < v.from; k++) tr += '<u class="' + (k >= v.to ? 'cut' : 'keep') + '" style="--k:' + k + ';--x:' + (k / (MAX - 1) * 100) + '%;--d:' + Math.max(0, k - v.to) + '"></u>';
      h += '<div class="o-row' + (x.r.highlight ? ' hi' : '') + (x.first ? '' : ' cont') + '" style="--i:' + i + ';--f:' + ((v.from - 1) / (MAX - 1) * 100) + '%;--t:' + ((v.to - 1) / (MAX - 1) * 100) + '%">' +
        '<div class="o-who">' + (x.first ? '<span class="o-pill">' + (x.r.highlight ? 'Highly recommended' : 'Recommended') + '</span><b>' + x.r.name + '</b>' : '') + '<i>' + v.tier + '</i></div>' +
        '<div class="o-track"><s></s>' + tr + '</div>' +
        '<div class="o-num"><b data-from="' + v.from + '" data-to="' + v.to + '">' + v.from + '</b><span>months</span><em>was ' + v.from + '</em></div>' +
        '<div class="o-price"><s>' + inr(v.mrp) + '</s><b>' + inr(v.offer) + '</b></div></div>';
    });
    h += '</div><div class="o-week"><div class="o-days">';
    o.week.forEach(function (w, i) {
      var camp = /campus/i.test(w);
      h += '<div class="o-day ' + (camp ? 'camp' : 'onl') + '" style="--j:' + i + '">' + (camp ? I_CAMPUS : I_ONLINE) + '<em>' + DAYS[i] + '</em><b>' + (camp ? 'Your campus' : 'Live online') + '</b></div>';
    });
    h += '<div class="o-day o-hrs" style="--j:5"><b>' + o.hours + '</b><em>a day</em></div><div class="o-batch" id="oBatch" style="--j:6"><b>' + o.minBatch + '</b><em>students start a batch</em></div></div></div>';
    el.innerHTML = h; OF.built = true;
    $('#oBatch').addEventListener('click', function (e) { e.stopPropagation(); offerMoney(); });
    return el;
  }
  function rollMonths(to) {
    $$('#offer .o-num b').forEach(function (b) {
      var a = +b.textContent, z = +b.getAttribute(to ? 'data-to' : 'data-from'), t0 = performance.now(), dur = reduce ? 1 : 900;
      (function tick(t) { var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); b.textContent = Math.round(a + (z - a) * e); if (k < 1) requestAnimationFrame(tick); })(t0);
    });
  }
  function offerOpen() {
    var el = offerBuild(); if (!el) return;
    OF.open = true; OF.hyb = false; el.classList.remove('hyb', 'money');
    $$('#offer .o-num b').forEach(function (b) { b.textContent = b.getAttribute('data-from'); });
    el.classList.add('open'); el.setAttribute('aria-hidden', 'false'); el.parentNode.classList.add('offer-on'); try { PB.mode(3); } catch (e) {}
  }
  function offerHybrid(on) { OF.hyb = on; $('#offer').classList.toggle('hyb', on); rollMonths(on); }
  function offerMoney() { if (OF.open) $('#offer').classList.toggle('money'); }
  function offerClose() {
    var el = $('#offer'); if (!el) return;
    OF.open = false; OF.hyb = false; el.classList.remove('open', 'hyb', 'money'); el.setAttribute('aria-hidden', 'true'); el.parentNode.classList.remove('offer-on');
  }
  (function () { var hot = $('#offerHot'); if (hot) hot.addEventListener('click', function () { OF.open ? offerClose() : offerOpen(); }); })();
  hooks.plans.enter = (function (orig) { return function (sl) { orig(sl); PB.start(sl.querySelector('#plansBg')); }; })(hooks.plans.enter);

  /* Pick-a-path backgrounds: 0 game world · 1 VFX sparks · 2 motion shapes · 3 UI wireframes */
  var PB = (function () {
    var cv, c, raf = 0, mode = 0, fade = 1, t0 = 0, parts = [];
    function rnd(a, b) { return a + Math.random() * (b - a); }
    function game(t) {
      var W = 1920, H = 1080, hor = 640;
      c.strokeStyle = 'rgba(92,225,230,.5)'; c.lineWidth = 1.2;
      for (var z = 0; z < 22; z++) {                       // scrolling terrain grid
        var zz = (z + (t * 0.6) % 1) / 22, y = hor + Math.pow(zz, 2.2) * 520;
        c.beginPath();
        for (var x = -40; x <= W + 40; x += 40) {
          var h = Math.sin(x * .006 + z * .7) * 30 * (1 - zz) + Math.sin(x * .017 - z) * 12;
          x === -40 ? c.moveTo(x, y - h) : c.lineTo(x, y - h);
        }
        c.stroke();
      }
      for (var k = -12; k <= 12; k++) { c.beginPath(); c.moveTo(W / 2 + k * 30, hor); c.lineTo(W / 2 + k * 260, H); c.stroke(); }
      c.fillStyle = 'rgba(255,181,71,.55)';                // floating pickup gems
      for (var g = 0; g < 7; g++) { var gx = 260 + g * 230, gy = 560 + Math.sin(t * 2 + g) * 18; c.save(); c.translate(gx, gy); c.rotate(t + g); c.fillRect(-9, -9, 18, 18); c.restore(); }
    }
    function vfx(t) {
      while (parts.length < 260) parts.push({ x: rnd(0, 1920), y: rnd(700, 1180), vx: rnd(-.4, .4), vy: rnd(-3.2, -.8), l: rnd(.4, 1), s: rnd(1, 3.5) });
      parts.forEach(function (p) {
        p.x += p.vx + Math.sin(t * 2 + p.y * .01) * .4; p.y += p.vy; p.l -= .004;
        if (p.l <= 0 || p.y < 0) { p.x = rnd(0, 1920); p.y = rnd(900, 1180); p.l = rnd(.5, 1); }
        c.fillStyle = 'rgba(255,' + Math.round(120 + 100 * p.l) + ',40,' + (p.l * .8).toFixed(2) + ')';
        c.beginPath(); c.arc(p.x, p.y, p.s, 0, 7); c.fill();
      });
      var b = (t % 3) / 3; c.strokeStyle = 'rgba(255,181,71,' + (1 - b) * .5 + ')'; c.lineWidth = 3;   // shockwave ring
      c.beginPath(); c.arc(1500, 820, b * 420, 0, 7); c.stroke();
    }
    function motion(t) {
      var cols = ['255,122,26', '92,225,230', '255,181,71', '236,238,244'];
      for (var i = 0; i < 9; i++) {
        var ph = (t * .5 + i / 9) % 1, e = ph < .5 ? 4 * ph * ph * ph : 1 - Math.pow(-2 * ph + 2, 3) / 2;   // ease in-out
        var x = 160 + i * 205, y = 900 - Math.abs(Math.sin(e * Math.PI)) * 300, s = 40 + 30 * Math.sin(e * Math.PI);
        c.save(); c.translate(x, y); c.rotate(e * Math.PI * (i % 2 ? 1 : -1));
        c.fillStyle = 'rgba(' + cols[i % 4] + ',.55)';
        if (i % 3 === 0) { c.beginPath(); c.arc(0, 0, s / 2, 0, 7); c.fill(); }
        else if (i % 3 === 1) c.fillRect(-s / 2, -s / 2, s, s);
        else { c.beginPath(); c.moveTo(0, -s / 2); c.lineTo(s / 2, s / 2); c.lineTo(-s / 2, s / 2); c.closePath(); c.fill(); }
        c.restore();
      }
    }
    function ui(t) {
      c.strokeStyle = 'rgba(92,225,230,.55)'; c.lineWidth = 1.5;
      for (var i = 0; i < 6; i++) {
        var x = 120 + i * 300, y = 560 + Math.sin(t * .8 + i) * 12;
        c.strokeRect(x, y, 220, 380);                           // phone frames
        c.strokeRect(x + 20, y + 30, 180, 90);                  // hero card
        for (var r = 0; r < 4; r++) { c.beginPath(); c.moveTo(x + 20, y + 150 + r * 34); c.lineTo(x + 20 + (r % 2 ? 120 : 170), y + 150 + r * 34); c.stroke(); }
        c.fillStyle = 'rgba(255,181,71,' + (.25 + .3 * Math.max(0, Math.sin(t * 2 - i))) + ')'; c.fillRect(x + 20, y + 310, 180, 40);   // CTA pulse
      }
      var cx = 300 + ((t * 160) % 1500), cy = 880 + Math.sin(t * 3) * 20;   // cursor
      c.fillStyle = 'rgba(236,238,244,.9)'; c.beginPath(); c.moveTo(cx, cy); c.lineTo(cx + 18, cy + 26); c.lineTo(cx + 6, cy + 24); c.lineTo(cx, cy + 34); c.closePath(); c.fill();
    }
    var DRAW = [game, vfx, motion, ui];
    function frame(now) {
      var t = (now - t0) / 1000;
      c.clearRect(0, 0, 1920, 1080);
      fade = Math.min(1, fade + .03);
      c.globalAlpha = fade;
      DRAW[mode](t);
      c.globalAlpha = 1;
      raf = requestAnimationFrame(frame);
    }
    return {
      start: function (canvas) { cv = canvas; c = cv.getContext('2d'); t0 = performance.now(); cancelAnimationFrame(raf); if (!reduce) raf = requestAnimationFrame(frame); },
      stop: function () { cancelAnimationFrame(raf); },
      mode: function (m) { if (m !== mode) { mode = Math.max(0, Math.min(3, m)); fade = 0; parts = []; } }
    };
  })();

  /* ---- 9 · UI/UX spotlight ---- */
  hooks.uiux = (function () {
    var built = false;
    return {
      enter: function () {
        if (built) return; built = true;
        var c = (CFG.COURSES || []).filter(function (x) { return x.highlight; })[0];
        var ROLE = { 'Photoshop': 'edit images', 'Adobe XD': 'first prototypes', 'Notion': 'research & docs', 'Figma': 'design systems',
                     'Illustrator': 'icons & vectors', 'Miro': 'research board', 'FigJam': 'team brainstorms', 'Framer': 'live websites' };
        function chip(s, up) { return '<span class="tool tool2' + (up ? ' up' : '') + '"><b>' + s + '</b><small>' + (ROLE[s] || '') + '</small></span>'; }
        if (c) $('#uiuxTools').innerHTML = c.software.map(function (s) { return chip(s); }).join('');
        var up = CFG.UIUX_UPGRADE;
        if (up && up.adds && up.adds.length) $('#uiuxUp').innerHTML = '<span class="up-l">The ' + up.months + '-month Professional Program adds</span>' + up.adds.map(function (s) { return chip(s, true); }).join('');
        $('#ships').innerHTML = (CFG.UIUX_SHIPS || []).map(function (s, i) { return '<li style="--i:' + i + '">' + ICON_Y + s + '</li>'; }).join('');
        render();
      }
    };
  })();

  /* ---- 12 · side-hustle calculator ---- */
  hooks.calc = (function () {
    var init = false, role = 0;
    var C = CFG.CALC || {}, ROLES = C.ROLES || [{ name: 'UI/UX design', min: C.rateMin || 800, max: C.rateMax || 4000, start: C.rate || 1200 }];
    function inr(n) { return '₹' + Math.round(n).toLocaleString('en-IN'); }
    function lakh(n) { return n >= 100000 ? '₹' + (n / 100000).toFixed(1).replace(/\.0$/, '') + ' lakh a year' : inr(n) + ' a year'; }
    function upd() {
      var h = +$('#hours').value, r = +$('#rate').value, m = h * r * 4.33;
      $('#hVal').textContent = h;
      $('#rVal').textContent = inr(r);
      $('#mVal').textContent = inr(Math.round(m / 100) * 100);
      $('#yVal').textContent = lakh(m * 12);
    }
    function pick(i) {
      role = Math.max(0, Math.min(ROLES.length - 1, i));
      var R = ROLES[role], r = $('#rate');
      r.min = R.min; r.max = R.max; r.step = 100; r.value = R.start;
      $$('#rolePick button').forEach(function (b, k) { b.classList.toggle('on', k === role); });
      $('#calcFine').textContent = 'Hours × rate × 4.33 weeks. ' + R.name + ' in India: ' + inr(R.min) + '–' + inr(R.max) + ' an hour.';
      upd();
    }
    return {
      enter: function () {
        if (init) return; init = true;
        var h = $('#hours');
        h.min = 2; h.max = C.hoursMax || 30; h.step = 1; h.value = C.hours || 10;
        $('#rolePick').innerHTML = ROLES.map(function (R, i) { return '<button data-r="' + i + '">' + R.name + '</button>'; }).join('');
        $$('#rolePick button').forEach(function (b) { b.onclick = function () { pick(+b.getAttribute('data-r')); }; });
        h.addEventListener('input', upd); $('#rate').addEventListener('input', upd);
        pick(0);
      },
      step: function (s, st) { if (init) pick(st); }
    };
  })();

  /* ---- 15 · student wall ---- */
  hooks.wall = (function () {
    var loaded = false, items = [], sections = [], at = 0, timer = 0, el, track;
    function esc(t) { return String(t || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function tileHTML(it) {
      var PLAY = '<svg viewBox="0 0 24 24" width="22" height="22"><path class="i-play" d="M7 4l13 8-13 8z" fill="currentColor"/><g class="i-pause" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></g></svg>';
      var inner = it.kind === 'video' ? '<video src="' + it.src + '#t=0.1" playsinline muted preload="metadata"></video>' +
          '<button class="v-big" aria-label="Play">' + PLAY + '</button>' +
          '<div class="vc"><button class="v-pp" aria-label="Play or pause">' + PLAY + '</button><input class="v-seek" type="range" min="0" max="1000" value="0" step="1" aria-label="Seek">' +
          '<span class="v-t">0:00</span><button class="v-sp" aria-label="Speed">1×</button><button class="v-mu" aria-label="Sound">🔇 Sound</button></div>'
        : it.kind === 'youtube' ? '<img src="' + it.thumb + '" alt="" decoding="async"><button class="v-big yt" data-yt="' + it.id + '" aria-label="Play">' + PLAY + '</button>'
        : '<img src="' + it.src + '" alt="" decoding="async" loading="lazy">';
      return '<figure class="ct" data-path="' + esc(it.path) + '">' + inner +
        (it.title ? '<figcaption>' + esc(it.title) + (it.by ? '<small>' + esc(it.by) + '</small>' : '') + '</figcaption>' : '') +
        '<button class="adm-x" title="Move to archive" aria-label="Move to archive">✕</button>' +
        '<button class="adm-mv" title="Move to another section" aria-label="Move to another section">⇄</button></figure>';
    }
    function layout(instant) {
      var tiles = $$('.ct', track); if (!tiles.length) return;
      at = (at + tiles.length) % tiles.length;
      var x = 0, centre = 0;
      tiles.forEach(function (t, i) {
        var w = t.offsetWidth;
        if (i === at) centre = x + w / 2;
        x += w + 28;
        t.classList.toggle('on', i === at);
        var v = t.querySelector('video');
        if (v && i !== at) v.pause();
        if (i !== at) { var yf = t.querySelector('iframe'); if (yf) yf.remove(); }
      });
      track.style.transition = instant ? 'none' : '';
      track.style.transform = 'translateX(' + (el.offsetWidth / 2 - centre) + 'px)';
      $$('.car-dots i', el).forEach(function (d, i) { d.classList.toggle('on', i === at); });
      var sec = items[at] && items[at].section;
      $$('.car-secs button', el).forEach(function (b) { b.classList.toggle('on', b.dataset.sec === sec); });
    }
    function go(d) { at += d; layout(); restart(); }
    function busy() { return !!track && (Array.prototype.some.call(track.querySelectorAll('video'), function (v) { return !v.paused; }) || !!track.querySelector('iframe')); }
    function restart() { clearInterval(timer); timer = setInterval(function () { if (slides[cur] === el.closest('.slide') && !busy()) { at++; layout(); } }, 6000); }
    function fmt(x) { x = Math.max(0, Math.floor(x || 0)); return Math.floor(x / 60) + ':' + ('0' + x % 60).slice(-2); }
    function wireVideo(t) {
      var v = t.querySelector('video'); if (!v) return;
      var seek = t.querySelector('.v-seek'), tt = t.querySelector('.v-t'), sp = t.querySelector('.v-sp'), mu = t.querySelector('.v-mu');
      function toggle() { if (v.paused) { $$('#wall video').forEach(function (o) { if (o !== v) o.pause(); }); var p = v.play(); if (p && p.catch) p.catch(function () {}); } else v.pause(); }
      function stop(e) { e.stopPropagation(); }
      ['pointerdown', 'pointerup', 'click', 'keydown'].forEach(function (ev) { t.querySelector('.vc').addEventListener(ev, stop); });
      t.querySelector('.v-big').addEventListener('click', function (e) { if (t.classList.contains('on')) { e.stopPropagation(); toggle(); } });
      t.querySelector('.v-pp').addEventListener('click', toggle);
      v.addEventListener('play', function () { t.classList.add('playing'); });
      v.addEventListener('pause', function () { t.classList.remove('playing'); });
      v.addEventListener('ended', function () { t.classList.remove('playing'); });
      v.addEventListener('timeupdate', function () { if (!seek._drag && v.duration) seek.value = Math.round(v.currentTime / v.duration * 1000); tt.textContent = fmt(v.currentTime) + ' / ' + fmt(v.duration); });
      v.addEventListener('loadedmetadata', function () { tt.textContent = '0:00 / ' + fmt(v.duration); });
      seek.addEventListener('input', function () { seek._drag = true; if (v.duration) v.currentTime = seek.value / 1000 * v.duration; });
      seek.addEventListener('change', function () { seek._drag = false; seek.blur(); });
      sp.addEventListener('click', function () { v.playbackRate = v.playbackRate === 1 ? 2 : 1; sp.textContent = v.playbackRate + '×'; sp.classList.toggle('on', v.playbackRate !== 1); });
      mu.addEventListener('click', function () { v.muted = !v.muted; mu.textContent = v.muted ? '🔇 Sound' : '🔊 On'; mu.classList.toggle('on', !v.muted); });
    }
    function wireYT(t) {
      var b = t.querySelector('.v-big.yt'); if (!b) return;
      b.addEventListener('click', function (e) {
        if (!t.classList.contains('on')) return; e.stopPropagation();
        var f = document.createElement('iframe');
        f.src = 'https://www.youtube-nocookie.com/embed/' + b.dataset.yt + '?autoplay=1&rel=0&modestbranding=1&playsinline=1';
        f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen'; f.allowFullscreen = true; f.className = 'yt-frame';
        t.appendChild(f);
      });
    }
    function sizeTile(t) {
      var m = t.querySelector('img, video'), H = 600;
      function set(ar) { t.style.width = Math.round(H * Math.max(0.6, Math.min(1.9, ar || 16 / 9))) + 'px'; layout(true); }
      if (m.tagName === 'VIDEO') m.addEventListener('loadedmetadata', function () { set(m.videoWidth / m.videoHeight); });
      else if (m.complete && m.naturalWidth) set(m.naturalWidth / m.naturalHeight);
      else m.addEventListener('load', function () { set(m.naturalWidth / m.naturalHeight); });
      set(16 / 9);
    }
    function build() {
      if (!items.length) {
        el.className = '';
        el.innerHTML = '<div class="wall-empty"><div class="h3">Student work drops in here.</div><div class="body">Upload files to the folders in <code>media/work/</code> named <code>01-title.jpg</code>, <code>02-title.mp4</code>…</div></div>';
        return;
      }
      el.className = 'car';
      var used = sections.filter(function (n) { return items.some(function (it) { return it.section === n; }); });
      el.innerHTML = '<div class="car-secs">' + used.map(function (n) { var c = items.filter(function (it) { return it.section === n; }).length; return '<button data-sec="' + esc(n) + '">' + esc(n) + '<em>' + c + '</em></button>'; }).join('') + '</div>' +
        '<div class="car-track">' + items.map(tileHTML).join('') + '</div>' +
        '<button class="car-btn prev" aria-label="Previous">‹</button><button class="car-btn next" aria-label="Next">›</button>' +
        '<div class="car-dots">' + items.map(function () { return '<i></i>'; }).join('') + '</div>';
      track = el.querySelector('.car-track');
      $$('.ct', track).forEach(function (t, i) {
        sizeTile(t); wireVideo(t); wireYT(t);
        t.addEventListener('click', function (e) {
          if (e.target.closest('.adm-x, .adm-mv, .mv-menu, .vc')) return;
          if (i !== at) { at = i; layout(); restart(); return; }
          var v = t.querySelector('video'); if (v) { if (v.paused) v.play(); else v.pause(); }
        });
      });
      $$('.car-secs button', el).forEach(function (b) { b.onclick = function () { var k = items.findIndex(function (it) { return it.section === b.dataset.sec; }); if (k >= 0) { at = k; layout(); restart(); } }; });
      $$('.adm-mv', el).forEach(function (b) { b.onclick = function (e) {
        e.stopPropagation();
        var fig = b.closest('.ct'), path = fig.dataset.path, old = el.querySelector('.mv-menu'); if (old) old.remove();
        var m = document.createElement('div'); m.className = 'mv-menu';
        m.innerHTML = '<b>Move to</b>' + sections.map(function (n) { return '<button data-to="' + esc(n) + '">' + esc(n) + '</button>'; }).join('') + '<button data-to="">Original section</button>';
        fig.appendChild(m);
        $$('button', m).forEach(function (x) { x.onclick = function (ev) { ev.stopPropagation(); DeckAdmin.move(path, x.dataset.to); loaded = false; m.remove(); hooks.wall.enter(slides[cur]); }; });
      }; });
      el.querySelector('.prev').onclick = function () { go(-1); };
      el.querySelector('.next').onclick = function () { go(1); };
      var x0 = null;
      track.addEventListener('pointerdown', function (e) { x0 = e.target.closest('.vc') ? null : e.clientX; });
      track.addEventListener('pointerup', function (e) { if (x0 !== null && Math.abs(e.clientX - x0) > 40) go(e.clientX < x0 ? 1 : -1); x0 = null; });
      layout(true); restart();
    }
    document.addEventListener('keydown', function (e) {
      if (!el || slides[cur] !== el.closest('.slide') || !track) return;
      if (e.key === ',' || e.key === '[') go(-1);
      if (e.key === '.' || e.key === ']') go(1);
    });
    return {
      enter: function (sl) {
        el = $('#wall');
        if (loaded) { layout(true); restart(); ambient(sl); return; }
        loaded = true;
        if (!window.DeckMedia) return;
        window.DeckMedia.gallery().then(function (g) { items = g.items; sections = g.sections; at = Math.min(at, Math.max(0, items.length - 1)); build(); ambient(sl); });
      },
      leave: function () { clearInterval(timer); $$('#wall video').forEach(function (v) { v.pause(); }); $$('#wall iframe').forEach(function (f) { f.remove(); }); },
      remove: function (path) { items = items.filter(function (it) { return it.path !== path; }); at = Math.min(at, items.length - 1); build(); }
    };
  })();

  /* ---- 17 · Creative Quest QR ---- */
  hooks.quest = (function () {
    var done = false;
    return {
      enter: function () {
        if (done) return; done = true;
        var box = $('#qr');
        if (!CFG.QUEST_URL) {
          box.innerHTML = '<div class="qr-ph"><b>QR goes here</b><span>Paste the quest link into QUEST_URL in assets/config.js</span></div>';
          return;
        }
        // self-hosted QR generator (assets/vendor/qrcode.js), so it works with no internet
        try {
          var qr = window.qrcode(0, 'M'); qr.addData(CFG.QUEST_URL); qr.make();
          box.innerHTML = qr.createSvgTag({ cellSize: 8, margin: 0, scalable: true });
          var svg = box.querySelector('svg'); svg.setAttribute('width', '100%'); svg.setAttribute('height', '100%');
          svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'QR code for ' + CFG.QUEST_URL);
        } catch (e) {
          box.innerHTML = '<div class="qr-ph"><b>' + CFG.QUEST_URL.replace(/^https?:\/\//, '') + '</b><span>Share this link with the room.</span></div>';
        }
      }
    };
  })();

  /* ---- ambient glow: a slide takes on the colour of the media playing in it ---- */
  var ambCanvas = document.createElement('canvas'); ambCanvas.width = ambCanvas.height = 12;
  function sampleColour(el) {
    try {
      var x = ambCanvas.getContext('2d', { willReadFrequently: true });
      x.drawImage(el, 0, 0, 12, 12);
      var d = x.getImageData(0, 0, 12, 12).data, r = 0, g = 0, b = 0, n = 0;
      for (var i = 0; i < d.length; i += 4) {
        var mx = Math.max(d[i], d[i + 1], d[i + 2]), mn = Math.min(d[i], d[i + 1], d[i + 2]);
        var w = 0.2 + (mx - mn) / 255;             // favour saturated pixels so the glow has colour
        if (mx < 30) continue;
        r += d[i] * w; g += d[i + 1] * w; b += d[i + 2] * w; n += w;
      }
      return n ? [r / n, g / n, b / n].map(Math.round) : null;
    } catch (e) { return null; }                    // e.g. a YouTube thumbnail (cross-origin)
  }
  var ambTimer = 0;
  function ambient(slide) {
    clearInterval(ambTimer);
    if (!slide) return;
    function tick() {
      var pool = $$('.ct.on img, .ct.on video', slide); if (!pool.length) pool = $$('img, video', slide);
      var cols = pool.filter(function (m) { return (m.complete || m.readyState >= 2) && m.offsetParent; }).map(sampleColour).filter(Boolean);
      if (!cols.length) return;
      var c = [0, 0, 0]; cols.forEach(function (k) { c[0] += k[0]; c[1] += k[1]; c[2] += k[2]; });
      slide.style.setProperty('--amb', c.map(function (v) { return Math.round(v / cols.length); }).join(' '));
      slide.classList.add('ambient');
    }
    tick(); ambTimer = setInterval(tick, 1200);
  }

  /* ---- studio visits: each tile cross-fades through its folder ---- */
  hooks.visits = (function () {
    var loaded = false, timers = [];
    return {
      enter: function (s) {
        ambient(s);
        if (loaded || !window.DeckMedia) return; loaded = true;
        $$('.vtile', s).forEach(function (tile, ti) {
          window.DeckMedia.list(tile.getAttribute('data-folder')).then(function (items) {
            var box = tile.querySelector('.vmedia');
            items = items.filter(function (it) { return it.kind !== 'youtube'; });
            if (!items.length) { tile.classList.add('empty'); return; }
            box.innerHTML = items.map(function (it, i) {
              return it.kind === 'video'
                ? '<video class="vm' + (i ? '' : ' on') + '" data-path="' + it.path + '" src="' + it.src + '" muted loop playsinline preload="' + (i ? 'none' : 'auto') + '" data-autoplay="1"></video>'
                : '<img class="vm' + (i ? '' : ' on') + '" data-path="' + it.path + '" src="' + it.src + '" alt="" decoding="async"' + (i ? ' loading="lazy"' : '') + '>';
            }).join('') + '<button class="adm-x" title="Move the photo on screen to archive">✕</button>';
            syncVideos();
            if (items.length > 1) {
              var k = 0, els = $$('.vm', box);
              timers.push(setInterval(function () {
                els[k].classList.remove('on'); k = (k + 1) % els.length; els[k].classList.add('on');
                if (els[k].tagName === 'VIDEO') { els[k].preload = 'auto'; var pr = els[k].play(); if (pr && pr.catch) pr.catch(function () {}); }
              }, 3800 + ti * 450));
            }
          });
        });
      },
    };
  })();

  /* ---- Code Lab cover: a studio "boots" in a terminal over drifting code ---- */
  hooks.labcover = (function () {
    var LINES = [
      ['texture.py', 'kernels on pixels'], ['modelling.py', 'recursion'], ['environments.py', 'noise functions'],
      ['rigging.py', 'inverse kinematics'], ['animation.css', 'easing curves'], ['lighting.frag', 'GPU shaders'], ['crowds.py', 'simulation']
    ];
    var timers = [], raf = 0, cols = [], cv, cx;
    var TOK = ['for', 'if', 'return', 'def', 'vec3', '0.72', 'noise()', 'sin(t)', '[i][j]', 'lerp', '=>', '{ }', 'bpy', 'uv', 'kernel', '++', '0xFF', 'mesh', 'frame', 'dt'];
    function line(html, at) { timers.push(setTimeout(function () { var pre = $('#bootlog'); pre.innerHTML += html + '\n'; }, at)); }
    function boot() {
      var pre = $('#bootlog'); pre.innerHTML = ''; timers.forEach(clearTimeout); timers = [];
      line('<span class="dim">$</span> python <span class="fn">studio.py</span>', 200);
      LINES.forEach(function (l, i) {
        var dots = new Array(Math.max(2, 18 - l[0].length)).join('.');
        line('  loading <span class="hl">' + l[0] + '</span> <span class="dim">' + dots + '</span> <span class="ok">ok</span>  <span class="dim">// ' + l[1] + '</span>', 700 + i * 520);
      });
      line('', 700 + LINES.length * 520);
      line('<span class="ok">7 departments online.</span> Opening the studio<span class="caret"></span>', 900 + LINES.length * 520);
    }
    function frame() {
      var W = cv.width, H = cv.height;
      cx.clearRect(0, 0, W, H);
      cx.font = '500 20px "JetBrains Mono", monospace';
      cols.forEach(function (c) {
        c.y -= c.v;
        if (c.y < -40) { c.y = H + 40; c.x = Math.random() * W; c.t = TOK[(Math.random() * TOK.length) | 0]; }
        cx.fillStyle = c.amber ? 'rgba(255,181,71,' + c.a + ')' : 'rgba(92,225,230,' + c.a + ')';
        cx.fillText(c.t, c.x, c.y);
      });
      raf = requestAnimationFrame(frame);
    }
    return {
      enter: function (s) {
        cv = s.querySelector('#glyphs'); cv.width = 1920; cv.height = 1080; cx = cv.getContext('2d');
        if (!cols.length) for (var i = 0; i < 90; i++) cols.push({ x: Math.random() * 1920, y: Math.random() * 1080, v: .3 + Math.random() * .9, a: .08 + Math.random() * .22, amber: Math.random() < .35, t: TOK[(Math.random() * TOK.length) | 0] });
        boot();
        cancelAnimationFrame(raf); if (!reduce) raf = requestAnimationFrame(frame);
      },
      leave: function () { cancelAnimationFrame(raf); timers.forEach(clearTimeout); }
    };
  })();

  /* ---- Gen AI: three circles; the overlap ("You") grows with every click ---- */
  hooks.venn = (function () {
    var cv, c, raf = 0, P = null, T = null;
    var STAGES = [
      { r: [190, 190, 150], o: [[-230, -110], [230, -110], [0, 230]], you: 0.0 },
      { r: [300, 190, 150], o: [[-170, -70], [250, -110], [10, 260]], you: 0.2 },
      { r: [300, 300, 170], o: [[-130, -60], [140, -60], [0, 230]], you: 0.6 },
      { r: [310, 310, 290], o: [[-110, -50], [110, -50], [0, 130]], you: 1.0 }
    ];
    var COL = [[92, 225, 230], [255, 122, 26], [255, 181, 71]], NAME = ['Code', 'Design', 'AI'];
    function lerpS(a, b, t) {
      return { r: a.r.map(function (v, i) { return v + (b.r[i] - v) * t; }),
        o: a.o.map(function (p, i) { return [p[0] + (b.o[i][0] - p[0]) * t, p[1] + (b.o[i][1] - p[1]) * t]; }),
        you: a.you + (b.you - a.you) * t };
    }
    var PAIR = [[0, 1, 'Design engineer'], [0, 2, 'AI developer'], [1, 2, 'AI artist']];
    function inC(k, x, y) { var dx = x - k[0], dy = y - k[1]; return dx * dx + dy * dy <= k[2] * k[2]; }
    function regions(circ, W, H) {
      // sample a grid once per frame: triple overlap + each pair-only lens (area + centroid)
      var g = 10, R = { t: [0, 0, 0], p: [[0, 0, 0], [0, 0, 0], [0, 0, 0]] };
      var x0 = Math.max(0, Math.min(circ[0][0] - circ[0][2], circ[1][0] - circ[1][2], circ[2][0] - circ[2][2])), x1 = Math.min(W, Math.max(circ[0][0] + circ[0][2], circ[1][0] + circ[1][2], circ[2][0] + circ[2][2]));
      var y0 = Math.max(0, Math.min(circ[0][1] - circ[0][2], circ[1][1] - circ[1][2], circ[2][1] - circ[2][2])), y1 = Math.min(H, Math.max(circ[0][1] + circ[0][2], circ[1][1] + circ[1][2], circ[2][1] + circ[2][2]));
      for (var y = y0; y < y1; y += g) for (var x = x0; x < x1; x += g) {
        var a = inC(circ[0], x, y), b = inC(circ[1], x, y), c3 = inC(circ[2], x, y);
        if (a && b && c3) { R.t[0]++; R.t[1] += x; R.t[2] += y; }
        else if (a && b) { R.p[0][0]++; R.p[0][1] += x; R.p[0][2] += y; }
        else if (a && c3) { R.p[1][0]++; R.p[1][1] += x; R.p[1][2] += y; }
        else if (b && c3) { R.p[2][0]++; R.p[2][1] += x; R.p[2][2] += y; }
      }
      return R;
    }
    function draw(S, time) {
      var W = cv.width, H = cv.height, cx0 = W / 2, cy0 = H / 2 - 40;
      c.clearRect(0, 0, W, H);
      var K = 1.32; var circ = S.r.map(function (r, i) { var wob = reduce ? 0 : Math.sin(time * .8 + i * 2) * 5; return [cx0 + S.o[i][0] * K, cy0 + S.o[i][1] * K + wob, r * K]; });
      // soft glow behind everything once "You" exists
      if (S.you > .05) {
        var gx = (circ[0][0] + circ[1][0] + circ[2][0]) / 3, gy = (circ[0][1] + circ[1][1] + circ[2][1]) / 3;
        var gl = c.createRadialGradient(gx, gy, 0, gx, gy, 520);
        gl.addColorStop(0, 'rgba(255,181,71,' + (0.16 * S.you * (0.85 + 0.15 * Math.sin(time * 2))) + ')'); gl.addColorStop(1, 'rgba(255,181,71,0)');
        c.fillStyle = gl; c.fillRect(0, 0, W, H);
      }
      circ.forEach(function (k, i) {
        var rg = c.createRadialGradient(k[0] - k[2] * .3, k[1] - k[2] * .3, k[2] * .1, k[0], k[1], k[2]);
        rg.addColorStop(0, 'rgba(' + COL[i] + ',.22)'); rg.addColorStop(1, 'rgba(' + COL[i] + ',.07)');
        c.beginPath(); c.arc(k[0], k[1], k[2], 0, 7); c.fillStyle = rg; c.fill();
        c.lineWidth = 3; c.strokeStyle = 'rgba(' + COL[i] + ',.9)'; c.stroke();
      });
      var R = regions(circ, W, H), cell = 100;           // each sample = 10×10 px
      // pair-only lenses: faint tint now, role label after "You"
      PAIR.forEach(function (pr, j) {
        if (R.p[j][0] * cell < 9000) return;
        c.save(); c.beginPath(); c.arc(circ[pr[0]][0], circ[pr[0]][1], circ[pr[0]][2], 0, 7); c.clip();
        c.beginPath(); c.arc(circ[pr[1]][0], circ[pr[1]][1], circ[pr[1]][2], 0, 7); c.clip();
        c.fillStyle = 'rgba(255,255,255,.05)'; c.fillRect(0, 0, W, H); c.restore();
      });
      // triple overlap = "You"
      var tn = R.t[0], area = tn * cell;
      if (area > 600) {
        c.save();
        circ.forEach(function (k) { c.beginPath(); c.arc(k[0], k[1], k[2], 0, 7); c.clip(); });
        var tx = R.t[1] / tn, ty = R.t[2] / tn, tr = Math.sqrt(area / Math.PI);
        var yg = c.createRadialGradient(tx, ty, 0, tx, ty, tr * 1.6);
        yg.addColorStop(0, 'rgba(255,205,120,' + (0.55 + 0.4 * S.you) + ')'); yg.addColorStop(1, 'rgba(255,170,50,' + (0.35 + 0.5 * S.you) + ')');
        c.fillStyle = yg; c.fillRect(0, 0, W, H);
        // sparkles drifting inside the zone on the last stage
        if (S.you > .8 && !reduce) for (var q = 0; q < 14; q++) {
          var ang = q * 2.4 + time * .35, rr = tr * (0.25 + 0.6 * ((q * 37 % 10) / 10));
          c.fillStyle = 'rgba(255,255,255,' + (0.25 + 0.25 * Math.sin(time * 3 + q)) + ')';
          c.beginPath(); c.arc(tx + Math.cos(ang) * rr, ty + Math.sin(ang) * rr, 2.5, 0, 7); c.fill();
        }
        c.restore();
        c.lineWidth = 2; c.strokeStyle = 'rgba(255,220,160,' + (0.3 + 0.5 * S.you) + ')';
        var fs = Math.max(30, Math.min(120, tr * 0.62));
        c.font = '800 ' + Math.round(fs) + 'px "Bricolage Grotesque", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        c.fillStyle = 'rgba(13,14,19,' + Math.min(1, area / 9000) + ')';
        c.fillText('You', tx, ty);
      }
      PAIR.forEach(function (pr, j) {
        var n = R.p[j][0]; if (n * cell < 22000) return;
        var al = Math.min(1, (n * cell - 22000) / 20000);
        c.font = '600 34px "Bricolage Grotesque", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        c.fillStyle = 'rgba(236,238,244,' + (0.8 * al) + ')';
        c.fillText(pr[2], R.p[j][1] / n, R.p[j][2] / n);
      });
      c.font = '700 58px "Bricolage Grotesque", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
      var lab = [[-1, -1], [1, -1], [0, 1]];
      circ.forEach(function (k, i) { c.fillStyle = 'rgba(' + COL[i] + ',1)'; c.fillText(NAME[i], k[0] + lab[i][0] * k[2] * .5, k[1] + lab[i][1] * k[2] * .62); });
    }
    function frame(t) {
      if (T) { var k = Math.min(1, (t - T.t0) / 1100); var e = 1 - Math.pow(1 - k, 3); P = lerpS(T.from, T.to, e); if (k >= 1) T = null; }
      draw(P, t / 1000);
      raf = requestAnimationFrame(frame);
    }
    return {
      enter: function (s) {
        cv = s.querySelector('#venn'); c = cv.getContext('2d');
        if (!P) P = STAGES[0];
        cancelAnimationFrame(raf); raf = requestAnimationFrame(frame);
      },
      step: function (s, st) {
        if (!cv) { cv = s.querySelector('#venn'); c = cv.getContext('2d'); }
        T = { from: P || STAGES[0], to: STAGES[st], t0: performance.now() };
        $$('.vstep', s).forEach(function (el) { var v = +el.getAttribute('data-v'); el.classList.toggle('on', v === st); el.classList.toggle('past', v < st); });
      },
      leave: function () { cancelAnimationFrame(raf); }
    };
  })();

  /* ---- 50 ms counter (stretched to 2 s so it can be seen) ---- */
  hooks.ms50 = (function () {
    var raf = 0;
    return {
      enter: function (s) {
        var v = s.querySelector('#msVal'), bar = s.querySelector('#msBar'), t0 = performance.now() + 500;
        cancelAnimationFrame(raf);
        (function tick(t) {
          var k = Math.max(0, Math.min(1, (t - t0) / (reduce ? 1 : 2000)));
          v.textContent = Math.round(k * 50); bar.style.width = (k * 100) + '%';
          if (k < 1) raf = requestAnimationFrame(tick);
        })(performance.now());
      },
      leave: function () { cancelAnimationFrame(raf); }
    };
  })();

  /* ---- Career growth: India salary by experience, then the abroad column ---- */
  hooks.growth = (function () {
    var built = false;
    var X = [0, 5, 10], XL = ['First job', 'After 5 years', 'After 10 years'];
    var SERIES = [
      { name: '3D & game art', col: '#5ce1e6', v: [3.2, 6.2, 8.1], note: '7 yrs' },
      { name: 'VFX', col: '#8d93a8', v: [2.9, 4.5, 6.8], note: '8 yrs' },
      { name: 'Motion graphics', col: '#ff7a1a', v: [3.4, 8.1, 15.7] },
      { name: 'UI/UX', col: '#ffb547', v: [4.6, 11.5, 17.4], hi: true }
    ];
    function build(svg) {
      var L = 90, R = 1180, T = 70, B = 560, MAX = 20;
      function px(i) { return L + (R - L) * X[i] / 10; }
      function py(v) { return B - (B - T) * v / MAX; }
      var h = '<g class="grid">';
      [0, 5, 10, 15, 20].forEach(function (v) { h += '<line x1="' + L + '" x2="' + R + '" y1="' + py(v) + '" y2="' + py(v) + '"/><text x="' + (L - 16) + '" y="' + (py(v) + 7) + '" text-anchor="end">₹' + v + 'L</text>'; });
      h += '</g><text class="axcap" x="' + (L - 16) + '" y="24">Yearly salary in India, ₹ lakh per year</text>';
      XL.forEach(function (t, i) { h += '<text class="xl" x="' + px(i) + '" y="' + (B + 40) + '" text-anchor="middle">' + t + '</text>'; });
      // end-label positions, pushed apart so they never overlap
      var ly = SERIES.map(function (S, k) { return { k: k, y: py(S.v[2]) }; }).sort(function (a, b) { return a.y - b.y; });
      for (var q = 1; q < ly.length; q++) if (ly[q].y - ly[q - 1].y < 62) ly[q].y = ly[q - 1].y + 62;
      var LY = []; ly.forEach(function (o) { LY[o.k] = o.y; });
      SERIES.forEach(function (S, k) {
        var d = S.v.map(function (v, i) { return (i ? 'L' : 'M') + px(i) + ' ' + py(v); }).join(' ');
        h += '<path class="ln" d="' + d + '" stroke="' + S.col + '" pathLength="1" style="stroke-dasharray:1;stroke-dashoffset:1;transition:stroke-dashoffset 1.3s cubic-bezier(.2,.8,.2,1) ' + (0.3 + k * 0.45) + 's"/>';
        S.v.forEach(function (v, i) {
          h += '<circle class="pt" cx="' + px(i) + '" cy="' + py(v) + '" r="' + (S.hi ? 10 : 8) + '" fill="' + S.col + '" style="opacity:0;transition:opacity .4s ' + (0.5 + k * 0.45 + i * 0.35) + 's"/>';
        });
        var last = S.v[2];
        h += '<g style="opacity:0;transition:opacity .5s ' + (1.4 + k * 0.45) + 's" class="endlab"><text class="lab" x="' + (R + 22) + '" y="' + (LY[k] + 2) + '" fill="' + S.col + '">' + S.name + '</text>' +
          '<text class="val" x="' + (R + 22) + '" y="' + (LY[k] + 30) + '">₹' + last + ' L a year' + (S.note ? ' <tspan fill="#5f6579" font-size="17">(' + S.note + ')</tspan>' : '') + '</text></g>';
      });
      h += '<g class="abroad"><line x1="1420" x2="1420" y1="0" y2="' + B + '" stroke="#2b2f42" stroke-dasharray="6 8"/>' +
        '<text class="axcap" x="1450" y="24" text-anchor="start">Same job in the US</text>' +
        '<text class="sm" x="1450" y="' + (T + 6) + '">median yearly pay</text>' +
        '<text class="big" x="1450" y="' + (T + 110) + '" fill="#ffb547">₹98 L<tspan class="per"> / year</tspan></text><text class="sm" x="1450" y="' + (T + 142) + '">UI/UX ($104k)</text>' +
        '<text class="big" x="1450" y="' + (T + 250) + '" fill="#5ce1e6">₹96 L<tspan class="per"> / year</tspan></text><text class="sm" x="1450" y="' + (T + 282) + '">Animation &amp; VFX ($102k)</text>' +
        '<text class="sm dim" x="1450" y="' + (T + 380) + '">Middle of all US salaries,</text><text class="sm dim" x="1450" y="' + (T + 408) + '">every experience level.</text>' +
        '<text class="sm dim" x="1450" y="' + (T + 436) + '">Rent and living cost more too.</text></g>';
      svg.innerHTML = h;
    }
    return {
      enter: function (s) {
        var svg = s.querySelector('#growthSvg');
        if (!built) { build(svg); built = true; }
        $$('.ln, .pt, .endlab', svg).forEach(function (p) { if (p.dataset.tr === undefined) p.dataset.tr = p.style.transition; p.style.transition = 'none'; if (p.classList.contains('ln')) p.style.strokeDashoffset = 1; else p.style.opacity = 0; });
        svg.getBoundingClientRect();
        $$('.ln, .pt, .endlab', svg).forEach(function (p) { p.style.transition = p.dataset.tr; });
        requestAnimationFrame(function () {
          $$('.ln', svg).forEach(function (p) { p.style.strokeDashoffset = 0; });
          $$('.pt, .endlab', svg).forEach(function (p) { p.style.opacity = 1; });
        });
      },
      step: function (s, st) { var svg = s.querySelector('#growthSvg'); if (svg) svg.classList.toggle('abroad-on', st >= 1); }
    };
  })();

  /* ---- Where your code fits: one language per click, animated explainer ---- */
  hooks.tech = (function () {
    var built = false;
    function build(s) {
      var py = s.querySelector('.v-py'); py.innerHTML = Array.from({ length: 70 }, function (_, i) { return '<b style="--i:' + i + '"></b>'; }).join('');
      s.querySelector('.v-bp').innerHTML = '<i>Event: Begin Play</i><i>Spawn Actor</i><i>Play Sound</i><u></u><u></u><em></em>';
      s.querySelector('.v-pipe').innerHTML = '<span>model</span><span>texture</span><span>render</span><span>comp</span><b>robot_v003.fbx</b>';
      s.querySelector('.v-three').innerHTML = '<div class="cube"><i></i><i></i><i></i><i></i><i></i><i></i></div>';
      var G = [['#ff7a1a', '#8b5cf6'], ['#5ce1e6', '#1d4ed8'], ['#ffb547', '#ef4444'], ['#22c55e', '#0ea5e9']];
      s.querySelector('.v-ai').innerHTML = '<div class="prompt">generate("a neon city at dusk, 4 variations")</div><div class="tiles">' +
        G.map(function (g, i) { return '<b style="--i:' + i + ';--a:' + g[0] + ';--b:' + g[1] + '"></b>'; }).join('') + '</div>';
    }
    return {
      enter: function (s) { if (!built) { build(s); built = true; } },
      step: function (s, st) {
        if (!built) { build(s); built = true; }
        $$('.tech-list li', s).forEach(function (li, k) { li.classList.toggle('on', k === st); li.classList.toggle('done', k < st); });
        $$('.xp', s).forEach(function (x, k) { x.classList.toggle('on', k === st); });
      }
    };
  })();


  /* ---- Blender demo: copy the World Builder script ---- */
  (function () {
    var b = $('#copyWB'); if (!b) return;
    b.addEventListener('click', function () {
      fetch('blender/zica_world_builder.py', { cache: 'no-store' }).then(function (r) { return r.text(); }).then(function (t) {
        return navigator.clipboard.writeText(t);
      }).then(function () { b.textContent = 'Copied ✓ now paste in Blender'; b.classList.add('on'); setTimeout(function () { b.textContent = 'Copy World Builder script'; b.classList.remove('on'); }, 4000); })
        .catch(function () { b.textContent = 'Copy failed: use Download .py'; });
    });
  })();

  /* ---- The life you can get: Zynga video ---- */
  hooks.studiolife = (function () {
    var wired = false;
    return {
      enter: function () {
        var v = $('#slVideo'); if (wired) return; wired = true;
        $('#slSpeed').onclick = function () { v.playbackRate = v.playbackRate === 1 ? 2 : 1; this.textContent = v.playbackRate + '× speed'; this.classList.toggle('on', v.playbackRate !== 1); };
        $('#slSound').onclick = function () { v.muted = !v.muted; this.textContent = v.muted ? '🔇 Sound off' : '🔊 Sound on'; this.classList.toggle('on', !v.muted); };
      },
      leave: function () { var v = $('#slVideo'); if (v) v.pause(); }
    };
  })();

  /* ---- Life at ZICA: one set of real photos per click ---- */
  hooks.life = {
    step: function (s, st) {
      $$('.life-tabs li', s).forEach(function (li, k) { li.classList.toggle('on', k === st); li.classList.toggle('done', k < st); });
      $$('.life-set', s).forEach(function (x, k) { x.classList.toggle('on', k === st); });
    }
  };

  /* ---- Industry flow: playhead runs the 7 stages on entry ---- */
  hooks.flow = {
    enter: function (s) { var f = s.querySelector('.flow'); f.classList.remove('go'); void f.offsetWidth; requestAnimationFrame(function () { f.classList.add('go'); }); },
    leave: function () { var f = document.querySelector('#s-flow .flow'); if (f) f.classList.remove('go'); }
  };

  /* ---- AVGC: five live mini-animations, one per letter ---- */
  hooks.avgc = (function () {
    var raf = 0, cvs = [], t0 = 0, W = 360, H = 300, DPR = 2;
    function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
    function ease(x) { x = clamp01(x); return x * x * (3 - 2 * x); }
    function lerp(a, b, k) { return a + (b - a) * k; }
    function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }

    /* ---------- A · a desk lamp that hops: anticipation, squash, stretch, keyframes ---------- */
    function lampPose(t) {
      var HOP = 1.15, N = 3, HOLD = 0.9, L = HOP * N + HOLD, tt = t % L, k = Math.min(N - 1, Math.floor(tt / HOP)), u = (tt - k * HOP) / HOP;
      var x0 = 60 + k * 66, x = x0, y = 0, c = 0;
      if (tt >= HOP * N) { x = 60 + N * 66; u = 1; }
      if (u < 0.28) c = ease(u / 0.28);                                // anticipation crouch
      else if (u < 0.72) { var a = (u - 0.28) / 0.44; y = Math.sin(a * Math.PI) * 74; x = x0 + ease(a) * 66; c = lerp(1, -0.55, ease(a * 2)) * (a < 0.5 ? 1 : 0) + (a >= 0.5 ? lerp(-0.55, 0.2, ease((a - .5) * 2)) : 0); }
      else if (u < 0.86) { x = x0 + 66; c = Math.sin((u - 0.72) / 0.14 * Math.PI) * 1.1; }    // land: squash
      else { x = x0 + 66; c = -Math.sin((u - 0.86) / 0.14 * Math.PI) * 0.18; }               // settle
      if (tt >= HOP * N) { var f = (tt - HOP * N) / HOLD; c = 0; return { x: x, y: 0, c: 0, fade: f > .7 ? (1 - (f - .7) / .3) : 1, u: u, frame: Math.floor(t * 24) }; }
      return { x: x, y: y, c: c, fade: 1, frame: Math.floor(t * 24), k: k, u: u };
    }
    function drawLamp(c, p, alpha, ghost) {
      var G = 222, bx = p.x, by = G - p.y, cc = p.c;
      var squash = 1 + 0.12 * Math.max(0, cc), stretch = 1 + 0.18 * Math.max(0, -cc);
      var th1 = -Math.PI / 2 - (0.42 + 0.5 * cc), L1 = 54 * stretch / squash;
      var jx = bx + Math.cos(th1) * L1, jy = by - 9 + Math.sin(th1) * L1;
      var th2 = th1 + (1.55 + 0.8 * cc), L2 = 48 * stretch / squash;
      var hx = jx + Math.cos(th2) * L2, hy = jy + Math.sin(th2) * L2, th3 = th2 + 1.05 + 0.25 * cc;
      c.save(); c.globalAlpha = alpha;
      if (!ghost) {   // light cone + pool on the floor
        var lx = hx + Math.cos(th3) * 26, ly = hy + Math.sin(th3) * 26, gx = lx + Math.cos(th3) * (G - ly) / Math.max(.3, Math.sin(th3)), gy = G;
        c.globalCompositeOperation = 'lighter';
        var cone = c.createLinearGradient(lx, ly, gx, gy); cone.addColorStop(0, 'rgba(255,214,140,.55)'); cone.addColorStop(1, 'rgba(255,181,71,0)');
        c.fillStyle = cone; c.beginPath(); var sp = 0.38, d = Math.hypot(gx - lx, gy - ly);
        c.moveTo(lx, ly); c.lineTo(lx + Math.cos(th3 - sp) * d, ly + Math.sin(th3 - sp) * d); c.lineTo(lx + Math.cos(th3 + sp) * d, ly + Math.sin(th3 + sp) * d); c.closePath(); c.fill();
        var pool = c.createRadialGradient(gx, G, 0, gx, G, 70); pool.addColorStop(0, 'rgba(255,200,110,.45)'); pool.addColorStop(1, 'rgba(255,181,71,0)');
        c.fillStyle = pool; c.save(); c.translate(gx, G); c.scale(1, .22); c.beginPath(); c.arc(0, 0, 70, 0, 7); c.fill(); c.restore();
        c.globalCompositeOperation = 'source-over';
        // contact shadow
        var sh = 1 - Math.min(1, p.y / 90); c.fillStyle = 'rgba(0,0,0,' + (0.45 * sh) + ')'; c.save(); c.translate(bx, G + 2); c.scale(1, .18); c.beginPath(); c.arc(0, 0, 30 * (0.6 + .4 * sh), 0, 7); c.fill(); c.restore();
      }
      var metal = ghost ? 'rgba(255,181,71,.5)' : '#e9ecf3', dark = ghost ? 'rgba(255,181,71,.35)' : '#9aa1b5';
      // base
      c.fillStyle = metal; c.save(); c.translate(bx, by - 4); c.scale(1.0 * squash, 1 / squash);
      c.beginPath(); c.ellipse(0, 0, 26, 7, 0, 0, 7); c.fill(); c.fillStyle = dark; c.fillRect(-5, -11, 10, 8); c.restore();
      // arms (double struts)
      c.lineCap = 'round'; c.strokeStyle = metal; c.lineWidth = 4.5;
      c.beginPath(); c.moveTo(bx, by - 9); c.lineTo(jx, jy); c.lineTo(hx, hy); c.stroke();
      c.strokeStyle = dark; c.lineWidth = 1.6;
      c.beginPath(); c.moveTo(bx + 5, by - 10); c.lineTo(jx + 4, jy + 2); c.lineTo(hx + 2, hy + 4); c.stroke();
      [[bx, by - 9], [jx, jy], [hx, hy]].forEach(function (q) { c.fillStyle = dark; c.beginPath(); c.arc(q[0], q[1], 4.5, 0, 7); c.fill(); c.fillStyle = metal; c.beginPath(); c.arc(q[0], q[1], 2, 0, 7); c.fill(); });
      // shade
      c.save(); c.translate(hx, hy); c.rotate(th3);
      var sg = c.createLinearGradient(0, -16, 0, 16); sg.addColorStop(0, ghost ? 'rgba(255,181,71,.4)' : '#ffffff'); sg.addColorStop(1, ghost ? 'rgba(255,181,71,.2)' : '#a9b0c4');
      c.fillStyle = sg; c.beginPath(); c.moveTo(-4, -8); c.lineTo(28, -19); c.lineTo(28, 19); c.lineTo(-4, 8); c.closePath(); c.fill();
      if (!ghost) { c.fillStyle = '#fff6dc'; c.shadowColor = '#ffcf7a'; c.shadowBlur = 18; c.beginPath(); c.ellipse(28, 0, 4, 17, 0, 0, 7); c.fill(); c.shadowBlur = 0; }
      c.restore(); c.restore();
    }
    function A(c, w, h, t) {
      var bg = c.createLinearGradient(0, 0, 0, h); bg.addColorStop(0, '#11131c'); bg.addColorStop(.74, '#191c28'); bg.addColorStop(.74, '#0b0c11'); bg.addColorStop(1, '#07080b');
      c.fillStyle = bg; c.fillRect(0, 0, w, h);
      var p = lampPose(t);
      for (var g = 4; g >= 1; g--) { var q = lampPose(Math.max(0, t - g * 0.07)); if (q.fade === 1 && p.fade === 1) drawLamp(c, q, 0.08 * (5 - g), true); }   // onion skin
      drawLamp(c, p, p.fade, false);
      // reflection line + keyframe strip
      c.fillStyle = 'rgba(13,14,19,.85)'; c.fillRect(0, h - 44, w, 44);
      c.strokeStyle = '#2b2f42'; c.beginPath(); c.moveTo(16, h - 22); c.lineTo(w - 16, h - 22); c.stroke();
      var loopT = (1.15 * 3 + .9), ph = (t % loopT) / loopT;
      for (var i = 0; i <= 12; i++) { var kx = 16 + (w - 32) * i / 12, on = i / 12 <= ph; c.save(); c.translate(kx, h - 22); c.rotate(Math.PI / 4); c.fillStyle = on ? '#ffb547' : '#0d0e13'; c.strokeStyle = on ? '#ffb547' : '#4a4f66'; c.fillRect(-3.5, -3.5, 7, 7); c.strokeRect(-3.5, -3.5, 7, 7); c.restore(); }
      var px = 16 + (w - 32) * ph; c.fillStyle = '#5ce1e6'; c.fillRect(px - 1, h - 38, 2, 32);
      c.font = '600 11px "JetBrains Mono", monospace'; c.fillStyle = '#8d93a8'; c.fillText('f ' + String(p.frame % 1000).padStart(3, '0'), 14, 20);
      c.textAlign = 'right'; c.fillText(p.c > .5 ? 'SQUASH' : p.c < -.3 ? 'STRETCH' : p.y > 4 ? 'ARC' : 'ANTICIPATION', w - 14, 20); c.textAlign = 'left';
    }

    /* ---------- V · green-screen plate → cinematic comp (wipe) ---------- */
    var embers = [];
    function figure(c, x, y, s, fill, rim) {
      c.save(); c.translate(x, y); c.scale(s, s);
      c.fillStyle = fill; c.beginPath();
      c.arc(0, -78, 9, 0, 7); c.fill();
      c.beginPath(); c.moveTo(-11, -66); c.lineTo(11, -66); c.lineTo(14, -30); c.lineTo(9, 0); c.lineTo(3, 0); c.lineTo(0, -26); c.lineTo(-3, 0); c.lineTo(-9, 0); c.lineTo(-14, -30); c.closePath(); c.fill();
      c.beginPath(); c.moveTo(-11, -64); c.quadraticCurveTo(-30, -40, -26, -6); c.lineTo(-14, -30); c.closePath(); c.fill();   // cape
      c.fillRect(10, -62, 18, 4);   // arm pointing
      if (rim) { c.strokeStyle = rim; c.lineWidth = 1.6; c.beginPath(); c.arc(0, -78, 9, -1.2, 1.2); c.stroke(); c.beginPath(); c.moveTo(11, -66); c.lineTo(14, -30); c.lineTo(9, 0); c.stroke(); }
      c.restore();
    }
    function comp(c, w, h, t) {
      var sky = c.createLinearGradient(0, 0, 0, h); sky.addColorStop(0, '#120c2e'); sky.addColorStop(.45, '#5a1f4f'); sky.addColorStop(.72, '#ff7a1a'); sky.addColorStop(1, '#2a0f0a');
      c.fillStyle = sky; c.fillRect(0, 0, w, h);
      var sx = w * .62, sy = h * .58;
      c.globalCompositeOperation = 'lighter';
      var bl = c.createRadialGradient(sx, sy, 0, sx, sy, 190); bl.addColorStop(0, 'rgba(255,230,170,.9)'); bl.addColorStop(.12, 'rgba(255,170,80,.6)'); bl.addColorStop(1, 'rgba(255,90,30,0)');
      c.fillStyle = bl; c.fillRect(0, 0, w, h);
      for (var r = 0; r < 7; r++) {   // god rays
        var a = -Math.PI / 2 + (r - 3) * .32 + Math.sin(t * .3 + r) * .03; c.fillStyle = 'rgba(255,200,120,.05)';
        c.beginPath(); c.moveTo(sx, sy); c.lineTo(sx + Math.cos(a - .06) * 400, sy + Math.sin(a - .06) * 400); c.lineTo(sx + Math.cos(a + .06) * 400, sy + Math.sin(a + .06) * 400); c.fill();
      }
      c.globalCompositeOperation = 'source-over';
      function ridge(base, amp, col, f, off) { c.fillStyle = col; c.beginPath(); c.moveTo(0, h); for (var x = 0; x <= w; x += 6) c.lineTo(x, base - amp * (Math.sin(x * f + off) * .6 + Math.sin(x * f * 2.7 + off * 1.7) * .4)); c.lineTo(w, h); c.fill(); }
      ridge(h * .64, 26, 'rgba(70,34,78,.85)', .018, t * .05);
      // city with windows
      c.fillStyle = '#1c1229';
      for (var b = 0; b < 16; b++) { var bw = 18 + (b * 13) % 14, bh = 40 + (b * 37) % 70, bx = (b * 25 - t * 4) % (w + 40) - 20; c.fillRect(bx, h * .76 - bh, bw, bh + 40); }
      c.fillStyle = 'rgba(255,190,110,.75)';
      for (var i = 0; i < 70; i++) { var wx = ((i * 47) % 400 - t * 4) % (w + 40) - 20, wy = h * .76 - 10 - (i * 29) % 90; if ((i * 7 + Math.floor(t)) % 9) c.fillRect(wx, wy, 2, 3); }
      var fog = c.createLinearGradient(0, h * .6, 0, h * .85); fog.addColorStop(0, 'rgba(255,140,80,0)'); fog.addColorStop(1, 'rgba(255,140,80,.28)'); c.fillStyle = fog; c.fillRect(0, h * .55, w, h * .35);
      ridge(h * .9, 10, '#0a0608', .03, 1);
      figure(c, w * .42, h * .86, 1.05, '#07050a', 'rgba(255,190,110,.95)');
      // embers
      c.globalCompositeOperation = 'lighter';
      embers.forEach(function (e) { var g = c.createRadialGradient(e.x, e.y, 0, e.x, e.y, e.r * 3); g.addColorStop(0, 'rgba(255,200,120,' + e.a + ')'); g.addColorStop(1, 'rgba(255,120,40,0)'); c.fillStyle = g; c.beginPath(); c.arc(e.x, e.y, e.r * 3, 0, 7); c.fill(); });
      c.globalCompositeOperation = 'source-over';
      var vg = c.createRadialGradient(w / 2, h / 2, h * .3, w / 2, h / 2, w * .75); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.55)'); c.fillStyle = vg; c.fillRect(0, 0, w, h);
    }
    function plate(c, w, h) {
      var g = c.createRadialGradient(w * .45, h * .4, 20, w * .45, h * .4, w * .8); g.addColorStop(0, '#3fd17a'); g.addColorStop(1, '#127a3e');
      c.fillStyle = g; c.fillRect(0, 0, w, h);
      c.fillStyle = 'rgba(0,0,0,.18)'; c.fillRect(0, h * .78, w, h);
      c.strokeStyle = 'rgba(255,255,255,.8)'; c.lineWidth = 1.5;
      for (var y = 40; y < h * .75; y += 60) for (var x = 30; x < w; x += 70) { c.beginPath(); c.moveTo(x - 5, y); c.lineTo(x + 5, y); c.moveTo(x, y - 5); c.lineTo(x, y + 5); c.stroke(); }
      c.fillStyle = '#6c7280'; c.fillRect(0, h * .86, w, h);
      figure(c, w * .42, h * .86, 1.05, '#3a3f4b', null);
    }
    function V(c, w, h, t) {
      // embers sim
      if (embers.length < 70) embers.push({ x: Math.random() * w, y: h + 5, vx: (Math.random() - .5) * 12, vy: -(18 + Math.random() * 40), r: .8 + Math.random() * 1.6, a: .9 });
      embers.forEach(function (e) { e.x += e.vx / 60 + Math.sin(t * 2 + e.y * .05) * .2; e.y += e.vy / 60; e.a *= .996; });
      embers = embers.filter(function (e) { return e.y > -10 && e.a > .05; });
      var wx = w * (.5 + .38 * Math.sin(t * .55));
      plate(c, w, h);
      c.save(); c.beginPath(); c.rect(wx, 0, w - wx, h); c.clip(); comp(c, w, h, t); c.restore();
      // letterbox on the comp side
      c.fillStyle = '#000'; c.fillRect(wx, 0, w - wx, 26); c.fillRect(wx, h - 26, w - wx, 26);
      c.fillStyle = '#fff'; c.fillRect(wx - 1, 0, 2, h);
      c.beginPath(); c.arc(wx, h / 2, 9, 0, 7); c.fill(); c.fillStyle = '#0d0e13'; c.font = '700 10px sans-serif'; c.textAlign = 'center'; c.fillText('⇆', wx, h / 2 + 3.5); c.textAlign = 'left';
      c.font = '600 10px "JetBrains Mono", monospace';
      c.fillStyle = 'rgba(0,0,0,.55)'; c.fillRect(10, 10, 46, 18); c.fillStyle = '#fff'; c.fillText('PLATE', 17, 23);
      if (w - wx > 70) { c.fillStyle = 'rgba(255,181,71,.9)'; c.fillRect(w - 64, 34, 54, 18); c.fillStyle = '#0d0e13'; c.fillText('FINAL', w - 55, 47); }
    }

    /* ---------- G · synthwave racer: pseudo-3D road ---------- */
    function G(c, w, h, t) {
      var hz = h * .46, speed = 26, z0 = t * speed, curve = Math.sin(t * .45) * 1.0 + Math.sin(t * .17) * .6;
      var sky = c.createLinearGradient(0, 0, 0, hz); sky.addColorStop(0, '#0a0620'); sky.addColorStop(.6, '#3b0d4f'); sky.addColorStop(1, '#ff2e88');
      c.fillStyle = sky; c.fillRect(0, 0, w, hz);
      for (var s = 0; s < 40; s++) { c.fillStyle = 'rgba(255,255,255,' + (.3 + (s % 3) * .2) + ')'; c.fillRect((s * 83) % w, (s * 37) % (hz * .6), 1.2, 1.2); }
      // striped sun
      var sxx = w / 2 - curve * 30, syy = hz - 6;
      c.save(); c.beginPath(); c.rect(0, 0, w, hz); c.clip();
      var sg = c.createLinearGradient(0, syy - 60, 0, syy); sg.addColorStop(0, '#ffe66d'); sg.addColorStop(1, '#ff3d8b');
      c.fillStyle = sg; c.shadowColor = '#ff3d8b'; c.shadowBlur = 30; c.beginPath(); c.arc(sxx, syy, 58, Math.PI, 0); c.fill(); c.shadowBlur = 0;
      c.fillStyle = '#3b0d4f'; for (var k = 0; k < 6; k++) { var yy = syy - 30 + k * 6 + ((t * 8) % 6); c.fillRect(sxx - 60, yy, 120, 1 + k * .5); }
      c.restore();
      // mountains
      c.fillStyle = '#1a0830'; c.strokeStyle = '#ff2e88'; c.lineWidth = 1;
      c.beginPath(); c.moveTo(0, hz); for (var x = 0; x <= w; x += 8) c.lineTo(x, hz - 18 - 16 * Math.abs(Math.sin((x + curve * 40) * .03)) * Math.abs(Math.sin((x + curve * 40) * .011))); c.lineTo(w, hz); c.fill(); c.stroke();
      // road rows
      var cx = w / 2, dx = 0, ddx = 0;
      for (var y = h; y > hz; y--) {
        var p = (y - hz) / (h - hz), z = 1 / p, zz = z * 9 + z0;
        ddx = curve * 0.0016 * (1 - p) * (1 - p) * 220; dx += ddx;
        var rc = cx - dx * (h - y) * 0.6 * (1 - p);
        var half = 18 + p * 150, band = Math.floor(zz / 6) % 2;
        c.fillStyle = band ? '#14062a' : '#1b0936'; c.fillRect(0, y, w, 1);
        c.fillStyle = band ? '#2b2d3d' : '#33364a'; c.fillRect(rc - half, y, half * 2, 1);
        c.fillStyle = band ? '#ff2e88' : '#f4f4f8'; c.fillRect(rc - half - half * .08, y, half * .08, 1); c.fillRect(rc + half, y, half * .08, 1);
        if (band) { c.fillStyle = '#ffe66d'; c.fillRect(rc - half * .02, y, half * .04, 1); }
        if (Math.floor(zz / 6) !== Math.floor(((1 / ((y - 1 - hz) / (h - hz))) * 9 + z0) / 6)) { c.fillStyle = 'rgba(92,225,230,.35)'; c.fillRect(0, y, rc - half * 1.1, 1); c.fillRect(rc + half * 1.1, y, w, 1); }
      }
      // neon side grid verticals
      c.strokeStyle = 'rgba(92,225,230,.25)';
      for (var gl = -6; gl <= 6; gl++) { if (gl === 0) continue; c.beginPath(); c.moveTo(w / 2 + gl * 6 - curve * 30, hz); c.lineTo(w / 2 + gl * 120, h); c.stroke(); }
      // car
      var lean = -curve * .06, carx = w / 2 + Math.sin(t * 1.3) * 8;
      c.save(); c.translate(carx, h - 30); c.rotate(lean);
      c.fillStyle = 'rgba(0,0,0,.45)'; c.beginPath(); c.ellipse(0, 18, 50, 7, 0, 0, 7); c.fill();
      c.fillStyle = '#c71f5b'; rr(c, -46, -6, 92, 22, 5); c.fill();
      c.fillStyle = '#2a0b1f'; rr(c, -30, -24, 60, 20, 6); c.fill();
      c.fillStyle = 'rgba(92,225,230,.5)'; rr(c, -25, -21, 50, 13, 4); c.fill();
      c.fillStyle = '#0b0b10'; c.fillRect(-44, 12, 18, 9); c.fillRect(26, 12, 18, 9);
      c.shadowColor = '#ff3355'; c.shadowBlur = 14; c.fillStyle = '#ff3355'; c.fillRect(-42, 0, 22, 5); c.fillRect(20, 0, 22, 5); c.shadowBlur = 0;
      c.fillStyle = '#f4f4f8'; c.fillRect(-12, 4, 24, 6); c.fillStyle = '#0d0e13'; c.font = '700 6px "JetBrains Mono", monospace'; c.textAlign = 'center'; c.fillText('ZICA', 0, 9.5); c.textAlign = 'left';
      c.restore();
      // speed lines + HUD
      c.strokeStyle = 'rgba(255,255,255,.25)'; for (var l = 0; l < 8; l++) { var ly = hz + 20 + ((l * 53 + t * 260) % (h - hz)), side = l % 2 ? 1 : -1; c.beginPath(); c.moveTo(w / 2 + side * (20 + (ly - hz) * 1.4), ly); c.lineTo(w / 2 + side * (40 + (ly - hz) * 1.9), ly + 12); c.stroke(); }
      c.font = '700 12px "JetBrains Mono", monospace'; c.fillStyle = '#5ce1e6'; c.fillText((180 + Math.round(Math.sin(t) * 12)) + ' km/h', 14, 22);
      c.fillStyle = '#ffe66d'; c.textAlign = 'right'; var lt = t % 60; c.fillText('LAP 0' + (1 + Math.floor(t / 60) % 3) + '  ' + Math.floor(lt / 10) + (Math.floor(lt) % 10) + '.' + String(Math.floor((t * 100) % 100)).padStart(2, '0'), w - 14, 22); c.textAlign = 'left';
    }

    /* ---------- C · a three-panel comic page that builds itself ---------- */
    function halftone(c, x, y, w, h, col, cx, cy, maxr, step) {
      c.fillStyle = col; step = step || 8;
      for (var yy = y; yy < y + h + step; yy += step) for (var xx = x; xx < x + w + step; xx += step) {
        var d = Math.hypot(xx - cx, yy - cy) / Math.hypot(w, h), r = Math.max(0, maxr * (1 - d * 1.3));
        if (r > .3) { c.beginPath(); c.arc(xx + ((yy / step) % 2) * step / 2, yy, r, 0, 7); c.fill(); }
      }
    }
    function burst(c, x, y, r1, r2, n, rot) { c.beginPath(); for (var i = 0; i < n * 2; i++) { var a = rot + i / (n * 2) * Math.PI * 2, r = i % 2 ? r1 : r2 * (1 + (i % 3) * .08); c.lineTo(x + Math.cos(a) * r * 1.3, y + Math.sin(a) * r * .85); } c.closePath(); }
    function C(c, w, h, t) {
      var L = 6, tt = t % L, ap = [ease(tt / .5), ease((tt - 1.4) / .5), ease((tt - 2.8) / .45)], out = tt > L - .5 ? 1 - ease((tt - (L - .5)) / .5) : 1;
      c.fillStyle = '#f2e8d4'; c.fillRect(0, 0, w, h);
      var P = [[10, 10, w - 20, 118], [10, 136, 132, 154], [150, 136, w - 160, 154]];
      P.forEach(function (q, i) {
        var a = ap[i] * out; if (a <= 0) return;
        c.save(); c.globalAlpha = a; c.translate(q[0] + q[2] / 2, q[1] + q[3] / 2); var sc = .9 + .1 * a; c.scale(sc, sc); c.translate(-(q[0] + q[2] / 2), -(q[1] + q[3] / 2));
        c.save(); c.beginPath(); c.rect(q[0], q[1], q[2], q[3]); c.clip();
        if (i === 0) {   // night city establishing shot
          var g = c.createLinearGradient(0, q[1], 0, q[1] + q[3]); g.addColorStop(0, '#1b2a6b'); g.addColorStop(1, '#5c3ea8'); c.fillStyle = g; c.fillRect(q[0], q[1], q[2], q[3]);
          halftone(c, q[0], q[1], q[2], q[3], 'rgba(255,255,255,.12)', q[0] + q[2] * .78, q[1] + 30, 3.2, 7);
          c.fillStyle = '#fff6c9'; c.beginPath(); c.arc(q[0] + q[2] * .78, q[1] + 34, 18, 0, 7); c.fill();
          c.fillStyle = '#0d0b1e';
          for (var b = 0; b < 14; b++) { var bw = 14 + (b * 7) % 16, bh = 30 + (b * 23) % 52; c.fillRect(q[0] + b * 25 - 6, q[1] + q[3] - bh, bw, bh); }
          c.fillStyle = '#ffd54a'; for (var wi = 0; wi < 40; wi++) c.fillRect(q[0] + (wi * 37) % q[2], q[1] + q[3] - 8 - (wi * 13) % 44, 2, 3);
          var txt = 'MEANWHILE, IN PUNE…', n = Math.max(0, Math.min(txt.length, Math.floor((tt - .4) * 18)));
          c.fillStyle = '#ffe14d'; c.fillRect(q[0] + 8, q[1] + 8, 150, 22); c.strokeStyle = '#111'; c.lineWidth = 2; c.strokeRect(q[0] + 8, q[1] + 8, 150, 22);
          c.fillStyle = '#111'; c.font = '800 12px "Bricolage Grotesque", sans-serif'; c.fillText(txt.slice(0, n), q[0] + 15, q[1] + 23);
        } else if (i === 1) {   // hero leaps, speed lines
          c.fillStyle = '#ff9f1a'; c.fillRect(q[0], q[1], q[2], q[3]);
          var cx = q[0] + q[2] * .5, cy = q[1] + q[3] * .45;
          c.strokeStyle = 'rgba(255,255,255,.75)'; c.lineWidth = 1.4;
          for (var s = 0; s < 36; s++) { var a = s / 36 * Math.PI * 2 + tt * .1, r0 = 30 + (s * 13) % 18; c.beginPath(); c.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0); c.lineTo(cx + Math.cos(a) * 140, cy + Math.sin(a) * 140); c.stroke(); }
          c.save(); c.translate(cx, cy + 10 - Math.sin(Math.min(1, (tt - 1.4)) * 3) * 6); c.rotate(-.5); c.fillStyle = '#111';
          c.beginPath(); c.arc(0, -36, 9, 0, 7); c.fill(); c.beginPath(); c.moveTo(-10, -26); c.lineTo(10, -26); c.lineTo(8, 4); c.lineTo(-8, 4); c.closePath(); c.fill();
          c.lineWidth = 6; c.lineCap = 'round'; c.strokeStyle = '#111';
          c.beginPath(); c.moveTo(6, -22); c.lineTo(26, -40); c.moveTo(-6, -22); c.lineTo(-24, -6); c.moveTo(-4, 2); c.lineTo(-18, 26); c.moveTo(4, 2); c.lineTo(20, 18); c.stroke();
          c.fillStyle = '#e8322b'; c.beginPath(); c.moveTo(-10, -24); c.quadraticCurveTo(-40, -30, -46, 4); c.lineTo(-8, -6); c.fill();
          c.restore();
        } else {   // impact
          var sh = tt > 2.8 && tt < 3.3 ? Math.sin(tt * 90) * 3 : 0;
          c.translate(sh, 0);
          c.fillStyle = '#e8322b'; c.fillRect(q[0] - 4, q[1], q[2] + 8, q[3]);
          halftone(c, q[0], q[1], q[2], q[3], 'rgba(255,214,0,.85)', q[0] + q[2] / 2, q[1] + q[3] / 2, 4.2, 9);
          var pc = ease((tt - 2.8) / .3), pulse = 1 + .05 * Math.sin(tt * 8);
          c.save(); c.translate(q[0] + q[2] / 2, q[1] + q[3] / 2); c.scale(pc * pulse, pc * pulse);
          c.fillStyle = '#ffe14d'; burst(c, 0, 0, 34, 60, 11, tt * .2); c.fill(); c.strokeStyle = '#111'; c.lineWidth = 3; c.stroke();
          c.fillStyle = '#fff'; burst(c, 0, 0, 24, 40, 11, -tt * .2); c.fill();
          c.rotate(-.12); c.font = '900 36px "Bricolage Grotesque", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
          c.lineWidth = 6; c.strokeStyle = '#111'; c.strokeText('POW!', 0, 2); c.fillStyle = '#e8322b'; c.fillText('POW!', 0, 2);
          c.restore(); c.textAlign = 'left'; c.textBaseline = 'alphabetic';
          c.fillStyle = '#111'; for (var d = 0; d < 7; d++) { var ang = d * .9 + 1, rd = 60 + pc * 40; c.save(); c.translate(q[0] + q[2] / 2 + Math.cos(ang) * rd, q[1] + q[3] / 2 + Math.sin(ang) * rd * .7); c.rotate(ang + tt); c.fillRect(-3, -2, 6, 4); c.restore(); }
        }
        c.restore();
        c.strokeStyle = '#111'; c.lineWidth = 3.5; c.strokeRect(q[0], q[1], q[2], q[3]);
        c.restore();
      });
    }

    /* ---------- XR · AR object placed on a detected table ---------- */
    var ICO = (function () {
      var p = (1 + Math.sqrt(5)) / 2, v = [[-1, p, 0], [1, p, 0], [-1, -p, 0], [1, -p, 0], [0, -1, p], [0, 1, p], [0, -1, -p], [0, 1, -p], [p, 0, -1], [p, 0, 1], [-p, 0, -1], [-p, 0, 1]];
      var f = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]];
      return { v: v.map(function (q) { var l = Math.hypot(q[0], q[1], q[2]); return [q[0] / l, q[1] / l, q[2] / l]; }), f: f };
    })();
    function X(c, w, h, t) {
      var L = 7, tt = t % L;
      // "camera feed": a room and a table
      var wall = c.createLinearGradient(0, 0, 0, h); wall.addColorStop(0, '#2e3243'); wall.addColorStop(.55, '#3d4152'); c.fillStyle = wall; c.fillRect(0, 0, w, h);
      c.fillStyle = 'rgba(255,230,190,.08)'; c.fillRect(w * .62, 20, 70, 90); c.strokeStyle = 'rgba(255,255,255,.12)'; c.strokeRect(w * .62, 20, 70, 90);
      var ty = h * .56;
      c.fillStyle = '#6b4a33'; c.beginPath(); c.moveTo(30, ty); c.lineTo(w - 30, ty); c.lineTo(w + 40, h); c.lineTo(-40, h); c.closePath(); c.fill();
      var wood = c.createLinearGradient(0, ty, 0, h); wood.addColorStop(0, 'rgba(255,220,180,.18)'); wood.addColorStop(1, 'rgba(0,0,0,.25)'); c.fillStyle = wood; c.fill();
      // plane detection sweep (dots on the table)
      var det = clamp01(tt / 1.6);
      for (var i = 0; i < 9; i++) for (var j = 0; j < 7; j++) {
        var u = i / 8, v = j / 6, yy = ty + 8 + v * (h - ty - 16), sp = lerp(.78, 1.12, v), xx = w / 2 + (u - .5) * (w - 60) * sp;
        if (u > det * 1.15) continue;
        c.fillStyle = 'rgba(92,225,230,' + (.35 + .4 * (1 - det)) + ')'; c.beginPath(); c.arc(xx, yy, 1.6, 0, 7); c.fill();
      }
      var cx = w / 2, cy = ty + 34, pop = ease((tt - 1.8) / .6) * (tt > L - .6 ? 1 - ease((tt - (L - .6)) / .6) : 1);
      // placement ring
      c.strokeStyle = 'rgba(92,225,230,' + (.8 * (det >= 1 ? 1 : 0)) + ')'; c.lineWidth = 2;
      c.save(); c.translate(cx, cy); c.scale(1, .32); c.beginPath(); c.arc(0, 0, 46 + Math.sin(tt * 4) * 2, 0, 7); c.stroke(); c.restore();
      if (pop > 0) {
        c.fillStyle = 'rgba(0,0,0,' + (.35 * pop) + ')'; c.save(); c.translate(cx, cy + 2); c.scale(1, .28); c.beginPath(); c.arc(0, 0, 40 * pop, 0, 7); c.fill(); c.restore();
        var R = 38 * pop, ay = t * .9, ax = .45, lt = [-.4, -.7, .55], ll = Math.hypot(lt[0], lt[1], lt[2]); lt = lt.map(function (q) { return q / ll; });
        var hov = Math.sin(t * 2) * 3, oy = cy - 46 - hov;
        var V3 = ICO.v.map(function (q) { var x = q[0] * Math.cos(ay) - q[2] * Math.sin(ay), z = q[0] * Math.sin(ay) + q[2] * Math.cos(ay), y = q[1]; var y2 = y * Math.cos(ax) - z * Math.sin(ax), z2 = y * Math.sin(ax) + z * Math.cos(ax); return [x, y2, z2]; });
        var faces = ICO.f.map(function (f) { var a = V3[f[0]], b = V3[f[1]], d = V3[f[2]]; var u1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], u2 = [d[0] - a[0], d[1] - a[1], d[2] - a[2]]; var n = [u1[1] * u2[2] - u1[2] * u2[1], u1[2] * u2[0] - u1[0] * u2[2], u1[0] * u2[1] - u1[1] * u2[0]]; var nl = Math.hypot(n[0], n[1], n[2]); n = n.map(function (q) { return q / nl; }); return { f: f, z: (a[2] + b[2] + d[2]) / 3, n: n }; })
          .filter(function (o) { return o.n[2] < 0; }).sort(function (p, q) { return q.z - p.z; });
        faces.forEach(function (o) {
          var lum = Math.max(0, -(o.n[0] * lt[0] + o.n[1] * lt[1] + o.n[2] * lt[2]));
          var r = Math.round(lerp(30, 255, lum * .9 + .1)), g = Math.round(lerp(40, 181, lum)), b = Math.round(lerp(70, 71, lum));
          c.fillStyle = 'rgb(' + r + ',' + g + ',' + b + ')'; c.strokeStyle = 'rgba(255,230,180,.35)'; c.lineWidth = .8;
          c.beginPath(); o.f.forEach(function (k, m) { var p = V3[k]; var X2 = cx + p[0] * R, Y2 = oy + p[1] * R; if (m) c.lineTo(X2, Y2); else c.moveTo(X2, Y2); }); c.closePath(); c.fill(); c.stroke();
        });
        if (pop > .9) { c.font = '600 10px "JetBrains Mono", monospace'; c.fillStyle = '#5ce1e6'; c.fillText('anchor · 0.42 m', cx + 48, oy - 30); c.strokeStyle = 'rgba(92,225,230,.6)'; c.beginPath(); c.moveTo(cx + 28, oy - 18); c.lineTo(cx + 46, oy - 33); c.lineTo(cx + 120, oy - 33); c.stroke(); }
      }
      // HUD: reticle corners + status
      c.strokeStyle = 'rgba(255,255,255,.8)'; c.lineWidth = 2; var m = 14, Lc = 16;
      [[m, m, 1, 1], [w - m, m, -1, 1], [m, h - m, 1, -1], [w - m, h - m, -1, -1]].forEach(function (k) { c.beginPath(); c.moveTo(k[0], k[1] + Lc * k[3]); c.lineTo(k[0], k[1]); c.lineTo(k[0] + Lc * k[2], k[1]); c.stroke(); });
      c.font = '600 10px "JetBrains Mono", monospace'; c.fillStyle = 'rgba(0,0,0,.5)'; c.fillRect(24, 22, 128, 18);
      c.fillStyle = det < 1 ? '#ffe14d' : '#5ce1e6'; c.fillText(det < 1 ? '● SCANNING SURFACE' : (pop > 0 ? '● OBJECT PLACED' : '● PLANE FOUND'), 30, 35);
      c.fillStyle = '#e8322b'; c.beginPath(); c.arc(w - 30, 31, 4, 0, 7); c.fill(); c.fillStyle = '#fff'; c.fillText('REC', w - 60, 35);
    }

    var FN = [A, V, G, C, X];
    function frame(now) {
      var t = reduce ? 2.2 : (now - t0) / 1000;
      cvs.forEach(function (cv, i) { var c = cv.getContext('2d'); c.setTransform(DPR, 0, 0, DPR, 0, 0); c.clearRect(0, 0, W, H); c.save(); FN[i](c, W, H, t); c.restore(); });
      if (!reduce) raf = requestAnimationFrame(frame);
    }
    return {
      enter: function (s) {
        cvs = $$('.av canvas', s); cvs.forEach(function (cv) { cv.width = W * DPR; cv.height = H * DPR; });
        embers = []; t0 = performance.now(); cancelAnimationFrame(raf); raf = requestAnimationFrame(frame);
      },
      step: function (s, st) {
        $$('.av', s).forEach(function (el, k) { el.classList.toggle('focus', st >= 1 && st <= 4 && k === st - 1); el.classList.toggle('dim', st >= 1 && st <= 4 && k !== st - 1); el.classList.toggle('on', k < 4 || st >= 5); });
        s.classList.toggle('avgc-all', st >= 5);
        if (st >= 5 && !s._counted) { s._counted = true; $$('.avgc-nums [data-count]', s).forEach(countUp); }
        if (st < 5) s._counted = false;
      },
      leave: function () { cancelAnimationFrame(raf); }
    };
  })();

  /* ---- Digital Design & Marketing: one stage per click ---- */
  hooks.ddm = (function () {
    var raf = 0;
    function counters(s) {
      var bs = $$('.v-dash .kpis b', s), t0 = performance.now();
      cancelAnimationFrame(raf);
      (function tick(t) {
        var k = Math.min(1, (t - t0) / (reduce ? 1 : 1600)), e = 1 - Math.pow(1 - k, 3);
        bs.forEach(function (b) { b.textContent = Math.round(+b.dataset.to * e).toLocaleString('en-IN'); });
        if (k < 1) raf = requestAnimationFrame(tick);
      })(t0);
    }
    return {
      step: function (s, st) {
        $$('.tech-list li', s).forEach(function (li, k) { li.classList.toggle('on', k === st); li.classList.toggle('done', k < st); });
        $$('.xp', s).forEach(function (x, k) { x.classList.toggle('on', k === st); });
        if (st === 2) counters(s);
      },
      leave: function () { cancelAnimationFrame(raf); }
    };
  })();

  /* ---- Pipeline film: YouTube player that loads once and pauses when you leave ---- */
  hooks.film = (function () {
    var loaded = false, ifr = null;
    function cmd(f) { try { ifr && ifr.contentWindow.postMessage(JSON.stringify({ event: 'command', func: f, args: [] }), '*'); } catch (e) {} }
    return {
      enter: function (s) {
        if (loaded) return; loaded = true;
        var box = s.querySelector('#filmFrame'), id = box.getAttribute('data-yt');
        ifr = document.createElement('iframe');
        ifr.src = 'https://www.youtube-nocookie.com/embed/' + id + '?rel=0&modestbranding=1&playsinline=1&enablejsapi=1';
        ifr.title = 'Pipeline film';
        ifr.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
        ifr.allowFullscreen = true;
        box.appendChild(ifr);
      },
      leave: function () { cmd('pauseVideo'); }
    };
  })();

  /* ---- 7 · the designed login types, signs in and loops (subtle) ---- */
  hooks.ux = (function () {
    var t = [], on = false;
    function q(id) { return document.getElementById(id); }
    function later(fn, ms) { t.push(setTimeout(fn, ms)); }
    function reset() {
      q('pxEmail').textContent = ''; q('pxPass').textContent = '';
      ['pxF1', 'pxF2'].forEach(function (id) { q(id).classList.remove('on', 'filled'); });
      q('pxCta').className = 'cta';
    }
    function run() {
      if (!on) return;
      reset();
      var email = 'aarav@ibmr.in', at = 700;
      later(function () { q('pxF1').classList.add('on'); }, at);
      for (var i = 1; i <= email.length; i++) (function (k) { later(function () { q('pxEmail').textContent = email.slice(0, k); }, at + 300 + k * 85); })(i);
      at += 300 + email.length * 85 + 500;
      later(function () { q('pxF1').classList.remove('on'); q('pxF1').classList.add('filled'); q('pxF2').classList.add('on'); }, at);
      for (var j = 1; j <= 10; j++) (function (k) { later(function () { q('pxPass').textContent = new Array(k + 1).join('•'); }, at + 250 + k * 70); })(j);
      at += 250 + 10 * 70 + 500;
      later(function () { q('pxF2').classList.remove('on'); q('pxF2').classList.add('filled'); q('pxCta').classList.add('press'); }, at);
      later(function () { q('pxCta').classList.remove('press'); q('pxCta').classList.add('load'); }, at + 180);
      later(function () { q('pxCta').classList.remove('load'); q('pxCta').classList.add('done'); }, at + 1300);
      later(run, at + 4200);
    }
    return {
      step: function (s, st) {
        if (st >= 1 && !on) { on = true; if (reduce) { q('pxEmail').textContent = 'aarav@ibmr.in'; q('pxPass').textContent = '••••••••••'; q('pxF1').classList.add('filled'); q('pxF2').classList.add('filled'); } else run(); }
        if (st < 1) { on = false; t.forEach(clearTimeout); t = []; reset(); }
      },
      leave: function () { on = false; t.forEach(clearTimeout); t = []; }
    };
  })();

  /* ---- Team slides: portraits "render" in; photo optional, initials fallback ---- */
  hooks.team = (function () {
    function initials(name) {
      var w = name.replace(/\[|\]/g, '').trim().split(/\s+/).filter(Boolean);
      return ((w[0] || '?')[0] + (w.length > 1 ? w[w.length - 1][0] : '')).toUpperCase();
    }
    function glowFrom(img, el) {
      try {
        var c = document.createElement('canvas'); c.width = c.height = 16;
        var x = c.getContext('2d'); x.drawImage(img, 0, 0, 16, 16);
        var d = x.getImageData(0, 0, 16, 16).data, r = 0, g = 0, b = 0, n = 0;
        for (var i = 0; i < d.length; i += 4) { var m = Math.max(d[i], d[i + 1], d[i + 2]); if (m < 40) continue; r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
        if (n) el.style.setProperty('--glow', Math.round(r / n) + ' ' + Math.round(g / n) + ' ' + Math.round(b / n));
      } catch (e) {}
    }
    $$('.slide.team').forEach(function (sl) {
      var people = $$('.person', sl), draft = false;
      var row = sl.querySelector('.team-row');
      people.forEach(function (p, i) {
        var top = p.classList.contains('top'), inRow = row && row.contains(p);
        var d = sl.querySelector('.team-duo') ? 0.2 + i * 0.7 : 0.4 + i * 0.55;
        p.style.setProperty('--d', d + 's');
        var name = (p.querySelector('.pname') || {}).textContent || '';
        if (/\[.*\]/.test(name)) draft = true;
        var ph = p.querySelector('.ph');
        var ticks = '';
        for (var k = 0; k < 24; k++) { var a = k / 24 * Math.PI * 2, r1 = 49, r2 = k % 6 ? 47.5 : 46; ticks += '<line class="tick" x1="' + (50 + Math.cos(a) * r1).toFixed(2) + '" y1="' + (50 + Math.sin(a) * r1).toFixed(2) + '" x2="' + (50 + Math.cos(a) * r2).toFixed(2) + '" y2="' + (50 + Math.sin(a) * r2).toFixed(2) + '"/>'; }
        ph.innerHTML = '<div class="disc"><div class="mono">' + initials(name) + '</div><div class="img"></div></div>' +
          '<svg class="gizmo" viewBox="0 0 100 100"><circle class="ring" cx="50" cy="50" r="45" pathLength="1"/>' + ticks +
          '<g class="orbit"><circle class="arc" cx="50" cy="50" r="45" pathLength="1"/><rect class="key" x="48" y="2.2" width="4" height="4" transform="rotate(45 50 4.2)"/></g></svg>';
        var src = p.getAttribute('data-photo');
        if (src) {
          var im = new Image();
          im.onload = function () { var el = ph.querySelector('.img'); el.style.backgroundImage = 'url("' + src + '")'; ph.querySelector('.mono').style.display = 'none'; glowFrom(im, ph); };
          im.src = src;
        }
      });
      var tag = sl.querySelector('.team-draft'); if (tag) tag.classList.toggle('show', draft);
    });
    var timers = [];
    return {
      enter: function (s) {
        timers.forEach(clearTimeout); timers = [];
        $$('.person', s).forEach(function (p) {
          p.classList.remove('done');
          var d = parseFloat(p.style.getPropertyValue('--d')) || 0;
          timers.push(setTimeout(function () { p.classList.add('done'); }, (d + 1.7) * 1000));
        });
      }
    };
  })();

  /* ---------- Admin mode: M → code 1111 → ✕ moves media to the Archive ---------- */
  function adminGate() {
    if (document.body.classList.contains('admin')) { adminBar(); return; }
    var g = $('#adminGate');
    g.classList.add('show');
    var inp = g.querySelector('input'); inp.value = ''; g.querySelector('.err').textContent = '';
    setTimeout(function () { inp.focus(); }, 30);
  }
  function adminOn(pin) {
    try { sessionStorage.setItem('deck-admin', pin); } catch (e) {}
    document.body.classList.add('admin'); adminBar();
  }
  function adminBar() {
    var b = $('#adminBar'), A = window.DeckAdmin;
    var list = A ? A.list() : [];
    b.querySelector('.n').textContent = list.length;
    b.querySelector('.where').textContent = A ? A.where() : '';
    b.querySelector('.arch').innerHTML = list.length ? list.map(function (p) {
      return '<li><span>' + p.replace(/^media\//, '') + '</span><button data-restore="' + p.replace(/"/g, '&quot;') + '">Restore</button></li>';
    }).join('') : '<li class="none">Nothing archived.</li>';
  }
  (function () {
    var g = $('#adminGate'), inp = g.querySelector('input');
    g.querySelector('form').addEventListener('submit', function (e) {
      e.preventDefault();
      if (window.DeckAdmin && window.DeckAdmin.checkPin(inp.value)) { g.classList.remove('show'); adminOn(inp.value); inp.blur(); }
      else { g.querySelector('.err').textContent = 'Wrong code.'; inp.select(); }
    });
    g.querySelector('.cancel').onclick = function () { g.classList.remove('show'); inp.blur(); };
    var b = $('#adminBar');
    b.querySelector('.toggle').onclick = function () { b.classList.toggle('open'); adminBar(); };
    b.querySelector('.exit').onclick = function () { document.body.classList.remove('admin'); b.classList.remove('open'); try { sessionStorage.removeItem('deck-admin'); } catch (e) {} };
    b.addEventListener('click', function (e) {
      var r = e.target.closest('[data-restore]'); if (!r) return;
      window.DeckAdmin.restore(r.getAttribute('data-restore')).then(function () { location.reload(); });
    });
    // ✕ on any archived-able media
    stage.addEventListener('click', function (e) {
      var x = e.target.closest('.adm-x'); if (!x || !document.body.classList.contains('admin')) return;
      e.stopPropagation();
      var holder = x.closest('[data-path]');
      if (x.closest('.vtile')) holder = x.closest('.vtile').querySelector('.vm.on');
      if (!holder) return;
      var path = holder.getAttribute('data-path');
      window.DeckAdmin.hide(path).then(function () {
        if (x.closest('#wall')) hooks.wall.remove(path);
        else { holder.remove(); }
        adminBar();
      });
    }, true);
    try { var pin = sessionStorage.getItem('deck-admin'); if (pin && window.DeckAdmin && window.DeckAdmin.checkPin(pin)) adminOn(pin); } catch (e) {}
  })();

  /* ---------- Code Lab hooks (assets/lab.js) ---------- */
  if (window.LAB_HOOKS) Object.keys(window.LAB_HOOKS).forEach(function (k) { hooks[k] = window.LAB_HOOKS[k]; });

  /* ---------- start ---------- */
  (function () {
    // Fresh open (new tab, another PC, a bookmark) always starts at slide 1 with every demo reset.
    // A refresh (F5) in the same tab resumes where you were. ?at=12 or ?at=12.2 jumps (for testing).
    var m = (location.search.match(/[?&]at=(\d+)(?:\.(\d+))?/) || null), saved = null;
    try { saved = JSON.parse(sessionStorage.getItem('deck-pos') || 'null'); } catch (e) {}
    if (m) { cur = +m[1] - 1; step = +(m[2] || 0); }
    else if (saved && performance.getEntriesByType && (performance.getEntriesByType('navigation')[0] || {}).type === 'reload') { cur = saved[0]; step = saved[1]; }
    cur = Math.max(0, Math.min(N - 1, cur)); step = Math.min(maxStep(cur), step);
    try { history.replaceState(null, '', location.pathname); } catch (e) {}
    render();
  })();
})();
