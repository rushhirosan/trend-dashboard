// OpenAlex学術論文トレンド
let openalexManager = null;

if (typeof createDropdownTrendsManager === 'function') {
    openalexManager = createDropdownTrendsManager({
        serviceName: 'openalex',
        selectId: 'openalexCategorySelect',
        apiEndpoint: '/api/openalex-trends',
        defaultValue: 'trending',
        paramName: 'category',
        storageKey: 'openalex',
        getParams: () => ({ region: 'jp' }),  // 日本トレンド: 日本の研究機関に所属する論文
        uiIds: {
            loading: 'openalexLoading',
            results: 'openalexResults',
            tableBody: 'openalexTrendsTableBody',
            statusMessage: 'openalexStatusMessage',
            errorMessage: 'openalexStatusMessage'
        },
        displayFunction: displayOpenAlexResults,
        allPaneSync: { mainTableBodyId: 'openalexTrendsTableBody', allTableBodyId: 'all-openalexTrendsTableBody', limit: 5 }
    });
}

function fetchOpenAlexTrends() {
    if (openalexManager) {
        openalexManager.fetchTrends();
    }
}

function displayOpenAlexResults(data) {
    const tableBody = document.getElementById('openalexTrendsTableBody');
    if (!tableBody) return;
    tableBody.innerHTML = '';

    const items = (data && data.data && Array.isArray(data.data)) ? data.data : [];
    if (items.length > 0) {
        items.forEach(item => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            const url = item.url || (item.doi ? `https://doi.org/${item.doi.replace('https://doi.org/', '')}` : `https://openalex.org/${item.work_id || ''}`);
            const title = item.title || 'タイトルなし';
            const citedBy = item.cited_by_count != null ? item.cited_by_count.toLocaleString() : 'N/A';
            row.innerHTML = `
                <td><span class="badge bg-secondary">${item.rank || '-'}</span></td>
                <td><strong><a href="${url}" target="_blank" rel="noopener noreferrer" class="text-decoration-none">${escapeHtml(title)}</a></strong></td>
                <td>${citedBy}</td>
            `;
            makeTableRowClickable(row, url, `${title}を開く`);
            tableBody.appendChild(row);
        });
        showOpenAlexResults();
        if (typeof syncToAllPane === 'function') {
            setTimeout(() => syncToAllPane('openalexTrendsTableBody', 'all-openalexTrendsTableBody', 5), 0);
        }
        if (typeof applyCategoryAccordionForAllTables === 'function') {
            setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
        }
    } else {
        showOpenAlexError('データが見つかりませんでした');
    }
}

function showOpenAlexLoading() {
    const el = document.getElementById('openalexLoading');
    if (el) el.style.display = 'block';
}

function hideOpenAlexLoading() {
    const el = document.getElementById('openalexLoading');
    if (el) el.style.display = 'none';
}

function showOpenAlexResults() {
    const el = document.getElementById('openalexResults');
    if (el) el.style.display = 'block';
}

function hideOpenAlexResults() {
    const el = document.getElementById('openalexResults');
    if (el) el.style.display = 'none';
}

function showOpenAlexError(message) {
    if (openalexManager && openalexManager.showError) {
        openalexManager.showError(message);
    } else {
        const statusEl = document.getElementById('openalexStatusMessage');
        if (statusEl) {
            statusEl.textContent = message;
            statusEl.className = 'alert alert-danger';
            statusEl.style.display = 'block';
        }
        showOpenAlexResults();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
