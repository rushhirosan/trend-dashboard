// データ管理とキャッシュ表示に関するJavaScriptファイル

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

// キャッシュデータを自動読み込み（外部から呼び出し用）
function loadCachedDataExternal() {
    console.log('📦 キャッシュデータの読み込み処理開始');
    
    // 全カテゴリを定義
    const allCategories = [
        loadGoogleTrendsFromCache,
        loadYouTubeTrendsFromCache,
        loadMusicTrendsFromCache,
        loadNewsTrendsFromCache,
        loadStockTrendsFromCache,
        loadCryptoTrendsFromCache,
        loadPodcastTrendsFromCache,
        loadMovieTrendsFromCache,
        loadBookTrendsFromCache,
        loadGitHubTrendsFromCache,
        loadAppStoreTrendsFromCache,
        loadRakutenTrendsFromCache,
        loadHatenaTrendsFromCache,
        loadTwitchTrendsFromCache,
        loadNHKTrendsFromCache,
        loadQiitaTrendsFromCache
    ];
    
    // バッチ処理: 一度に4つずつ実行（データベース接続の競合を防ぐ）
    const BATCH_SIZE = 4;
    console.log('🚀 全カテゴリのバッチ読み込み開始（並列数: ' + BATCH_SIZE + '）');
    console.log('🚀 実行する関数:', allCategories.map(f => f.name));
    
    // バッチごとに順次実行（データベース接続の競合を防ぐ）
    function executeBatch(batchIndex) {
        if (batchIndex >= allCategories.length) {
            console.log('✅ 全バッチの実行完了');
            return;
        }
        
        const batchEnd = Math.min(batchIndex + BATCH_SIZE, allCategories.length);
        const batch = allCategories.slice(batchIndex, batchEnd);
        const batchNumber = Math.floor(batchIndex / BATCH_SIZE) + 1;
        console.log(`📦 バッチ ${batchNumber} 実行中 (${batch.map(f => f.name).join(', ')})`);
        
        // バッチ内の関数を並列実行
        batch.forEach(loadFunction => {
            try {
                console.log(`🚀 実行中: ${loadFunction.name}`);
                loadFunction();
            } catch (error) {
                console.error(`❌ ${loadFunction.name} 実行エラー:`, error);
            }
        });
        
        // 次のバッチを200ms後に実行（データベース接続の競合を防ぐ）
        if (batchEnd < allCategories.length) {
            setTimeout(() => {
                executeBatch(batchEnd);
            }, 200);
        } else {
            console.log('✅ 全バッチの実行完了');
        }
    }
    
    // 最初のバッチを実行
    executeBatch(0);
    
    console.log('✅ キャッシュデータの読み込み処理完了');
}

