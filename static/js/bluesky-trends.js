// Bluesky トレンド（What's Hot フィード、カテゴリ選択なし）
// 日本ページ(/): region=jp で日本語投稿、USページ(/us): region=us
function getBlueskyRegion() {
    const path = (window.location.pathname || '').toLowerCase();
    return path.includes('/us') ? 'us' : 'jp';
}
function fetchBlueskyTrends() {
    const loadingEl = document.getElementById('blueskyLoading');
    if (loadingEl) loadingEl.style.display = 'block';
    const region = getBlueskyRegion();
    fetch(`/api/bluesky-trends?limit=25&force_refresh=true&region=${region}`)
        .then(r => r.json())
        .then(data => {
            if (loadingEl) loadingEl.style.display = 'none';
            if (typeof displayBlueskyResults === 'function') displayBlueskyResults(data);
        })
        .catch(err => {
            if (loadingEl) loadingEl.style.display = 'none';
            if (typeof showBlueskyError === 'function') showBlueskyError(err.message || '取得に失敗しました');
        });
}

function displayBlueskyResults(data) {
    const tableBody = document.getElementById('blueskyTrendsTableBody');
    if (!tableBody) return;
    tableBody.innerHTML = '';

    const items = (data && data.data && Array.isArray(data.data)) ? data.data : [];
    if (items.length > 0) {
        items.forEach(item => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            const url = item.url || '#';
            const title = (item.title || '').substring(0, 80) + (item.title && item.title.length > 80 ? '…' : '');
            const user = item.user_display_name || item.user_handle || '—';
            const likes = item.like_count != null ? item.like_count.toLocaleString() : '0';
            row.innerHTML = `
                <td><span class="badge bg-secondary">${item.rank || '-'}</span></td>
                <td><strong><a href="${url}" target="_blank" rel="noopener noreferrer" class="text-decoration-none">${escapeHtmlBluesky(title || '(投稿)')}</a></strong></td>
                <td>${escapeHtmlBluesky(user)}</td>
                <td>${likes}</td>
            `;
            makeTableRowClickable(row, url, title + 'を開く');
            tableBody.appendChild(row);
        });
        showBlueskyResults();
        if (typeof syncToAllPane === 'function') {
            setTimeout(() => syncToAllPane('blueskyTrendsTableBody', 'all-blueskyTrendsTableBody', 5), 0);
        }
        if (typeof applyCategoryAccordionForAllTables === 'function') {
            setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
        }
    } else {
        showBlueskyError('データが見つかりませんでした');
    }
}

function showBlueskyLoading() {
    const el = document.getElementById('blueskyLoading');
    if (el) el.style.display = 'block';
}

function hideBlueskyLoading() {
    const el = document.getElementById('blueskyLoading');
    if (el) el.style.display = 'none';
}

function showBlueskyResults() {
    const el = document.getElementById('blueskyResults');
    if (el) el.style.display = 'block';
}

function hideBlueskyResults() {
    const el = document.getElementById('blueskyResults');
    if (el) el.style.display = 'none';
}

function showBlueskyError(message) {
    const statusEl = document.getElementById('blueskyStatusMessage');
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.className = 'alert alert-danger';
        statusEl.style.display = 'block';
    }
    showBlueskyResults();
}

function escapeHtmlBluesky(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
