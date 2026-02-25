// makeTableRowClickable が未定義の場合のフォールバック（app-common.js キャッシュ対策）
if (typeof window.makeTableRowClickable === 'undefined') {
    window.makeTableRowClickable = function() {};
}

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

    // Popularity（score）の降順でソート
    const sortedData = [...data.data].sort((a, b) => {
        const scoreA = a.score || a.popularity || 0;
        const scoreB = b.score || b.popularity || 0;
        return scoreB - scoreA; // 降順
    });

    tableBody.innerHTML = '';
    sortedData.forEach((trend, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        row.style.minHeight = '100px';

        const popularity = trend.score || trend.popularity || 0;
        const keyword = trend.keyword || trend.term || 'N/A';
        const googleSearchUrl = trend.google_search_url || '#';

        // キーワードを行リンク化（G検索ボタンは不要、行クリックで検索へ）
        row.innerHTML = `
            <td><span class="badge bg-primary">${index + 1}</span></td>
            <td><strong><a href="${googleSearchUrl}" target="_blank">${keyword}</a></strong></td>
            <td><strong>${Math.round(popularity).toLocaleString()}</strong></td>
        `;
        makeTableRowClickable(row, googleSearchUrl, `${keyword}をGoogleで検索`);
        tableBody.appendChild(row);

        if (index < 3) { // 最初の3件のみログ出力
            console.log(`displayGoogleResults: 行${index + 1}追加完了`, {
                rank: index + 1,
                keyword: trend.keyword,
                term: trend.term,
                score: popularity
            });
        }
    });

    // グラフを更新（ソート済みデータを使用）
    console.log('displayGoogleResults: グラフ更新開始');
    updateGoogleChart(sortedData);

    // 結果を表示
    console.log('displayGoogleResults: 結果表示開始');
    showGoogleResults();
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
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
    console.log('displayYouTubeResults: テーブル更新開始', { dataLength: data.data ? data.data.length : 0 });

    // 視聴回数でソート（降順）
    const sortedData = (data.data && Array.isArray(data.data))
        ? [...data.data].sort((a, b) => {
            const viewCountA = a.view_count || 0;
            const viewCountB = b.view_count || 0;
            return viewCountB - viewCountA; // 降順ソート
        })
        : [];

    if (sortedData.length === 0) {
        // データが空のときはスケルトン（ダミー）を表示
        tableBody.innerHTML = `
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
        `;
        showYouTubeResults();
        return;
    }

    tableBody.innerHTML = '';

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
        const videoTitle = video.title || 'N/A';

        row.innerHTML = `
            <td><span class="badge bg-danger">${index + 1}</span></td>
            <td><a href="${youtubeUrl}" target="_blank" class="text-decoration-none"><strong>${videoTitle}</strong></a>${additionalInfo}</td>
            <td>${video.channel_title}</td>
            <td><strong>${formatViewCount(video.view_count)}</strong></td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, youtubeUrl, `${videoTitle}の動画を開く`);
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
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
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
        const musicTitle = item.title || 'N/A';

        row.innerHTML = `
            <td><span class="badge bg-success">${item.rank}</span></td>
            <td><a href="${spotifyUrl}" target="_blank" class="text-decoration-none"><strong>${musicTitle}</strong></a>${additionalInfo}</td>
            <td>${item.artist}</td>
            <td><strong>${popularity}</strong></td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, spotifyUrl, `${musicTitle}の楽曲を開く`);
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
    if (count == null || count === undefined) return '0';
    const n = Number(count);
    if (isNaN(n)) return '0';
    if (n >= 1000000) {
        return (n / 1000000).toFixed(1) + 'M';
    } else if (n >= 1000) {
        return (n / 1000).toFixed(1) + 'K';
    } else {
        return n.toString();
    }
}

