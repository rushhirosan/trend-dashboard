/**
 * 号外帯: /api/dashboard/edition-strip から版ラベル・注目3件を描画
 */
(function () {
  'use strict';

  var ENDPOINT = '/api/dashboard/edition-strip';

  function qs(root, sel) {
    return root.querySelector(sel);
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function formatNext(iso, locale) {
    if (!iso) return '';
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return '';
      var t = d.toLocaleTimeString(locale === 'en' ? 'en-US' : 'ja-JP', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'Asia/Tokyo'
      });
      return locale === 'en' ? 'Next ' + t : '次 ' + t;
    } catch (e) {
      return '';
    }
  }

  function kindLabel(kind, locale) {
    if (locale === 'en') {
      if (kind === 'new') return 'NEW';
      if (kind === 'rising') return 'Rising';
      return '';
    }
    if (kind === 'new') return 'NEW';
    if (kind === 'rising') return '急上昇';
    return '';
  }

  function movementText(h, locale) {
    if (h.kind === 'rising' && h.rank_from != null && h.rank_to != null) {
      return String(h.rank_from) + '→' + String(h.rank_to);
    }
    if (h.kind === 'new' && h.rank_to != null) {
      return locale === 'en' ? '#' + h.rank_to : h.rank_to + '位';
    }
    return '';
  }

  function scrollToSource(dataSource) {
    if (!dataSource) return;
    var el =
      document.querySelector('.all-freshness[data-source="' + dataSource + '"]') ||
      document.querySelector('[data-source="' + dataSource + '"]') ||
      document.getElementById(dataSource + '-trends') ||
      document.getElementById(dataSource);
    if (!el) return;
    try {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      el.scrollIntoView(true);
    }
  }

  function renderHighlight(h, locale) {
    var kind = kindLabel(h.kind, locale);
    var move = movementText(h, locale);
    var parts = [];
    if (kind) {
      parts.push('<span class="edition-strip__kind edition-strip__kind--' + esc(h.kind) + '">' + esc(kind) + '</span>');
    }
    if (h.source) {
      parts.push('<span class="edition-strip__src">' + esc(h.source) + '</span>');
    }
    parts.push('<span class="edition-strip__label">' + esc(h.label || '') + '</span>');
    if (move) {
      parts.push('<span class="edition-strip__move text-muted">' + esc(move) + '</span>');
    }
    var li = document.createElement('li');
    li.className = 'edition-strip__item';
    if (h.data_source) {
      li.setAttribute('data-source', h.data_source);
      li.tabIndex = 0;
      li.setAttribute('role', 'button');
      li.addEventListener('click', function () {
        scrollToSource(h.data_source);
      });
      li.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          scrollToSource(h.data_source);
        }
      });
    }
    li.innerHTML = parts.join(' ');
    return li;
  }

  function applyPayload(root, data) {
    var locale = root.getAttribute('data-locale') || 'ja';
    var editionEl = qs(root, '[data-edition-label]');
    var justEl = qs(root, '[data-just-refreshed]');
    var nextEl = qs(root, '[data-next-refresh]');
    var listEl = qs(root, '[data-highlights]');
    var emptyEl = qs(root, '[data-empty]');

    if (editionEl) {
      editionEl.textContent = data.edition_label || '—';
    }
    if (justEl) {
      if (data.just_refreshed) {
        justEl.classList.remove('d-none');
      } else {
        justEl.classList.add('d-none');
      }
    }
    if (nextEl) {
      nextEl.textContent = formatNext(data.next_refresh_at, locale);
    }

    var highlights = Array.isArray(data.highlights) ? data.highlights : [];
    if (listEl) {
      listEl.innerHTML = '';
      highlights.slice(0, 3).forEach(function (h) {
        listEl.appendChild(renderHighlight(h, locale));
      });
    }
    if (emptyEl) {
      if (highlights.length === 0) {
        if (data.has_snapshot === false) {
          emptyEl.textContent =
            locale === 'en'
              ? 'Highlights appear once this edition’s snapshot is ready.'
              : 'この版のスナップショット取得後に注目差分を表示します。';
        } else {
          emptyEl.textContent =
            locale === 'en'
              ? 'No standout moves vs the previous edition.'
              : '前の版と比べて大きな動きは見当たりません。';
        }
        emptyEl.classList.remove('d-none');
      } else {
        emptyEl.classList.add('d-none');
      }
    }

    root.removeAttribute('hidden');
    root.classList.add('edition-strip--ready');
  }

  function init() {
    var root = document.getElementById('edition-strip');
    if (!root) return;
    var region = root.getAttribute('data-region') || 'jp';
    var locale = root.getAttribute('data-locale') || 'ja';
    var url = ENDPOINT + '?region=' + encodeURIComponent(region) + '&locale=' + encodeURIComponent(locale);

    fetch(url)
      .then(function (res) {
        return res.json();
      })
      .then(function (body) {
        if (!body || !body.success || !body.data) {
          root.removeAttribute('hidden');
          return;
        }
        applyPayload(root, body.data);
      })
      .catch(function (err) {
        console.warn('edition-strip: fetch failed', err);
        root.removeAttribute('hidden');
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
