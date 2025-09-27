// はてなブックマークトレンド関連の関数
function fetchHatenaTrends() {
    showHatenaLoading();
    hideHatenaResults();
    
    // 選択されたカテゴリーを取得
    const categorySelect = document.getElementById('hatenaCategorySelect');
    const selectedCategory = categorySelect ? categorySelect.value : 'all';
    
    fetch(`/api/hatena-trends?category=${selectedCategory}&limit=25&type=hot`)
        .then(response => response.json())
        .then(data => {
            hideHatenaLoading();
            if (data.success) {
                displayHatenaResults(data);
            } else {
                showHatenaError(data.error || 'はてなブックマークトレンドの取得に失敗しました');
            }
        })
        .catch(error => {
            hideHatenaLoading();
            showHatenaError('ネットワークエラー: ' + error.message);
        });
}

function displayHatenaResults(data) {
    const tableBody = document.getElementById('hatenaTrendsTableBody');
    tableBody.innerHTML = '';
    
    if (data.data && data.data.length > 0) {
        data.data.forEach(item => {
            const row = document.createElement('tr');
            
            // ブックマーク数をフォーマット
            const bookmarkCount = item.bookmark_count || 0;
            const bookmarkInfo = bookmarkCount > 0 ? `${bookmarkCount}件` : '0件';
            
            row.innerHTML = `
                <td><span class="badge bg-info">${item.rank}</span></td>
                <td>
                    <strong>${item.title}</strong>
                    <br>
                    <small class="text-muted">${item.description || ''}</small>
                    <br>
                    <a href="${item.url}" target="_blank" class="btn btn-sm btn-outline-info mt-1">
                        <i class="fas fa-external-link-alt"></i> 記事を読む
                    </a>
                </td>
                <td>${bookmarkInfo}</td>
                <td>${item.category || '不明'}</td>
                <td>${item.author || '不明'}</td>
            `;
            tableBody.appendChild(row);
        });
        
        showHatenaResults();
        showHatenaStatusMessage(`✅ ${data.source} - ${data.total_count}件のエントリーを取得しました`, 'success');
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
