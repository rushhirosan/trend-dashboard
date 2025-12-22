// Podcastトレンド関連の関数
function fetchPodcastTrends(type = 'program') {
    showPodcastLoading();
    hidePodcastResults();
    
    fetch(`/api/podcast-trends?type=${type}&limit=25&force_refresh=false`)
        .then(response => response.json())
        .then(data => {
            hidePodcastLoading();
            if (data.success) {
                displayPodcastResults(data);
            } else {
                showPodcastError(data.error || 'Podcastトレンドの取得に失敗しました');
            }
        })
        .catch(error => {
            hidePodcastLoading();
            showPodcastError('ネットワークエラー: ' + error.message);
        });
}

function displayPodcastResults(data) {
    const tableBody = document.getElementById('podcastTrendsTableBody');
    tableBody.innerHTML = '';
    
    if (data.data && data.data.length > 0) {
        data.data.forEach(item => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            
            row.innerHTML = `
                <td><span class="badge bg-purple">${item.rank}</span></td>
                <td><strong>${item.title}</strong></td>
                <td>${item.description ? item.description.substring(0, 100) + '...' : '説明なし'}</td>
                <td>${item.score || 'N/A'}</td>
            `;
            tableBody.appendChild(row);
        });
        
        showPodcastResults();
    } else {
        showPodcastError('データが見つかりませんでした');
    }
}

// ポッドキャストローディング表示
function showPodcastLoading() {
    const loadingElement = document.getElementById('podcastLoading');
    const resultsElement = document.getElementById('podcastResults');
    
    if (!loadingElement || !resultsElement) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    loadingElement.style.display = 'block';
    resultsElement.style.display = 'none';
}

// ポッドキャストローディング非表示
function hidePodcastLoading() {
    const loadingElement = document.getElementById('podcastLoading');
    
    if (!loadingElement) {
        console.error('podcastLoading要素が見つかりません');
        return;
    }
    
    loadingElement.style.display = 'none';
}

// ポッドキャスト結果表示
function showPodcastResults() {
    const resultsElement = document.getElementById('podcastResults');
    
    if (!resultsElement) {
        console.error('podcastResults要素が見つかりません');
        return;
    }
    
    resultsElement.style.display = 'block';
}

// ポッドキャスト結果非表示
function hidePodcastResults() {
    const resultsElement = document.getElementById('podcastResults');
    
    if (!resultsElement) {
        console.error('podcastResults要素が見つかりません');
        return;
    }
    
    resultsElement.style.display = 'none';
}

// ポッドキャストエラー表示
function showPodcastError(message) {
    const errorElement = document.getElementById('errorMessage');
    
    if (!errorElement) {
        console.error('errorMessage要素が見つかりません');
        return;
    }
    
    errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    errorElement.style.display = 'block';
}

