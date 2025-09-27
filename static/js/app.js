// グローバル変数
let currentGoogleChart = null;
let currentYouTubeChart = null;
let currentMusicChart = null;

// Google Trendsデータを取得
async function fetchGoogleTrends() {
    console.log('fetchGoogleTrends: 開始');
    
    const country = 'JP'; // 日本固定
    
    console.log('fetchGoogleTrends: パラメータ', { country });
    
    // ローディング表示
    showGoogleLoading();
    console.log('fetchGoogleTrends: ローディング表示完了');
    
    try {
        console.log(`Google API呼び出し: /api/google-trends?country=${country}`);
        
        const response = await fetch(`/api/google-trends?country=${country}`);
        console.log('Google API レスポンス受信:', response.status, response.ok);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Google APIレスポンス:', data);
        
        if (data.error) {
            console.error('Google API エラー:', data.error);
            showGoogleError(data.error);
            hideGoogleLoading();
            return;
        }
        
        // データの存在チェックを改善
        if (!data.data || !Array.isArray(data.data)) {
            console.error('Google API データ形式エラー:', data);
            console.error('データキー:', Object.keys(data));
            console.error('データの型:', typeof data.data);
            showGoogleError('データの形式が正しくありません');
            hideGoogleLoading();
            return;
        }
        
        console.log('fetchGoogleTrends: データ表示開始');
        displayGoogleResults(data);
        hideGoogleLoading();
        console.log('fetchGoogleTrends: 完了');
        
    } catch (error) {
        console.error('Google Trends取得エラー:', error);
        showGoogleError('Google Trendsの取得に失敗しました: ' + error.message);
        hideGoogleLoading();
    } finally {
        // 確実にローディングを停止
        console.log('fetchGoogleTrends: finally処理開始');
        hideGoogleLoading();
        console.log('fetchGoogleTrends: finally処理完了');
    }
}

// YouTube Trendsデータを取得
async function fetchYouTubeTrends() {
    console.log('fetchYouTubeTrends: 開始');
    
    const region = 'JP'; // 日本固定
    const trendType = document.querySelector('input[name="youtubeTrendType"]:checked').value;
    
    console.log('fetchYouTubeTrends: パラメータ', { region, trendType });
    
    // ローディング表示
    showYouTubeLoading();
    console.log('fetchYouTubeTrends: ローディング表示完了');
    
    try {
        const endpoint = trendType === 'rising' ? '/api/youtube-rising-trends' : '/api/youtube-trends';
        console.log(`YouTube API呼び出し: ${endpoint}?region=${region}`);
        
        const response = await fetch(`${endpoint}?region=${region}`);
        console.log('YouTube API レスポンス受信:', response.status, response.ok);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('YouTube APIレスポンス:', data);
        
        if (data.error) {
            console.error('YouTube API エラー:', data.error);
            showYouTubeError(data.error);
            hideYouTubeLoading();
            return;
        }
        
        // データの存在チェックを改善
        if (!data.data || !Array.isArray(data.data)) {
            console.error('YouTube API データ形式エラー:', data);
            console.error('データキー:', Object.keys(data));
            console.error('データの型:', typeof data.data);
            showYouTubeError('データの形式が正しくありません');
            hideYouTubeLoading();
            return;
        }
        
        console.log('fetchYouTubeTrends: データ表示開始');
        displayYouTubeResults(data);
        hideYouTubeLoading();
        console.log('fetchYouTubeTrends: 完了');
        
    } catch (error) {
        console.error('YouTube Trends取得エラー:', error);
        showYouTubeError('YouTube Trendsの取得に失敗しました: ' + error.message);
        hideYouTubeLoading();
    } finally {
        // 確実にローディングを停止
        console.log('fetchYouTubeTrends: finally処理開始');
        hideYouTubeLoading();
        console.log('fetchYouTubeTrends: finally処理完了');
    }
}

