/**
 * 政府調達 Public Sector Signals（直近30日×AI/DX/サイバー件数＋都道府県ランキング）
 * ヘッダー・全部入り用のコンパクト表示（高さ抑えめ）
 */
(function () {
    'use strict';

    function escapeHtml(s) {
        if (s == null) return '';
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    var RANKING_LABELS = { ai: 'AI案件', dx: 'DX案件', cyber: 'サイバー案件' };

    function renderCompactBody(data) {
        if (!data) return '';
        if (data.api_unreachable) {
            return '<div class="mt-0 text-warning">政府調達APIに接続できません（タイムアウト）。しばらく後にお試しください。</div>';
        }
        var signals = data.signals || [];
        var rankings = data.prefecture_rankings || {};
        var parts = [];
        signals.forEach(function (s) {
            parts.push(escapeHtml(s.label) + ' <strong>' + (s.count != null ? s.count : '—') + '</strong>件');
        });
        var line1 = parts.length ? parts.join('　') : '—';
        var lines = ['<div class="mt-0">' + line1 + '</div>'];
        ['ai', 'dx', 'cyber'].forEach(function (key) {
            var ranking = rankings[key] || data.prefecture_ranking || [];
            if (key === 'dx' && !rankings[key] && data.prefecture_ranking) ranking = data.prefecture_ranking;
            var rankParts = ranking.slice(0, 5).map(function (r) {
                return r.rank + '.' + escapeHtml((r.name || '').replace(/(県|府|都)$/, ''));
            });
            var line2 = rankParts.length ? rankParts.join(' ') : '—';
            lines.push('<div class="mt-0 text-muted">県別 ' + (RANKING_LABELS[key] || key) + ' Top5: ' + line2 + '</div>');
        });
        return lines.join('');
    }

    function renderAdminTabBody(data) {
        if (!data) return '';
        if (data.api_unreachable) {
            return '<p class="text-warning mb-0">政府調達APIに接続できません（タイムアウト）。しばらく後にお試しください。</p>';
        }
        var signals = data.signals || [];
        var rankings = data.prefecture_rankings || {};
        var asOf = data.as_of || '';
        var parts = [];
        parts.push('<div class="row g-3">');
        parts.push('<div class="col-12 col-md-6"><h4 class="h6 text-secondary mb-2">キーワード別件数（直近30日）</h4><ul class="list-unstyled mb-0">');
        signals.forEach(function (s) {
            parts.push('<li class="d-flex justify-content-between py-1 border-bottom border-light"><span>' + escapeHtml(s.label) + '</span><span><strong>' + (s.count != null ? s.count : '—') + '</strong>件</span></li>');
        });
        parts.push('</ul></div>');
        parts.push('<div class="col-12 col-md-6"><h4 class="h6 text-secondary mb-2">県別 案件 Top5（AI / DX / サイバー）</h4>');
        ['ai', 'dx', 'cyber'].forEach(function (key) {
            var ranking = rankings[key] || (key === 'dx' ? (data.prefecture_ranking || []) : []);
            var label = RANKING_LABELS[key] || key;
            parts.push('<p class="small fw-bold mb-1 mt-2">県別 ' + escapeHtml(label) + ' Top5</p>');
            if (ranking.length) {
                parts.push('<ol class="list-unstyled mb-0">');
                ranking.forEach(function (r) {
                    parts.push('<li class="py-1 border-bottom border-light">' + r.rank + '. ' + escapeHtml(r.name || '') + ' <span class="text-muted">(' + (r.count != null ? r.count : '—') + '件)</span></li>');
                });
                parts.push('</ol>');
            } else {
                parts.push('<p class="text-muted small mb-0">—</p>');
            }
        });
        parts.push('</div></div>');
        if (asOf) parts.push('<p class="small text-muted mt-2 mb-0">更新: ' + escapeHtml(asOf) + '</p>');
        return parts.join('');
    }

    function showError(msg) {
        var el = document.getElementById('header-kkj-compact-body');
        if (el) el.innerHTML = '<span class="text-muted">' + escapeHtml(msg || '取得できませんでした') + '</span>';
        var adminEl = document.getElementById('admin-kkj-body');
        if (adminEl) {
            var body = adminEl.querySelector('.card-body');
            if (body) body.innerHTML = '<p class="text-muted small mb-0">' + escapeHtml(msg || '取得できませんでした') + '</p>';
        }
    }

    function loadKkjCompact() {
        var bodyEl = document.getElementById('header-kkj-compact-body');
        if (!bodyEl) return;
        var timeout = window.setTimeout(function () {
            timeout = null;
            showError('取得できませんでした');
        }, 12000);
        fetch('/api/kkj-trends')
            .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error('API error ' + res.status)); })
            .then(function (json) {
                if (timeout) { window.clearTimeout(timeout); timeout = null; }
                if (!json.success || !json.data) {
                    showError(json.error || 'データがありません');
                    return;
                }
                var html = renderCompactBody(json.data);
                if (html) bodyEl.innerHTML = html; else showError('データがありません');
                var adminEl = document.getElementById('admin-kkj-body');
                if (adminEl) {
                    var cardBody = adminEl.querySelector('.card-body');
                    if (cardBody) cardBody.innerHTML = renderAdminTabBody(json.data) || '<p class="text-muted small mb-0">データがありません</p>';
                }
            })
            .catch(function (err) {
                if (timeout) { window.clearTimeout(timeout); timeout = null; }
                showError('取得できませんでした');
                if (console && console.warn) console.warn('KKJ trends load error:', err);
            });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadKkjCompact);
    } else {
        loadKkjCompact();
    }
})();
