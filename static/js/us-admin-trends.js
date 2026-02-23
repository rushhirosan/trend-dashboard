/**
 * US Gov Data tab: BLS (economy) + USAspending (federal spending)
 * Single tab with US Economy on top, US Government Spending below.
 */
(function () {
    'use strict';

    var SAMPLE_BLS = [
        { indicator_id: 'cpi', name_en: 'CPI (All Items, SA)', unit: '1982-84=100', series: [{ period: '202601', value: '314.2' }] },
        { indicator_id: 'unemployment', name_en: 'Unemployment Rate', unit: '%', series: [{ period: '202601', value: '3.9' }] },
        { indicator_id: 'employment', name_en: 'Total Nonfarm Employment', unit: 'thousands', series: [{ period: '202601', value: '159526' }] },
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
            if (m && m !== '00') return y + '-' + parseInt(m, 10);
        }
        return y;
    }

    function formatNumber(num) {
        if (num == null || isNaN(num)) return '—';
        if (num >= 1e12) return (num / 1e12).toFixed(1) + 'T';
        if (num >= 1e9) return (num / 1e9).toFixed(1) + 'B';
        if (num >= 1e6) return (num / 1e6).toFixed(1) + 'M';
        if (num >= 1e3) return (num / 1e3).toFixed(1) + 'K';
        return String(num);
    }

    function renderBlsCompactLatest(data) {
        if (!data || !data.length) return '<span class="text-muted">—</span>';
        var shortLabels = {
            cpi: 'CPI',
            unemployment: 'Unemp',
            employment: 'Jobs',
            jolts_openings: 'JOLTS',
            jolts_hires: 'Hires',
            jolts_quits: 'Quits',
            eci: 'ECI',
            construction_emp: 'Const'
        };
        var order = ['cpi', 'unemployment', 'employment', 'jolts_openings', 'jolts_hires', 'jolts_quits', 'eci', 'construction_emp'];
        var parts = [];
        var byId = {};
        data.forEach(function (item) {
            if (!item) return;
            var id = item.indicator_id || '';
            if (id) byId[id] = item;
        });
        order.forEach(function (id) {
            var item = byId[id];
            if (!item) return;
            var label = shortLabels[id] || (item.name_en || id || '—');
            var latest = item.series && item.series[0];
            var val = latest ? latest.value : '—';
            var unit = (latest && latest.unit) || item.unit || '';
            if (id === 'cpi') unit = '';
            if (id === 'eci' && unit && unit.toLowerCase() === 'index') unit = '';
            if (unit && unit.toLowerCase() === 'thousands') unit = 'K';
            var unitText = unit ? ' ' + escapeHtml(unit) : '';
            parts.push(escapeHtml(label) + ' ' + escapeHtml(val) + unitText);
        });
        return (
            '<div class="header-admin-latest-title">' +
            '<span class="header-admin-latest-line">' + (parts.length ? parts.join(' / ') : '—') + '</span>' +
            '</div>'
        );
    }

    function getBlsLatestPeriod(data) {
        var bestKey = 0;
        var bestLabel = '';
        (data || []).forEach(function (item) {
            var key = 0;
            var label = '';
            if (item && item.series && item.series[0] && item.series[0].period) {
                key = parseInt(item.series[0].period, 10) || 0;
                label = formatPeriod(item.series[0].period);
            }
            if (key >= bestKey) {
                bestKey = key;
                bestLabel = label;
            }
        });
        return bestLabel;
    }

    function renderUsaspendingCompactBody(data) {
        if (!data) return '<span class="text-muted">—</span>';
        var parts = [];
        var trend = data.total_budget_trend || [];
        if (trend.length > 0) {
            var t = trend[0];
            var amt = t.total_budgetary_resources;
            parts.push('FY' + (t.fiscal_year || '') + ' Total $' + formatNumber(amt));
        }
        var agencies = data.agency_rankings || [];
        if (agencies.length > 0) {
            var a = agencies[0];
            var amt2 = a.current_total_budget_authority_amount || a.obligation_total;
            parts.push('Top Agency ' + escapeHtml(a.abbreviation || a.agency_name || '—') + ' $' + formatNumber(amt2));
        }
        var awards = data.award_trends || {};
        var awardResults = awards.results || awards;
        if (awardResults && typeof awardResults === 'object') {
            var contracts = awardResults.contract || awardResults.contracts;
            var grants = awardResults.grant || awardResults.grants;
            var awardsParts = [];
            if (contracts != null) awardsParts.push('Contracts ' + formatNumber(contracts.count || contracts));
            if (grants != null) awardsParts.push('Grants ' + formatNumber(grants.count || grants));
            if (awardsParts.length) parts.push(awardsParts.join(' / '));
        }
        if (!parts.length) return '<span class="text-muted">—</span>';
        var firstLine = parts[0] || '—';
        var secondLine = parts[1] || '';
        var thirdLine = parts[2] || '';
        return (
            '<div class="header-admin-latest-title">' +
            '<span class="header-admin-latest-line">' + firstLine + '</span>' +
            (secondLine ? '<span class="header-admin-latest-line">' + secondLine + '</span>' : '') +
            (thirdLine ? '<span class="header-admin-latest-line">' + thirdLine + '</span>' : '') +
            '</div>'
        );
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

    var BLS_CARD_STYLE = {
        cpi: { header: 'bg-primary text-white', icon: 'fa-chart-line' },
        unemployment: { header: 'bg-warning text-dark', icon: 'fa-user-clock' },
        employment: { header: 'bg-info text-white', icon: 'fa-briefcase' },
        jolts_openings: { header: 'bg-success text-white', icon: 'fa-door-open' },
        jolts_hires: { header: 'bg-success text-white', icon: 'fa-user-plus' },
        jolts_quits: { header: 'bg-secondary text-white', icon: 'fa-sign-out-alt' },
        eci: { header: 'bg-dark text-white', icon: 'fa-yen-sign' },
        construction_emp: { header: 'bg-info text-white', icon: 'fa-hard-hat' },
    };

    function renderBlsCard(item) {
        var rows = (item.series || []).slice(0, 12).map(function (s) {
            return '<tr><td>' + escapeHtml(formatPeriod(s.period)) + '</td><td>' + escapeHtml(s.value) + '</td><td class="text-muted small">' + escapeHtml(s.unit || '') + '</td></tr>';
        }).join('');
        var tableHtml = rows
            ? '<div class="card trend-table category-card"><div class="card-body"><div class="trend-table-container"><div class="table-responsive"><table class="table table-hover trend-table mb-0"><thead class="table-dark"><tr><th>Period</th><th>Value</th><th>Unit</th></tr></thead><tbody>' + rows + '</tbody></table></div></div></div></div>'
            : '<p class="text-muted small mb-0">No data available.</p>';
        var style = BLS_CARD_STYLE[item.indicator_id] || { header: 'bg-secondary text-white', icon: 'fa-chart-bar' };
        var title = escapeHtml(item.name_en || item.indicator_id || '');
        return (
            '<article class="col-12 col-md-6 col-lg-4" aria-label="' + title + '">' +
            '  <div class="card h-100">' +
            '    <div class="card-header ' + style.header + ' py-2"><h2 class="h6 mb-0"><i class="fas ' + style.icon + '"></i> ' + title + '</h2></div>' +
            '    <div class="card-body p-2">' + tableHtml + '</div>' +
            '  </div>' +
            '</article>'
        );
    }

    var US_TOP_CASES_LABELS = { ai: 'AI / IT', dx: 'DX / IT Services', cyber: 'Cybersecurity' };
    var US_TOP_CASES_ORDER = ['ai', 'dx', 'cyber'];

    function renderUsaspendingBody(data) {
        if (!data) return '';
        var html = [];

        // 1行2列: Annual Total Spending | Agency Spending Rankings（最初に表示）
        var trend = data.total_budget_trend || [];
        var agencies = data.agency_rankings || [];
        var trendCard = '';
        var agencyCard = '';

        if (trend.length > 0) {
            var trendRows = trend.slice(0, 8).map(function (r) {
                var amt = r.total_budgetary_resources;
                return '<tr><td>FY' + (r.fiscal_year || '') + '</td><td class="text-end">' + formatNumber(amt) + ' USD</td></tr>';
            }).join('');
            trendCard = '<div class="card h-100">' +
                '<div class="card-header bg-primary text-white py-2"><h5 class="h6 mb-0"><i class="fas fa-chart-area"></i> Annual Total Spending (FY-end)</h5></div>' +
                '<div class="card-body"><div class="card trend-table category-card"><div class="card-body"><div class="trend-table-container"><div class="table-responsive"><table class="table table-hover trend-table mb-0"><thead class="table-dark"><tr><th>Fiscal Year</th><th class="text-end">Total (approx)</th></tr></thead><tbody id="usGovTrendTrendsTableBody">' + trendRows + '</tbody></table></div></div></div></div></div></div>';
        }
        if (agencies.length > 0) {
            var agencyRows = agencies.map(function (a) {
                var amt = a.current_total_budget_authority_amount || a.obligation_total;
                return '<tr><td>' + a.rank + '</td><td>' + escapeHtml(a.agency_name || a.abbreviation || '') + '</td><td class="text-end">' + formatNumber(amt) + '</td></tr>';
            }).join('');
            agencyCard = '<div class="card h-100">' +
                '<div class="card-header bg-info text-white py-2"><h5 class="h6 mb-0"><i class="fas fa-building"></i> Agency Spending Rankings (FY2025)</h5></div>' +
                '<div class="card-body"><div class="card trend-table category-card"><div class="card-body"><div class="trend-table-container"><div class="table-responsive"><table class="table table-hover trend-table mb-0"><thead class="table-dark"><tr><th>Rank</th><th>Agency</th><th class="text-end">Budget (approx)</th></tr></thead><tbody id="usGovAgencyTrendsTableBody">' + agencyRows + '</tbody></table></div></div></div></div></div></div>';
        }
        if (trendCard || agencyCard) {
            html.push('<div class="row g-3 mb-3 align-items-stretch"><div class="col-12 col-md-6">' + trendCard + '</div><div class="col-12 col-md-6">' + agencyCard + '</div></div>');
        }

        // Top5 事例（PSC/NAICS）: その下に表示。カード下部が切れないよう構造を簡素化
        var keywordTopCases = data.keyword_top_cases || {};
        var categoryLabels = data.category_labels || US_TOP_CASES_LABELS;
        var categoryOrder = data.category_order || US_TOP_CASES_ORDER;
        var hasTopCases = (keywordTopCases.ai && keywordTopCases.ai.length > 0) ||
            (keywordTopCases.dx && keywordTopCases.dx.length > 0) ||
            (keywordTopCases.cyber && keywordTopCases.cyber.length > 0);
        if (hasTopCases) {
            var caseRows = [];
            categoryOrder.forEach(function (key) {
                var cases = keywordTopCases[key] || [];
                cases.forEach(function (c) {
                    var title = (c.title || '').substring(0, 80) + (c.title && c.title.length > 80 ? '\u2026' : '');
                    var linkCell = c.url
                        ? '<a href="' + escapeHtml(c.url) + '" target="_blank" rel="noopener noreferrer" class="text-decoration-none">' + escapeHtml(title) + '</a>'
                        : escapeHtml(title);
                    caseRows.push('<tr><td>' + escapeHtml(categoryLabels[key] || key) + '</td><td class="text-end">' + c.rank + '</td><td class="small">' + linkCell + '</td><td class="small text-muted">' + escapeHtml(c.organization || '') + '</td><td class="small">' + escapeHtml(c.obligation_date || '') + '</td><td class="small">' + escapeHtml(c.state || '') + '</td></tr>');
                });
            });
            var caseTable = '<div class="card mb-3">' +
                '<div class="card-header bg-dark text-white py-2"><h5 class="h6 mb-0"><i class="fas fa-file-contract"></i> Top 5 Awards by Category (PSC/NAICS)</h5></div>' +
                '<div class="card-body pb-3">' +
                '<div class="table-responsive" style="max-height: 380px; overflow-y: auto;">' +
                '<table class="table table-hover trend-table mb-2"><thead class="table-dark sticky-top"><tr><th>Category</th><th class="text-end">Rank</th><th>Description</th><th>Agency</th><th>Date</th><th>State</th></tr></thead><tbody id="usGovTopCasesTrendsTableBody">' +
                caseRows.join('') + '</tbody></table></div>' +
                '<p class="text-muted small mb-0">Source: USAspending.gov. AI: NAICS 541512/541511. DX: PSC Service/D. Cyber: PSC Service/D/DJ.</p></div></div>';
            html.push(caseTable);
        }

        // Award trends (Contracts, Grants, etc.)
        var awardTrends = data.award_trends || {};
        var awardResults = awardTrends.results || awardTrends;
        if (awardResults && typeof awardResults === 'object') {
            var awardParts = [];
            var keys = ['contract', 'grant', 'idv', 'loan', 'direct_payment', 'other', 'contracts', 'grants', 'idvs', 'loans'];
            keys.forEach(function (key) {
                var v = awardResults[key];
                if (v != null) {
                    var count = (typeof v === 'object') ? (v.count || v) : v;
                    var amt = (typeof v === 'object' && v.amount != null) ? v.amount : null;
                    var label = key.replace(/_/g, ' ');
                    var str = label + ': ' + formatNumber(count);
                    if (amt != null) str += ', $' + formatNumber(amt);
                    awardParts.push('<span class="me-3">' + escapeHtml(str) + '</span>');
                }
            });
            if (awardParts.length > 0) {
                html.push(
                    '<div class="card mb-3">' +
                    '<div class="card-header bg-success text-white py-2"><h5 class="h6 mb-0"><i class="fas fa-file-contract"></i> Award Count by Type (FY' + (awardTrends.fiscal_year || '2025') + ')</h5></div>' +
                    '<div class="card-body p-2"><p class="mb-0 small">' + awardParts.join('') + '</p></div></div>'
                );
            }
        }

        // Disaster overview
        var disaster = data.disaster_overview || {};
        if (disaster && !disaster.error) {
            var disasterHtml = '<p class="text-muted small mb-0">' + escapeHtml(disaster.message || 'Disaster/emergency funding data available via USAspending.') + '</p>';
            if (disaster.total_spending) {
                disasterHtml = '<p class="mb-0">Total disaster-related spending: ' + formatNumber(disaster.total_spending) + '</p>';
            }
            html.push(
                '<div class="card mb-3">' +
                '<div class="card-header bg-warning text-dark py-2"><h5 class="h6 mb-0"><i class="fas fa-cloud-showers-heavy"></i> Disaster/Emergency Funding</h5></div>' +
                '<div class="card-body p-2">' + disasterHtml + '</div></div>'
            );
        }

        return html.length ? html.join('') : '<p class="text-muted small">No spending data available.</p>';
    }

    function fetchAndRender(forceRefresh) {
        var url = '/api/us-admin-trends' + (forceRefresh ? '?force_refresh=true' : '');
        var loading = document.getElementById('us-gov-loading');
        var body = document.getElementById('us-gov-body');
        var blsCards = document.getElementById('us-bls-cards');
        var usaspendingCards = document.getElementById('us-usaspending-cards');
        var blsCompact = document.getElementById('header-estat-compact-body');
        var usaCompact = document.getElementById('header-kkj-compact-body');

        if (forceRefresh && loading) loading.style.display = 'block';
        if (forceRefresh && body) body.style.display = 'none';

        fetch(url)
            .then(function (res) { return res.json(); })
            .then(function (json) {
                if (loading) loading.style.display = 'none';
                if (body) body.style.display = 'block';

                // BLS
                var bls = json.bls || {};
                var blsData = (bls.success && bls.data && bls.data.length) ? bls.data : null;
                if (blsCards) {
                    blsCards.innerHTML = blsData
                        ? blsData.map(renderBlsCard).join('')
                        : SAMPLE_BLS.map(renderBlsCard).join('');
                }
                if (blsCompact) {
                    blsCompact.innerHTML = blsData
                        ? renderBlsCompactLatest(blsData)
                        : '<span class="text-muted">' + escapeHtml(bls.error || 'Data unavailable') + '</span>';
                    var periodEl = document.getElementById('header-estat-latest-period');
                    if (periodEl) {
                        var latestPeriod = blsData ? getBlsLatestPeriod(blsData) : '';
                        periodEl.textContent = latestPeriod ? ' (Latest: ' + escapeHtml(latestPeriod) + ')' : '';
                    }
                }

                // USAspending
                var usaspending = json.usaspending || {};
                var usData = (usaspending.success && usaspending.data) ? usaspending.data : null;
                if (usaspendingCards) {
                    usaspendingCards.innerHTML = usData
                        ? renderUsaspendingBody(usData)
                        : '<p class="text-muted small">' + escapeHtml(usaspending.error || 'Data unavailable') + '</p>';
                    if (usData && typeof applyCategoryAccordionForAllTables === 'function') {
                        setTimeout(function () { applyCategoryAccordionForAllTables(5); }, 50);
                    }
                }
                if (usaCompact) {
                    usaCompact.innerHTML = usData
                        ? renderUsaspendingCompactBody(usData)
                        : '<span class="text-muted">' + escapeHtml(usaspending.error || 'Data unavailable') + '</span>';
                }
                bindGotoTab();
            })
            .catch(function (err) {
                var msg = err && err.message ? err.message : 'Network error';
                if (loading) loading.style.display = 'none';
                if (body) body.style.display = 'block';
                if (blsCards) blsCards.innerHTML = '<div class="col-12"><div class="alert alert-danger mb-0">' + escapeHtml(msg) + '</div></div>';
                if (usaspendingCards) usaspendingCards.innerHTML = '';
                if (blsCompact) blsCompact.innerHTML = '<span class="text-muted">' + escapeHtml(msg) + '</span>';
                if (usaCompact) usaCompact.innerHTML = '<span class="text-muted">' + escapeHtml(msg) + '</span>';
                var periodEl = document.getElementById('header-estat-latest-period');
                if (periodEl) periodEl.textContent = '';
                bindGotoTab();
            });
    }

    function init() {
        fetchAndRender(false);
        // Lazy load: only fetch when Gov Data tab is shown
        var tabEl = document.getElementById('tab-govdata');
        if (tabEl) {
            tabEl.addEventListener('shown.bs.tab', function () {
                fetchAndRender(false);
            });
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