// Google Trendsキャッシュデータの読み込み
function loadGoogleTrendsFromCache() {
    console.log('📊 Google Trends キャッシュデータ読み込み');
    
    // ローディング表示
    const loadingElement = document.getElementById('googleTrendsLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/google-trends?country=JP&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('Google Trends API レスポンス:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('Google Trends API データ:', data);
            if (data.data && data.data.length > 0) {
                console.log('Google Trends データ表示開始');
                if (typeof displayGoogleResults === 'function') {
                    displayGoogleResults(data);
                } else {
                    console.error('displayGoogleResults関数が見つかりません');
                }
            } else {
                console.log('Google Trends データなしまたはエラー:', data);
            }
            
            // ローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            
            // 結果エリアを表示
            const resultsElement = document.getElementById('googleResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Google Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Google Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時もローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('googleResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// Google Trends結果エリアを表示する関数（app.jsに定義されていない場合のフォールバック）
function showGoogleResults() {
    const resultsElement = document.getElementById('googleResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}

// YouTube Trendsキャッシュデータの読み込み
function loadYouTubeTrendsFromCache() {
    console.log('📊 YouTube Trends キャッシュデータ読み込み');
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/youtube-trends?region=JP&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('YouTube Trends API レスポンス:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('YouTube Trends API データ:', data);
            if (data.data && data.data.length > 0) {
                console.log('YouTube Trends データ表示開始');
                if (typeof displayYouTubeResults === 'function') {
                    displayYouTubeResults(data);
                } else {
                    console.error('displayYouTubeResults関数が見つかりません');
                }
            } else {
                console.log('YouTube Trends データなしまたはエラー:', data);
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('YouTube Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('YouTube Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('youtubeResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// 音楽トレンドキャッシュデータの読み込み
// Spotify音楽トレンドキャッシュデータの読み込み
function loadMusicTrendsFromCache() {
    console.log('📊 Music Trends キャッシュデータ読み込み');
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/music-trends?service=spotify&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            console.log('📊 Music API response:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('📊 Music API data:', data);
            console.log('📊 Music data.success:', data.success);
            console.log('📊 Music data.data:', data.data);
            console.log('📊 Music data.data.length:', data.data ? data.data.length : 'data.data is null/undefined');
            // data.successをチェック
            if (data.success && data.data && Array.isArray(data.data) && data.data.length > 0) {
                console.log('📊 Music データ表示開始');
                if (typeof displayMusicResults === 'function') {
                    displayMusicResults(data);
                } else {
                    console.error('displayMusicResults関数が見つかりません');
                }
            } else {
                console.log('📊 Music データが見つかりません:', data);
                console.log('📊 data.success:', data.success);
                console.log('📊 data.data:', data.data);
                console.log('📊 data.data.length:', data.data ? data.data.length : 'data.data is null/undefined');
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Music Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Music Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('musicResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// ニューストレンドキャッシュデータの読み込み
function loadNewsTrendsFromCache() {
    console.log('📊 News Trends キャッシュデータ読み込み');
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/worldnews-trends?country=jp&category=general&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            console.log('📊 News API response:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('📊 News Trends データ取得完了:', data);
            console.log('📊 News Trends data.success:', data.success);
            console.log('📊 News Trends data.data:', data.data);
            if (data.success && data.data && Array.isArray(data.data) && data.data.length > 0) {
                console.log('📊 News Trends データ表示開始');
                if (typeof displayWorldNewsResults === 'function') {
                    displayWorldNewsResults(data);
                } else {
                    console.error('displayWorldNewsResults関数が見つかりません');
                }
            } else {
                console.log('📊 News Trends データが見つかりません:', data);
                console.log('📊 data.success:', data.success);
                console.log('📊 data.data:', data.data);
                console.log('📊 data.data.length:', data.data ? data.data.length : 'data.data is null/undefined');
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('News Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('News Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('newsResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// Podcastトレンドキャッシュデータの読み込み
function loadPodcastTrendsFromCache() {
    console.log('📊 Podcast Trends キャッシュデータ読み込み');
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/podcast-trends?trend_type=best_podcasts&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.data && data.data.length > 0) {
                console.log('Podcast Trends データ表示開始');
                if (typeof displayPodcastResults === 'function') {
                    displayPodcastResults(data);
                } else {
                    console.error('displayPodcastResults関数が見つかりません');
                }
            } else {
                console.log('Podcast Trends データなしまたはエラー:', data);
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Podcast Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Podcast Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('podcastResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// 楽天トレンドキャッシュデータの読み込み
function loadRakutenTrendsFromCache() {
    console.log('📊 Rakuten Trends キャッシュデータ読み込み');
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/rakuten-trends?force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Rakuten Trends API データ:', data);
            if (data.data && data.data.length > 0) {
                console.log('Rakuten Trends データ表示開始');
                if (typeof displayRakutenResults === 'function') {
                    displayRakutenResults(data);
                } else {
                    console.error('displayRakutenResults関数が見つかりません');
                }
            } else {
                console.log('Rakuten Trends データなしまたはエラー:', data);
            }
            // 結果エリアを表示
            const resultsElement = document.getElementById('rakutenResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Rakuten Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Rakuten Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('rakutenResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// はてなブックマークトレンドキャッシュデータの読み込み
function loadHatenaTrendsFromCache() {
    console.log('📊 Hatena Trends キャッシュデータ読み込み');
    
    // 初期読み込み時は常に'all'カテゴリを使用
    const selectedCategory = 'all';
    
    console.log(`🔍 はてなブックマーク: 初期読み込み時のカテゴリ '${selectedCategory}' のデータを取得中...`);
    
    // ローディング表示
    const loadingElement = document.getElementById('hatenaTrendsLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry(`/api/hatena-trends?category=${selectedCategory}&limit=25&type=hot&force_refresh=false`, { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('📊 Hatena API response:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('📊 Hatena API data:', data);
            // ローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            
            if (data.success && data.data && data.data.length > 0) {
                console.log('📊 Hatena データ表示開始 (source:', data.source, ')');
                if (typeof displayHatenaResults === 'function') {
                    displayHatenaResults(data);
                } else {
                    console.error('displayHatenaResults関数が見つかりません');
                }
            } else {
                console.log('📊 Hatena データが見つかりません:', data);
                // キャッシュにデータがない場合は、ローディングを非表示にして終了
                // APIを呼び出さない（画面更新のたびにAPIを呼び出さないようにするため）
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Hatena Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Hatena Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時もローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        });
}

// Twitchトレンドキャッシュデータの読み込み
function loadTwitchTrendsFromCache() {
    console.log('📊 Twitch Trends キャッシュデータ読み込み');
    
    // 初期読み込み時は常に'games'カテゴリを使用
    const selectedType = 'games';
    
    console.log(`🔍 Twitch: 初期読み込み時のカテゴリ '${selectedType}' のデータを取得中...`);
    
    // ローディング表示
    const loadingElement = document.getElementById('twitchTrendsLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry(`/api/twitch-trends?type=${selectedType}&limit=25&force_refresh=false`, { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // ローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            
            if (data.success && data.data && data.data.length > 0) {
                console.log('📊 Twitch データ表示開始 (source:', data.source, ')');
                if (typeof displayTwitchResults === 'function') {
                    displayTwitchResults(data);
                } else {
                    console.error('displayTwitchResults関数が見つかりません');
                }
            } else {
                console.log('📊 Twitch データが見つかりません:', data);
                // キャッシュにデータがない場合は、ローディングを非表示にして終了
                // APIを呼び出さない（画面更新のたびにAPIを呼び出さないようにするため）
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Twitch Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Twitch Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時もローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        });
}

// キャッシュデータ表示関数群
function displayGoogleTrendsFromCache(cachedData) {
    console.log('📊 Google キャッシュデータ表示');
    console.log('Google データ構造:', cachedData);
    if (cachedData.data) {
        let googleData = cachedData.data;
        if (googleData.data && Array.isArray(googleData.data)) {
            displayGoogleResults({
                success: true,
                data: googleData.data,
                status: 'cached'
            });
        } else if (Array.isArray(googleData)) {
            displayGoogleResults({
                success: true,
                data: googleData,
                status: 'cached'
            });
        }
    }
}

function displayYouTubeTrendsFromCache(cachedData) {
    console.log('📊 YouTube キャッシュデータ表示');
    console.log('YouTube データ構造:', cachedData);
    if (cachedData.data) {
        let youtubeData = cachedData.data;
        if (youtubeData.data && Array.isArray(youtubeData.data)) {
            displayYouTubeResults({
                success: true,
                data: youtubeData.data,
                status: 'cached'
            });
        } else if (Array.isArray(youtubeData)) {
            displayYouTubeResults({
                success: true,
                data: youtubeData,
                status: 'cached'
            });
        }
    }
}

function displayMusicTrendsFromCache(cachedData) {
    console.log('📊 Music キャッシュデータ表示');
    console.log('Music データ構造:', cachedData);
    if (cachedData.data) {
        let musicData = cachedData.data;
        if (musicData.data && Array.isArray(musicData.data)) {
            displayMusicResults({
                success: true,
                data: musicData.data,
                status: 'cached'
            });
        } else if (Array.isArray(musicData)) {
            displayMusicResults({
                success: true,
                data: musicData,
                status: 'cached'
            });
        }
    }
}

function displayNewsTrendsFromCache(cachedData) {
    console.log('📊 News キャッシュデータ表示');
    console.log('News データ構造:', cachedData);
    if (cachedData.data) {
        let newsData = cachedData.data;
        if (newsData.data && Array.isArray(newsData.data)) {
            displayWorldNewsResults({
                success: true,
                data: newsData.data,
                status: 'cached'
            });
        } else if (Array.isArray(newsData)) {
            displayWorldNewsResults({
                success: true,
                data: newsData,
                status: 'cached'
            });
        }
    }
}

function displayPodcastTrendsFromCache(cachedData) {
    console.log('📊 Podcast キャッシュデータ表示');
    console.log('Podcast データ構造:', cachedData);
    if (cachedData.data) {
        let podcastData = cachedData.data;
        if (podcastData.data && Array.isArray(podcastData.data)) {
            displayPodcastResults({
                success: true,
                data: podcastData.data,
                status: 'cached'
            });
        } else if (Array.isArray(podcastData)) {
            displayPodcastResults({
                success: true,
                data: podcastData,
                status: 'cached'
            });
        }
    }
}

function displayHatenaTrendsFromCache(cachedData) {
    console.log('📊 Hatena キャッシュデータ表示');
    console.log('Hatena データ構造:', cachedData);
    if (cachedData.data) {
        let hatenaData = cachedData.data;
        if (hatenaData.data && Array.isArray(hatenaData.data)) {
            displayHatenaResults({
                success: true,
                data: hatenaData.data,
                status: 'cached'
            });
        } else if (Array.isArray(hatenaData)) {
            displayHatenaResults({
                success: true,
                data: hatenaData,
                status: 'cached'
            });
        }
    }
}

function displayTwitchTrendsFromCache(cachedData) {
    console.log('📊 Twitch キャッシュデータ表示');
    console.log('Twitch データ構造:', cachedData);
    if (cachedData.data) {
        let twitchData = cachedData.data;
        if (twitchData.data && Array.isArray(twitchData.data)) {
            displayTwitchResults({
                success: true,
                data: twitchData.data,
                status: 'cached'
            });
        } else if (Array.isArray(twitchData)) {
            displayTwitchResults({
                success: true,
                data: twitchData,
                status: 'cached'
            });
        }
    }
}

function displayRakutenTrendsFromCache(cachedData) {
    console.log('📊 Rakuten キャッシュデータ表示');
    console.log('Rakuten データ構造:', cachedData);
    if (cachedData.data) {
        let rakutenData = cachedData.data;
        if (rakutenData.data && Array.isArray(rakutenData.data)) {
            displayRakutenResults({
                success: true,
                data: rakutenData.data,
                status: 'cached'
            });
        } else if (Array.isArray(rakutenData)) {
            displayRakutenResults({
                success: true,
                data: rakutenData,
                status: 'cached'
            });
        }
    }
}

// NHK ニュースキャッシュデータの読み込み
function loadNHKTrendsFromCache() {
    console.log('📊 NHK ニュース キャッシュデータ読み込み');
    // ローディング表示
    const loadingElement = document.getElementById('nhkLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/nhk-trends?force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('NHK ニュース API レスポンス:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('NHK ニュース API データ:', data);
            if (data.data && data.data.length > 0) {
                console.log('NHK ニュース データ表示開始');
                if (typeof displayNHKResults === 'function') {
                    displayNHKResults(data);
                } else {
                    console.error('displayNHKResults関数が見つかりません');
                }
            } else {
                console.log('NHK ニュース データなしまたはエラー:', data);
            }
            
            // ローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('NHK ニュース キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('NHK ニュース キャッシュ読み込みエラー:', error);
            }
            // エラー時もローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        });
}

// Qiita トレンドキャッシュデータの読み込み
function loadQiitaTrendsFromCache() {
    console.log('📊 Qiita トレンド キャッシュデータ読み込み');
    // ローディング表示
    const loadingElement = document.getElementById('qiitaLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/qiita-trends?limit=25&sort=likes_count&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('Qiita トレンド API レスポンス:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('Qiita トレンド API データ:', data);
            if (data.data && data.data.length > 0) {
                console.log('Qiita トレンド データ表示開始');
                if (typeof displayQiitaResults === 'function') {
                    displayQiitaResults(data);
                } else {
                    console.error('displayQiitaResults関数が見つかりません');
                }
            } else {
                console.log('Qiita トレンド データなしまたはエラー:', data);
            }
            
            // ローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Qiita トレンド キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Qiita トレンド キャッシュ読み込みエラー:', error);
            }
            // エラー時もローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        });
}

// 株価トレンドキャッシュデータの読み込み
function loadStockTrendsFromCache() {
    console.log('📊 Stock Trends キャッシュデータ読み込み');
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/stock-trends?market=JP&limit=25&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // データが空でも表示関数を呼び出す（「本日取引はありません」を表示するため）
            if (typeof displayStockResults === 'function') {
                displayStockResults(data);
            } else {
                console.error('displayStockResults関数が見つかりません');
            }
            // 結果エリアを表示
            const resultsElement = document.getElementById('stockResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Stock Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Stock Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('stockResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// 仮想通貨トレンドキャッシュデータの読み込み
function loadCryptoTrendsFromCache() {
    console.log('📊 Crypto Trends キャッシュデータ読み込み');
    // AbortControllerを使用したタイムアウト処理（30秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    fetchWithRetry('/api/crypto-trends?limit=25&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Crypto Trends API response:', data);
            console.log('Crypto Trends data count:', data.data ? data.data.length : 0);
            if (data.data && data.data.length > 0) {
                console.log('Crypto Trends データ表示開始 (件数:', data.data.length, ')');
                if (typeof displayCryptoResults === 'function') {
                    displayCryptoResults(data);
                } else {
                    console.error('displayCryptoResults関数が見つかりません');
                }
            } else {
                console.log('Crypto Trends データなしまたはエラー:', data);
            }
            // 結果エリアを表示
            const resultsElement = document.getElementById('cryptoResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Crypto Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Crypto Trends キャッシュ読み込みエラー:', error);
            }
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('cryptoResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// 映画トレンドキャッシュデータの読み込み
function loadMovieTrendsFromCache() {
    console.log('📊 Movie Trends キャッシュデータ読み込み');
    const loadingElement = document.getElementById('movieLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30秒でタイムアウト

    fetchWithRetry('/api/movie-trends?country=JP&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('Movie Trends API レスポンス:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('Movie Trends API データ:', data);
            if (data.data && data.data.length > 0) {
                console.log('Movie Trends データ表示開始');
                if (typeof displayMovieResults === 'function') {
                    displayMovieResults(data);
                } else {
                    console.error('displayMovieResults関数が見つかりません');
                }
            } else {
                console.log('Movie Trends データなしまたはエラー:', data);
            }
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            const resultsElement = document.getElementById('movieResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Movie Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Movie Trends キャッシュ読み込みエラー:', error);
            }
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            const resultsElement = document.getElementById('movieResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// 本トレンドキャッシュデータの読み込み
function loadBookTrendsFromCache() {
    console.log('📊 Book Trends キャッシュデータ読み込み');
    const loadingElement = document.getElementById('bookLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30秒でタイムアウト

    fetchWithRetry('/api/book-trends?country=JP&limit=25&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('Book Trends API レスポンス:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('Book Trends API データ:', data);
            if (data.data && data.data.length > 0) {
                console.log('Book Trends データ表示開始');
                if (typeof displayBookResults === 'function') {
                    displayBookResults(data);
                } else {
                    console.error('displayBookResults関数が見つかりません');
                }
            } else {
                console.log('Book Trends データなしまたはエラー:', data);
            }
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            const resultsElement = document.getElementById('bookResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Book Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Book Trends キャッシュ読み込みエラー:', error);
            }
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            const resultsElement = document.getElementById('bookResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}


