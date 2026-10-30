/* =====================================================================
   media.js — lists the files in a repo folder (e.g. media/reel) so the
   wall and reel pages fill themselves. Reads the GitHub API for the live
   site; falls back to <folder>/manifest.json when opened offline.
   Also merges <folder>/youtube.txt  →  lines like:
       07 Robot short film | https://youtu.be/XXXXXXXXXXX
   ===================================================================== */
(function () {
  'use strict';
  var VIDEO = /\.(mp4|webm|m4v|mov)$/i;
  var IMAGE = /\.(jpe?g|png|webp|gif|avif)$/i;

  function natural(a, b) { return a.sort.localeCompare(b.sort, undefined, { numeric: true, sensitivity: 'base' }); }

  var ACR = { ai: 'AI', ui: 'UI', ux: 'UX', vfx: 'VFX', '3d': '3D', '2d': '2D', xr: 'XR', ar: 'AR', vr: 'VR', cgi: 'CGI' };
  function acr(t) { return t.replace(/\b(ai|ui|ux|vfx|3d|2d|xr|ar|vr|cgi)\b/gi, function (w) { return ACR[w.toLowerCase()]; }); }
  function cap(t) { return t ? acr(t.charAt(0).toUpperCase() + t.slice(1)) : ''; }
  function prettify(name) {
    var base = name.replace(/\.[^.]+$/, '').replace(/^\d+[\s._-]*/, '').split('--')[0];
    return cap(base.replace(/[_-]+/g, ' ').trim());
  }
  function credit(name) {
    var m = name.replace(/\.[^.]+$/, '').split('--')[1];
    if (!m) return '';
    if (/^faculty$/i.test(m)) return 'Faculty work';
    return m.split(/[-_]+/).map(function (w, i) { return i === 0 && /^by$/i.test(w) ? 'by' : cap(w); }).join(' ');
  }

  function ytId(url) {
    var m = String(url).match(/(?:youtu\.be\/|v=|shorts\/|embed\/)([\w-]{11})/);
    return m ? m[1] : '';
  }

  function cacheGet(k) {
    try { var v = JSON.parse(sessionStorage.getItem(k) || 'null'); if (v && Date.now() - v.t < 120000) return v.d; } catch (e) {}
    return null;
  }
  function cacheSet(k, d) { try { sessionStorage.setItem(k, JSON.stringify({ t: Date.now(), d: d })); } catch (e) {} }

  async function listNames(folder) {
    var cfg = window.DECK_CONFIG || {};
    var key = 'media:' + folder;
    var hit = cacheGet(key);
    if (hit) return hit;
    var names = [];
    var onGitHub = /github\.io$/.test(location.hostname);
    if (onGitHub && cfg.REPO) {
      try {
        var r = await fetch('https://api.github.com/repos/' + cfg.REPO + '/contents/' + folder + '?ref=' + (cfg.BRANCH || 'main'), { headers: { Accept: 'application/vnd.github+json' } });
        if (r.ok) names = (await r.json()).filter(function (f) { return f.type === 'file'; }).map(function (f) { return f.name; });
      } catch (e) {}
    }
    if (!names.length) {
      try { var m = await fetch(folder + '/manifest.json', { cache: 'no-store' }); if (m.ok) names = await m.json(); } catch (e) {}
    }
    if (names.length) cacheSet(key, names);
    return names;
  }

  async function list(folder) {
    var names = await listNames(folder);
    var out = [];
    names.forEach(function (n) {
      if (VIDEO.test(n)) out.push({ kind: 'video', path: folder + '/' + n, src: folder + '/' + encodeURIComponent(n), title: prettify(n), by: credit(n), sort: n });
      else if (IMAGE.test(n)) out.push({ kind: 'image', path: folder + '/' + n, src: folder + '/' + encodeURIComponent(n), title: prettify(n), by: credit(n), sort: n });
    });
    if (names.indexOf('captions.json') !== -1) {
      try {
        var cap = await (await fetch(folder + '/captions.json', { cache: 'no-store' })).json();
        out.forEach(function (it) { var k = it.path.split('/').pop(), c = cap[k]; if (c) { if (c.title) it.title = c.title; if ('by' in c) it.by = c.by; } });
      } catch (e) {}
    }
    if (names.indexOf('youtube.txt') !== -1) {
      try {
        var t = await (await fetch(folder + '/youtube.txt', { cache: 'no-store' })).text();
        t.split(/\r?\n/).forEach(function (line) {
          var parts = line.split('|');
          if (parts.length < 2) return;
          var id = ytId(parts[1].trim());
          if (!id) return;
          var label = parts[0].trim();
          out.push({ kind: 'youtube', path: folder + '/youtube:' + id, id: id, src: 'https://www.youtube.com/embed/' + id, thumb: 'https://i.ytimg.com/vi/' + id + '/hqdefault.jpg', title: prettify(label), sort: label });
        });
      } catch (e) {}
    }
    await DeckAdmin.ready;
    return out.filter(function (it) { return !DeckAdmin.isHidden(it.path); }).sort(natural);
  }

  /* ---------------------------------------------------------------
     Admin archive: hidden media is never deleted, only listed here.
     Stored in Supabase table deck_hidden when it exists (same list on
     every PC), otherwise in this browser.
     --------------------------------------------------------------- */
  var DeckAdmin = (function () {
    var cfg = (window.DECK_CONFIG || {}).ADMIN || {};
    var LS = 'deck-hidden', hidden = new Set(), remote = false;
    function lsLoad() { try { (JSON.parse(localStorage.getItem(LS) || '[]')).forEach(function (p) { hidden.add(p); }); } catch (e) {} }
    function lsSave() { try { localStorage.setItem(LS, JSON.stringify(Array.from(hidden))); } catch (e) {} }
    function api(path, opts) {
      opts = opts || {};
      opts.headers = Object.assign({ apikey: cfg.SUPABASE_KEY, authorization: 'Bearer ' + cfg.SUPABASE_KEY, 'content-type': 'application/json' }, opts.headers || {});
      return fetch(cfg.SUPABASE_URL.replace(/\/+$/, '') + path, opts);
    }
    var ready = (async function () {
      if (cfg.SUPABASE_URL && cfg.SUPABASE_KEY) {
        try {
          var r = await api('/rest/v1/deck_hidden?select=path');
          if (r.ok) { (await r.json()).forEach(function (x) { hidden.add(x.path); }); remote = true; return; }
        } catch (e) {}
      }
      lsLoad();
    })();
    async function set(path, hide) {
      if (hide) hidden.add(path); else hidden.delete(path);
      if (remote) {
        try {
          var r = await api('/rest/v1/rpc/deck_set_hidden', { method: 'POST', body: JSON.stringify({ p_pin: sessionStorage.getItem('deck-admin') || '', p_path: path, p_hidden: hide }) });
          if (r.ok) return true;
        } catch (e) {}
      }
      lsSave();
      return true;
    }
    return {
      ready: ready,
      isHidden: function (p) { return hidden.has(p); },
      list: function () { return Array.from(hidden).sort(); },
      hide: function (p) { return set(p, true); },
      restore: function (p) { return set(p, false); },
      where: function () { return remote ? 'Supabase (every PC)' : 'this browser only'; },
      checkPin: function (pin) { return pin === String(cfg.PIN || '1111'); },
      movedTo: function (p) { try { return (JSON.parse(localStorage.getItem('deck-moves') || '{}'))[p] || ''; } catch (e) { return ''; } },
      move: function (p, section) { try { var m = JSON.parse(localStorage.getItem('deck-moves') || '{}'); if (section) m[p] = section; else delete m[p]; localStorage.setItem('deck-moves', JSON.stringify(m)); } catch (e) {} }
    };
  })();
  window.DeckAdmin = DeckAdmin;

  /* All gallery sections in order; admin "move" overrides decide the section shown. */
  async function gallery() {
    var secs = (window.DECK_CONFIG || {}).GALLERY || [{ dir: 'media/reel', name: 'Student work' }];
    var lists = await Promise.all(secs.map(function (g) { return list(g.dir); }));
    var bySec = secs.map(function () { return []; });
    lists.forEach(function (l, i) { l.forEach(function (it) {
      var to = DeckAdmin.movedTo(it.path), k = i;
      if (to) { var j = secs.findIndex(function (g) { return g.name === to; }); if (j >= 0) k = j; }
      it.section = secs[k].name; bySec[k].push(it);
    }); });
    var out = []; bySec.forEach(function (l) { out = out.concat(l); });
    return { sections: secs.map(function (g) { return g.name; }), items: out };
  }

  window.DeckMedia = { list: list, gallery: gallery };
})();
