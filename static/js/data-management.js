// データ管理とキャッシュ表示に関するJavaScriptファイル

// キャッシュデータを自動読み込み（外部から呼び出し用）
function loadCachedDataExternal() {
    console.log('📦 キャッシュデータの読み込み処理開始');
    
    // 全カテゴリを並列実行（HatenaとTwitchも即座に実行）
    const allCategories = [
        loadGoogleTrendsFromCache,
        loadYouTubeTrendsFromCache,
        loadMusicTrendsFromCache,
        loadNewsTrendsFromCache,
        loadStockTrendsFromCache,
        loadCryptoTrendsFromCache,
        loadPodcastTrendsFromCache,
        loadRakutenTrendsFromCache,
        loadHatenaTrendsFromCache,
        loadTwitchTrendsFromCache,
        loadNHKTrendsFromCache,
        loadQiitaTrendsFromCache
    ];
    
    // 全カテゴリを並列実行（エラーハンドリング付き）
    console.log('🚀 全カテゴリの並列読み込み開始');
    console.log('🚀 実行する関数:', allCategories.map(f => f.name));
    allCategories.forEach(loadFunction => {
        try {
            console.log(`🚀 実行中: ${loadFunction.name}`);
            loadFunction();
        } catch (error) {
            console.error(`❌ ${loadFunction.name} 実行エラー:`, error);
        }
    });
    
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
    
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/google-trends?country=JP'),
        timeoutPromise
    ])
        .then(response => {
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
                displayGoogleResults(data);
            } else {
                console.log('Google Trends データなしまたはエラー:', data);
            }
            
            // ローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Google Trends キャッシュ読み込みエラー:', error);
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

// YouTube Trendsキャッシュデータの読み込み
function loadYouTubeTrendsFromCache() {
    console.log('📊 YouTube Trends キャッシュデータ読み込み');
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/youtube-trends?region=JP'),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('YouTube Trends キャッシュ読み込みエラー:', error);
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
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/music-trends?service=spotify'),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('Music Trends キャッシュ読み込みエラー:', error);
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
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/worldnews-trends?country=jp&category=general'),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('News Trends キャッシュ読み込みエラー:', error);
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
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    Promise.race([
        fetch('/api/podcast-trends?trend_type=best_podcasts&force_refresh=false'),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('Podcast Trends キャッシュ読み込みエラー:', error);
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
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/rakuten-trends'),
        timeoutPromise
    ])
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.data && data.data.length > 0) {
                if (typeof displayRakutenResults === 'function') {
                    displayRakutenResults(data);
                } else {
                    console.error('displayRakutenResults関数が見つかりません');
                }
            }
        })
        .catch(error => {
            console.error('Rakuten Trends キャッシュ読み込みエラー:', error);
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
    
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    Promise.race([
        fetch(`/api/hatena-trends?category=${selectedCategory}&limit=25&type=hot&force_refresh=false`),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('Hatena Trends キャッシュ読み込みエラー:', error);
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
    
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示（force_refresh=falseで明示的にキャッシュのみを使用）
    Promise.race([
        fetch(`/api/twitch-trends?type=${selectedType}&limit=25&force_refresh=false`),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('Twitch Trends キャッシュ読み込みエラー:', error);
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
    
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/nhk-trends'),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('NHK ニュース キャッシュ読み込みエラー:', error);
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
    
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/qiita-trends?limit=25&sort=likes_count'),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('Qiita トレンド キャッシュ読み込みエラー:', error);
            // エラー時もローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        });
}

// 株価トレンドキャッシュデータの読み込み
function loadStockTrendsFromCache() {
    console.log('📊 Stock Trends キャッシュデータ読み込み');
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/stock-trends?market=JP&limit=25'),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('Stock Trends キャッシュ読み込みエラー:', error);
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
    // タイムアウトを設定（キャッシュからの取得を想定、マネージャー初期化待機を考慮して15秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト（15秒）')), 15000);
    });
    
    // キャッシュデータを取得して表示
    Promise.race([
        fetch('/api/crypto-trends?limit=25'),
        timeoutPromise
    ])
        .then(response => {
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
            console.error('Crypto Trends キャッシュ読み込みエラー:', error);
            // エラー時でも結果エリアを表示（空でも）
            const resultsElement = document.getElementById('cryptoResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}


