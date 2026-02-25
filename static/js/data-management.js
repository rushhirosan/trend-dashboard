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
// 並び順: 全部入り（All）タブの表示順に合わせる（上からバッチで読み込み）
function loadCachedDataExternal() {
    console.log('📦 キャッシュデータの読み込み処理開始');
    var allCategories = [
        loadNHKTrendsFromCache,
        loadNewsTrendsFromCache,
        loadWikipediaTrendsFromCache,
        loadGoogleTrendsFromCache,
        loadYouTubeTrendsFromCache,
        loadPRTimesHatenaTrendsFromCache,
        loadQiitaTrendsFromCache,
        loadHatenaTrendsFromCache,
        loadZennTrendsFromCache,
        loadNoteTrendsFromCache,
        loadGitHubTrendsFromCache,
        loadIPATrendsFromCache,
        loadJPCERTTrendsFromCache,
        loadCryptoTrendsFromCache,
        loadStockTrendsFromCache,
        loadAppStoreTrendsFromCache,
        loadMusicTrendsFromCache,
        loadPodcastTrendsFromCache,
        loadMovieTrendsFromCache,
        loadBookTrendsFromCache,
        loadRakutenTrendsFromCache,
        loadTwitchTrendsFromCache
    ];
    console.log('🚀 全カテゴリのバッチ読み込み開始（並列数: 4）');
    console.log('🚀 実行する関数:', allCategories.map(function(f) { return f.name; }));
    if (typeof runBatchLoad === 'function') {
        runBatchLoad(allCategories, { batchSize: 4, delayMs: 200 });
    } else {
        allCategories.forEach(function(fn) { fn(); });
    }
    console.log('✅ キャッシュデータの読み込み処理完了');
}

