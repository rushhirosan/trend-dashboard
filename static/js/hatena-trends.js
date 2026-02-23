// はてなブックマークトレンド関連の関数（共通化）
let hatenaManager = null;

// ドロップダウンパターンの共通マネージャーを作成
if (typeof createDropdownTrendsManager === 'function') {
    hatenaManager = createDropdownTrendsManager({
        serviceName: 'hatena',
        selectId: 'hatenaCategorySelect',
        apiEndpoint: '/api/hatena-trends',
        defaultValue: 'all',
        paramName: 'category',
        storageKey: 'hatena',
        uiIds: {
            loading: 'hatenaTrendsLoading',
            results: 'hatenaResults',
            tableBody: 'hatenaTrendsTableBody',
            statusMessage: 'hatenaStatusMessage',
            errorMessage: 'hatenaErrorMessage'
        },
        displayFunction: displayHatenaResults,
        getParams: (category) => ({ type: 'hot' }),
        allPaneSync: { mainTableBodyId: 'hatenaTrendsTableBody', allTableBodyId: 'all-hatenaTrendsTableBody', limit: 5 }
    });
}

// 後方互換性のため、既存の関数名も保持
function fetchHatenaTrends() {
    if (hatenaManager) {
        hatenaManager.fetchTrends();
    }
}

function displayHatenaResults(data) {
    const tableBody = document.getElementById('hatenaTrendsTableBody');
    if (!tableBody) {
        console.error('hatenaTrendsTableBodyが見つかりません');
        return;
    }

    tableBody.innerHTML = '';

    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            row.style.minHeight = '100px';

            // ブックマーク数をフォーマット
            const bookmarkCount = item.bookmark_count || 0;
            const bookmarkInfo = bookmarkCount > 0 ? `${bookmarkCount.toLocaleString()}件` : '0件';

            const articleUrl = item.url || '#';
            const articleTitle = item.title || 'N/A';

            // 行全体がリンク（makeTableRowClickable）のため「記事を読む」ボタンは不要
            row.innerHTML = `
                <td><span class="badge bg-warning">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${articleUrl}" target="_blank">${articleTitle}</a></strong>
                </td>
                <td><strong>${bookmarkInfo}</strong></td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, articleUrl, `${articleTitle}の記事を開く`);
            tableBody.appendChild(row);
        });

        showHatenaResults();
        if (typeof applyCategoryAccordionForAllTables === 'function') {
            setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
        }
    } else {
        showHatenaError('データが見つかりませんでした');
    }
}

// 後方互換性のため、既存の関数名も保持（共通マネージャーを使用）
function showHatenaLoading() {
    if (hatenaManager) {
        hatenaManager.showLoading();
    } else {
        const element = document.getElementById('hatenaTrendsLoading');
        if (element) element.style.display = 'block';
    }
}

function hideHatenaLoading() {
    if (hatenaManager) {
        hatenaManager.hideLoading();
    } else {
        const element = document.getElementById('hatenaTrendsLoading');
        if (element) element.style.display = 'none';
    }
}

function showHatenaResults() {
    if (hatenaManager) {
        hatenaManager.showResults();
    } else {
        const element = document.getElementById('hatenaResults');
        if (element) element.style.display = 'block';
    }
}

function hideHatenaResults() {
    if (hatenaManager) {
        hatenaManager.hideResults();
    } else {
        const element = document.getElementById('hatenaResults');
        if (element) element.style.display = 'none';
    }
}

function showHatenaStatusMessage(message, type = 'info') {
    const statusElement = document.getElementById('hatenaStatusMessage');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.className = `alert alert-${type}`;
        statusElement.style.display = 'block';
    }
}

function showHatenaError(message) {
    if (hatenaManager) {
        hatenaManager.showError(message);
    } else {
        showHatenaStatusMessage(message, 'danger');
        showHatenaResults();
    }
}