// 再生回数をフォーマット
function formatPlayCount(count) {
    if (count == null || count === undefined) return '0';
    const n = Number(count);
    if (isNaN(n)) return '0';
    if (n >= 1000000) {
        return (n / 1000000).toFixed(1) + 'M';
    } else if (n >= 1000) {
        return (n / 1000).toFixed(1) + 'K';
    } else {
        return n.toString();
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

// YouTube Trendsローディング表示（スケルトン表示のため results は非表示にしない）
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
    // ダミー/スケルトン表示のため results は表示したまま
    resultsElement.style.display = 'block';
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

/**
 * 全部入り（All）タブ用: メインのテーブル先頭N行をAll用tbodyへコピーする
 * @param {string} mainTableBodyId - メインペインのtbody要素ID（例: 'googleTrendsTableBody'）
 * @param {string} allTableBodyId - Allペインのtbody要素ID（例: 'all-googleTrendsTableBody'）
 * @param {number} limit - コピーする最大行数（デフォルト5）
 */
function syncToAllPane(mainTableBodyId, allTableBodyId, limit = 5) {
    const mainTbody = document.getElementById(mainTableBodyId);
    const allTbody = document.getElementById(allTableBodyId);
    if (!mainTbody || !allTbody) return;
    const table = allTbody.closest('table');
    if (!table) return;
    const cardBody = table.closest('.card-body');
    const dataRows = Array.from(mainTbody.querySelectorAll('tr:not(.skeleton-row)'));
    const isMobile = window.matchMedia && window.matchMedia('(max-width: 767.98px)').matches;
    // 全部入りタブは常にトップN件のみ表示（デスクトップでもlimitを適用）
    const toCopy = dataRows.slice(0, limit);
    const topCount = 3;
    const visibleRows = toCopy.slice(0, topCount);
    const hiddenRows = toCopy.slice(topCount);
    const moreTbodyId = `all-more-${allTableBodyId}`;

    const existingMoreList = table.querySelectorAll(`tbody[data-all-more-for="${allTableBodyId}"]`);
    existingMoreList.forEach(node => node.remove());
    if (cardBody) {
        const existingToggles = cardBody.querySelectorAll(`[data-all-more-toggle="${moreTbodyId}"]`);
        existingToggles.forEach(node => node.remove());
    }

    const wasOpen = allTbody.dataset.moreOpen === 'true';
    allTbody.innerHTML = '';
    allTbody.classList.remove('has-more', 'more-rows-open');

    const cloneWithWrapper = (tr, extraClass) => {
        const cloned = tr.cloneNode(true);
        if (extraClass) cloned.classList.add(extraClass);
        cloned.querySelectorAll('td').forEach(td => {
            const wrapper = document.createElement('div');
            wrapper.className = 'all-td-inner';
            while (td.firstChild) {
                wrapper.appendChild(td.firstChild);
            }
            td.appendChild(wrapper);
        });
        return cloned;
    };

    if (!isMobile) {
        toCopy.forEach(tr => allTbody.appendChild(cloneWithWrapper(tr)));
        return;
    }

    visibleRows.forEach((tr, index) => {
        const isLastVisible = index === visibleRows.length - 1 && hiddenRows.length > 0;
        const extraClass = isLastVisible ? 'more-row-end' : '';
        allTbody.appendChild(cloneWithWrapper(tr, extraClass));
    });
    hiddenRows.forEach((tr, index) => {
        const extraClass = index === 0 ? 'more-row-start' : '';
        const hiddenClone = cloneWithWrapper(tr, extraClass);
        hiddenClone.classList.add('more-row');
        hiddenClone.style.display = 'none';
        allTbody.appendChild(hiddenClone);
    });

    if (hiddenRows.length > 0 && cardBody) {
        allTbody.classList.add('has-more');
        if (wasOpen) {
            allTbody.classList.add('more-rows-open');
        }
        allTbody.dataset.moreOpen = wasOpen ? 'true' : 'false';
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'btn btn-sm btn-outline-secondary w-100 mt-2 all-more-toggle';
        toggle.setAttribute('aria-expanded', wasOpen ? 'true' : 'false');
        toggle.setAttribute('data-all-more-toggle', moreTbodyId);
        toggle.textContent = wasOpen ? '閉じる' : '続きを表示';
        toggle.addEventListener('click', function () {
            const isOpen = allTbody.classList.toggle('more-rows-open');
            allTbody.dataset.moreOpen = isOpen ? 'true' : 'false';
            allTbody.querySelectorAll('.more-row').forEach(row => {
                row.style.display = isOpen ? 'table-row' : 'none';
            });
            this.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            this.textContent = isOpen ? '閉じる' : '続きを表示';
        });
        cardBody.appendChild(toggle);
    }
}

// 前回開いていたタブを復元するための有効なタブID一覧（行政データ含む）
var TREND_TAB_IDS = ['tab-all', 'tab-news', 'tab-search', 'tab-tech', 'tab-market', 'tab-entertainment', 'tab-admin'];

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DOMContentLoaded: 初期化開始 ===');

    // 日本ページを開いたことを記憶（次回のルート訪問時のリダイレクト用）
    if (typeof setTrendPreference === 'function') {
        setTrendPreference('page', 'jp');
    }

    // 前回開いていたタブを復元（loadCachedDataExternal の前に実行）
    var trendTabsEl = document.getElementById('trendCategoryTabs');
    if (trendTabsEl && typeof getTrendPreference === 'function' && typeof bootstrap !== 'undefined') {
        var savedTabId = getTrendPreference('active_tab');
        if (savedTabId && TREND_TAB_IDS.indexOf(savedTabId) !== -1) {
            var tabBtn = document.getElementById(savedTabId);
            if (tabBtn) {
                var tab = new bootstrap.Tab(tabBtn);
                tab.show();
            }
        }
    }

    // 全部入り「もっと見る」: タブ切り替え後に対象ソースのアンカーへスクロール（各要素に直接リスナー・body委譲はハイパーリンクを妨げるため使わない）
    var pendingMoreLinkAnchor = null;
    function bindMoreLink(el) {
        el.addEventListener('click', function(e) {
            e.preventDefault();
            var targetTabId = this.getAttribute('data-target-tab');
            var targetAnchorId = this.getAttribute('data-target-anchor');
            if (!targetTabId) return;
            var tabEl = document.getElementById(targetTabId);
            if (tabEl && typeof bootstrap !== 'undefined') {
                pendingMoreLinkAnchor = targetAnchorId || null;
                var tab = new bootstrap.Tab(tabEl);
                tab.show();
            }
        });
    }
    document.querySelectorAll('.all-more-link').forEach(bindMoreLink);
    document.querySelectorAll('.estat-goto-tab').forEach(bindMoreLink);

    // 全部入りタブ: カテゴリ選択ドロップダウン変更時
    document.querySelectorAll('.all-category-select').forEach(select => {
        select.addEventListener('change', function() {
            const mainSelectId = this.dataset.mainSelect;
            const service = this.dataset.service;
            const mainSelect = document.getElementById(mainSelectId);
            if (mainSelect) {
                mainSelect.value = this.value;
                if (service === 'hatena' && typeof hatenaManager !== 'undefined' && hatenaManager) {
                    hatenaManager.fetchTrends();
                } else if (service === 'note' && typeof noteManager !== 'undefined' && noteManager) {
                    noteManager.fetchTrends();
                } else if (service === 'twitch' && typeof twitchManager !== 'undefined' && twitchManager) {
                    twitchManager.fetchTrends();
                } else if (service === 'rakuten' && typeof fetchRakutenTrends === 'function') {
                    fetchRakutenTrends();
                } else if (service === 'book' && typeof loadBookTrendsFromCache === 'function') {
                    loadBookTrendsFromCache();
                }
            }
        });
    });
    // メインのカテゴリ選択変更時 → Allタブのドロップダウンを同期（双方向）
    const syncPairs = [
        { main: 'hatenaCategorySelect', all: 'all-hatenaCategorySelect' },
        { main: 'noteCategorySelect', all: 'all-noteCategorySelect' },
        { main: 'twitchTypeSelect', all: 'all-twitchTypeSelect' },
        { main: 'rakutenGenreSelect', all: 'all-rakutenGenreSelect' },
        { main: 'bookCategorySelect', all: 'all-bookCategorySelect' }
    ];
    syncPairs.forEach(({ main, all }) => {
        const mainEl = document.getElementById(main);
        const allEl = document.getElementById(all);
        if (mainEl && allEl) {
            allEl.value = mainEl.value; // 初期値同期
            mainEl.addEventListener('change', () => { allEl.value = mainEl.value; });
        }
    });
    // 本トレンド: カテゴリ変更で再読み込み
    const bookCategorySelect = document.getElementById('bookCategorySelect');
    if (bookCategorySelect && typeof loadBookTrendsFromCache === 'function') {
        bookCategorySelect.addEventListener('change', function() { loadBookTrendsFromCache(); });
    }

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

    // トレンドカテゴリタブ切り替え時: 前回タブを保存 ＋ グラフリサイズ ＋ もっと見るからのアンカースクロール
    if (trendTabsEl) {
        trendTabsEl.addEventListener('shown.bs.tab', function(e) {
            var tabId = e.target && e.target.id;
            if (tabId && typeof setTrendPreference === 'function') {
                setTrendPreference('active_tab', tabId);
            }
            if (pendingMoreLinkAnchor) {
                var anchor = document.getElementById(pendingMoreLinkAnchor);
                if (anchor) {
                    anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
                pendingMoreLinkAnchor = null;
            }
            if (typeof currentGoogleChart !== 'undefined' && currentGoogleChart) {
                try { currentGoogleChart.resize(); } catch (err) { /* ignore */ }
            }
            if (typeof currentYouTubeChart !== 'undefined' && currentYouTubeChart) {
                try { currentYouTubeChart.resize(); } catch (err) { /* ignore */ }
            }
            if (typeof currentMusicChart !== 'undefined' && currentMusicChart) {
                try { currentMusicChart.resize(); } catch (err) { /* ignore */ }
            }
        });
    }

    console.log('=== 初期化完了 ===');
});

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
    if (data.data && data.data.length > 0) {
        data.data.forEach((news, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            row.style.minHeight = '100px';

            const titleText = news.title || 'N/A';
            const titleLink = news.url
                ? `<a href="${news.url}" target="_blank" class="text-decoration-none">${titleText}<i class="fas fa-external-link-alt ms-1"></i></a>`
                : `<span>${titleText}</span>`;

            const publishedDateRaw = news.published_at || news.publish_date || news.publishedDate || news.published_date;
            const publishedDate = typeof formatDate === 'function' ? formatDate(publishedDateRaw) : (publishedDateRaw || '');
            const sourceName = news.source || '';
            const metaInfoParts = [];
            if (publishedDate && publishedDate !== '不明') metaInfoParts.push(publishedDate);
            if (sourceName) metaInfoParts.push(sourceName);
            const metaInfo = metaInfoParts.join(' / ') || '不明';

            const newsUrl = news.url || '#';
            row.innerHTML = `
                <td><span class="badge bg-info">${news.rank || index + 1}</span></td>
                <td><strong>${titleLink}</strong></td>
                <td><small class="text-muted">${metaInfo}</small></td>
            `;
            makeTableRowClickable(row, newsUrl, `${titleText}のニュース記事を開く`);
            tableBody.appendChild(row);
        });
    }

    // グラフを更新
    if (typeof updateNewsChart === 'function' && data.data) {
        updateNewsChart(data.data);
    }

    // 結果を表示
    const newsResultsEl = document.getElementById('newsResults');
    if (newsResultsEl) newsResultsEl.style.display = 'block';
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

        const rakutenUrl = item.url || item.item_url || '#';
        const productTitle = item.title || 'N/A';

        row.innerHTML = `
            <td><span class="badge bg-danger">${index + 1}</span></td>
            <td>
                <strong><a href="${rakutenUrl}" target="_blank">${productTitle}</a></strong>
            </td>
            <td>${price}</td>
            <td>${reviewInfo}</td>
            <td>${salesInfo}</td>
            <td>${item.shop_name || '不明'}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, rakutenUrl, `${productTitle}の商品を開く`);
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

            const articleUrl = item.url || '#';
            const articleTitle = item.title || 'N/A';

            // 行全体がリンク（makeTableRowClickable）のため「記事を読む」ボタンは不要
            row.innerHTML = `
                <td><span class="badge bg-warning">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${articleUrl}" target="_blank">${articleTitle}</a></strong>
                </td>
                <td><strong>${bookmarkInfo}</strong></td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, articleUrl, `${articleTitle}の記事を開く`);
            tableBody.appendChild(row);
        });

        showHatenaResults();
        // database_cache 表示は不要（技術的な内部状態をユーザーに表示しない）
        if (data.source !== 'database_cache') {
            showHatenaStatusMessage(`✅ ${data.source} - ${data.total_count || data.data.length}件のエントリーを取得しました`, 'success');
        }
        if (typeof applyCategoryAccordionForAllTables === 'function') {
            setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
        }
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
        const articleUrl = item.url || '#';
        const articleTitle = item.title || 'タイトルなし';
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${articleUrl}" target="_blank" rel="noopener noreferrer">${articleTitle}</a></td>
            <td>${item.published_date ? new Date(item.published_date).toLocaleDateString('ja-JP') : '-'}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, articleUrl, `${articleTitle}の記事を開く`);
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

