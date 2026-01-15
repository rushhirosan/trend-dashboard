// グローバル変数
let currentGoogleChart = null;
let currentYouTubeChart = null;
let currentMusicChart = null;

// リトライ付きfetch関数（接続エラー時の自動リトライ）
async function fetchWithRetry(url, options = {}, maxRetries = 2) {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(url, options);
            // 500エラーやネットワークエラーもリトライ対象
            if (!response.ok && response.status >= 500 && attempt < maxRetries - 1) {
                console.warn(`⚠️ API呼び出しエラー (${response.status})。リトライします (試行 ${attempt + 1}/${maxRetries})`);
                await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1))); // 指数バックオフ
                continue;
            }
            return response;
        } catch (error) {
            if (attempt < maxRetries - 1) {
                console.warn(`⚠️ ネットワークエラーが発生しました: ${error.message}。リトライします (試行 ${attempt + 1}/${maxRetries})`);
                await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1))); // 指数バックオフ
                continue;
            }
            throw error;
        }
    }
}

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
        
        const response = await fetchWithRetry(`/api/google-trends?country=${country}`);
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
    // Rising機能は削除されたため、常にtop25を使用
    const trendType = 'top25';
    
    console.log('fetchYouTubeTrends: パラメータ', { region, trendType });
    
    // ローディング表示
    showYouTubeLoading();
    console.log('fetchYouTubeTrends: ローディング表示完了');
    
    try {
        const endpoint = '/api/youtube-trends';
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
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    // テーブルを更新
    console.log('displayYouTubeResults: テーブル更新開始', { dataLength: data.data.length });
    tableBody.innerHTML = '';
    
    // 視聴回数でソート（降順）
    const sortedData = [...data.data].sort((a, b) => {
        const viewCountA = a.view_count || 0;
        const viewCountB = b.view_count || 0;
        return viewCountB - viewCountA; // 降順ソート
    });
    
    sortedData.forEach((video, index) => {
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
            <td><span class="badge bg-danger">${index + 1}</span></td>
            <td><a href="${youtubeUrl}" target="_blank" class="text-decoration-none"><strong>${video.title}</strong></a>${additionalInfo}</td>
            <td>${video.channel_title}</td>
            <td><strong>${formatViewCount(video.view_count)}</strong></td>
        `;
        tableBody.appendChild(row);
        
        if (index < 3) { // 最初の3件のみログ出力
            console.log(`displayYouTubeResults: 行${index + 1}追加完了`, {
                rank: index + 1,
                view_count: video.view_count,
                title: video.title.substring(0, 30) + '...',
                channel: video.channel_title
            });
        }
    });

    // グラフを更新（ソート済みデータを使用）
    console.log('displayYouTubeResults: グラフ更新開始');
    updateYouTubeChart(sortedData);

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
    
    // インラインスタイルを上書き
    resultsElement.style.setProperty('display', 'block', 'important');
    errorElement.style.setProperty('display', 'none', 'important');
    console.log('🎵 showMusicResults: 表示完了 - display:', resultsElement.style.display);
    console.log('🎵 showMusicResults: computedStyle:', window.getComputedStyle(resultsElement).display);
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
    
    // キャッシュデータを自動読み込み
    console.log('loadCachedDataExternal関数の存在確認:', typeof loadCachedDataExternal);
    if (typeof loadCachedDataExternal === 'function') {
        console.log('✅ キャッシュデータの自動読み込みを開始します');
        try {
            loadCachedDataExternal();
        } catch (error) {
            console.error('❌ loadCachedDataExternal実行エラー:', error);
        }
    } else {
        console.warn('⚠️ loadCachedDataExternal関数が見つかりません');
        console.warn('利用可能な関数:', Object.keys(window).filter(k => k.includes('load') || k.includes('Load')));
    }
    
    // YouTube急上昇機能は削除されたため、ラジオボタンの監視は不要
    
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
        const response = await fetchWithRetry('/api/news-trends?country=jp&category=general');
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
        const response = await fetchWithRetry('/api/worldnews-trends?country=jp&category=general');
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
        
        // ニュースリンクを追加（他のセクションと同じ形式）
        const newsLink = news.url ? 
            `<br><a href="${news.url}" target="_blank" class="btn btn-sm btn-outline-info mt-1">
                <i class="fas fa-external-link-alt"></i> 記事を読む
            </a>` : '';
        
        // 公開日時をフォーマット
        const publishedDate = news.published_date || news.source || '';
        
        row.innerHTML = `
            <td><span class="badge bg-info">${news.rank || index + 1}</span></td>
            <td>
                <strong>${news.title || 'N/A'}</strong>${newsLink}
            </td>
            <td><small class="text-muted">${publishedDate}</small></td>
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
        const response = await fetch(`/api/podcast-trends?trend_type=${trendType}&force_refresh=false`);
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
                <td><span class="badge bg-warning">${index + 1}</span></td>
                <td><strong>${item.title}</strong></td>
                <td>${item.description || '説明なし'}</td>
                <td>${item.publisher || '不明'}</td>
                <td>${item.language || '不明'}</td>
            `;
        } else {
            row.innerHTML = `
                <td><span class="badge bg-warning">${index + 1}</span></td>
                <td><span class="badge bg-warning">${index + 1}</span></td>
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
        console.log('Podcast API呼び出し: /api/podcast-trends?trend_type=best_podcasts&force_refresh=false');
        
        const response = await fetchWithRetry('/api/podcast-trends?trend_type=best_podcasts&force_refresh=false');
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
    
    // エピソード数でソート（降順）、同じ場合はスコアでソート
    const sortedData = [...data.data].sort((a, b) => {
        const episodesA = a.total_episodes || 0;
        const episodesB = b.total_episodes || 0;
        const scoreA = a.score || 0;
        const scoreB = b.score || 0;
        if (episodesA !== episodesB) {
            return episodesB - episodesA; // エピソード数で降順ソート
        }
        return scoreB - scoreA; // 同じ場合はスコアで降順ソート
    });
    
    sortedData.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        
        row.innerHTML = `
            <td><span class="badge bg-warning">${index + 1}</span></td>
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
        
        const response = await fetchWithRetry('/api/rakuten-trends');
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
    
    // 売上数でソート（降順）、同じ場合はレビュー数でソート
    const sortedData = [...data.data].sort((a, b) => {
        // sales_countを数値に変換
        const salesCountA = typeof a.sales_count === 'number' ? a.sales_count : (typeof a.sales_count === 'string' && a.sales_count !== 'N/A' ? parseInt(a.sales_count) || 0 : 0);
        const salesCountB = typeof b.sales_count === 'number' ? b.sales_count : (typeof b.sales_count === 'string' && b.sales_count !== 'N/A' ? parseInt(b.sales_count) || 0 : 0);
        const reviewCountA = a.review_count || 0;
        const reviewCountB = b.review_count || 0;
        
        if (salesCountA !== salesCountB) {
            return salesCountB - salesCountA; // 売上数で降順ソート
        }
        return reviewCountB - reviewCountA; // 同じ場合はレビュー数で降順ソート
    });
    
    sortedData.forEach((item, index) => {
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
            <td><span class="badge bg-danger">${index + 1}</span></td>
            <td>
                <strong>${item.title}</strong>
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
    
    fetchWithRetry('/api/hatena-trends?category=all&limit=25&type=hot')
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
    if (!tableBody) {
        console.error('hatenaTrendsTableBodyが見つかりません');
        return;
    }
    
    tableBody.innerHTML = '';
    
    if (data.data && data.data.length > 0) {
        // ブックマーク数でソート（降順）
        const sortedData = [...data.data].sort((a, b) => {
            const bookmarkCountA = a.bookmark_count || 0;
            const bookmarkCountB = b.bookmark_count || 0;
            return bookmarkCountB - bookmarkCountA; // 降順ソート
        });
        
        sortedData.forEach((item, index) => {
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

// NHK ニュース トレンド取得
async function fetchNHKTrends() {
    console.log('=== NHK ニュース トレンド取得開始 ===');
    
    const resultsElement = document.getElementById('nhkResults');
    const statusMessage = document.getElementById('nhkStatusMessage');
    const errorElement = document.getElementById('nhkErrorMessage');
    const tableBody = document.getElementById('nhkTrendsTableBody');
    const loadingElement = document.getElementById('nhkLoading');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    try {
        // ローディング表示
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
        resultsElement.style.display = 'none';
        errorElement.style.display = 'none';
        
        // API呼び出し
        const response = await fetchWithRetry('/api/nhk-trends');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (!data.success) {
            throw new Error(data.error || '不明なエラーが発生しました');
        }
        
        console.log('NHK ニュース API 成功:', data);
        
        // ローディング非表示
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // 結果を表示
        displayNHKResults(data);
        
    } catch (error) {
        console.error('NHK ニュース API エラー:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        showNHKError(error.message);
    }
}

// NHK ニュース 結果表示
function displayNHKResults(data) {
    const resultsElement = document.getElementById('nhkResults');
    const tableBody = document.getElementById('nhkTrendsTableBody');
    const statusMessage = document.getElementById('nhkStatusMessage');
    
    if (!resultsElement || !tableBody) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    // テーブルをクリア
    tableBody.innerHTML = '';
    
    if (!data.data || data.data.length === 0) {
        showNHKError('データがありません');
        return;
    }
    
    // データを表示
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${item.url || '#'}" target="_blank" rel="noopener noreferrer">${item.title || 'タイトルなし'}</a></td>
            <td>${item.published_date ? new Date(item.published_date).toLocaleDateString('ja-JP') : '-'}</td>
        `;
        tableBody.appendChild(row);
    });
    
    // 結果を表示
    resultsElement.style.display = 'block';
    
    // ステータスメッセージは非表示（他のトレンドと統一）
    if (statusMessage) {
        statusMessage.style.display = 'none';
    }
}

