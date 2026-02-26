/**
 * 行政データ統合表示（e-Stat + 政府調達）
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

    // ニュース・テックタブと同様のカード見た目（指標ごとにヘッダー色・アイコン）
    var ESTAT_CARD_STYLE = {
        cpi:            { header: 'bg-primary text-white',    icon: 'fa-chart-line' },
        job_ratio:      { header: 'bg-info text-white',       icon: 'fa-briefcase' },
        housing_starts: { header: 'bg-success text-white',    icon: 'fa-home' },
        unemployment:   { header: 'bg-warning text-dark',      icon: 'fa-user-clock' },
        real_wages:     { header: 'bg-secondary text-white',  icon: 'fa-yen-sign' },
        retail_sales:   { header: 'bg-dark text-white',       icon: 'fa-shopping-cart' }
    };

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
                body += '<div class="table-responsive mt-2"><table class="table table-sm trend-table mb-0"><thead class="table-dark"><tr><th>期間</th><th>前年比</th><th>単位</th></tr></thead><tbody>' + cpiRows + '</tbody></table></div>';
                if (item.series.length <= 1) {
                    body += '<p class="text-muted small mt-1 mb-0">※ この統計表で月次が取得できない場合は1行のみ表示されます。再取得で月次データが利用可能か確認できます。</p>';
                }
            }
        } else if (item.indicator_id === 'housing_starts') {
            if (item.series && item.series.length) {
                var rows = item.series.slice(0, 12).map(function (s) {
                    return '<tr><td>' + escapeHtml(formatPeriod(s.period)) + '</td><td>' + escapeHtml(s.value) + '</td><td class="text-muted small">' + escapeHtml(s.unit || '戸') + '</td></tr>';
                }).join('');
                body += '<p class="small text-muted mb-1">直近1年（その月から過去12ヶ月）</p>';
                body += '<div class="table-responsive mt-2"><table class="table table-sm trend-table mb-0"><thead class="table-dark"><tr><th>期間</th><th>戸数</th><th>単位</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
                var total12 = item.total_12m;
                if (total12 == null && item.series && item.series.length > 0) {
                    total12 = 0;
                    for (var i = 0; i < Math.min(12, item.series.length); i++) {
                        var v = parseInt(String(item.series[i].value || '0').replace(/,/g, ''), 10);
                        if (!isNaN(v)) total12 += v;
                    }
                }
                var forecast = item.forecast_2026_man != null ? item.forecast_2026_man : 77.7;
                body += '<p class="text-muted small mt-2 mb-0">直近12ヶ月合計: <strong>' + (total12 != null ? (total12 / 10000).toFixed(1) + ' 万戸' : '—') + '</strong>　2026年度予測: <strong>' + escapeHtml(String(forecast)) + '</strong> 万戸（' + escapeHtml(item.forecast_2026_note || '前年度比+5.5％増') + '）</p>';
            } else {
                body += '<p class="text-muted small mb-0">2026年以降のデータはまだありません。</p>';
            }
        } else {
            var rows = (item.series || []).map(function (s) {
                return '<tr><td>' + escapeHtml(formatPeriod(s.period)) + '</td><td>' + escapeHtml(s.value) + '</td><td class="text-muted small">' + escapeHtml(s.unit || '') + '</td></tr>';
            }).join('');
            body = rows
                ? '<div class="table-responsive"><table class="table table-sm trend-table mb-0"><thead class="table-dark"><tr><th>期間</th><th>値</th><th>単位</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
                : '<p class="text-muted small mb-0">2026年以降のデータはまだありません。</p>';
        }
        var style = ESTAT_CARD_STYLE[item.indicator_id] || { header: 'bg-secondary text-white', icon: 'fa-chart-bar' };
        var title = escapeHtml(item.name_ja || item.indicator_id || '');
        return (
            '<article class="col-12 col-md-6 col-lg-4" aria-label="' + title + '">' +
            '  <div class="card h-100">' +
            '    <div class="card-header ' + style.header + ' d-flex justify-content-between align-items-center">' +
            '      <h2 class="h5 mb-0"><i class="fas ' + style.icon + '" aria-hidden="true"></i> ' + title + '</h2>' +
            '    </div>' +
            '    <div class="card-body">' + body + '</div>' +
            '  </div>' +
            '</article>'
        );
    }

    // --- KKJ 描画 ---
    var KKJ_RANKING_LABELS = { ai: 'AI案件', dx: 'DX案件', cyber: 'サイバー案件' };

    function renderKkjCompactBody(data) {
        if (!data) return '';
        if (data.api_unreachable) {
            return '<div class="text-warning">政府調達APIに接続できません（タイムアウト）。</div>';
        }
        var signals = data.signals || [];
        var signalsMonthly = data.signals_monthly || {};
        var latestPeriod = '';
        var monthPeriod = '';
        if (signalsMonthly.ai && signalsMonthly.ai.length > 0 && signalsMonthly.ai[0].period) {
            latestPeriod = signalsMonthly.ai[0].period;
            monthPeriod = formatPeriod(latestPeriod);
        }
        var aiMonth = signalsMonthly.ai && signalsMonthly.ai[0] ? signalsMonthly.ai[0].value : null;
        var dxMonth = signalsMonthly.dx && signalsMonthly.dx[0] ? signalsMonthly.dx[0].value : null;
        var cyMonth = signalsMonthly.cyber && signalsMonthly.cyber[0] ? signalsMonthly.cyber[0].value : null;
        var parts = [];
        if (aiMonth != null || dxMonth != null || cyMonth != null) {
            parts.push('AI関連 <strong>' + (aiMonth != null ? aiMonth : '—') + '</strong>件');
            parts.push('DX関連 <strong>' + (dxMonth != null ? dxMonth : '—') + '</strong>件');
            parts.push('サイバー <strong>' + (cyMonth != null ? cyMonth : '—') + '</strong>件');
        } else {
            parts = signals.map(function (s) {
                var label = s.label || KKJ_RANKING_LABELS[s.key] || s.key || '';
                var count = s.count != null ? s.count : '—';
                return escapeHtml(label) + ' <strong>' + count + '</strong>件';
            });
        }
        var summary = parts.length ? parts.join(' / ') : '—';
        return '<div class="header-admin-latest-title">' + summary + '</div>';
    }

    function formatPeriod(period) {
        if (!period || period.length < 4) return period || '';
        var y = period.substring(0, 4);
        if (period.length >= 6) {
            var m = period.substring(4, 6);
            if (m && m !== '00') return y + '年' + parseInt(m, 10) + '月';
        }
        return y + '年';
    }

    function parsePeriodLabel(label) {
        if (!label) return 0;
        var m = label.match(/(\d{4})年(\d{1,2})月/);
        if (!m) return 0;
        var yy = parseInt(m[1], 10);
        var mm = parseInt(m[2], 10);
        if (!yy || !mm) return 0;
        return yy * 100 + mm;
    }

    function getEstatLatestPeriod(data) {
        var bestKey = 0;
        var bestLabel = '';
        (data || []).forEach(function (item) {
            var key = 0;
            var label = '';
            if (item && item.series && item.series[0] && item.series[0].period) {
                key = parseInt(item.series[0].period, 10) || 0;
                label = formatPeriod(item.series[0].period);
            } else if (item && item.updated_at) {
                key = parseInt(item.updated_at, 10) || 0;
                label = formatPeriod(item.updated_at);
            } else if (item && item.cpi_lines && item.cpi_lines[0] && item.cpi_lines[0].period_label) {
                key = parsePeriodLabel(item.cpi_lines[0].period_label);
                label = item.cpi_lines[0].period_label;
            }
            if (key >= bestKey) {
                bestKey = key;
                bestLabel = label;
            }
        });
        return bestLabel;
    }

    function renderEstatCompactLatest(data) {
        if (!data || !data.length) return '<span class="text-muted">—</span>';
        var shortLabels = {
            cpi: 'CPI',
            job_ratio: '求人',
            housing_starts: '住宅',
            unemployment: '失業',
            real_wages: '賃金',
            retail_sales: '小売'
        };
        var unitOverride = {
            job_ratio: '倍',
            housing_starts: '戸',
            unemployment: '%',
            real_wages: '指数',
            retail_sales: '億円'
        };
        var parts = [];
        (data || []).forEach(function (item) {
            if (!item) return;
            var id = item.indicator_id || '';
            var label = shortLabels[id] || (item.name_ja || id || '—');
            if (id === 'cpi' && item.cpi_lines && item.cpi_lines.length > 0) {
                var line = item.cpi_lines.find(function (l) { return l.area === '全国'; }) || item.cpi_lines[0];
                var pct = line.value_pct != null ? (line.value_pct >= 0 ? '+' + line.value_pct : String(line.value_pct)) : '—';
                parts.push(escapeHtml(label) + ' ' + pct + '%');
                return;
            }
            var latest = item.series && item.series[0];
            var val = latest ? latest.value : '—';
            var unit = unitOverride[id] || (latest && latest.unit) || item.unit || '';
            var unitText = unit ? ' ' + escapeHtml(unit) : '';
            parts.push(escapeHtml(label) + ' ' + escapeHtml(val) + unitText);
        });
        var summary = parts.length ? parts.join(' / ') : '—';
        var latestPeriod = getEstatLatestPeriod(data);
        var periodText = latestPeriod ? '（最新: ' + escapeHtml(latestPeriod) + '）' : '';
        var periodEl = document.getElementById('header-estat-latest-period');
        if (periodEl) {
            periodEl.textContent = periodText;
        }
        var firstLine = summary;
        var secondLine = '';
        if (parts.length > 3) {
            var splitIndex = Math.ceil(parts.length / 2);
            firstLine = parts.slice(0, splitIndex).join(' / ');
            secondLine = parts.slice(splitIndex).join(' / ');
        }
        return (
            '<div class="header-admin-latest-title">' +
            '<span class="header-admin-latest-line">' + firstLine + '</span>' +
            (secondLine ? '<span class="header-admin-latest-line">' + secondLine + '</span>' : '') +
            '</div>'
        );
    }

    function renderKkjAdminTabBody(data, selectedKeyword) {
        if (!data) return '';
        if (data.api_unreachable) {
            return '<p class="text-warning mb-0">政府調達APIに接続できません（タイムアウト）。しばらく後にお試しください。</p>';
        }
        selectedKeyword = selectedKeyword || 'all';
        var signals = data.signals || [];
        var rankings = data.prefecture_rankings || {};
        var categoryLabels = data.category_labels || {};
        var categoryOrder = data.category_order || ['digital', 'security'];
        var keywordCategory = data.keyword_category || {};
        var asOf = data.as_of || '';
        var periodDays = data.period_days != null ? data.period_days : 30;
        var keysToShow = selectedKeyword === 'all'
            ? (categoryOrder.reduce(function (acc, catKey) {
                ['ai', 'dx', 'cyber'].forEach(function (k) { if ((keywordCategory[k] || '') === catKey) acc.push(k); });
                return acc;
            }, []).length ? categoryOrder.reduce(function (acc, catKey) {
                ['ai', 'dx', 'cyber'].forEach(function (k) { if ((keywordCategory[k] || '') === catKey) acc.push(k); });
                return acc;
            }, []) : ['ai', 'dx', 'cyber'])
            : [selectedKeyword];
        if (keysToShow.length === 0) keysToShow = ['ai', 'dx', 'cyber'];

        var parts = [];
        var summaryParts = signals.map(function (s) {
            var label = s.label || KKJ_RANKING_LABELS[s.key] || s.key || '';
            var count = s.count != null ? s.count : '—';
            return escapeHtml(label) + ' <strong>' + count + '</strong>件';
        });
        var summaryLine = summaryParts.length ? summaryParts.join(' / ') : '';
        var summaryMeta = [];
        if (asOf) summaryMeta.push('更新: ' + escapeHtml(asOf));
        if (periodDays != null) summaryMeta.push('直近' + periodDays + '日');
        if (summaryLine || summaryMeta.length) {
            parts.push('<div class="mb-3">');
            if (summaryLine) parts.push('<div class="header-admin-latest-title">' + summaryLine + '</div>');
            if (summaryMeta.length) parts.push('<div class="header-admin-latest-value text-muted">' + summaryMeta.join(' / ') + '</div>');
            parts.push('</div>');
        }
        // はてなブックマーク同様: キーワードをドロップダウンで選択
        parts.push('<div class="mb-3">');
        parts.push('<label for="kkjKeywordSelect" class="form-label">キーワードを選択:</label>');
        parts.push('<select class="form-select form-select-sm" id="kkjKeywordSelect" style="max-width: 12rem;" aria-label="政府調達キーワード選択">');
        parts.push('<option value="all"' + (selectedKeyword === 'all' ? ' selected' : '') + '>すべて</option>');
        parts.push('<option value="ai"' + (selectedKeyword === 'ai' ? ' selected' : '') + '>AI案件</option>');
        parts.push('<option value="dx"' + (selectedKeyword === 'dx' ? ' selected' : '') + '>DX案件</option>');
        parts.push('<option value="cyber"' + (selectedKeyword === 'cyber' ? ' selected' : '') + '>サイバー案件</option>');
        parts.push('</select>');
        parts.push('</div>');

        // 2列レイアウト: NHK・World Newsと同じカード形式で統一
        parts.push('<div class="row g-3 mt-1 mb-3">');

        // 左列: キーワード別 注目の案件 Top5（NHK形式）
        var keywordTopCases = data.keyword_top_cases || {};
        var hasTopCases = (keywordTopCases.ai && keywordTopCases.ai.length > 0) ||
            (keywordTopCases.dx && keywordTopCases.dx.length > 0) ||
            (keywordTopCases.cyber && keywordTopCases.cyber.length > 0);
        parts.push('<article class="col-12 col-md-6" id="source-kkj-cases">');
        parts.push('<div class="card h-100">');
        parts.push('<div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">');
        parts.push('<h2 class="h5 mb-0"><i class="fas fa-file-contract" aria-hidden="true"></i> 注目の案件 Top5（案件名・リンク）</h2>');
        parts.push('</div>');
        parts.push('<div class="card-body">');
        parts.push('<div class="card trend-table category-card">');
        parts.push('<div class="card-body">');
        parts.push('<div class="trend-table-container">');
        parts.push('<div class="table-responsive">');
        if (hasTopCases) {
            var caseRows = [];
            keysToShow.forEach(function (key) {
                var cases = keywordTopCases[key] || [];
                cases.forEach(function (c) {
                    var title = (c.title || '').substring(0, 80) + (c.title && c.title.length > 80 ? '…' : '');
                    var linkCell = c.url
                        ? '<a href="' + escapeHtml(c.url) + '" target="_blank" rel="noopener noreferrer" class="text-decoration-none">' + escapeHtml(title) + '</a>'
                        : escapeHtml(title);
                    if (selectedKeyword === 'all') {
                        caseRows.push('<tr><td>' + escapeHtml(KKJ_RANKING_LABELS[key] || key) + '</td><td class="text-end">' + c.rank + '</td><td class="small">' + linkCell + '</td><td class="small text-muted">' + escapeHtml(c.organization || '') + '</td><td class="small">' + escapeHtml(c.cft_issue_date || '') + '</td><td class="small">' + escapeHtml(c.prefecture || '') + '</td></tr>');
                    } else {
                        caseRows.push('<tr><td class="text-end">' + c.rank + '</td><td class="small">' + linkCell + '</td><td class="small text-muted">' + escapeHtml(c.organization || '') + '</td><td class="small">' + escapeHtml(c.cft_issue_date || '') + '</td><td class="small">' + escapeHtml(c.prefecture || '') + '</td></tr>');
                    }
                });
            });
            var caseTableHeader = selectedKeyword === 'all'
                ? '<tr><th>キーワード</th><th class="text-end">順位</th><th>案件名</th><th>機関</th><th>公告日</th><th>都道府県</th></tr>'
                : '<tr><th class="text-end">順位</th><th>案件名</th><th>機関</th><th>公告日</th><th>都道府県</th></tr>';
            parts.push('<table class="table trend-table mb-0" id="kkjCasesTrendsTable"><thead class="table-dark">' + caseTableHeader + '</thead><tbody id="kkjCasesTrendsTableBody">' + caseRows.join('') + '</tbody></table>');
        } else {
            parts.push('<table class="table trend-table mb-0"><tbody><tr><td class="text-muted">—</td></tr></tbody></table>');
        }
        parts.push('</div></div></div></div>');
        if (hasTopCases) {
            parts.push('<p class="text-muted small mt-2 mb-0">※ リンクは公告時のURLのため、切れている場合があります。詳細は<a href="https://www.kkj.go.jp/" target="_blank" rel="noopener">官公需情報ポータル</a>で検索してください。</p>');
        } else {
            parts.push('<p class="text-muted small mt-2 mb-0"><strong>「再取得」</strong>ボタンを押すと、AI・DX・サイバー各キーワードの注目案件が表示されます。</p>');
        }
        parts.push('</div></div></article>');

        // 右列: キーワード別月次件数（World News形式）
        var signalsMonthly = data.signals_monthly || {};
        var periodMonths = data.period_months != null ? data.period_months : 12;
        parts.push('<article class="col-12 col-md-6" id="source-kkj-monthly">');
        parts.push('<div class="card h-100">');
        parts.push('<div class="card-header bg-info text-white d-flex justify-content-between align-items-center">');
        parts.push('<h2 class="h5 mb-0"><i class="fas fa-chart-bar" aria-hidden="true"></i> 月次件数（直近' + periodMonths + 'ヶ月）</h2>');
        parts.push('</div>');
        parts.push('<div class="card-body">');
        parts.push('<div class="card trend-table category-card">');
        parts.push('<div class="card-body">');
        parts.push('<div class="trend-table-container">');
        parts.push('<div class="table-responsive">');
        if (signalsMonthly.ai && signalsMonthly.ai.length > 0) {
            var months = signalsMonthly.ai;
            var headers = '<tr><th>期間</th><th>AI関連</th><th>DX関連</th><th>サイバー</th></tr>';
            var rows = months.map(function (m) {
                var p = m.period || '';
                var y = p.length >= 4 ? p.substring(0, 4) : '';
                var mo = p.length >= 6 ? p.substring(4, 6) : '';
                var periodLabel = y && mo ? y + '年' + parseInt(mo, 10) + '月' : p;
                var aiVal = (signalsMonthly.ai && signalsMonthly.ai.find(function (x) { return x.period === p; })) ? (signalsMonthly.ai.find(function (x) { return x.period === p; }).value) : '—';
                var dxVal = (signalsMonthly.dx && signalsMonthly.dx.find(function (x) { return x.period === p; })) ? (signalsMonthly.dx.find(function (x) { return x.period === p; }).value) : '—';
                var cyVal = (signalsMonthly.cyber && signalsMonthly.cyber.find(function (x) { return x.period === p; })) ? (signalsMonthly.cyber.find(function (x) { return x.period === p; }).value) : '—';
                return '<tr><td>' + escapeHtml(periodLabel) + '</td><td>' + aiVal + '</td><td>' + dxVal + '</td><td>' + cyVal + '</td></tr>';
            }).join('');
            parts.push('<table class="table trend-table mb-0" id="kkjMonthlyTrendsTable"><thead class="table-dark">' + headers + '</thead><tbody>' + rows + '</tbody></table>');
        } else {
            parts.push('<table class="table trend-table mb-0"><tbody><tr><td class="text-muted">月次データはありません。</td></tr></tbody></table>');
        }
        parts.push('</div></div></div></div>');
        if (asOf) parts.push('<p class="small text-muted mt-2 mb-0">更新: ' + escapeHtml(asOf) + '</p>');
        parts.push('</div></div></article>');

        parts.push('</div>');
        return parts.join('');
    }

    function applyMakeTableRowClickableToKkjCases() {
        var tbody = document.getElementById('kkjCasesTrendsTableBody');
        if (!tbody || typeof window.makeTableRowClickable !== 'function') return;
        tbody.querySelectorAll('tr').forEach(function (row) {
            var link = row.querySelector('a[href]');
            if (link && link.href && link.href !== '#' && link.href.indexOf('example.com') === -1) {
                window.makeTableRowClickable(row, link.href, (link.textContent || '').trim() + 'の案件を開く');
            }
        });
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
                        ? renderEstatCompactLatest(estatData)
                        : '<span class="text-muted">' + escapeHtml(estat.error || '取得できませんでした') + '</span>';
                    var periodEl = document.getElementById('header-estat-latest-period');
                    if (periodEl && !estatData) periodEl.textContent = '';
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
                    window.__lastKkjData = kkjData;
                    kkjAdminBody.innerHTML = kkjData
                        ? renderKkjAdminTabBody(kkjData, 'all') || '<p class="text-muted small mb-0">データがありません</p>'
                        : '<p class="text-muted small mb-0">' + escapeHtml(kkj.error || '取得できませんでした') + '</p>';
                    applyMakeTableRowClickableToKkjCases();
                    function bindKkjKeywordSelect() {
                        var sel = document.getElementById('kkjKeywordSelect');
                        if (sel && window.__lastKkjData) {
                            sel.onchange = function () {
                                kkjAdminBody.innerHTML = renderKkjAdminTabBody(window.__lastKkjData, this.value);
                                applyMakeTableRowClickableToKkjCases();
                                bindKkjKeywordSelect();
                            };
                        }
                    }
                    bindKkjKeywordSelect();
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
                if (estatCompact) {
                    estatCompact.innerHTML = '<span class="text-muted">' + escapeHtml(msg) + '</span>';
                    var periodEl = document.getElementById('header-estat-latest-period');
                    if (periodEl) periodEl.textContent = '';
                }
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
