// Noteトレンド関連の関数
function fetchNoteTrends() {
    showNoteLoading();
    hideNoteResults();
    
    // 選択されたカテゴリーを取得
    const categorySelect = document.getElementById('noteCategorySelect');
    const selectedCategory = categorySelect ? categorySelect.value : 'all';
    
    console.log(`🔍 Note: カテゴリ '${selectedCategory}' のデータを取得中...`);
    
    fetch(`/api/note-trends?category=${selectedCategory}&limit=25`)
        .then(response => response.json())
        .then(data => {
            hideNoteLoading();
            console.log(`📊 Note: カテゴリ '${selectedCategory}' のデータ取得完了`, data);
            if (data.success) {
                displayNoteResults(data);
            } else {
                showNoteError(data.error || 'Noteトレンドの取得に失敗しました');
            }
        })
        .catch(error => {
            hideNoteLoading();
            console.error('❌ Note: エラー', error);
            showNoteError('ネットワークエラー: ' + error.message);
        });
}

// カテゴリ選択時のイベントリスナー
document.addEventListener('DOMContentLoaded', function() {
    const categorySelect = document.getElementById('noteCategorySelect');
    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
            console.log(`🔄 Note: カテゴリが '${this.value}' に変更されました`);
            fetchNoteTrends();
        });
    }
});

function displayNoteResults(data) {
    const tableBody = document.getElementById('noteTrendsTableBody');
    if (!tableBody) {
        console.error('noteTrendsTableBodyが見つかりません');
        return;
    }
    
    tableBody.innerHTML = '';
    
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            row.style.minHeight = '100px';
            
            // 公開日をフォーマット
            let publishedDate = 'N/A';
            if (item.published_date) {
                try {
                    const date = new Date(item.published_date);
                    publishedDate = date.toLocaleDateString('ja-JP', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit'
                    });
                } catch (e) {
                    publishedDate = item.published_date;
                }
            }
            
            // リンクを追加
            const articleLink = item.url ? 
                `<br><a href="${item.url}" target="_blank" class="btn btn-sm btn-outline-secondary mt-1">
                    <i class="fas fa-external-link-alt"></i> 記事を読む
                </a>` : '';
            
            row.innerHTML = `
                <td><span class="badge bg-secondary">${item.rank || index + 1}</span></td>
                <td>
                    <strong>${item.title || 'N/A'}</strong>${articleLink}
                </td>
                <td>${publishedDate}</td>
            `;
            tableBody.appendChild(row);
        });
        
        showNoteResults();
        showNoteStatusMessage(`✅ ${data.source || 'Note RSS'} - ${data.total_count || data.data.length}件のエントリーを取得しました`, 'success');
    } else {
        showNoteError('データが見つかりませんでした');
    }
}

function showNoteLoading() {
    const loadingElement = document.getElementById('noteLoading');
    if (loadingElement) loadingElement.style.display = 'block';
}

function hideNoteLoading() {
    const loadingElement = document.getElementById('noteLoading');
    if (loadingElement) loadingElement.style.display = 'none';
}

function showNoteResults() {
    const resultsElement = document.getElementById('noteResults');
    if (resultsElement) resultsElement.style.display = 'block';
}

function hideNoteResults() {
    const resultsElement = document.getElementById('noteResults');
    if (resultsElement) resultsElement.style.display = 'none';
}

function showNoteStatusMessage(message, type = 'info') {
    const statusElement = document.getElementById('noteStatusMessage');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.className = `alert alert-${type}`;
        statusElement.style.display = 'block';
    }
}

function showNoteError(message) {
    showNoteStatusMessage(message, 'danger');
    showNoteResults();
}

