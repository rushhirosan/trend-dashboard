// データ管理とキャッシュ表示に関するJavaScriptファイル

// キャッシュデータを自動読み込み（外部から呼び出し用）
function loadCachedDataExternal() {
    console.log('📦 キャッシュデータの読み込み処理開始');
    
    // 高速カテゴリ（並列実行）
    const fastCategories = [
        loadGoogleTrendsFromCache,
        loadYouTubeTrendsFromCache,
        loadMusicTrendsFromCache,
        loadNewsTrendsFromCache,
        loadPodcastTrendsFromCache,
        loadRakutenTrendsFromCache
    ];
    
    // 低速カテゴリ（個別実行、優先度低）
    const slowCategories = [
        loadHatenaTrendsFromCache,
        loadTwitchTrendsFromCache
    ];
    
    // 高速カテゴリを並列実行
    console.log('🚀 高速カテゴリの並列読み込み開始');
    console.log('🚀 実行する関数:', fastCategories.map(f => f.name));
    fastCategories.forEach(loadFunction => {
        console.log(`🚀 実行中: ${loadFunction.name}`);
        loadFunction();
    });
    
    // 低速カテゴリを遅延実行（ユーザー体験向上）
    setTimeout(() => {
        console.log('⏳ 低速カテゴリの読み込み開始');
        slowCategories.forEach(loadFunction => {
            loadFunction();
        });
    }, 1000); // 1秒後に開始
    
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
    
    // キャッシュデータを取得して表示
    fetch('/api/google-trends?country=JP')
        .then(response => {
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
        });
}

// YouTube Trendsキャッシュデータの読み込み
function loadYouTubeTrendsFromCache() {
    console.log('📊 YouTube Trends キャッシュデータ読み込み');
    // キャッシュデータを取得して表示
    fetch('/api/youtube-trends?region=JP')
        .then(response => {
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
        .catch(error => console.error('YouTube Trends キャッシュ読み込みエラー:', error));
}

// 音楽トレンドキャッシュデータの読み込み
function loadMusicTrendsFromCache() {
    console.log('📊 Music Trends キャッシュデータ読み込み - 関数開始');
    console.log('📊 DOM要素確認:', {
        musicResults: !!document.getElementById('musicResults'),
        musicTrendsTableBody: !!document.getElementById('musicTrendsTableBody'),
        displayMusicResults: typeof displayMusicResults
    });
    // キャッシュデータを取得して表示
    fetch('/api/music-trends?service=spotify')
        .then(response => {
            console.log('Music Trends API レスポンス:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('Music Trends API データ:', data);
            console.log('Music Trends データ詳細:', {
                hasData: !!data.data,
                dataLength: data.data ? data.data.length : 0,
                dataType: typeof data.data,
                success: data.success,
                keys: Object.keys(data)
            });
            
            if (data.data && data.data.length > 0) {
                console.log('✅ Music Trends データ表示開始 - データあり');
                console.log('✅ データ詳細:', {
                    dataLength: data.data.length,
                    firstItem: data.data[0]
                });
                if (typeof displayMusicResults === 'function') {
                    console.log('✅ displayMusicResults関数を呼び出し中...');
                    try {
                        displayMusicResults(data);
                        console.log('✅ displayMusicResults関数呼び出し完了');
                    } catch (error) {
                        console.error('❌ displayMusicResults実行エラー:', error);
                    }
                } else {
                    console.error('❌ displayMusicResults関数が見つかりません');
                    console.log('利用可能な関数:', Object.keys(window).filter(key => key.includes('display')));
                }
            } else {
                console.log('❌ Music Trends データなしまたはエラー:', data);
                console.log('条件チェック結果:', {
                    dataExists: !!data.data,
                    dataLength: data.data ? data.data.length : 'N/A',
                    condition: !!(data.data && data.data.length > 0)
                });
            }
        })
        .catch(error => console.error('Music Trends キャッシュ読み込みエラー:', error));
}

// ニューストレンドキャッシュデータの読み込み
function loadNewsTrendsFromCache() {
    console.log('📊 News Trends キャッシュデータ読み込み');
    // キャッシュデータを取得して表示
    fetch('/api/worldnews-trends?country=jp&category=general')
        .then(response => response.json())
        .then(data => {
            if (data.data && data.data.length > 0) {
                if (typeof displayWorldNewsResults === 'function') {
                    displayWorldNewsResults(data);
                } else {
                    console.error('displayWorldNewsResults関数が見つかりません');
                }
            }
        })
        .catch(error => console.error('News Trends キャッシュ読み込みエラー:', error));
}

// Podcastトレンドキャッシュデータの読み込み
function loadPodcastTrendsFromCache() {
    console.log('📊 Podcast Trends キャッシュデータ読み込み');
    // キャッシュデータを取得して表示
    fetch('/api/podcast-trends?trend_type=best_podcasts')
        .then(response => response.json())
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
        .catch(error => console.error('Podcast Trends キャッシュ読み込みエラー:', error));
}

// 楽天トレンドキャッシュデータの読み込み
function loadRakutenTrendsFromCache() {
    console.log('📊 Rakuten Trends キャッシュデータ読み込み');
    // キャッシュデータを取得して表示
    fetch('/api/rakuten-trends')
        .then(response => response.json())
        .then(data => {
            if (data.data && data.data.length > 0) {
                if (typeof displayRakutenResults === 'function') {
                    displayRakutenResults(data);
                } else {
                    console.error('displayRakutenResults関数が見つかりません');
                }
            }
        })
        .catch(error => console.error('Rakuten Trends キャッシュ読み込みエラー:', error));
}

// はてなブックマークトレンドキャッシュデータの読み込み
function loadHatenaTrendsFromCache() {
    console.log('📊 Hatena Trends キャッシュデータ読み込み');
    
    // ローディング表示
    const loadingElement = document.getElementById('hatenaTrendsLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    
    // キャッシュデータを取得して表示
    fetch('/api/hatena-trends?category=all&limit=25&type=hot')
        .then(response => response.json())
        .then(data => {
            if (data.data && data.data.length > 0) {
                if (typeof displayHatenaResults === 'function') {
                    displayHatenaResults(data);
                } else {
                    console.error('displayHatenaResults関数が見つかりません');
                }
            }
            
            // ローディング表示を非表示
            if (loadingElement) {
                loadingElement.style.display = 'none';
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
    
    // ローディング表示を最初から非表示
    const loadingElement = document.getElementById('twitchTrendsLoading');
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
    
    // キャッシュデータを取得して表示
    fetch('/api/twitch-trends?type=games')
        .then(response => response.json())
        .then(data => {
            // ローディング表示を確実に非表示
            const loadingElement = document.getElementById('twitchTrendsLoading');
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            
            if (data.data && data.data.length > 0) {
                if (typeof displayTwitchResults === 'function') {
                    displayTwitchResults(data);
                } else {
                    console.error('displayTwitchResults関数が見つかりません');
                }
            } else {
                console.log('Twitch Trends データなしまたはエラー:', data);
            }
        })
        .catch(error => {
            console.error('Twitch Trends キャッシュ読み込みエラー:', error);
            // エラー時もローディング表示を非表示
            const loadingElement = document.getElementById('twitchTrendsLoading');
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


