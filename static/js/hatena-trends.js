// はてなブックマークトレンド関連の関数（共通化）
let hatenaManager = null;

// ドロップダウンパターンの共通マネージャーを作成
console.log('🔧 hatena-trends.js: スクリプト読み込み開始');
console.log('🔧 hatena-trends.js: createDropdownTrendsManager関数の存在確認:', typeof createDropdownTrendsManager);
if (typeof createDropdownTrendsManager === 'function') {
    console.log('✅ hatena-trends.js: createDropdownTrendsManager関数が見つかりました、マネージャーを作成します');
    hatenaManager = createDropdownTrendsManager({
        serviceName: 'hatena',
        selectId: 'hatenaCategorySelect',
        apiEndpoint: '/api/hatena-trends',
        defaultValue: 'all',
        paramName: 'category',
        uiIds: {
            loading: 'hatenaTrendsLoading',
            results: 'hatenaResults',
            tableBody: 'hatenaTrendsTableBody',
            statusMessage: 'hatenaStatusMessage',
            errorMessage: 'hatenaErrorMessage'
        },
        displayFunction: displayHatenaResults,
        getParams: (category) => ({ type: 'hot' })
    });
    console.log('✅ hatena-trends.js: hatenaManager作成完了', hatenaManager);
} else {
    console.error('❌ hatena-trends.js: createDropdownTrendsManager関数が見つかりません');
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
            
            // リンクを追加（他のセクションと同じ形式）
            const articleLink = item.url ? 
                `<br><a href="${item.url}" target="_blank" class="btn btn-sm btn-outline-warning mt-1">
                    <i class="fas fa-external-link-alt"></i> 記事を読む
                </a>` : '';
            
            row.innerHTML = `
                <td><span class="badge bg-warning">${item.rank || index + 1}</span></td>
                <td>
                    <strong>${item.title || 'N/A'}</strong>${articleLink}
                </td>
                <td><strong>${bookmarkInfo}</strong></td>
            `;
            tableBody.appendChild(row);
        });
        
        showHatenaResults();
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
