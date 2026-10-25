/* =====================================================================
   deck.js — slide engine for the ZICA × ASM IBMR deck
   ===================================================================== */
(function () {
  'use strict';
  var CFG = window.DECK_CONFIG || {};
  var stage = document.getElementById('stage');
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
    try { history.replaceState(null, '', '#' + (cur + 1) + (step ? '.' + step : '')); } catch (e) {}
    broadcast();
  }

  function next() {
    if (step < maxStep(cur)) { step++; render(); }
    else if (cur < N - 1) { cur++; step = 0; render(); }
  }
  function prev() {
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
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key;
    if (k === 'ArrowRight' || k === 'PageDown' || k === ' ' || k === 'ArrowDown' || (k === 'Enter' && !numBuf)) { e.preventDefault(); next(); }
    else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'ArrowUp' || k === 'Backspace') { e.preventDefault(); prev(); }
    else if (k === 'Home') go(0);
    else if (k === 'End') go(N - 1);
    else if (/^[0-9]$/.test(k)) { numBuf += k; clearTimeout(numBuf.t); }
    else if (k === 'Enter' && numBuf) { go(parseInt(numBuf, 10) - 1); numBuf = ''; }
    else if (k === 'f' || k === 'F') toggleFS();
    else if (k === 't' || k === 'T') tl.classList.toggle('hidden');
    else if (k === 'p' || k === 'P') openPresenter();
    else if (k === 'b' || k === 'B' || k === '.') stage.style.opacity = stage.style.opacity === '0' ? '1' : '0';
    else if (k === '?' || k === 'h' || k === 'H') $('#help').classList.toggle('show');
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
      el.textContent = Math.round(from + (to - from) * e);
      if (p < 1) requestAnimationFrame(tick);
    })(t0);
  }

  /* =====================================================================
     Slide hooks
     ===================================================================== */
  var hooks = {};
  function onEnter(i) {
    var s = slides[i];
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
          html += '<div class="plan' + (c.highlight ? ' hi' : '') + '" data-step="' + (i + 1) + '">' +
            (c.highlight ? '<div class="pill">Best for MCA</div>' : '') +
            '<div class="pn">' + c.name + '</div>' +
            '<div class="dur"><b>' + c.months + '</b><span>months</span></div>' +
            '<div class="tg">' + (c.tagline || '') + '</div><ul>';
          used.forEach(function (sw) {
            var has = c.software.indexOf(sw) !== -1;
            html += '<li class="' + (has ? 'y' : 'x') + '">' + (has ? ICON_Y : ICON_X) + sw + '</li>';
          });
          html += '</ul></div>';
        });
        $('#plans').innerHTML = html;
        render(); // pick up the new data-step elements
      }
    };
  })();

  /* ---- 9 · UI/UX spotlight ---- */
  hooks.uiux = (function () {
    var built = false;
    return {
      enter: function () {
        if (built) return; built = true;
        var c = (CFG.COURSES || []).filter(function (x) { return x.highlight; })[0];
        if (c) $('#uiuxTools').innerHTML = c.software.map(function (s) { return '<span class="tool">' + s + '</span>'; }).join('');
        $('#ships').innerHTML = (CFG.UIUX_SHIPS || []).map(function (s, i) { return '<li data-step="' + (i + 1) + '">' + ICON_Y + s + '</li>'; }).join('');
        render();
      }
    };
  })();

  /* ---- 12 · side-hustle calculator ---- */
  hooks.calc = (function () {
    var init = false;
    function inr(n) { return '₹' + Math.round(n).toLocaleString('en-IN'); }
    function lakh(n) { return n >= 100000 ? '₹' + (n / 100000).toFixed(1).replace(/\.0$/, '') + ' lakh a year' : inr(n) + ' a year'; }
    function upd() {
      var h = +$('#hours').value, r = +$('#rate').value, m = h * r * 4.33;
      $('#hVal').textContent = h;
      $('#rVal').textContent = inr(r);
      $('#mVal').textContent = inr(Math.round(m / 100) * 100);
      $('#yVal').textContent = lakh(m * 12);
    }
    return {
      enter: function () {
        if (init) return; init = true;
        var C = CFG.CALC || {};
        var h = $('#hours'), r = $('#rate');
        h.min = 2; h.max = C.hoursMax || 30; h.step = 1; h.value = C.hours || 10;
        r.min = C.rateMin || 800; r.max = C.rateMax || 4000; r.step = 100; r.value = C.rate || 1200;
        h.addEventListener('input', upd); r.addEventListener('input', upd);
        upd();
      }
    };
  })();

  /* ---- 15 · student wall ---- */
  hooks.wall = (function () {
    var loaded = false;
    return {
      enter: function () {
        if (loaded || !window.DeckMedia) return; loaded = true;
        var el = $('#wall');
        window.DeckMedia.list('media/reel').then(function (items) {
          if (!items.length) {
            el.innerHTML = '<div class="wall-empty"><div class="h3">Student work drops in here.</div><div class="body">Upload files to <code>media/reel/</code> named <code>01-title.mp4</code>, <code>02-title.jpg</code>…</div></div>';
            return;
          }
          el.className = 'wall';
          el.innerHTML = items.slice(0, 7).map(function (it) {
            var inner = it.kind === 'video' ? '<video src="' + it.src + '" muted loop playsinline preload="metadata" data-autoplay="1"></video>'
              : it.kind === 'youtube' ? '<img src="' + it.thumb + '" alt="">' : '<img src="' + it.src + '" alt="">';
            return '<div class="tile">' + inner + (it.title ? '<div class="cap">' + it.title + '</div>' : '') + '</div>';
          }).join('');
          syncVideos();
        });
      }
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
        var s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
        s.onload = function () { new window.QRCode(box, { text: CFG.QUEST_URL, width: 440, height: 440, colorDark: '#0d0e13', colorLight: '#eceef4', correctLevel: window.QRCode.CorrectLevel.M }); };
        s.onerror = function () { box.innerHTML = '<div class="qr-ph"><b>' + CFG.QUEST_URL.replace(/^https?:\/\//, '') + '</b><span>QR library could not load. Share the link instead.</span></div>'; };
        document.head.appendChild(s);
      }
    };
  })();

  /* ---------- start ---------- */
  (function () {
    var m = (location.hash || '').match(/^#(\d+)(?:\.(\d+))?/);
    if (m) { cur = Math.max(0, Math.min(N - 1, +m[1] - 1)); step = Math.min(maxStep(cur), +(m[2] || 0)); }
    render();
  })();
})();
