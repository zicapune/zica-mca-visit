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
    k.className = 'tl-key'; k.style.left = x + '%'; k.title = s.dataset.title || '';
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
        if (done) { draw(total); cubes.forEach(function (c) { c.classList.add('in'); }); return; }
        var n = 0; draw(0); clearInterval(timer);
        setTimeout(function () {
          timer = setInterval(function () { n += 2; if (n >= total) finish(); else draw(n); }, reduce ? 1 : 28);
        }, 500);
      },
      step: function (s, st) { if (st >= 1 && !done) finish(); },
      leave: function () { clearInterval(timer); }
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
      var inner = it.kind === 'video' ? '<video src="' + it.src + '" muted loop playsinline preload="metadata"></video>'
        : it.kind === 'youtube' ? '<img src="' + it.thumb + '" alt="" decoding="async">' : '<img src="' + it.src + '" alt="" decoding="async" loading="lazy">';
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
        if (v) { if (i === at && slides[cur] === el.closest('.slide')) { var pr = v.play(); if (pr && pr.catch) pr.catch(function () {}); } else v.pause(); }
      });
      track.style.transition = instant ? 'none' : '';
      track.style.transform = 'translateX(' + (el.offsetWidth / 2 - centre) + 'px)';
      $$('.car-dots i', el).forEach(function (d, i) { d.classList.toggle('on', i === at); });
      var sec = items[at] && items[at].section;
      $$('.car-secs button', el).forEach(function (b) { b.classList.toggle('on', b.dataset.sec === sec); });
    }
    function go(d) { at += d; layout(); restart(); }
    function restart() { clearInterval(timer); timer = setInterval(function () { if (slides[cur] === el.closest('.slide')) { at++; layout(); } }, 6000); }
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
        sizeTile(t);
        t.addEventListener('click', function (e) {
          if (e.target.closest('.adm-x')) return;
          if (i !== at) { at = i; layout(); restart(); return; }
          var v = t.querySelector('video'); if (v) { v.muted = !v.muted; }
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
      track.addEventListener('pointerdown', function (e) { x0 = e.clientX; });
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
      leave: function () { clearInterval(timer); $$('#wall video').forEach(function (v) { v.pause(); }); },
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
        svg.getBoundingClientRect();
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
    var raf = 0, cvs = [], t0 = 0;
    function A(c, w, h, t) {
      c.fillStyle = '#0c0d12'; c.fillRect(0, 0, w, h);
      c.strokeStyle = '#2b2f42'; c.beginPath(); c.moveTo(20, 250); c.lineTo(w - 20, 250); c.stroke();
      var per = 2.6, trail = 14;
      for (var k = trail; k >= 0; k--) {
        var tt = t - k * 0.035, ph = ((tt % per) + per) % per / per, x = 40 + ph * (w - 80);
        var b = Math.abs(Math.sin(ph * Math.PI * 3)), y = 250 - 22 - b * 150;
        var contact = Math.max(0, 1 - b * 6), sy = 1 - .38 * contact + .18 * (1 - contact) * (1 - b), sx = 1 / sy;
        c.save(); c.translate(x, y + 22 * (1 - sy)); c.scale(sx, sy);
        c.beginPath(); c.arc(0, 0, 22, 0, 7);
        c.fillStyle = k ? 'rgba(255,181,71,' + (0.18 * (1 - k / trail)) + ')' : '#ffb547'; c.fill(); c.restore();
      }
      c.fillStyle = '#5f6579'; c.font = '500 15px "JetBrains Mono", monospace'; c.fillText('f ' + String(Math.floor(t * 24) % 1000).padStart(3, '0'), 18, 28);
    }
    function person(c, x, y, col) {
      c.fillStyle = col; c.beginPath(); c.arc(x, y - 92, 16, 0, 7); c.fill();
      c.beginPath(); c.moveTo(x - 30, y); c.quadraticCurveTo(x - 32, y - 70, x, y - 72); c.quadraticCurveTo(x + 32, y - 70, x + 30, y); c.fill();
    }
    function V(c, w, h, t) {
      var wx = w / 2 + Math.sin(t * 1.1) * (w * .36);
      // plate (green screen)
      c.fillStyle = '#1fa356'; c.fillRect(0, 0, w, h);
      c.fillStyle = '#178a47'; c.fillRect(0, 230, w, 70);
      person(c, w / 2, 262, '#14151c');
      // comp, right of the wipe
      c.save(); c.beginPath(); c.rect(wx, 0, w - wx, h); c.clip();
      var g = c.createLinearGradient(0, 0, 0, h); g.addColorStop(0, '#1b1446'); g.addColorStop(.6, '#ff7a1a'); g.addColorStop(1, '#ffb547');
      c.fillStyle = g; c.fillRect(0, 0, w, h);
      c.fillStyle = '#ffe2a8'; c.beginPath(); c.arc(w * .7, 150, 34, 0, 7); c.fill();
      c.fillStyle = '#0d0e13';
      [[10, 170, 40], [55, 130, 34], [95, 185, 30], [130, 110, 38], [175, 160, 30], [210, 125, 44], [262, 175, 34], [300, 140, 40]].forEach(function (b) { c.fillRect(b[0], b[1], b[2], 300 - b[1]); });
      c.fillStyle = 'rgba(255,220,150,.75)';
      for (var i = 0; i < 40; i++) { var bx = (i * 53) % 330 + 14, by = 150 + (i * 37) % 120; c.fillRect(bx, by, 3, 4); }
      person(c, w / 2, 262, '#08090c');
      c.restore();
      c.fillStyle = '#fff'; c.fillRect(wx - 1.5, 0, 3, h);
      c.beginPath(); c.arc(wx, h / 2, 10, 0, 7); c.fill();
      c.font = '600 14px "JetBrains Mono", monospace'; c.fillStyle = 'rgba(255,255,255,.85)'; c.fillText('plate', 14, 24); c.textAlign = 'right'; c.fillText('final comp', w - 14, 24); c.textAlign = 'left';
    }
    function G(c, w, h, t) {
      c.fillStyle = '#0c0d12'; c.fillRect(0, 0, w, h);
      for (var i = 0; i < 26; i++) { var sx = ((i * 97 - t * (20 + (i % 3) * 18)) % w + w) % w; c.fillStyle = 'rgba(141,147,168,' + (.2 + (i % 3) * .15) + ')'; c.fillRect(sx, (i * 41) % 200 + 10, 2, 2); }
      c.fillStyle = '#2b2f42'; c.fillRect(0, 240, w, 2);
      var speed = 170, gap = 210, px = 90;
      var off = (t * speed) % gap, nearest = 1e9;
      for (var k = 0; k < 3; k++) {
        var ox = w + 20 - off - k * gap + gap; if (ox < -30 || ox > w + 30) continue;
        c.fillStyle = '#ff7a1a'; c.fillRect(ox, 212, 22, 28);
        var d = ox - px; if (d > -30 && d < nearest) nearest = d;
      }
      // jump arc timed to the nearest obstacle
      var jt = 1 - Math.min(1, Math.max(0, (nearest + 40) / 110));
      var jy = nearest < 70 && nearest > -40 ? Math.sin(Math.min(1, (70 - nearest) / 110) * Math.PI) * 78 : 0;
      c.fillStyle = '#5ce1e6'; c.fillRect(px - 14, 212 - jy, 28, 28);
      c.fillStyle = '#0c0d12'; c.fillRect(px + 2, 218 - jy, 5, 5);
      c.fillStyle = '#ffb547'; c.font = '700 16px "JetBrains Mono", monospace'; c.fillText('SCORE ' + String(Math.floor(t * 10)).padStart(5, '0'), 18, 28);
    }
    function C(c, w, h, t) {
      c.fillStyle = '#f4ead5'; c.fillRect(0, 0, w, h);
      for (var y = 0; y < h; y += 12) for (var x = 0; x < w; x += 12) {
        var d = Math.hypot(x - w * .3, y - h * .75) / 300, r = Math.max(0, 4.2 - d * 4.2);
        c.fillStyle = 'rgba(255,122,26,.55)'; c.beginPath(); c.arc(x + (y / 12 % 2) * 6, y, r, 0, 7); c.fill();
      }
      c.strokeStyle = '#111'; c.lineWidth = 5; c.strokeRect(10, 10, w - 20, h - 20);
      var s = 1 + .12 * Math.sin(t * 6);
      c.save(); c.translate(w * .62, h * .42); c.scale(s, s); c.rotate(-.08);
      c.fillStyle = '#fff'; c.beginPath();
      for (var i = 0; i < 22; i++) { var a = i / 22 * Math.PI * 2, rr = i % 2 ? 62 : 86; c.lineTo(Math.cos(a) * rr * 1.25, Math.sin(a) * rr * .8); }
      c.closePath(); c.fill(); c.lineWidth = 3; c.stroke();
      c.fillStyle = '#e8322b'; c.font = '900 44px "Bricolage Grotesque", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('POW!', 0, 2);
      c.restore(); c.textAlign = 'left'; c.textBaseline = 'alphabetic';
      var txt = 'Meanwhile, in Pune…', n = Math.floor((t * 9) % (txt.length + 12));
      c.fillStyle = '#ffe14d'; c.fillRect(18, 18, 210, 34); c.strokeStyle = '#111'; c.lineWidth = 2; c.strokeRect(18, 18, 210, 34);
      c.fillStyle = '#111'; c.font = '700 17px "Bricolage Grotesque", sans-serif'; c.fillText(txt.slice(0, n), 28, 41);
    }
    function X(c, w, h, t) {
      c.fillStyle = '#0c0d12'; c.fillRect(0, 0, w, h);
      var cx = w / 2, cy = h / 2 - 10, f = 340;
      function P(x, y, z) { var ca = Math.cos(t * .7), sa = Math.sin(t * .7), cb = Math.cos(.5), sb = Math.sin(.5); var x1 = x * ca - z * sa, z1 = x * sa + z * ca; var y1 = y * cb - z1 * sb, z2 = y * sb + z1 * cb + 4; return [cx + x1 * f / (z2 * 1.5), cy + y1 * f / (z2 * 1.5)]; }
      c.strokeStyle = 'rgba(92,225,230,.25)'; c.lineWidth = 1;
      for (var i = -4; i <= 4; i++) { var a = P(i * .5, 1.1, -2), b = P(i * .5, 1.1, 2); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); a = P(-2, 1.1, i * .5); b = P(2, 1.1, i * .5); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); }
      var V3 = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]].map(function (v) { return P(v[0] * .7, v[1] * .7 - .2, v[2] * .7); });
      c.strokeStyle = '#5ce1e6'; c.lineWidth = 2;
      [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]].forEach(function (e) { c.beginPath(); c.moveTo(V3[e[0]][0], V3[e[0]][1]); c.lineTo(V3[e[1]][0], V3[e[1]][1]); c.stroke(); });
      c.fillStyle = '#ffb547'; V3.forEach(function (p) { c.fillRect(p[0] - 3, p[1] - 3, 6, 6); });
    }
    var FN = [A, V, G, C, X];
    function frame(now) {
      var t = (now - t0) / 1000;
      cvs.forEach(function (cv, i) { if (!cv.offsetParent && i === 4 && !cv.closest('.on')) {} var c = cv.getContext('2d'); FN[i](c, cv.width, cv.height, reduce ? 1.3 : t); });
      raf = requestAnimationFrame(frame);
    }
    return {
      enter: function (s) { cvs = $$('.av canvas', s); t0 = performance.now(); cancelAnimationFrame(raf); raf = requestAnimationFrame(frame); },
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
