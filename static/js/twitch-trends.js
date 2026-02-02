// Twitchトレンド関連の関数（共通化）
let twitchManager = null;

// ドロップダウンパターンの共通マネージャーを作成
if (typeof createDropdownTrendsManager === 'function') {
    twitchManager = createDropdownTrendsManager({
        serviceName: 'twitch',
        selectId: 'twitchTypeSelect',
        apiEndpoint: '/api/twitch-trends',
        defaultValue: 'games',
        paramName: 'type',
        uiIds: {
            loading: 'twitchTrendsLoading',
            results: 'twitchResults',
            tableBody: 'twitchTrendsTableBody',
            statusMessage: 'twitchStatusMessage',
            errorMessage: 'twitchErrorMessage'
        },
        displayFunction: displayTwitchResults,
        allPaneSync: { mainTableBodyId: 'twitchTrendsTableBody', allTableBodyId: 'all-twitchTrendsTableBody', limit: 5 }
    });
}

// 後方互換性のため、既存の関数名も保持
function fetchTwitchTrends() {
    if (twitchManager) {
        twitchManager.fetchTrends();
    }
}

function displayTwitchResults(data) {
    const tableBody = document.getElementById('twitchTrendsTableBody');
    tableBody.innerHTML = '';
    
    if (data.data && data.data.length > 0) {
        data.data.forEach(item => {
            const row = document.createElement('tr');
            
            // Twitchリンクを作成
            const twitchUrl = `https://www.twitch.tv/${item.user_name || item.name || ''}`;
            const streamName = item.name || item.title || 'N/A';
            const countCell = item.viewer_count ? `${item.viewer_count.toLocaleString()}人` : 'N/A';
            
            row.innerHTML = `
                <td><span class="badge bg-secondary">${item.rank}</span></td>
                <td><strong><a href="${twitchUrl}" target="_blank">${streamName}</a></strong></td>
                <td>${countCell}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, twitchUrl, `${streamName}のTwitch配信を開く`);
            tableBody.appendChild(row);
        });
        
        showTwitchResults();
    } else {
        showTwitchError('データが見つかりませんでした');
    }
}

// 後方互換性のため、既存の関数名も保持（共通マネージャーを使用）
function showTwitchLoading() {
    if (twitchManager) {
        twitchManager.showLoading();
    } else {
        const element = document.getElementById('twitchTrendsLoading');
        if (element) element.style.display = 'block';
    }
}

function hideTwitchLoading() {
    if (twitchManager) {
        twitchManager.hideLoading();
    } else {
        const element = document.getElementById('twitchTrendsLoading');
        if (element) element.style.display = 'none';
    }
}

function showTwitchResults() {
    if (twitchManager) {
        twitchManager.showResults();
    } else {
        const element = document.getElementById('twitchResults');
        if (element) element.style.display = 'block';
    }
}

function hideTwitchResults() {
    if (twitchManager) {
        twitchManager.hideResults();
    } else {
        const element = document.getElementById('twitchResults');
        if (element) element.style.display = 'none';
    }
}

function showTwitchStatusMessage(message, type = 'info') {
    const statusElement = document.getElementById('twitchStatusMessage');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.className = `alert alert-${type}`;
        statusElement.style.display = 'block';
    }
}

function showTwitchError(message) {
    if (twitchManager) {
        twitchManager.showError(message);
    } else {
        showTwitchStatusMessage(message, 'danger');
        showTwitchResults();
    }
}

