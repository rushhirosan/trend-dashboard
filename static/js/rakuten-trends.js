// 楽天トレンド関連の関数（はてな同様 createDropdownTrendsManager で共通化）
let rakutenManager = null;

if (typeof createDropdownTrendsManager === 'function') {
    rakutenManager = createDropdownTrendsManager({
        serviceName: 'rakuten',
        selectId: 'rakutenGenreSelect',
        apiEndpoint: '/api/rakuten-trends',
        defaultValue: 'all',
        paramName: 'genre_id',
        storageKey: 'rakuten',
        uiIds: {
            loading: 'rakutenLoading',
            results: 'rakutenResults',
            tableBody: 'rakutenTrendsTableBody',
            statusMessage: 'rakutenStatusMessage',
            errorMessage: 'rakutenStatusMessage'
        },
        displayFunction: displayRakutenResults,
        getParams: () => ({}),
        allPaneSync: { mainTableBodyId: 'rakutenTrendsTableBody', allTableBodyId: 'all-rakutenTrendsTableBody', limit: 5, targetTabId: 'tab-entertainment' }
    });
}

function fetchRakutenTrends() {
    if (rakutenManager) {
        rakutenManager.fetchTrends();
    } else {
        const selectEl = document.getElementById('rakutenGenreSelect');
        const genreId = selectEl ? selectEl.value : 'all';
        showRakutenLoading();
        hideRakutenResults();
        fetch('/api/rakuten-trends?genre_id=' + encodeURIComponent(genreId) + '&limit=25')
            .then(r => r.json())
            .then(data => {
                hideRakutenLoading();
                if (data && !data.error && data.data && Array.isArray(data.data)) {
                    displayRakutenResults(data);
                } else {
                    showRakutenError(data && data.error ? data.error : 'データの取得に失敗しました');
                }
            })
            .catch(err => {
                hideRakutenLoading();
                showRakutenError(err.message || '楽天商品トレンドの取得に失敗しました');
            });
    }
}

function displayRakutenResults(data) {
    const tableBody = document.getElementById('rakutenTrendsTableBody');
    const statusMessage = document.getElementById('rakutenStatusMessage');
    if (!tableBody) return;

    if (statusMessage) {
        if (data.status === 'fresh') {
            statusMessage.innerHTML = `<i class="fas fa-sync"></i> 楽天商品トレンドデータを新規取得しました！`;
        } else {
            statusMessage.innerHTML = `<i class="fas fa-info-circle"></i> 楽天商品トレンドデータを取得しました！`;
        }
    }

    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach(item => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            const price = item.price ? `¥${item.price.toLocaleString()}` : '価格不明';
            const reviewInfo = item.review_count > 0 ? `${item.review_average || 0}/5.0` : 'レビューなし';
            const reviewCount = item.review_count > 0 ? `${item.review_count}件` : '0件';
            const rakutenUrl = item.url || '#';
            const displayTitle = item.title && item.title.length > 50 ? item.title.substring(0, 50) + '...' : item.title;
            row.innerHTML = `
                <td><span class="badge bg-danger">${item.rank}</span></td>
                <td>
                    <strong><a href="${rakutenUrl}" target="_blank" class="text-decoration-none" title="${item.title || ''}">${displayTitle || ''}</a></strong>
                </td>
                <td>${price}</td>
                <td>${reviewInfo}</td>
                <td>${reviewCount}</td>
                <td>${item.shop_name || '不明'}</td>
            `;
            if (typeof makeTableRowClickable === 'function') {
                makeTableRowClickable(row, rakutenUrl, (item.title || '') + 'の商品を開く');
            }
            tableBody.appendChild(row);
        });
        showRakutenResults();
    } else {
        if (statusMessage) {
            statusMessage.innerHTML = '<i class="fas fa-info-circle"></i> データがありません';
        }
        showRakutenResults();
    }
}

function showRakutenLoading() {
    const loadingElement = document.getElementById('rakutenLoading');
    const resultsElement = document.getElementById('rakutenResults');
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
}

function hideRakutenLoading() {
    const loadingElement = document.getElementById('rakutenLoading');
    if (loadingElement) loadingElement.style.display = 'none';
}

function showRakutenResults() {
    const resultsElement = document.getElementById('rakutenResults');
    if (resultsElement) resultsElement.style.display = 'block';
}

function hideRakutenResults() {
    const resultsElement = document.getElementById('rakutenResults');
    if (resultsElement) resultsElement.style.display = 'none';
}

function showRakutenError(message) {
    if (rakutenManager) {
        rakutenManager.showError(message);
    } else {
        const statusElement = document.getElementById('rakutenStatusMessage');
        if (statusElement) {
            statusElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
            statusElement.className = 'alert alert-danger';
            statusElement.style.display = 'block';
        }
        showRakutenResults();
    }
}
