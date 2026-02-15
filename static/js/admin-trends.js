/**
 * 行政データ統合表示（e-Stat + 官公需）
 * 外部APIは1回だけ呼び、キャッシュがあればそれを表示する。
 * /api/admin-trends を1回呼び出して estat + kkj を一度に取得。
 */
(function () {
    'use strict';

    /** e-Stat サンプルデータ（API未取得時・空のときのフォールバック） */
    var SAMPLE_ESTAT = [
        { indicator_id: 'cpi', name_ja: '消費者物価指数（総合・前年同月比）', unit: '前年同月=100', series: [{ period: '202602', value: '102.1', unit: '' }], updated_at: '202602' },
        { indicator_id: 'job_ratio', name_ja: '有効求人倍率', unit: '倍', series: [{ period: '202601', value: '1.31', unit: '2020年=100' }], updated_at: '202601' },
        { indicator_id: 'housing_starts', name_ja: '住宅着工', unit: '棟', series: [{ period: '202601', value: '45230', unit: '棟' }], updated_at: '202601' },
    ];

    function escapeHtml(s) {
        if (s == null) return '';
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function formatPeriod(period) {
        if (!period || period.length < 4) return period;
        var y = period.substring(0, 4);
        if (period.length >= 6) {
            var m = period.substring(4, 6);
            if (m && m !== '00') return y + '年' + parseInt(m, 10) + '月';
        }
        return y + '年';
    }

    // --- e-Stat 描画（CPI: 東京都区部/全国 前年比%、住宅着工: 直近12ヶ月+2026年度予測） ---
    function renderEstatCompactHtml(data) {
        if (!data || !data.length) return '';
        var html = '<ul class="list-unstyled mb-0">';
        (data.length > 3 ? data.slice(0, 3) : data).forEach(function (item) {
            var name = item.name_ja || item.indicator_id || '—';
            if (item.indicator_id === 'cpi' && item.cpi_lines && item.cpi_lines.length > 0) {
                // 全部入り: 直近1行のみ（全国を優先、なければ先頭）
                var line = item.cpi_lines.find(function (l) { return l.area === '全国'; }) || item.cpi_lines[0];
                var pct = line.value_pct != null ? (line.value_pct >= 0 ? '+' + line.value_pct : String(line.value_pct)) : '—';
                var label = escapeHtml(line.area) + (line.period_label ? '（' + line.period_label + (line.label_suffix ? '・' + line.label_suffix : '') + '）' : '');
                html += '<li class="d-flex justify-content-between py-1 border-bottom border-light"><span class="text-secondary">' + label + '</span><span>前年比<strong>' + pct + '%</strong></span></li>';
                return;
            }
            if (item.indicator_id === 'housing_starts') {
                var total12 = item.total_12m;
                if (total12 == null && item.series && item.series.length > 0) {
                    total12 = 0;
                    for (var i = 0; i < Math.min(12, item.series.length); i++) {
                        var v = parseInt(String(item.series[i].value || '0').replace(/,/g, ''), 10);
                        if (!isNaN(v)) total12 += v;
                    }
                }
                if (total12 != null) {
                    html += '<li class="d-flex justify-content-between py-1 border-bottom border-light"><span class="text-secondary" title="建築着工統計の月次データを直近12ヶ月分合算した着工戸数">直近12ヶ月の着工戸数合計</span><span><strong>' + (total12 / 10000).toFixed(1) + '</strong> 万戸</span></li>';
                }
                var forecast = item.forecast_2026_man != null ? item.forecast_2026_man : 77.7;
                var note = item.forecast_2026_note || '前年度比+5.5％増と予測';
                html += '<li class="d-flex justify-content-between py-1 border-bottom border-light"><span class="text-secondary" title="業界予測の目安">2026年度予測</span><span><strong>' + escapeHtml(String(forecast)) + '</strong> 万戸 <span class="text-muted small">(' + escapeHtml(note) + ')</span></span></li>';
                return;
            }
            var latest = item.series && item.series[0];
            var val = latest ? latest.value : '—';
            var period = latest ? formatPeriod(latest.period) : '';
            var unit = (latest && latest.unit) || item.unit || '';
            html += '<li class="d-flex justify-content-between py-1 border-bottom border-light"><span class="text-secondary">' + escapeHtml(name) + '</span><span><strong>' + escapeHtml(val) + '</strong>' + (unit ? ' ' + escapeHtml(unit) : '') + (period ? ' <span class="text-muted">(' + period + ')</span>' : '') + '</span></li>';
        });
        html += '</ul>';
        return html;
    }

    function renderEstatFullCard(item) {
        var body = '';
        if (item.indicator_id === 'cpi' && item.cpi_lines && item.cpi_lines.length > 0) {
            body = '<div class="mb-2">';
            item.cpi_lines.forEach(function (line) {
                var pct = line.value_pct != null ? (line.value_pct >= 0 ? '+' + line.value_pct : String(line.value_pct)) : '—';
                body += '<p class="mb-1"><strong>' + escapeHtml(line.area) + '（' + (line.period_label || '') + '・' + line.label_suffix + '）</strong>: 前年比' + pct + '%</p>';
            });
            if (item.tendency) body += '<p class="text-muted small mb-0">傾向: ' + escapeHtml(item.tendency) + '</p>';
            body += '</div>';
            if (item.series && item.series.length > 0) {
                var cpiRows = item.series.slice(0, 12).map(function (s) {
                    var val = s.value;
                    var pctStr = '—';
                    if (val != null && val !== '') {
                        var f = parseFloat(String(val).replace(/,/g, ''));
                        if (!isNaN(f)) pctStr = (f - 100 >= 0 ? '+' : '') + (f - 100).toFixed(1) + '%';
                    }
                    return '<tr><td>' + escapeHtml(formatPeriod(s.period)) + '</td><td>' + pctStr + '</td><td class="text-muted small">' + escapeHtml(s.unit || '前年同月=100') + '</td></tr>';
                }).join('');
                body += '<p class="small text-muted mb-1">直近1年（その月から過去12ヶ月）</p>';
                body += '<div class="table-responsive mt-2"><table class="table table-sm table-hover mb-0"><thead class="table-light"><tr><th>期間</th><th>前年比</th><th>単位</th></tr></thead><tbody>' + cpiRows + '</tbody></table></div>';
                if (item.series.length <= 1) {
                    body += '<p class="text-muted small mt-1 mb-0">※ この統計表で月次が取得できない場合は1行のみ表示されます。再取得で月次データが利用可能か確認できます。</p>';
                }
            }
        } else if (item.indicator_id === 'housing_starts') {
            var total12 = item.total_12m;
            if (total12 == null && item.series && item.series.length > 0) {
                total12 = 0;
                for (var i = 0; i < Math.min(12, item.series.length); i++) {
                    var v = parseInt(String(item.series[i].value || '0').replace(/,/g, ''), 10);
                    if (!isNaN(v)) total12 += v;
                }
            }
            if (total12 != null) body += '<p class="mb-1">直近12ヶ月の着工戸数合計: <strong>' + (total12 / 10000).toFixed(1) + '</strong> 万戸</p>';
            var forecast = item.forecast_2026_man != null ? item.forecast_2026_man : 77.7;
            body += '<p class="mb-1">2026年度予測: <strong>' + escapeHtml(String(forecast)) + '</strong> 万戸（' + escapeHtml(item.forecast_2026_note || '前年度比+5.5％増') + '）</p>';
            if (item.series && item.series.length) {
                var rows = item.series.slice(0, 6).map(function (s) {
                    return '<tr><td>' + escapeHtml(formatPeriod(s.period)) + '</td><td>' + escapeHtml(s.value) + '</td><td class="text-muted small">' + escapeHtml(s.unit || '') + '</td></tr>';
                }).join('');
                body += '<div class="table-responsive mt-2"><table class="table table-sm table-hover mb-0"><thead class="table-light"><tr><th>期間</th><th>戸数</th><th>単位</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
            }
        } else {
            var rows = (item.series || []).map(function (s) {
                return '<tr><td>' + escapeHtml(formatPeriod(s.period)) + '</td><td>' + escapeHtml(s.value) + '</td><td class="text-muted small">' + escapeHtml(s.unit || '') + '</td></tr>';
            }).join('');
            body = rows
                ? '<div class="table-responsive"><table class="table table-sm table-hover mb-0"><thead class="table-light"><tr><th>期間</th><th>値</th><th>単位</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
                : '<p class="text-muted small mb-0">2026年以降のデータはまだありません。</p>';
        }
        return (
            '<div class="col-12 col-lg-4">' +
            '  <div class="card h-100">' +
            '    <div class="card-header bg-secondary text-white"><span class="small fw-bold">' + escapeHtml(item.name_ja) + '</span></div>' +
            '    <div class="card-body p-2">' + body + '</div>' +
            '  </div>' +
            '</div>'
        );
    }

    // --- KKJ 描画 ---
    var KKJ_RANKING_LABELS = { ai: 'AI案件', dx: 'DX案件', cyber: 'サイバー案件' };

    function renderKkjCompactBody(data) {
        if (!data) return '';
        if (data.api_unreachable) {
            return '<div class="mt-0 text-warning">官公需APIに接続できません（タイムアウト）。しばらく後にお試しください。</div>';
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
            var ranking = rankings[key] || (key === 'dx' ? (data.prefecture_ranking || []) : []);
            var rankParts = ranking.slice(0, 5).map(function (r) {
                return r.rank + '.' + escapeHtml((r.name || '').replace(/(県|府|都)$/, ''));
            });
            var line2 = rankParts.length ? rankParts.join(' ') : '—';
            lines.push('<div class="mt-0 text-muted">県別 ' + (KKJ_RANKING_LABELS[key] || key) + ' Top5: ' + line2 + '</div>');
        });
        return lines.join('');
    }

    function renderKkjAdminTabBody(data) {
        if (!data) return '';
        if (data.api_unreachable) {
            return '<p class="text-warning mb-0">官公需APIに接続できません（タイムアウト）。しばらく後にお試しください。</p>';
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
            parts.push('<p class="small fw-bold mb-1 mt-2">県別 ' + (KKJ_RANKING_LABELS[key] || key) + ' Top5</p>');
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

    function bindGotoTab() {
        document.querySelectorAll('.estat-goto-tab').forEach(function (a) {
            a.addEventListener('click', function (e) {
                e.preventDefault();
                var tabId = this.getAttribute('data-target-tab');
                if (tabId) {
                    var tabEl = document.getElementById(tabId);
                    if (tabEl && window.bootstrap && window.bootstrap.Tab) {
                        var tab = new window.bootstrap.Tab(tabEl);
                        tab.show();
                    }
                }
            });
        });
    }

    function fetchAndRender(forceRefresh) {
        bindGotoTab();
        var url = '/api/admin-trends' + (forceRefresh ? '?force_refresh=true' : '');
        var loading = document.getElementById('estat-full-loading');
        var fullBody = document.getElementById('estat-full-body');
        var estatCompact = document.getElementById('header-estat-compact-body');
        var kkjCompact = document.getElementById('header-kkj-compact-body');
        var kkjAdminBody = document.getElementById('admin-kkj-body');
        if (forceRefresh && loading) loading.style.display = 'block';
        if (forceRefresh && fullBody) fullBody.style.display = 'none';

        fetch(url)
            .then(function (res) { return res.json(); })
            .then(function (json) {
                // e-Stat
                var estat = json.estat || {};
                var estatData = (estat.success && estat.data && estat.data.length && (estat.data[0].name_ja || estat.data[0].indicator_id))
                    ? estat.data : null;
                if (estatCompact) {
                    estatCompact.innerHTML = estatData
                        ? renderEstatCompactHtml(estatData.length > 3 ? estatData.slice(0, 3) : estatData)
                        : '<p class="text-danger small mb-0">' + escapeHtml(estat.error || '取得できませんでした') + '</p>';
                }
                if (loading) loading.style.display = 'none';
                if (fullBody) {
                    fullBody.style.display = 'flex';
                    if (estatData) {
                        fullBody.innerHTML = estatData.map(renderEstatFullCard).join('');
                    } else {
                        var hint = (estat.error && estat.error.indexOf('ESTAT') !== -1)
                            ? ' <span class="text-muted small">（e-Stat APIキーを.envに設定すると実データを取得できます）</span>'
                            : '';
                        fullBody.innerHTML = '<div class="col-12 mb-2"><span class="badge bg-warning text-dark">サンプルデータ</span>' + hint + '</div>' + SAMPLE_ESTAT.map(renderEstatFullCard).join('');
                    }
                }

                // KKJ
                var kkj = json.kkj || {};
                var kkjData = (kkj.success && kkj.data) ? kkj.data : null;
                if (kkjCompact) {
                    kkjCompact.innerHTML = kkjData
                        ? renderKkjCompactBody(kkjData)
                        : '<span class="text-muted">' + escapeHtml(kkj.error || '取得できませんでした') + '</span>';
                }
                if (kkjAdminBody) {
                    var cardBody = kkjAdminBody.querySelector('.card-body');
                    if (cardBody) {
                        cardBody.innerHTML = kkjData
                            ? renderKkjAdminTabBody(kkjData) || '<p class="text-muted small mb-0">データがありません</p>'
                            : '<p class="text-muted small mb-0">' + escapeHtml(kkj.error || '取得できませんでした') + '</p>';
                    }
                }

                bindGotoTab();
            })
            .catch(function (err) {
                var msg = err && err.message ? err.message : '通信エラー';
                if (loading) loading.style.display = 'none';
                if (fullBody) {
                    fullBody.style.display = 'block';
                    fullBody.innerHTML = '<div class="col-12"><div class="alert alert-danger mb-0">' + escapeHtml(msg) + '</div></div>';
                }
                if (estatCompact) estatCompact.innerHTML = '<p class="text-danger small mb-0">' + escapeHtml(msg) + '</p>';
                if (kkjCompact) kkjCompact.innerHTML = '<span class="text-muted">' + escapeHtml(msg) + '</span>';
                bindGotoTab();
            });
    }

    function init() {
        fetchAndRender(false);
        function onRefreshClick() {
            var btns = document.querySelectorAll('#admin-refresh-btn, #admin-refresh-btn-header');
            btns.forEach(function (b) { b.disabled = true; });
            var loading = document.getElementById('estat-full-loading');
            if (loading) loading.style.display = 'block';
            fetchAndRender(true);
            setTimeout(function () {
                btns.forEach(function (b) { b.disabled = false; });
            }, 3000);
        }
        document.querySelectorAll('#admin-refresh-btn, #admin-refresh-btn-header').forEach(function (btn) {
            if (btn) btn.addEventListener('click', onRefreshClick);
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