// PR TIMES 結果表示（RSSのそのまま: title, url, published_date, tags）
function displayPRTimesResults(data) {
    const resultsElement = document.getElementById('prtimesResults');
    const tableBody = document.getElementById('prtimesTrendsTableBody');
    const errorEl = document.getElementById('prtimesErrorMessage');
    function esc(s) {
        if (s == null) return '';
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    if (!resultsElement || !tableBody) return;

    tableBody.innerHTML = '';
    if (errorEl) errorEl.style.display = 'none';

    if (!data.data || data.data.length === 0) {
        showPRTimesError('データがありません');
        return;
    }

    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const articleUrl = item.url || '#';
        const articleTitle = item.title || 'タイトルなし';
        const tags = item.tags || [];
        const tagsHtml = tags.length
            ? tags.map(function(t) {
                const term = (t && (t.term != null ? t.term : t.label)) || '';
                return term ? '<span class="badge bg-secondary me-1">' + esc(String(term)) + '</span>' : '';
            }).filter(Boolean).join(' ')
            : '-';
        row.innerHTML =
            '<td>' + (item.rank || index + 1) + '</td>' +
            '<td><a href="' + esc(articleUrl) + '" target="_blank" rel="noopener noreferrer">' + esc(articleTitle) + '</a></td>' +
            '<td>' + (item.published_date ? new Date(item.published_date).toLocaleDateString('ja-JP') : '-') + '</td>' +
            '<td class="small">' + tagsHtml + '</td>';
        makeTableRowClickable(row, articleUrl, articleTitle + 'の記事を開く');
        tableBody.appendChild(row);
    });

    resultsElement.style.display = 'block';
    if (typeof syncToAllPane === 'function') {
        setTimeout(function() { syncToAllPane('prtimesTrendsTableBody', 'all-prtimesTrendsTableBody', 5); }, 0);
    }
}