// Google Trendsキャッシュデータの読み込み（共通化）
function loadGoogleTrendsFromCache() {
    var country = (typeof getTrendPreference === 'function' ? (getTrendPreference('google') || 'JP') : 'JP');
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Google',
            apiEndpoint: '/api/google-trends',
            params: { country: country },
            uiIds: {
                loading: 'googleTrendsLoading',
                results: 'googleResults'
            },
            displayFunction: displayGoogleResults,
            allPaneSync: { mainTableBodyId: 'googleTrendsTableBody', allTableBodyId: 'all-googleTrendsTableBody', targetTabId: 'tab-search' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Google Trends キャッシュデータ読み込み');
        const loadingElement = document.getElementById('googleTrendsLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        
        fetchWithRetry('/api/google-trends?country=' + encodeURIComponent(country) + '&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayGoogleResults === 'function') {
                    displayGoogleResults(data);
                }
                const resultsElement = document.getElementById('googleResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Google Trends キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
                const resultsElement = document.getElementById('googleResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// Google Trends結果エリアを表示する関数（app.jsに定義されていない場合のフォールバック）
function showGoogleResults() {
    const resultsElement = document.getElementById('googleResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}

// YouTube Trendsキャッシュデータの読み込み（共通化）
function loadYouTubeTrendsFromCache() {
    var region = (typeof getTrendPreference === 'function' ? (getTrendPreference('youtube') || 'JP') : 'JP');
    if (typeof loadTrendsFromCache === 'function') {
        // Rising機能は削除されたため、常にtrendingを使用
        const endpoint = '/api/youtube-trends';
        loadTrendsFromCache({
            serviceName: 'YouTube',
            apiEndpoint: endpoint,
            params: { region: region },
            uiIds: {
                results: 'youtubeResults'
            },
            displayFunction: displayYouTubeResults,
            allPaneSync: { mainTableBodyId: 'youtubeTrendsTableBody', allTableBodyId: 'all-youtubeTrendsTableBody', targetTabId: 'tab-search' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 YouTube Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/youtube-trends?region=' + encodeURIComponent(region) + '&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.data && data.data.length > 0 && typeof displayYouTubeResults === 'function') {
                    displayYouTubeResults(data);
                }
                const resultsElement = document.getElementById('youtubeResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('YouTube Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('youtubeResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// 音楽トレンドキャッシュデータの読み込み（共通化）
// Spotify音楽トレンドキャッシュデータの読み込み
function loadMusicTrendsFromCache() {
    var musicPref = (typeof getTrendPreference === 'function' ? getTrendPreference('music') : null);
    var service = (musicPref && typeof musicPref === 'object' ? musicPref.service : null) || (typeof musicPref === 'string' ? musicPref : null) || 'spotify';
    var region = (musicPref && typeof musicPref === 'object' && musicPref.region) ? musicPref.region : 'JP';
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Music',
            apiEndpoint: '/api/music-trends',
            params: { service: service, region: region },
            uiIds: {
                results: 'musicResults'
            },
            displayFunction: displayMusicResults,
            allPaneSync: { mainTableBodyId: 'musicTrendsTableBody', allTableBodyId: 'all-musicTrendsTableBody', targetTabId: 'tab-search' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Music Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        
        fetchWithRetry('/api/music-trends?service=' + encodeURIComponent(service) + '&region=' + encodeURIComponent(region) + '&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                return response.json();
            })
            .then(data => {
                if (data.success && data.data && Array.isArray(data.data) && data.data.length > 0) {
                    if (typeof displayMusicResults === 'function') {
                        displayMusicResults(data);
                    }
                }
                const resultsElement = document.getElementById('musicResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Music Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('musicResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// ニューストレンドキャッシュデータの読み込み（共通化）
function loadNewsTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'News',
            apiEndpoint: '/api/worldnews-trends',
            params: { country: 'jp', category: 'general' },
            uiIds: {
                results: 'newsResults'
            },
            displayFunction: displayWorldNewsResults,
            alwaysCallDisplay: true,
            allPaneSync: { mainTableBodyId: 'newsTrendsTableBody', allTableBodyId: 'all-newsTrendsTableBody', targetTabId: 'tab-news' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 News Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/worldnews-trends?country=jp&category=general&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                return response.json();
            })
            .then(data => {
                if (data.success && data.data && Array.isArray(data.data) && data.data.length > 0 && typeof displayWorldNewsResults === 'function') {
                    displayWorldNewsResults(data);
                }
                const resultsElement = document.getElementById('newsResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('News Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('newsResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// Podcastトレンドキャッシュデータの読み込み（共通化）
function loadPodcastTrendsFromCache() {
    var podcastPref = (typeof getTrendPreference === 'function' ? getTrendPreference('podcast') : null) || {};
    var podcastParams = Object.assign(
        { trend_type: 'best_podcasts', region: 'jp' },
        typeof podcastPref === 'object' && podcastPref !== null ? podcastPref : {}
    );
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Podcast',
            apiEndpoint: '/api/podcast-trends',
            params: podcastParams,
            uiIds: {
                results: 'podcastResults'
            },
            displayFunction: displayPodcastResults,
            allPaneSync: { mainTableBodyId: 'podcastTrendsTableBody', allTableBodyId: 'all-podcastTrendsTableBody', targetTabId: 'tab-entertainment' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Podcast Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        var podcastQs = new URLSearchParams(podcastParams);
        podcastQs.set('force_refresh', 'false');
        fetchWithRetry('/api/podcast-trends?' + podcastQs.toString(), { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.data && data.data.length > 0 && typeof displayPodcastResults === 'function') {
                    displayPodcastResults(data);
                }
                const resultsElement = document.getElementById('podcastResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Podcast Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('podcastResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// 楽天トレンドキャッシュデータの読み込み（共通化）
function loadRakutenTrendsFromCache() {
    var genreSelect = document.getElementById('rakutenGenreSelect');
    var genreId = genreSelect ? genreSelect.value : (typeof getTrendPreference === 'function' ? (getTrendPreference('rakuten') || 'all') : 'all');
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Rakuten',
            apiEndpoint: '/api/rakuten-trends',
            params: { genre_id: genreId },
            uiIds: {
                results: 'rakutenResults'
            },
            displayFunction: displayRakutenResults,
            allPaneSync: { mainTableBodyId: 'rakutenTrendsTableBody', allTableBodyId: 'all-rakutenTrendsTableBody', targetTabId: 'tab-entertainment' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Rakuten Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/rakuten-trends?genre_id=' + encodeURIComponent(genreId) + '&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.data && data.data.length > 0 && typeof displayRakutenResults === 'function') {
                    displayRakutenResults(data);
                }
                const resultsElement = document.getElementById('rakutenResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Rakuten Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('rakutenResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// はてなブックマークトレンドキャッシュデータの読み込み
function loadHatenaTrendsFromCache() {
    console.log('📊 Hatena Trends キャッシュデータ読み込み');
    
    // 前回選択を復元済みのselectから取得（無ければ'all'）
    const categorySelect = document.getElementById('hatenaCategorySelect');
    const selectedCategory = categorySelect ? categorySelect.value : (typeof getTrendPreference === 'function' ? (getTrendPreference('hatena') || 'all') : 'all');
    
    console.log(`🔍 はてなブックマーク: カテゴリ '${selectedCategory}' のデータを取得中...`);
    
    // ローディング表示
    const loadingElement = document.getElementById('hatenaTrendsLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    
    // AbortControllerを使用したタイムアウト処理（60秒・サーバ応答遅延対策）
    const hatenaTimeoutMs = 60000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), hatenaTimeoutMs);
    
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
                if (typeof syncToAllPane === 'function') {
                    setTimeout(() => syncToAllPane('hatenaTrendsTableBody', 'all-hatenaTrendsTableBody', 5), 0);
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
                console.error(`Hatena Trends キャッシュ読み込みエラー: タイムアウト（${hatenaTimeoutMs / 1000}秒）`);
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
    
    // 前回選択を復元済みのselectから取得（無ければ'games'）
    const typeSelect = document.getElementById('twitchTypeSelect');
    const selectedType = typeSelect ? typeSelect.value : (typeof getTrendPreference === 'function' ? (getTrendPreference('twitch') || 'games') : 'games');
    
    console.log(`🔍 Twitch: タイプ '${selectedType}' のデータを取得中...`);
    
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
                if (typeof syncToAllPane === 'function') {
                    setTimeout(() => syncToAllPane('twitchTrendsTableBody', 'all-twitchTrendsTableBody', 5), 0);
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

// NHK ニュースキャッシュデータの読み込み（共通化）
function loadNHKTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'NHK',
            apiEndpoint: '/api/nhk-trends',
            params: {},
            uiIds: {
                loading: 'nhkLoading',
                results: 'nhkResults'
            },
            displayFunction: displayNHKResults,
            alwaysCallDisplay: true,
            allPaneSync: { mainTableBodyId: 'nhkTrendsTableBody', allTableBodyId: 'all-nhkTrendsTableBody', targetTabId: 'tab-news' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 NHK ニュース キャッシュデータ読み込み');
        const loadingElement = document.getElementById('nhkLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/nhk-trends?force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayNHKResults === 'function') {
                    displayNHKResults(data);
                }
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('NHK ニュース キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
            });
    }
}

// PR TIMES × はてブ キャッシュデータ読み込み
function loadPRTimesHatenaTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'PR TIMES × はてブ',
            apiEndpoint: '/api/prtimes-hatena-trends',
            params: { limit: 5 },
            uiIds: {
                loading: 'prtimesHatenaLoading',
                results: 'prtimesHatenaResults'
            },
            displayFunction: displayPRTimesHatenaResults,
            allPaneSync: { mainTableBodyId: 'prtimesHatenaTrendsTableBody', allTableBodyId: 'all-prtimesHatenaTrendsTableBody', targetTabId: 'tab-news', limit: 5 }
        });
    } else {
        console.log('📊 PR TIMES × はてブ キャッシュデータ読み込み');
        var loadingElement = document.getElementById('prtimesHatenaLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        var controller = new AbortController();
        var timeoutId = setTimeout(function() { controller.abort(); }, 30000);
        fetchWithRetry('/api/prtimes-hatena-trends?limit=5&force_refresh=false', { signal: controller.signal })
            .then(function(response) {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayPRTimesHatenaResults === 'function') {
                    displayPRTimesHatenaResults(data);
                }
                var resultsElement = document.getElementById('prtimesHatenaResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(function(error) {
                clearTimeout(timeoutId);
                console.error('PR TIMES × はてブ キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
                var resultsElement = document.getElementById('prtimesHatenaResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// PR TIMES 単体（RSS）: 紛らわしいためUI非使用。バッチからは呼ばない。
function loadPRTimesTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'PR TIMES',
            apiEndpoint: '/api/prtimes-trends',
            params: {},
            uiIds: {
                loading: 'prtimesLoading'
            },
            displayFunction: displayPRTimesResults,
            allPaneSync: { mainTableBodyId: 'prtimesTrendsTableBody', allTableBodyId: 'all-prtimesTrendsTableBody', targetTabId: 'tab-news' }
        });
    } else {
        console.log('📊 PR TIMES キャッシュデータ読み込み');
        var loadingElement = document.getElementById('prtimesLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        var controller = new AbortController();
        var timeoutId = setTimeout(function() { controller.abort(); }, 30000);
        fetchWithRetry('/api/prtimes-trends?force_refresh=false', { signal: controller.signal })
            .then(function(response) {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayPRTimesResults === 'function') {
                    displayPRTimesResults(data);
                }
                var resultsElement = document.getElementById('prtimesResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(function(error) {
                clearTimeout(timeoutId);
                console.error('PR TIMES キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
                var resultsElement = document.getElementById('prtimesResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// Wikipedia 人気記事 キャッシュデータ読み込み（日本語）
function loadWikipediaTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Wikipedia',
            apiEndpoint: '/api/wikipedia-trends',
            params: { lang: 'ja' },
            uiIds: {
                loading: 'wikipediaLoading',
                results: 'wikipediaResults'
            },
            displayFunction: displayWikipediaResults,
            alwaysCallDisplay: true,
            allPaneSync: { mainTableBodyId: 'wikipediaTrendsTableBody', allTableBodyId: 'all-wikipediaTrendsTableBody', targetTabId: 'tab-search' }
        });
    } else {
        console.log('📊 Wikipedia 人気記事 キャッシュデータ読み込み');
        const loadingElement = document.getElementById('wikipediaLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/wikipedia-trends?lang=ja&limit=25&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.success && typeof displayWikipediaResults === 'function') {
                    displayWikipediaResults(data);
                }
                const resultsElement = document.getElementById('wikipediaResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Wikipedia キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
            });
    }
}

// Qiita トレンドキャッシュデータの読み込み（共通化）
function loadQiitaTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Qiita',
            apiEndpoint: '/api/qiita-trends',
            params: { limit: 25, sort: 'likes_count' },
            uiIds: {
                loading: 'qiitaLoading'
            },
            displayFunction: displayQiitaResults,
            allPaneSync: { mainTableBodyId: 'qiitaTrendsTableBody', allTableBodyId: 'all-qiitaTrendsTableBody', targetTabId: 'tab-tech' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Qiita トレンド キャッシュデータ読み込み');
        const loadingElement = document.getElementById('qiitaLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/qiita-trends?limit=25&sort=likes_count&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayQiitaResults === 'function') {
                    displayQiitaResults(data);
                }
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Qiita トレンド キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
            });
    }
}

// 株価トレンドキャッシュデータの読み込み（共通化）
function loadStockTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Stock',
            apiEndpoint: '/api/stock-trends',
            params: { market: 'JP', limit: 25 },
            uiIds: {
                results: 'stockResults'
            },
            displayFunction: displayStockResults,
            alwaysCallDisplay: true, // データが空でも表示関数を呼び出す（「本日取引はありません」を表示するため）
            allPaneSync: { mainTableBodyId: 'stockTrendsTableBody', allTableBodyId: 'all-stockTrendsTableBody', targetTabId: 'tab-market' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Stock Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/stock-trends?market=JP&limit=25&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (typeof displayStockResults === 'function') {
                    displayStockResults(data);
                }
                const resultsElement = document.getElementById('stockResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Stock Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('stockResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// 仮想通貨トレンドキャッシュデータの読み込み（共通化）
function loadCryptoTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Crypto',
            apiEndpoint: '/api/crypto-trends',
            params: { limit: 25 },
            uiIds: {
                results: 'cryptoResults'
            },
            displayFunction: displayCryptoResults,
            allPaneSync: { mainTableBodyId: 'cryptoTrendsTableBody', allTableBodyId: 'all-cryptoTrendsTableBody', targetTabId: 'tab-market' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Crypto Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/crypto-trends?limit=25&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.data && data.data.length > 0 && typeof displayCryptoResults === 'function') {
                    displayCryptoResults(data);
                }
                const resultsElement = document.getElementById('cryptoResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Crypto Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('cryptoResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// 映画トレンドキャッシュデータの読み込み（共通化）
function loadMovieTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Movie',
            apiEndpoint: '/api/movie-trends',
            params: { country: 'JP' },
            uiIds: {
                loading: 'movieLoading',
                results: 'movieResults'
            },
            displayFunction: displayMovieResults,
            allPaneSync: { mainTableBodyId: 'movieTrendsTableBody', allTableBodyId: 'all-movieTrendsTableBody', targetTabId: 'tab-entertainment' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Movie Trends キャッシュデータ読み込み');
        const loadingElement = document.getElementById('movieLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/movie-trends?country=JP&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayMovieResults === 'function') {
                    displayMovieResults(data);
                }
                const resultsElement = document.getElementById('movieResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Movie Trends キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
                const resultsElement = document.getElementById('movieResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// 本トレンドキャッシュデータの読み込み（5択カテゴリ対応）
// @param {boolean} forceRefresh - カテゴリ切り替え時にAPIから再取得する場合はtrue
function loadBookTrendsFromCache(forceRefresh) {
    var category = 'all';
    var bookCategorySelect = document.getElementById('bookCategorySelect');
    if (bookCategorySelect) category = bookCategorySelect.value || 'all';
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Book',
            apiEndpoint: '/api/book-trends',
            params: { country: 'JP', limit: 25, category: category },
            uiIds: {
                loading: 'bookLoading',
                results: 'bookResults'
            },
            displayFunction: displayBookResults,
            alwaysCallDisplay: true,
            forceRefresh: !!forceRefresh,
            allPaneSync: { mainTableBodyId: 'bookTrendsTableBody', allTableBodyId: 'all-bookTrendsTableBody', targetTabId: 'tab-entertainment' }
        });
    } else {
        console.log('📊 Book Trends キャッシュデータ読み込み (category: ' + category + ', forceRefresh: ' + !!forceRefresh + ')');
        const loadingElement = document.getElementById('bookLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/book-trends?country=JP&limit=25&category=' + encodeURIComponent(category) + '&force_refresh=' + (!!forceRefresh), { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (typeof displayBookResults === 'function') {
                    displayBookResults(data);
                }
                const resultsElement = document.getElementById('bookResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Book Trends キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
                const resultsElement = document.getElementById('bookResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// GitHubトレンドキャッシュデータの読み込み（共通化）
function loadGitHubTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'GitHub',
            apiEndpoint: '/api/github-trends',
            params: { limit: 25 },
            uiIds: {
                results: 'githubResults'
            },
            displayFunction: displayGitHubResults,
            allPaneSync: { mainTableBodyId: 'githubTrendsTableBody', allTableBodyId: 'all-githubTrendsTableBody', targetTabId: 'tab-tech' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 GitHub Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/github-trends?limit=25&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.data && data.data.length > 0 && typeof displayGitHubResults === 'function') {
                    displayGitHubResults(data);
                }
                const resultsElement = document.getElementById('githubResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('GitHub Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('githubResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// App Storeトレンドキャッシュデータの読み込み（共通化）
function loadAppStoreTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'AppStore',
            apiEndpoint: '/api/appstore-trends',
            params: { country: 'JP', limit: 25 },
            uiIds: {
                results: 'appstoreResults'
            },
            displayFunction: displayAppStoreResults,
            allPaneSync: { mainTableBodyId: 'appstoreTrendsTableBody', allTableBodyId: 'all-appstoreTrendsTableBody', targetTabId: 'tab-tech' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 App Store Trends キャッシュデータ読み込み');
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/appstore-trends?country=JP&limit=25&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.data && data.data.length > 0 && typeof displayAppStoreResults === 'function') {
                    displayAppStoreResults(data);
                }
                const resultsElement = document.getElementById('appstoreResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('App Store Trends キャッシュ読み込みエラー:', error);
                const resultsElement = document.getElementById('appstoreResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// IPA注意喚起キャッシュデータの読み込み（共通化）
function loadIPATrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'IPA',
            apiEndpoint: '/api/ipa-trends',
            params: { limit: 25 },
            uiIds: {
                loading: 'ipaLoading',
                results: 'ipaResults'
            },
            displayFunction: displayIPAResults,
            allPaneSync: { mainTableBodyId: 'ipaTrendsTableBody', allTableBodyId: 'all-ipaTrendsTableBody', targetTabId: 'tab-tech' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 IPA Trends キャッシュデータ読み込み');
        const loadingElement = document.getElementById('ipaLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/ipa-trends?limit=25&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayIPAResults === 'function') {
                    displayIPAResults(data);
                }
                const resultsElement = document.getElementById('ipaResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('IPA Trends キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
                const resultsElement = document.getElementById('ipaResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// JPCERT/CCキャッシュデータの読み込み（共通化）
function loadJPCERTTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'JPCERT',
            apiEndpoint: '/api/jpcert-trends',
            params: { limit: 25 },
            uiIds: {
                loading: 'jpcertLoading',
                results: 'jpcertResults'
            },
            displayFunction: displayJPCERTResults,
            allPaneSync: { mainTableBodyId: 'jpcertTrendsTableBody', allTableBodyId: 'all-jpcertTrendsTableBody', targetTabId: 'tab-tech' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 JPCERT/CC Trends キャッシュデータ読み込み');
        const loadingElement = document.getElementById('jpcertLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/jpcert-trends?limit=25&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayJPCERTResults === 'function') {
                    displayJPCERTResults(data);
                }
                const resultsElement = document.getElementById('jpcertResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('JPCERT/CC Trends キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
                const resultsElement = document.getElementById('jpcertResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// Zennキャッシュデータの読み込み（共通化）
function loadZennTrendsFromCache() {
    if (typeof loadTrendsFromCache === 'function') {
        loadTrendsFromCache({
            serviceName: 'Zenn',
            apiEndpoint: '/api/zenn-trends',
            params: { limit: 25 },
            uiIds: {
                loading: 'zennLoading',
                results: 'zennResults'
            },
            displayFunction: displayZennResults,
            allPaneSync: { mainTableBodyId: 'zennTrendsTableBody', allTableBodyId: 'all-zennTrendsTableBody', targetTabId: 'tab-tech' }
        });
    } else {
        // フォールバック（共通関数が利用できない場合）
        console.log('📊 Zenn Trends キャッシュデータ読み込み');
        const loadingElement = document.getElementById('zennLoading');
        if (loadingElement) loadingElement.style.display = 'block';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        fetchWithRetry('/api/zenn-trends?limit=25&force_refresh=false', { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (loadingElement) loadingElement.style.display = 'none';
                if (data.data && data.data.length > 0 && typeof displayZennResults === 'function') {
                    displayZennResults(data);
                }
                const resultsElement = document.getElementById('zennResults');
                if (resultsElement) resultsElement.style.display = 'block';
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Zenn Trends キャッシュ読み込みエラー:', error);
                if (loadingElement) loadingElement.style.display = 'none';
                const resultsElement = document.getElementById('zennResults');
                if (resultsElement) resultsElement.style.display = 'block';
            });
    }
}

// Noteキャッシュデータの読み込み（カテゴリ対応）
function loadNoteTrendsFromCache() {
    // 選択されたカテゴリーを取得
    const categorySelect = document.getElementById('noteCategorySelect');
    const selectedCategory = categorySelect ? categorySelect.value : 'all';
    
    console.log(`📊 Note Trends キャッシュデータ読み込み (category: ${selectedCategory})`);
    const loadingElement = document.getElementById('noteLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    fetchWithRetry(`/api/note-trends?category=${selectedCategory}&limit=25&force_refresh=false`, { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('Note Trends API レスポンス:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('Note Trends API データ:', data);
            if (data.data && data.data.length > 0) {
                console.log('Note Trends データ表示開始');
                if (typeof displayNoteResults === 'function') {
                    displayNoteResults(data);
                } else {
                    console.error('displayNoteResults関数が見つかりません');
                }
                if (typeof syncToAllPane === 'function') {
                    setTimeout(() => syncToAllPane('noteTrendsTableBody', 'all-noteTrendsTableBody', 5), 0);
                }
            } else {
                console.log('Note Trends データなしまたはエラー:', data);
            }
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            const resultsElement = document.getElementById('noteResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error('Note Trends キャッシュ読み込みエラー: タイムアウト（30秒）');
            } else {
                console.error('Note Trends キャッシュ読み込みエラー:', error);
            }
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            const resultsElement = document.getElementById('noteResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}