// 音楽トレンドデータを取得
async function fetchMusicTrends() {
    console.log('=== fetchMusicTrends関数が呼び出されました ===');
    console.log('fetchMusicTrends: 開始');
    
    // Spotifyに固定
    const service = 'spotify';
    
    console.log('fetchMusicTrends: パラメータ', { service });
    
    try {
        console.log(`音楽API呼び出し: /api/music-trends?service=${service}`);
        
        const response = await fetch(`/api/music-trends?service=${service}`);
        console.log('音楽API レスポンス受信:', response.status, response.ok);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('音楽APIレスポンス:', data);
        
        if (data.error) {
            console.error('音楽API エラー:', data.error);
            showMusicError(data.error);
            return;
        }
        
        // データの存在チェックを改善
        if (!data.data || !Array.isArray(data.data)) {
            console.error('音楽API データ形式エラー:', data);
            console.error('データキー:', Object.keys(data));
            console.error('データの型:', typeof data.data);
            showMusicError('データの形式が正しくありません');
            return;
        }
        
        console.log('fetchMusicTrends: データ表示開始');
        displayMusicResults(data);
        console.log('fetchMusicTrends: 完了');
        
    } catch (error) {
        console.error('音楽トレンド取得エラー:', error);
        showMusicError('音楽トレンドの取得に失敗しました: ' + error.message);
    }
}

// テスト関数