function showPRTimesError(message) {
    const errorElement = document.getElementById('prtimesErrorMessage');
    const resultsElement = document.getElementById('prtimesResults');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'block';
}

// PR TIMES × はてブ 結果表示（title, url, bookmark_count, published_date）
function displayPRTimesHatenaResults(data) {
    const resultsElement = document.getElementById('prtimesHatenaResults');
    const tableBody = document.getElementById('prtimesHatenaTrendsTableBody');
    const errorEl = document.getElementById('prtimesHatenaErrorMessage');

    function esc(s) {
        if (s == null) return '';
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    if (!resultsElement || !tableBody) return;

    tableBody.innerHTML = '';
    if (errorEl) errorEl.style.display = 'none';

    if (!data.data || data.data.length === 0) {
        if (errorEl) {
            errorEl.textContent = 'データがありません';
            errorEl.style.display = 'block';
        }
        resultsElement.style.display = 'block';
        return;
    }

    data.data.forEach(function(item, index) {
        const row = document.createElement('tr');
        const articleUrl = item.url || '#';
        const articleTitle = item.title || 'タイトルなし';
        const bookmarkCount = item.bookmark_count || 0;
        const bookmarkInfo = bookmarkCount > 0 ? bookmarkCount.toLocaleString() + '件' : '0件';
        const publishedDate = item.published_date || item.published_date_iso;
        const dateStr = publishedDate ? new Date(publishedDate).toLocaleDateString('ja-JP') : '-';
        row.innerHTML =
            '<td>' + (item.rank || index + 1) + '</td>' +
            '<td><a href="' + esc(articleUrl) + '" target="_blank" rel="noopener noreferrer">' + esc(articleTitle) + '</a></td>' +
            '<td><strong>' + esc(bookmarkInfo) + '</strong></td>' +
            '<td>' + esc(dateStr) + '</td>';
        if (typeof makeTableRowClickable === 'function') {
            makeTableRowClickable(row, articleUrl, articleTitle + 'の記事を開く');
        }
        tableBody.appendChild(row);
    });

    resultsElement.style.display = 'block';
    if (typeof syncToAllPane === 'function') {
        setTimeout(function() { syncToAllPane('prtimesHatenaTrendsTableBody', 'all-prtimesHatenaTrendsTableBody', 5); }, 0);
    }
}

// Wikipedia 人気記事 トレンド取得（日本語）
async function fetchWikipediaTrends() {
    const resultsElement = document.getElementById('wikipediaResults');
    const errorElement = document.getElementById('wikipediaErrorMessage');
    const tableBody = document.getElementById('wikipediaTrendsTableBody');
    const loadingElement = document.getElementById('wikipediaLoading');

    if (!resultsElement || !tableBody) return;

    try {
        if (loadingElement) loadingElement.style.display = 'block';
        resultsElement.style.display = 'none';
        if (errorElement) errorElement.style.display = 'none';

        const response = await fetchWithRetry('/api/wikipedia-trends?lang=ja&limit=25');
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || 'HTTP ' + response.status);
        if (!data.success) throw new Error(data.error || '取得に失敗しました');

        if (loadingElement) loadingElement.style.display = 'none';
        displayWikipediaResults(data);
    } catch (error) {
        console.error('Wikipedia 人気記事 API エラー:', error);
        if (loadingElement) loadingElement.style.display = 'none';
        showWikipediaError(error.message);
    }
}