function showNHKError(message) {
    const errorElement = document.getElementById('nhkErrorMessage');
    const resultsElement = document.getElementById('nhkResults');
    
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}

// Qiita トレンド取得
async function fetchQiitaTrends() {
    console.log('=== Qiita トレンド取得開始 ===');
    
    const resultsElement = document.getElementById('qiitaResults');
    const statusMessage = document.getElementById('qiitaStatusMessage');
    const errorElement = document.getElementById('qiitaErrorMessage');
    const tableBody = document.getElementById('qiitaTrendsTableBody');
    const loadingElement = document.getElementById('qiitaLoading');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    try {
        // ローディング表示
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
        resultsElement.style.display = 'none';
        errorElement.style.display = 'none';
        
        // API呼び出し
        const response = await fetchWithRetry('/api/qiita-trends?limit=25&sort=likes_count');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (!data.success) {
            throw new Error(data.error || '不明なエラーが発生しました');
        }
        
        console.log('Qiita トレンド API 成功:', data);
        
        // ローディング非表示
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // 結果を表示
        displayQiitaResults(data);
        
    } catch (error) {
        console.error('Qiita トレンド API エラー:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        showQiitaError(error.message);
    }
}

// Qiita トレンド 結果表示
function displayQiitaResults(data) {
    const resultsElement = document.getElementById('qiitaResults');
    const tableBody = document.getElementById('qiitaTrendsTableBody');
    const statusMessage = document.getElementById('qiitaStatusMessage');
    
    if (!resultsElement || !tableBody) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    // テーブルをクリア
    tableBody.innerHTML = '';
    
    if (!data.data || data.data.length === 0) {
        showQiitaError('データがありません');
        return;
    }
    
    // データを表示
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${item.rank || index + 1}</td>
            <td><a href="${item.url || '#'}" target="_blank" rel="noopener noreferrer">${item.title || 'タイトルなし'}</a></td>
            <td>${item.user_name || item.user_id || '-'}</td>
            <td>${item.likes_count || 0}</td>
        `;
        tableBody.appendChild(row);
    });
    
    // 結果を表示（重要度付きでインラインスタイルを設定）
    resultsElement.style.setProperty('display', 'block', 'important');
    
    // ステータスメッセージは非表示（他のトレンドと統一）
    if (statusMessage) {
        statusMessage.style.display = 'none';
    }
}

function showQiitaError(message) {
    const errorElement = document.getElementById('qiitaErrorMessage');
    const resultsElement = document.getElementById('qiitaResults');
    
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}

// 株価トレンド取得（日本）
async function fetchStockTrends() {
    console.log('=== 株価トレンド取得開始 ===');
    
    const loadingElement = document.getElementById('stockLoading');
    const resultsElement = document.getElementById('stockResults');
    const errorElement = document.getElementById('stockErrorMessage');
    const tableBody = document.getElementById('stockTrendsTableBody');
    
    if (!resultsElement || !errorElement || !tableBody) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    try {
        // ローディング表示
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
        resultsElement.style.display = 'none';
        errorElement.style.display = 'none';
        
        // API呼び出し（日本株）
        const response = await fetchWithRetry('/api/stock-trends?market=JP&limit=25');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        if (!data.data || !Array.isArray(data.data)) {
            throw new Error('データの形式が正しくありません');
        }
        
        // ローディング非表示
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // データ表示
        displayStockResults(data);
        
    } catch (error) {
        console.error('株価トレンド取得エラー:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        showStockError('株価トレンドの取得に失敗しました: ' + error.message);
    }
}

// 株価結果表示
function displayStockResults(data) {
    console.log('📊 株価結果表示開始', data);
    const tableBody = document.getElementById('stockTrendsTableBody');
    const resultsElement = document.getElementById('stockResults');
    const errorElement = document.getElementById('stockErrorMessage');
    
    if (!tableBody || !resultsElement) {
        console.error('❌ 株価 DOM要素が見つかりません');
        return;
    }
    
    // テーブルをクリア
    tableBody.innerHTML = '';
    
    // データが空の場合の処理
    if (!data.data || data.data.length === 0 || data.status === 'cache_not_found') {
        if (errorElement) {
            errorElement.textContent = '本日取引はありません';
            errorElement.style.display = 'block';
        }
        // 空のメッセージ行を表示
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = '<td colspan="4" class="text-center text-muted py-4">本日取引はありません</td>';
        tableBody.appendChild(emptyRow);
        resultsElement.style.setProperty('display', 'block', 'important');
        console.log('✅ 株価結果表示完了（データなし）');
        return;
    }
    
    // エラーメッセージを非表示
    if (errorElement) {
        errorElement.style.display = 'none';
    }
    
    // 変動率の絶対値でソート（降順）
    const sortedData = [...data.data].sort((a, b) => {
        const changeA = Math.abs(a.change_percent || 0);
        const changeB = Math.abs(b.change_percent || 0);
        return changeB - changeA;
    });
    
    sortedData.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        // 数値に変換（文字列の場合に対応）
        const changePercent = parseFloat(item.change_percent || 0);
        const changeClass = changePercent >= 0 ? 'text-danger' : 'text-primary';
        const changeSymbol = changePercent >= 0 ? '↑' : '↓';
        const price = parseFloat(item.current_price || 0);
        
        // 株価のリンクを生成（日本株はYahoo Finance JP、米国株はYahoo Finance US）
        const market = data.market || 'JP';
        const symbol = item.symbol || '';
        const stockUrl = market === 'JP' 
            ? `https://finance.yahoo.co.jp/quote/${symbol}.T`
            : `https://finance.yahoo.com/quote/${symbol}`;
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${stockUrl}" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><strong>${item.name || 'N/A'}</strong><br><small class="text-muted">${item.symbol || 'N/A'}</small></a></td>
            <td>¥${price.toLocaleString()}</td>
            <td class="${changeClass}"><strong>${changeSymbol} ${Math.abs(changePercent).toFixed(2)}%</strong></td>
        `;
        tableBody.appendChild(row);
    });
    
    // 結果を表示
    resultsElement.style.setProperty('display', 'block', 'important');
    console.log('✅ 株価結果表示完了');
}

function showStockError(message) {
    const errorElement = document.getElementById('stockErrorMessage');
    const resultsElement = document.getElementById('stockResults');
    
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}

// 仮想通貨トレンド取得
async function fetchCryptoTrends() {
    console.log('=== 仮想通貨トレンド取得開始 ===');
    
    const loadingElement = document.getElementById('cryptoLoading');
    const resultsElement = document.getElementById('cryptoResults');
    const errorElement = document.getElementById('cryptoErrorMessage');
    const tableBody = document.getElementById('cryptoTrendsTableBody');
    
    if (!resultsElement || !errorElement || !tableBody) {
        console.error('必要なDOM要素が見つかりません');
        return;
    }
    
    try {
        // ローディング表示
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
        resultsElement.style.display = 'none';
        errorElement.style.display = 'none';
        
        // API呼び出し
        const response = await fetchWithRetry('/api/crypto-trends?limit=25');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        if (!data.data || !Array.isArray(data.data)) {
            throw new Error('データの形式が正しくありません');
        }
        
        // ローディング非表示
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // データ表示
        displayCryptoResults(data);
        
    } catch (error) {
        console.error('仮想通貨トレンド取得エラー:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        showCryptoError('仮想通貨トレンドの取得に失敗しました: ' + error.message);
    }
}

// 仮想通貨結果表示
function displayCryptoResults(data) {
    console.log('📊 仮想通貨結果表示開始', data);
    console.log('📊 仮想通貨: 受信データ件数:', data.data ? data.data.length : 0);
    const tableBody = document.getElementById('cryptoTrendsTableBody');
    const resultsElement = document.getElementById('cryptoResults');
    
    if (!tableBody || !resultsElement) {
        console.error('❌ 仮想通貨 DOM要素が見つかりません', {
            tableBody: !!tableBody,
            resultsElement: !!resultsElement
        });
        return;
    }
    
    // テーブルをクリア
    tableBody.innerHTML = '';
    
    // データの存在確認
    if (!data.data || !Array.isArray(data.data) || data.data.length === 0) {
        console.warn('⚠️ 仮想通貨: 表示するデータがありません');
        return;
    }
    
    // 時価総額順でソート（market_cap_rankの昇順）
    const sortedData = [...data.data].sort((a, b) => {
        const rankA = a.market_cap_rank || 999999;
        const rankB = b.market_cap_rank || 999999;
        return rankA - rankB;
    });
    
    console.log('📊 仮想通貨: ソート後のデータ件数:', sortedData.length);
    
    sortedData.forEach((item, index) => {
        try {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            // 数値に変換（文字列の場合に対応）
            const changePercent = parseFloat(item.price_change_percentage_24h || 0);
            const changeClass = changePercent >= 0 ? 'text-danger' : 'text-primary';
            const changeSymbol = changePercent >= 0 ? '↑' : '↓';
            const price = parseFloat(item.current_price || 0);
            const priceFormatted = price < 0.01 ? price.toFixed(6) : price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            
            // 仮想通貨のリンクを生成（CoinGecko）
            const coinId = item.coin_id || item.id || '';
            const cryptoUrl = coinId ? `https://www.coingecko.com/ja/coins/${coinId}` : '#';
            
            row.innerHTML = `
                <td>${index + 1}</td>
                <td><a href="${cryptoUrl}" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><strong>${item.symbol || 'N/A'}</strong><br><small>${item.name || 'N/A'}</small></a></td>
                <td>$${priceFormatted}</td>
                <td class="${changeClass}"><strong>${changeSymbol} ${Math.abs(changePercent).toFixed(2)}%</strong></td>
            `;
            tableBody.appendChild(row);
        } catch (error) {
            console.error(`仮想通貨行 ${index + 1} の処理エラー:`, error, item);
        }
    });
    
    console.log('📊 仮想通貨: テーブルに追加された行数:', tableBody.children.length);
    
    // 結果を表示
    resultsElement.style.setProperty('display', 'block', 'important');
    console.log('✅ 仮想通貨結果表示完了');
}

function showCryptoError(message) {
    const errorElement = document.getElementById('cryptoErrorMessage');
    const resultsElement = document.getElementById('cryptoResults');
    
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}