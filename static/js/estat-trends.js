/**
 * e-Stat 景気・行政データ（CPI・有効求人倍率・住宅着工）の表示
 * ヘッダー・全部入りタブのコンパクト表示と、行政データタブの詳細表示
 */
(function () {
    'use strict';

    /** 景気・行政データのサンプル（API未取得時・空のときの表示用） */
    var SAMPLE_DATA = [
        { indicator_id: 'cpi', name_ja: '消費者物価指数', unit: '前年同月=100', cpi_lines: [{ area: '東京都区部', period_label: '2026年1月', value_pct: 2.0, label_suffix: '速報' }, { area: '全国', period_label: '2025年12月', value_pct: 2.4, label_suffix: '確定' }], tendency: '東京のコアCPIは2%台を維持しつつも、鈍化の兆しが見え始めている。', series: [], updated_at: null, stats_data_id: null },
        { indicator_id: 'job_ratio', name_ja: '有効求人倍率', unit: '倍', series: [{ period: '202601', value: '1.31', unit: '2020年=100' }, { period: '202512', value: '1.29', unit: '2020年=100' }], updated_at: '202601', stats_data_id: null },
        { indicator_id: 'housing_starts', name_ja: '住宅着工', unit: '棟', total_12m: 777000, forecast_2026_man: 77.7, forecast_2026_note: '前年度比+5.5％増と予測', series: [{ period: '202601', value: '45230', unit: '棟' }], updated_at: '202601', stats_data_id: null }
    ];

    function formatPeriod(period) {
        if (!period || period.length < 4) return period;
        var y = period.substring(0, 4);
        if (period.length >= 6) {
            var m = period.substring(4, 6);
            if (m && m !== '00') return y + '年' + parseInt(m, 10) + '月';
        }
        return y + '年';
    }

    function renderCompactHtml(data) {
        if (!data || !data.length) return '';
        var html = '<ul class="list-unstyled mb-0">';
        data.forEach(function (item) {
            var name = item.name_ja || item.indicator_id || '—';
            // CPI: 直近1行のみ（全国を優先）
            if (item.indicator_id === 'cpi' && item.cpi_lines && item.cpi_lines.length > 0) {
                var line = item.cpi_lines.find(function (l) { return l.area === '全国'; }) || item.cpi_lines[0];
                var pct = line.value_pct != null ? (line.value_pct >= 0 ? '+' + line.value_pct : String(line.value_pct)) : '—';
                var label = escapeHtml(line.area) + (line.period_label ? '（' + line.period_label + (line.label_suffix ? '・' + line.label_suffix : '') + '）' : '');
                html += '<li class="d-flex justify-content-between py-1 border-bottom border-light"><span class="text-secondary">' + label + '</span><span>前年比<strong>' + pct + '%</strong></span></li>';
                return;
            }
            // 住宅着工: 常に直近12ヶ月合計・2026年度予測で表示（キャッシュ古い形式でも series から合算可能）
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
            // その他: 従来の1行表示
            var latest = item.series && item.series[0];
            var val = latest ? latest.value : '—';
            var period = latest ? formatPeriod(latest.period) : '';
            var unit = (latest && latest.unit) || item.unit || '';
            html += '<li class="d-flex justify-content-between py-1 border-bottom border-light"><span class="text-secondary">' + escapeHtml(name) + '</span><span><strong>' + escapeHtml(val) + '</strong>' + (unit ? ' ' + escapeHtml(unit) : '') + (period ? ' <span class="text-muted">(' + period + ')</span>' : '') + '</span></li>';
        });
        html += '</ul>';
        return html;
    }

    function renderFullCard(item) {
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

    function escapeHtml(s) {
        if (s == null) return '';
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function showCompactError(msg) {
        var html = '<p class="text-danger small mb-0">' + escapeHtml(msg) + '</p>';
        var el = document.getElementById('header-estat-compact-body');
        if (el) el.innerHTML = html;
    }

    function showFullError(msg) {
        var loading = document.getElementById('estat-full-loading');
        var body = document.getElementById('estat-full-body');
        if (loading) loading.style.display = 'none';
        if (body) {
            body.innerHTML = '<div class="col-12"><div class="alert alert-warning mb-0">' + escapeHtml(msg) + '</div></div>';
            body.style.display = 'block';
        }
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

    function showCompact(data) {
        if (!data || !data.length) return;
        var html = renderCompactHtml(data);
        if (!html) return;
        var el = document.getElementById('header-estat-compact-body');
        if (el) el.innerHTML = html;
    }

    function fetchAndRender() {
        bindGotoTab();
        fetch('/api/estat-trends')
            .then(function (res) { return res.json(); })
            .then(function (json) {
                var data = (json.success && json.data && json.data.length) ? json.data : null;
                // 全部入りタブのコンパクト表示は先頭3指標のみ（CPI・有効求人倍率・住宅着工）
                if (data && data.length > 0 && (data[0].name_ja || data[0].indicator_id)) showCompact(data.length > 3 ? data.slice(0, 3) : data);
                var fullBody = document.getElementById('estat-full-body');
                var loading = document.getElementById('estat-full-loading');
                if (loading) loading.style.display = 'none';
                if (fullBody) {
                    fullBody.style.display = 'flex';
                    if (data) {
                        // 行政タブは全指標を表示（6件：CPI・有効求人倍率・住宅着工・完全失業率・実質賃金指数・貿易統計）
                        fullBody.innerHTML = data.map(renderFullCard).join('');
                    } else {
                        fullBody.innerHTML = '<div class="col-12 mb-2"><span class="badge bg-warning text-dark">サンプルデータ</span></div>' + SAMPLE_DATA.map(renderFullCard).join('');
                    }
                }
                bindGotoTab();
            })
            .catch(function (err) {
                var msg = err && err.message ? err.message : '通信エラー';
                showCompact(SAMPLE_DATA);
                showFullError(msg);
                var loading = document.getElementById('estat-full-loading');
                if (loading) loading.style.display = 'none';
                var body = document.getElementById('estat-full-body');
                if (body) {
                    body.style.display = 'block';
                    body.innerHTML = '<div class="col-12"><div class="alert alert-danger mb-0">' + escapeHtml(msg) + '</div></div>';
                }
                bindGotoTab();
            });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fetchAndRender);
    } else {
        fetchAndRender();
    }
})();