function displayWikipediaResults(data) {
    const resultsElement = document.getElementById('wikipediaResults');
    const tableBody = document.getElementById('wikipediaTrendsTableBody');
    if (!resultsElement || !tableBody) return;

    tableBody.innerHTML = '';
    if (!data.data || data.data.length === 0) {
        showWikipediaError('この日は人気記事データが提供されていません。しばらく後にお試しください。');
        return;
    }

    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const url = item.url || '#';
        const title = item.title || 'タイトルなし';
        const views = item.views != null ? item.views.toLocaleString() : '-';
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a></td>
            <td>${views}</td>
        `;
        makeTableRowClickable(row, url, title + 'の記事を開く');
        tableBody.appendChild(row);
    });

    resultsElement.style.display = 'block';
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('wikipediaTrendsTableBody', 'all-wikipediaTrendsTableBody', 5), 0);
    }
}

function showWikipediaError(message) {
    const errorElement = document.getElementById('wikipediaErrorMessage');
    const resultsElement = document.getElementById('wikipediaResults');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'block';
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
        const articleUrl = item.url || '#';
        const articleTitle = item.title || 'タイトルなし';
        row.innerHTML = `
            <td>${item.rank || index + 1}</td>
            <td><a href="${articleUrl}" target="_blank" rel="noopener noreferrer">${articleTitle}</a></td>
            <td>${item.user_name || item.user_id || '-'}</td>
            <td>${item.likes_count || 0}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, articleUrl, `${articleTitle}の記事を開く`);
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
        const jpSymbol = symbol.includes('.') ? symbol : `${symbol}.T`;
        const stockUrl = market === 'JP'
            ? `https://finance.yahoo.co.jp/quote/${jpSymbol}`
            : `https://finance.yahoo.com/quote/${symbol}`;

        const stockName = item.name || 'N/A';
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${stockUrl}" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><strong>${stockName}</strong><br><small class="text-muted">${item.symbol || 'N/A'}</small></a></td>
            <td>¥${price.toLocaleString()}</td>
            <td class="${changeClass}"><strong>${changeSymbol} ${Math.abs(changePercent).toFixed(2)}%</strong></td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, stockUrl, `${stockName}の株価情報を開く`);
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

            const cryptoName = item.name || 'N/A';
            const cryptoSymbol = item.symbol || 'N/A';
            row.innerHTML = `
                <td>${index + 1}</td>
                <td><a href="${cryptoUrl}" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><strong>${cryptoSymbol}</strong><br><small>${cryptoName}</small></a></td>
                <td>$${priceFormatted}</td>
                <td class="${changeClass}"><strong>${changeSymbol} ${Math.abs(changePercent).toFixed(2)}%</strong></td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, cryptoUrl, `${cryptoName}の仮想通貨情報を開く`);
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