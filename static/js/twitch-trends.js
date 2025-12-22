// Twitchトレンド関連の関数
function fetchTwitchTrends() {
    showTwitchLoading();
    hideTwitchResults();
    
    // 選択されたトレンドタイプを取得
    const typeSelect = document.getElementById('twitchTypeSelect');
    const selectedType = typeSelect ? typeSelect.value : 'games';
    
    console.log(`🔍 Twitch: カテゴリ選択時のカテゴリ '${selectedType}' のデータを取得中...`);
    
    fetch(`/api/twitch-trends?type=${selectedType}&limit=25`)
        .then(response => response.json())
        .then(data => {
            hideTwitchLoading();
            if (data.success) {
                displayTwitchResults(data);
            } else {
                showTwitchError(data.error || 'Twitch トレンドの取得に失敗しました');
            }
        })
        .catch(error => {
            hideTwitchLoading();
            showTwitchError('ネットワークエラー: ' + error.message);
        });
}

// カテゴリ選択時のイベントリスナー
document.addEventListener('DOMContentLoaded', function() {
    const typeSelect = document.getElementById('twitchTypeSelect');
    if (typeSelect) {
        typeSelect.addEventListener('change', function() {
            console.log('🔍 Twitch: カテゴリ変更検出:', this.value);
            fetchTwitchTrends();
        });
    }
});

function displayTwitchResults(data) {
    const tableBody = document.getElementById('twitchTrendsTableBody');
    tableBody.innerHTML = '';
    
    if (data.data && data.data.length > 0) {
        data.data.forEach(item => {
            const row = document.createElement('tr');
            
            // シンプルな3カラム表示
            const titleCell = `<strong>${item.name || item.title}</strong>`;
            const countCell = item.viewer_count ? `${item.viewer_count.toLocaleString()}人` : 'N/A';
            
            row.innerHTML = `
                <td><span class="badge bg-secondary">${item.rank}</span></td>
                <td>${titleCell}</td>
                <td>${countCell}</td>
            `;
            tableBody.appendChild(row);
        });
        
        showTwitchResults();
        showTwitchStatusMessage(`✅ ${data.source} - ${data.total_count}件のトレンドを取得しました`, 'success');
    } else {
        showTwitchError('データが見つかりませんでした');
    }
}

function showTwitchLoading() {
    document.getElementById('twitchTrendsLoading').style.display = 'block';
}

function hideTwitchLoading() {
    document.getElementById('twitchTrendsLoading').style.display = 'none';
}

function showTwitchResults() {
    document.getElementById('twitchResults').style.display = 'block';
}

function hideTwitchResults() {
    document.getElementById('twitchResults').style.display = 'none';
}

function showTwitchStatusMessage(message, type = 'info') {
    const statusElement = document.getElementById('twitchStatusMessage');
    statusElement.textContent = message;
    statusElement.className = `alert alert-${type}`;
    statusElement.style.display = 'block';
}

function showTwitchError(message) {
    showTwitchStatusMessage(message, 'danger');
    showTwitchResults();
}

