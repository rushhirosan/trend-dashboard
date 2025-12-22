// はてなブックマークトレンド関連の関数
function fetchHatenaTrends() {
    showHatenaLoading();
    hideHatenaResults();
    
    // 選択されたカテゴリーを取得
    const categorySelect = document.getElementById('hatenaCategorySelect');
    const selectedCategory = categorySelect ? categorySelect.value : 'all';
    
    console.log(`🔍 はてなブックマーク: カテゴリ '${selectedCategory}' のデータを取得中...`);
    
    fetch(`/api/hatena-trends?category=${selectedCategory}&limit=25&type=hot`)
        .then(response => response.json())
        .then(data => {
            hideHatenaLoading();
            console.log(`📊 はてなブックマーク: カテゴリ '${selectedCategory}' のデータ取得完了`, data);
            if (data.success) {
                displayHatenaResults(data);
            } else {
                showHatenaError(data.error || 'はてなブックマークトレンドの取得に失敗しました');
            }
        })
        .catch(error => {
            hideHatenaLoading();
            console.error('❌ はてなブックマーク: エラー', error);
            showHatenaError('ネットワークエラー: ' + error.message);
        });
}

// カテゴリ選択時のイベントリスナー
document.addEventListener('DOMContentLoaded', function() {
    const categorySelect = document.getElementById('hatenaCategorySelect');
    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
            console.log(`🔄 はてなブックマーク: カテゴリが '${this.value}' に変更されました`);
            fetchHatenaTrends();
        });
    }
});

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
        showHatenaStatusMessage(`✅ ${data.source} - ${data.total_count || data.data.length}件のエントリーを取得しました`, 'success');
    } else {
        showHatenaError('データが見つかりませんでした');
    }
}

function showHatenaLoading() {
    document.getElementById('hatenaTrendsLoading').style.display = 'block';
}

function hideHatenaLoading() {
    document.getElementById('hatenaTrendsLoading').style.display = 'none';
}

function showHatenaResults() {
    document.getElementById('hatenaResults').style.display = 'block';
}

function hideHatenaResults() {
    document.getElementById('hatenaResults').style.display = 'none';
}

function showHatenaStatusMessage(message, type = 'info') {
    const statusElement = document.getElementById('hatenaStatusMessage');
    statusElement.textContent = message;
    statusElement.className = `alert alert-${type}`;
    statusElement.style.display = 'block';
}

function showHatenaError(message) {
    showHatenaStatusMessage(message, 'danger');
    showHatenaResults();
}
