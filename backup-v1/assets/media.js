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

  function prettify(name) {
    var t = name.replace(/\.[^.]+$/, '').replace(/^\d+[\s._-]*/, '').replace(/[_-]+/g, ' ').trim();
    return t ? t.charAt(0).toUpperCase() + t.slice(1) : '';
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
      if (VIDEO.test(n)) out.push({ kind: 'video', src: folder + '/' + encodeURIComponent(n), title: prettify(n), sort: n });
      else if (IMAGE.test(n)) out.push({ kind: 'image', src: folder + '/' + encodeURIComponent(n), title: prettify(n), sort: n });
    });
    if (names.indexOf('youtube.txt') !== -1) {
      try {
        var t = await (await fetch(folder + '/youtube.txt', { cache: 'no-store' })).text();
        t.split(/\r?\n/).forEach(function (line) {
          var parts = line.split('|');
          if (parts.length < 2) return;
          var id = ytId(parts[1].trim());
          if (!id) return;
          var label = parts[0].trim();
          out.push({ kind: 'youtube', id: id, src: 'https://www.youtube.com/embed/' + id, thumb: 'https://i.ytimg.com/vi/' + id + '/hqdefault.jpg', title: prettify(label), sort: label });
        });
      } catch (e) {}
    }
    return out.sort(natural);
  }

  window.DeckMedia = { list: list };
})();
