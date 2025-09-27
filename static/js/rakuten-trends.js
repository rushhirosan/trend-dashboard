// 楽天トレンドデータを取得
async function fetchRakutenTrends() {
    console.log('fetchRakutenTrends: 開始');
    
    // ローディング表示
    showRakutenLoading();
    hideRakutenResults();
    hideError();

    try {
        console.log('Rakuten API呼び出し: /api/rakuten-trends');
        
        const response = await fetch('/api/rakuten-trends');
        console.log('Rakuten API レスポンス受信:', response.status, response.ok);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Rakuten APIレスポンス:', data);
        
        if (data.error) {
            console.error('Rakuten API エラー:', data.error);
            showRakutenError(data.error);
            hideRakutenLoading();
            return;
        }
        
        // データの存在チェック
        if (!data.data || !Array.isArray(data.data)) {
            console.error('Rakuten API データ形式エラー:', data);
            showRakutenError('データの形式が正しくありません');
            hideRakutenLoading();
            return;
        }
        
        console.log('fetchRakutenTrends: データ表示開始');
        displayRakutenResults(data);
        hideRakutenLoading();
        console.log('fetchRakutenTrends: 完了');
        
    } catch (error) {
        console.error('Rakuten Trends取得エラー:', error);
        showRakutenError('楽天商品トレンドの取得に失敗しました: ' + error.message);
        hideRakutenLoading();
    } finally {
        hideRakutenLoading();
    }
}

// 楽天結果を表示
function displayRakutenResults(data) {
    const tableBody = document.getElementById('rakutenTrendsTableBody');
    const statusMessage = document.getElementById('rakutenStatusMessage');

    // ステータスアイコンを更新
    const statusIcon = document.getElementById('rakutenStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
    }

    // ステータスメッセージを更新
    if (data.status === 'fresh') {
        statusMessage.innerHTML = `<i class="fas fa-sync"></i> 楽天商品トレンドデータを新規取得しました！`;
    } else {
        statusMessage.innerHTML = `<i class="fas fa-info-circle"></i> 楽天商品トレンドデータを取得しました！`;
    }

    // テーブルを更新
    tableBody.innerHTML = '';
    data.data.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        
        // 価格をフォーマット
        const price = item.price ? `¥${item.price.toLocaleString()}` : '価格不明';
        
        // レビュー情報をフォーマット
        const reviewInfo = item.review_count > 0 
            ? `${item.review_average || 0}/5.0`
            : 'レビューなし';
        
        // レビュー数をフォーマット
        const reviewCount = item.review_count > 0 
            ? `${item.review_count}件`
            : '0件';
        
        // 楽天商品リンクを作成
        const rakutenUrl = item.url || '#';
        
        row.innerHTML = `
            <td><span class="badge bg-danger">${item.rank}</span></td>
            <td>
                <strong><a href="${rakutenUrl}" target="_blank" class="text-decoration-none">${item.title}</a></strong>
                ${item.image_url ? `<br><img src="${item.image_url}" alt="${item.title}" style="max-width: 50px; max-height: 50px;" class="mt-1">` : ''}
            </td>
            <td>${price}</td>
            <td>${reviewInfo}</td>
            <td>${reviewCount}</td>
            <td>${item.shop_name || '不明'}</td>
        `;
        tableBody.appendChild(row);
    });

    // 結果を表示
    showRakutenResults();
}

// 楽天ローディング表示
function showRakutenLoading() {
    const loadingElement = document.getElementById('rakutenLoading');
    const resultsElement = document.getElementById('rakutenResults');
    
    if (!loadingElement || !resultsElement) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    loadingElement.style.display = 'block';
    resultsElement.style.display = 'none';
}

// 楽天ローディング非表示
function hideRakutenLoading() {
    const loadingElement = document.getElementById('rakutenLoading');
    
    if (!loadingElement) {
        console.error('rakutenLoading要素が見つかりません');
        return;
    }
    
    loadingElement.style.display = 'none';
}

// 楽天結果表示
function showRakutenResults() {
    const resultsElement = document.getElementById('rakutenResults');
    
    if (!resultsElement) {
        console.error('rakutenResults要素が見つかりません');
        return;
    }
    
    resultsElement.style.display = 'block';
}

// 楽天結果非表示
function hideRakutenResults() {
    const resultsElement = document.getElementById('rakutenResults');
    
    if (!resultsElement) {
        console.error('rakutenResults要素が見つかりません');
        return;
    }
    
    resultsElement.style.display = 'none';
}

// 楽天エラー表示
function showRakutenError(message) {
    const errorElement = document.getElementById('errorMessage');
    
    if (!errorElement) {
        console.error('errorMessage要素が見つかりません');
        return;
    }
    
    errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    errorElement.style.display = 'block';
}