// Google Trends結果を表示
function displayGoogleResults(data) {
    console.log('displayGoogleResults: 開始', data);
    
    const tableBody = document.getElementById('googleTrendsTableBody');
    const statusMessage = document.getElementById('googleStatusMessage');
    const country = 'JP'; // 日本固定
    
    console.log('displayGoogleResults: 要素取得完了', {
        tableBody: !!tableBody,
        statusMessage: !!statusMessage,
        country: country
    });
    
    // ステータスアイコンを更新
    const statusIcon = document.getElementById('googleStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    // テーブルを更新
    console.log('displayGoogleResults: テーブル更新開始', { dataLength: data.data.length });
    tableBody.innerHTML = '';
    data.data.forEach((trend, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        row.style.minHeight = '100px';
        
        // Google検索リンクを追加
        console.log(`displayGoogleResults: 行${index + 1}の検索URL確認`, {
            keyword: trend.keyword,
            google_search_url: trend.google_search_url
        });
        
        const searchLink = trend.google_search_url ? 
            `<a href="${trend.google_search_url}" target="_blank" class="btn btn-sm btn-outline-primary">
                <i class="fab fa-google"></i> 検索
            </a>` : 
            `<button class="btn btn-sm btn-outline-secondary" disabled>
                <i class="fas fa-search"></i> 検索URLなし
            </button>`;
        
        row.innerHTML = `
            <td><span class="badge bg-primary">${index + 1}</span></td>
            <td><strong>${trend.keyword || trend.term || 'N/A'}</strong></td>
            <td><strong>${trend.score.toLocaleString()}</strong></td>
            <td>${searchLink}</td>
        `;
        tableBody.appendChild(row);
        
        if (index < 3) { // 最初の3件のみログ出力
            console.log(`displayGoogleResults: 行${index + 1}追加完了`, {
                rank: index + 1,
                keyword: trend.keyword,
                term: trend.term,
                score: trend.score
            });
        }
    });

    // グラフを更新
    console.log('displayGoogleResults: グラフ更新開始');
    updateGoogleChart(data.data);

    // 結果を表示
    console.log('displayGoogleResults: 結果表示開始');
    showGoogleResults();
    console.log('displayGoogleResults: 完了');
}

// YouTube Trends結果を表示
function displayYouTubeResults(data) {
    console.log('displayYouTubeResults: 開始', data);
    
    const tableBody = document.getElementById('youtubeTrendsTableBody');
    const statusMessage = document.getElementById('youtubeStatusMessage');
    const region = 'JP'; // 日本固定
    
    console.log('displayYouTubeResults: 要素取得完了', {
        tableBody: !!tableBody,
        statusMessage: !!statusMessage,
        region: region
    });
    
    // ステータスアイコンを更新
    const statusIcon = document.getElementById('youtubeStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    // テーブルを更新
    console.log('displayYouTubeResults: テーブル更新開始', { dataLength: data.data.length });
    tableBody.innerHTML = '';
    data.data.forEach((video, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        row.style.minHeight = '100px';
        
        // 追加情報を表示
        let additionalInfo = '';
        if (video.days_since_published !== undefined && video.days_since_published !== null) {
            const daysText = video.days_since_published === 1 ? '1日前' : `${video.days_since_published}日前`;
            additionalInfo = `<br><small class="text-muted">投稿: ${daysText}</small>`;
        }
        
        // YouTubeリンクを作成
        const youtubeUrl = `https://www.youtube.com/watch?v=${video.video_id}`;
        
        row.innerHTML = `
            <td><span class="badge bg-danger">${video.rank}</span></td>
            <td><a href="${youtubeUrl}" target="_blank" class="text-decoration-none"><strong>${video.title}</strong></a>${additionalInfo}</td>
            <td>${video.channel_title}</td>
            <td><strong>${formatViewCount(video.view_count)}</strong></td>
        `;
        tableBody.appendChild(row);
        
        if (index < 3) { // 最初の3件のみログ出力
            console.log(`displayYouTubeResults: 行${index + 1}追加完了`, {
                rank: video.rank,
                title: video.title.substring(0, 30) + '...',
                channel: video.channel_title
            });
        }
    });

    // グラフを更新
    console.log('displayYouTubeResults: グラフ更新開始');
    updateYouTubeChart(data.data);

    // 結果を表示
    console.log('displayYouTubeResults: 結果表示開始');
    showYouTubeResults();
    console.log('displayYouTubeResults: 完了');
}

// 音楽トレンド結果を表示
function displayMusicResults(data) {
    console.log('🎵 displayMusicResults: 開始', data);
    
    const tableBody = document.getElementById('musicTrendsTableBody');
    const statusMessage = document.getElementById('musicStatusMessage');
    const resultsElement = document.getElementById('musicResults');
    
    console.log('🎵 displayMusicResults: 要素取得完了', {
        tableBody: !!tableBody,
        statusMessage: !!statusMessage,
        resultsElement: !!resultsElement,
        dataLength: data.data ? data.data.length : 0
    });
    
    if (!tableBody) {
        console.error('❌ musicTrendsTableBody要素が見つかりません');
        return;
    }
    
    if (!resultsElement) {
        console.error('❌ musicResults要素が見つかりません');
        return;
    }
    
    // ステータスアイコンを更新
    const statusIcon = document.getElementById('musicStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    // テーブルを更新
    console.log('displayMusicResults: テーブル更新開始', { dataLength: data.data.length });
    tableBody.innerHTML = '';
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        row.style.minHeight = '100px';
        
        // 人気度を表示（Spotifyではplay_countの代わりにpopularityを使用）
        const popularity = item.popularity || 0;
        
        // 追加情報を表示
        let additionalInfo = '';
        if (item.days_since_published !== undefined) {
            const daysText = item.days_since_published === 1 ? '1日前' : `${item.days_since_published}日前`;
            additionalInfo = `<br><small class="text-muted">投稿: ${daysText}</small>`;
        }
        
        // Spotifyリンクを作成
        const spotifyUrl = item.spotify_url || `https://open.spotify.com/search/${encodeURIComponent(item.title + ' ' + item.artist)}`;
        
        row.innerHTML = `
            <td><span class="badge bg-success">${item.rank}</span></td>
            <td><a href="${spotifyUrl}" target="_blank" class="text-decoration-none"><strong>${item.title}</strong></a>${additionalInfo}</td>
            <td>${item.artist}</td>
            <td><strong>${popularity}</strong></td>
        `;
        tableBody.appendChild(row);
        
        if (index < 3) { // 最初の3件のみログ出力
            console.log(`displayMusicResults: 行${index + 1}追加完了`, {
                rank: item.rank,
                title: item.title.substring(0, 30) + '...',
                artist: item.artist
            });
        }
    });

    // グラフを更新
    console.log('displayMusicResults: グラフ更新開始');
    updateMusicChart(data.data);

    // 結果を表示
    console.log('🎵 displayMusicResults: 結果表示開始');
    showMusicResults();
    console.log('🎵 displayMusicResults: 完了 - テーブル行数:', tableBody.children.length);
}

// 視聴回数をフォーマット
function formatViewCount(count) {
    if (count >= 1000000) {
        return (count / 1000000).toFixed(1) + 'M';
    } else if (count >= 1000) {
        return (count / 1000).toFixed(1) + 'K';
    } else {
        return count.toString();
    }
}

// 再生回数をフォーマット
function formatPlayCount(count) {
    if (count >= 1000000) {
        return (count / 1000000).toFixed(1) + 'M';
    } else if (count >= 1000) {
        return (count / 1000).toFixed(1) + 'K';
    } else {
        return count.toString();
    }
}

// Google Trendsグラフを更新
function updateGoogleChart(data) {
    const chartElement = document.getElementById('googleTrendsChart');
    
    // グラフ要素が存在しない場合はスキップ
    if (!chartElement) {
        console.log('Google Trends グラフ要素が見つかりません。テーブル表示のみを使用します。');
        return;
    }
    
    const ctx = chartElement.getContext('2d');
    
    // 既存のグラフを破棄
    if (currentGoogleChart) {
        currentGoogleChart.destroy();
    }

    // 新しいグラフを作成
    currentGoogleChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(item => item.term),
            datasets: [{
                label: 'スコア',
                data: data.map(item => item.score),
                backgroundColor: 'rgba(54, 162, 235, 0.8)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'スコア'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'キーワード'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// YouTube Trendsグラフを更新
function updateYouTubeChart(data) {
    const chartElement = document.getElementById('youtubeTrendsChart');
    
    // グラフ要素が存在しない場合はスキップ
    if (!chartElement) {
        console.log('YouTube Trends グラフ要素が見つかりません。テーブル表示のみを使用します。');
        return;
    }
    
    const ctx = chartElement.getContext('2d');
    
    // 既存のグラフを破棄
    if (currentYouTubeChart) {
        currentYouTubeChart.destroy();
    }

    // 新しいグラフを作成
    currentYouTubeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(item => item.title),
            datasets: [{
                label: '視聴回数',
                data: data.map(item => item.view_count),
                backgroundColor: 'rgba(255, 99, 132, 0.8)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: '視聴回数'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '動画タイトル'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// 音楽トレンドグラフを更新
function updateMusicChart(data) {
    const chartElement = document.getElementById('musicTrendsChart');
    
    // グラフ要素が存在しない場合はスキップ
    if (!chartElement) {
        console.log('Music Trends グラフ要素が見つかりません。テーブル表示のみを使用します。');
        return;
    }
    
    const ctx = chartElement.getContext('2d');
    
    // 既存のグラフを破棄
    if (currentMusicChart) {
        currentMusicChart.destroy();
    }

    // 新しいグラフを作成
    currentMusicChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(item => item.title),
            datasets: [{
                label: '再生回数',
                data: data.map(item => item.play_count),
                backgroundColor: 'rgba(75, 192, 192, 0.8)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: '再生回数'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '曲名'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Google Trendsローディング表示
function showGoogleLoading() {
    const loadingElement = document.getElementById('googleLoading');
    const resultsElement = document.getElementById('googleResults');
    const errorElement = document.getElementById('googleErrorMessage');
    
    if (!loadingElement || !resultsElement || !errorElement) {
        console.error('必要なDOM要素が見つかりません:', {
            loading: !!loadingElement,
            results: !!resultsElement,
            error: !!errorElement
        });
        return;
    }
    
    loadingElement.style.display = 'block';
    resultsElement.style.display = 'none';
    errorElement.style.display = 'none';
}

// Google Trendsローディング非表示
function hideGoogleLoading() {
    const loadingElement = document.getElementById('googleLoading');
    
    if (!loadingElement) {
        console.error('googleLoading要素が見つかりません');
        return;
    }
    
    loadingElement.style.display = 'none';
}

// Google Trends結果表示
function showGoogleResults() {
    const resultsElement = document.getElementById('googleResults');
    const errorElement = document.getElementById('googleErrorMessage');
    
    if (!resultsElement || !errorElement) {
        console.error('必要なDOM要素が見つかりません:', {
            results: !!resultsElement,
            error: !!errorElement
        });
        return;
    }
    
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
}

// Google Trendsエラー表示
function showGoogleError(message) {
    const errorElement = document.getElementById('googleErrorMessage');
    const resultsElement = document.getElementById('googleResults');
    
    if (!errorElement || !resultsElement) {
        console.error('必要なDOM要素が見つかりません:', {
            error: !!errorElement,
            results: !!resultsElement
        });
        return;
    }
    
    errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    errorElement.style.display = 'block';
    resultsElement.style.display = 'none';
}

// YouTube Trendsローディング表示
function showYouTubeLoading() {
    const loadingElement = document.getElementById('youtubeLoading');
    const resultsElement = document.getElementById('youtubeResults');
    const errorElement = document.getElementById('youtubeErrorMessage');
    
    if (!loadingElement || !resultsElement || !errorElement) {
        console.error('必要なDOM要素が見つかりません:', {
            loading: !!loadingElement,
            results: !!resultsElement,
            error: !!errorElement
        });
        return;
    }
    
    loadingElement.style.display = 'block';
    resultsElement.style.display = 'none';
    errorElement.style.display = 'none';
}

// YouTube Trendsローディング非表示
function hideYouTubeLoading() {
    const loadingElement = document.getElementById('youtubeLoading');
    
    if (!loadingElement) {
        console.error('youtubeLoading要素が見つかりません');
        return;
    }
    
    loadingElement.style.display = 'none';
}

// YouTube Trends結果表示
function showYouTubeResults() {
    const resultsElement = document.getElementById('youtubeResults');
    const errorElement = document.getElementById('youtubeErrorMessage');
    
    if (!resultsElement || !errorElement) {
        console.error('必要なDOM要素が見つかりません:', {
            results: !!resultsElement,
            error: !!errorElement
        });
        return;
    }
    
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
}

// YouTube Trendsエラー表示
function showYouTubeError(message) {
    const errorElement = document.getElementById('youtubeErrorMessage');
    const resultsElement = document.getElementById('youtubeResults');
    
    if (!errorElement || !resultsElement) {
        console.error('必要なDOM要素が見つかりません:', {
            error: !!errorElement,
            results: !!resultsElement
        });
        return;
    }
    
    errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    errorElement.style.display = 'block';
    resultsElement.style.display = 'none';
}

// 音楽トレンド結果表示
function showMusicResults() {
    console.log('🎵 showMusicResults: 開始');
    const resultsElement = document.getElementById('musicResults');
    const errorElement = document.getElementById('musicErrorMessage');
    
    console.log('🎵 showMusicResults: 要素確認', {
        results: !!resultsElement,
        error: !!errorElement
    });
    
    if (!resultsElement || !errorElement) {
        console.error('❌ 必要なDOM要素が見つかりません:', {
            results: !!resultsElement,
            error: !!errorElement
        });
        return;
    }
    
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    console.log('🎵 showMusicResults: 表示完了 - display:', resultsElement.style.display);
}

// 音楽トレンドエラー表示
function showMusicError(message) {
    const errorElement = document.getElementById('musicErrorMessage');
    const resultsElement = document.getElementById('musicResults');
    
    if (!errorElement || !resultsElement) {
        console.error('必要なDOM要素が見つかりません:', {
            error: !!errorElement,
            results: !!resultsElement
        });
        return;
    }
    
    errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    errorElement.style.display = 'block';
    resultsElement.style.display = 'none';
}

// 国名を取得
function getCountryName(countryCode) {
    const countryNames = {
        'JP': '日本',
        'US': 'アメリカ',
        'GB': 'イギリス'
    };
    return countryNames[countryCode] || countryCode;
}

// エラーを表示
function hideError() {
    const errorElement = document.getElementById('errorMessage');
    if (errorElement) {
        errorElement.style.display = 'none';
    }
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DOMContentLoaded: 初期化開始 ===');
    
    // 要素の存在確認
    const elements = {
        googleLoading: document.getElementById('googleLoading'),
        googleResults: document.getElementById('googleResults'),
        youtubeLoading: document.getElementById('youtubeLoading'),
        youtubeResults: document.getElementById('youtubeResults'),
        musicResults: document.getElementById('musicResults')
    };
    
    console.log('要素の存在確認:', elements);
    
    // 初期取得は無効化（ユーザーがボタンをクリックした時のみ取得）
    console.log('初期自動取得は無効化されています');
    
    // YouTubeトレンドタイプラジオボタンの監視
    const youtubeTrendTypeRadios = document.querySelectorAll('input[name="youtubeTrendType"]');
    youtubeTrendTypeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            console.log('YouTubeトレンドタイプ変更:', this.value);
            fetchYouTubeTrends();
        });
    });
    
    console.log('YouTubeトレンドタイプラジオボタン:', youtubeTrendTypeRadios.length, '件');
    
    // YouTube地域選択は削除済み（日本固定）
    
    console.log('=== 初期化完了 ===');
});

// News API トレンド取得
async function fetchNewsTrends() {
    console.log('=== News API トレンド取得開始 ===');
    
    const resultsElement = document.getElementById('newsResults');
    const statusMessage = document.getElementById('newsStatusMessage');
    const errorElement = document.getElementById('newsErrorMessage');
    const tableBody = document.getElementById('newsTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('必要なDOM要素が見つかりません:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    try {
        // 結果表示エリアを表示
        resultsElement.style.display = 'block';
        errorElement.style.display = 'none';
        
        // ステータスメッセージを更新
        statusMessage.innerHTML = '<i class="fas fa-spinner fa-spin"></i> News トレンドデータを取得中...';
        
        // API呼び出し（日本固定）
        const response = await fetch('/api/news-trends?country=jp&category=general');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (!data.success) {
            throw new Error(data.error || '不明なエラーが発生しました');
        }
        
        console.log('News API 成功:', data);
        
        // 結果を表示
        displayNewsResults(data);
        
    } catch (error) {
        console.error('News API エラー:', error);
        showNewsError(error.message);
    }
}

// World News API トレンド取得
async function fetchWorldNewsTrends() {
    console.log('=== World News API トレンド取得開始 ===');
    
    const resultsElement = document.getElementById('newsResults');
    const statusMessage = document.getElementById('newsStatusMessage');
    const errorElement = document.getElementById('newsErrorMessage');
    const tableBody = document.getElementById('newsTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('必要なDOM要素が見つかりません:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    try {
        // 結果表示エリアを表示
        resultsElement.style.display = 'block';
        errorElement.style.display = 'none';
        
        // ステータスメッセージを更新
        statusMessage.innerHTML = '<i class="fas fa-spinner fa-spin"></i> World News APIからニューストレンドデータを取得中...';
        
        // API呼び出し（日本固定）
        const response = await fetch('/api/worldnews-trends?country=jp&category=general');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (!data.success) {
            throw new Error(data.error || '不明なエラーが発生しました');
        }
        
        console.log('World News API 成功:', data);
        
        // 結果を表示
        displayWorldNewsResults(data);
        
    } catch (error) {
        console.error('World News API エラー:', error);
        showNewsError(error.message);
    }
}

// World News API トレンド結果を表示
function displayWorldNewsResults(data) {
    console.log('displayWorldNewsResults: 開始', data);
    
    const tableBody = document.getElementById('newsTrendsTableBody');
    const statusMessage = document.getElementById('newsStatusMessage');
    
    if (!tableBody || !statusMessage) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    // ステータスアイコンを更新
    const statusIcon = document.getElementById('newsStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    data.data.forEach((news, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        row.style.minHeight = '100px';
        
        // ニュースリンクを追加
        const newsLink = news.url ? 
            `<br><a href="${news.url}" target="_blank" class="btn btn-sm btn-outline-success">
                <i class="fas fa-external-link-alt"></i> 記事を読む
            </a>` : '';
        
        row.innerHTML = `
            <td><span class="badge bg-info">${news.rank}</span></td>
            <td><strong>${news.title}</strong>${newsLink}</td>
            <td>${news.source}</td>
            <td><strong>${news.score}</strong></td>
        `;
        tableBody.appendChild(row);
    });
    
    // グラフを更新
    updateNewsChart(data.data);
    
    // 結果を表示
    showNewsResults();
}

// News トレンド結果を表示
function displayNewsResults(data) {
    console.log('displayNewsResults: 開始', data);
    
    const tableBody = document.getElementById('newsTrendsTableBody');
    const statusMessage = document.getElementById('newsStatusMessage');
    
    if (!tableBody || !statusMessage) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    // ステータスメッセージを更新（アイコンのみ）
    if (data.status === 'fresh') {
        statusMessage.innerHTML = `<i class="fas fa-sync text-success"></i>`;
    } else if (data.status === 'cached') {
        statusMessage.innerHTML = `<i class="fas fa-database text-info"></i>`;
    } else {
        statusMessage.innerHTML = `<i class="fas fa-info-circle text-primary"></i>`;
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    data.data.forEach((news, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        row.style.minHeight = '100px';
        
        // ニュースリンクを追加
        const newsLink = news.url ? 
            `<br><a href="${news.url}" target="_blank" class="btn btn-sm btn-outline-info">
                <i class="fas fa-external-link-alt"></i> 記事を読む
            </a>` : '';
        
        row.innerHTML = `
            <td><span class="badge bg-info">${news.rank}</span></td>
            <td><strong>${news.title}</strong>${newsLink}</td>
            <td>${news.source}</td>
            <td><strong>${news.score}</strong></td>
        `;
        tableBody.appendChild(row);
    });
    
    // グラフを更新
    updateNewsChart(data.data);
    
    // 結果を表示
    showNewsResults();
}

// News トレンドグラフを更新
function updateNewsChart(data) {
    const ctx = document.getElementById('newsTrendsChart');
    if (!ctx) {
        console.error('News トレンドグラフのキャンバスが見つかりません');
        return;
    }
    
    // 既存のグラフを破棄
    if (window.newsChart) {
        window.newsChart.destroy();
    }
    
    const chartData = {
        labels: data.slice(0, 10).map(item => `${item.rank}. ${item.title.substring(0, 20)}...`),
        datasets: [{
            label: 'News トレンドスコア',
            data: data.slice(0, 10).map(item => item.score),
            backgroundColor: 'rgba(23, 162, 184, 0.6)',
            borderColor: 'rgba(23, 162, 184, 1)',
            borderWidth: 2
        }]
    };
    
    window.newsChart = new Chart(ctx, {
        type: 'bar',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'スコア'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'ニュース'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'News トレンド スコア分布'
                }
            }
        }
    });
}

// News トレンド結果表示
function showNewsResults() {
    const resultsElement = document.getElementById('newsResults');
    const errorElement = document.getElementById('newsErrorMessage');
    
    if (!resultsElement || !errorElement) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
}

// News トレンドエラー表示
function showNewsError(message) {
    const errorElement = document.getElementById('newsErrorMessage');
    const resultsElement = document.getElementById('newsResults');
    
    if (!errorElement || !resultsElement) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    errorElement.style.display = 'block';
    resultsElement.style.display = 'none';
}

// Podcast トレンドデータを取得
async function fetchPodcastTrends(trendType) {
    hidePodcastResults(trendType);
    hideError();

    try {
        const response = await fetch(`/api/podcast-trends?trend_type=${trendType}`);
        const data = await response.json();

        if (data.success) {
            displayPodcastResults(data, trendType);
        } else {
            showPodcastError(data, trendType);
        }
    } catch (error) {
        showPodcastError({ error: 'ネットワークエラーが発生しました' }, trendType);
    }
}

// Podcast 結果を表示
function displayPodcastResults(data, trendType) {
    const resultsDiv = document.getElementById(`podcast${trendType.charAt(0).toUpperCase() + trendType.slice(1)}Results`);
    const statusMessage = document.getElementById(`podcast${trendType.charAt(0).toUpperCase() + trendType.slice(1)}StatusMessage`);
    const tableBody = document.getElementById(`podcast${trendType.charAt(0).toUpperCase() + trendType.slice(1)}TableBody`);

    // ステータスメッセージを更新
    if (data.status === 'fresh') {
        statusMessage.innerHTML = `<i class="fas fa-sync"></i> Podcast ${trendType === 'program' ? '番組ランキング' : '急上昇ワード'}データを新規取得しました！`;
    } else {
        statusMessage.innerHTML = `<i class="fas fa-info-circle"></i> Podcast ${trendType === 'program' ? '番組ランキング' : '急上昇ワード'}データを取得しました！`;
    }

    // テーブルを更新
    tableBody.innerHTML = '';
    data.data.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        
        if (trendType === 'program') {
            row.innerHTML = `
                <td><span class="badge bg-warning">${item.rank}</span></td>
                <td><strong>${item.title}</strong></td>
                <td>${item.description || '説明なし'}</td>
                <td>${item.publisher || '不明'}</td>
                <td>${item.language || '不明'}</td>
            `;
        } else {
            row.innerHTML = `
                <td><span class="badge bg-warning">${item.rank}</span></td>
                <td><span class="badge bg-warning">${item.rank}</span></td>
                <td><strong>${item.title}</strong></td>
                <td>${item.description || '説明なし'}</td>
                <td>${item.score || 'N/A'}</td>
            `;
        }
        tableBody.appendChild(row);
    });

    // 結果を表示
    resultsDiv.style.display = 'block';
}

// Podcast エラーを表示
function showPodcastError(data, trendType) {
    const errorMessage = document.getElementById(`podcast${trendType.charAt(0).toUpperCase() + trendType.slice(1)}ErrorMessage`);
    errorMessage.textContent = data.error || 'エラーが発生しました';
    errorMessage.style.display = 'block';
}

// Podcast 結果を非表示
function hidePodcastResults(trendType) {
    const resultsDiv = document.getElementById(`podcast${trendType.charAt(0).toUpperCase() + trendType.slice(1)}Results`);
    resultsDiv.style.display = 'none';
}

// シンプルなポッドキャスト表示関数（HTMLテンプレート用）
async function fetchPodcastTrends() {
    console.log('fetchPodcastTrends: 開始');
    
    // ローディング表示
    showPodcastLoading();
    hidePodcastResults();
    hideError();

    try {
        console.log('Podcast API呼び出し: /api/podcast-trends?trend_type=best_podcasts');
        
        const response = await fetch('/api/podcast-trends?trend_type=best_podcasts');
        console.log('Podcast API レスポンス受信:', response.status, response.ok);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Podcast APIレスポンス:', data);
        
        if (data.error) {
            console.error('Podcast API エラー:', data.error);
            showPodcastError(data.error);
            hidePodcastLoading();
            return;
        }
        
        // データの存在チェック
        if (!data.data || !Array.isArray(data.data)) {
            console.error('Podcast API データ形式エラー:', data);
            showPodcastError('データの形式が正しくありません');
            hidePodcastLoading();
            return;
        }
        
        console.log('fetchPodcastTrends: データ表示開始');
        displayPodcastResults(data);
        hidePodcastLoading();
        console.log('fetchPodcastTrends: 完了');
        
    } catch (error) {
        console.error('Podcast Trends取得エラー:', error);
        showPodcastError('Podcast Trendsの取得に失敗しました: ' + error.message);
        hidePodcastLoading();
    } finally {
        hidePodcastLoading();
    }
}

// シンプルなポッドキャスト結果表示
function displayPodcastResults(data) {
    const tableBody = document.getElementById('podcastTrendsTableBody');
    const statusMessage = document.getElementById('podcastStatusMessage');

    // ステータスメッセージを更新
    if (data.status === 'fresh') {
        statusMessage.innerHTML = `<i class="fas fa-sync"></i> Podcast 番組ランキングデータを新規取得しました！`;
    } else {
        statusMessage.innerHTML = `<i class="fas fa-info-circle"></i> Podcast 番組ランキングデータを取得しました！`;
    }

    // テーブルを更新
    tableBody.innerHTML = '';
    data.data.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        
        row.innerHTML = `
            <td><span class="badge bg-warning">${item.rank}</span></td>
            <td><strong>${item.title}</strong></td>
            <td>${item.description ? item.description.substring(0, 100) + '...' : '説明なし'}</td>
            <td>${item.score || 'N/A'}</td>
        `;
        tableBody.appendChild(row);
    });

    // 結果を表示
    showPodcastResults();
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
            ? `${item.review_average || 0}/5.0 (${item.review_count}件)`
            : 'レビューなし';
        
        // 売上情報をフォーマット
        const salesInfo = item.sales_rank && item.sales_rank !== 'N/A' 
            ? `ランク: ${item.sales_rank}`
            : item.sales_count && item.sales_count !== 'N/A'
            ? `売上: ${item.sales_count}`
            : '売上情報なし';
        
        row.innerHTML = `
            <td><span class="badge bg-danger">${item.rank}</span></td>
            <td>
                <strong>${item.title}</strong>
                ${item.image_url ? `<br><img src="${item.image_url}" alt="${item.title}" style="max-width: 50px; max-height: 50px;" class="mt-1">` : ''}
            </td>
            <td>${price}</td>
            <td>${reviewInfo}</td>
            <td>${salesInfo}</td>
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

// はてなブックマークトレンド関連の関数
function fetchHatenaTrends() {
    showHatenaLoading();
    hideHatenaResults();
    
    fetch('/api/hatena-trends?category=all&limit=25&type=hot')
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
    document.getElementById('hatenaLoading').style.display = 'block';
}

function hideHatenaLoading() {
    document.getElementById('hatenaLoading').style.display = 'none';
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