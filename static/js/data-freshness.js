// データ鮮度管理に関するJavaScriptファイル

// キャッシュの最終更新時刻を取得する関数
function getCacheLastUpdate(platform, platformName, lastUpdateElement, dataCountElement, statusElement, dataCount) {
    // プラットフォームごとのAPIエンドポイントを設定
    let apiEndpoint = '';
    let params = '';
    
    switch(platform) {
        case 'google':
            apiEndpoint = '/api/google-trends';
            params = '?country=JP';
            break;
        case 'youtube':
            apiEndpoint = '/api/youtube-trends';
            params = '?region=JP';
            break;
        case 'spotify':
            apiEndpoint = '/api/music-trends';
            params = '?service=spotify';
            break;
        case 'news':
            apiEndpoint = '/api/worldnews-trends';
            params = '?country=jp&category=general';
            break;
        case 'podcast':
            apiEndpoint = '/api/podcast-trends';
            params = '?trend_type=best_podcasts';
            break;
        case 'rakuten':
            apiEndpoint = '/api/rakuten-trends';
            params = '';
            break;
        case 'hatena':
            apiEndpoint = '/api/hatena-trends';
            params = '?category=all&limit=25&type=hot';
            break;
        case 'twitch':
            apiEndpoint = '/api/twitch-trends';
            params = '?type=games';
            break;
        case 'nhk':
            apiEndpoint = '/api/nhk-trends';
            params = '';
            break;
        case 'qiita':
            apiEndpoint = '/api/qiita-trends';
            params = '?limit=25&sort=likes_count';
            break;
        case 'zenn':
            apiEndpoint = '/api/zenn-trends';
            params = '?limit=25';
            break;
        case 'note':
            apiEndpoint = '/api/note-trends';
            params = '?category=all&limit=25';
            break;
        case 'ipa':
            apiEndpoint = '/api/ipa-trends';
            params = '?limit=25';
            break;
        case 'jpcert':
            apiEndpoint = '/api/jpcert-trends';
            params = '?limit=25';
            break;
        case 'stock':
            apiEndpoint = '/api/stock-trends';
            params = '?market=JP&limit=25';
            break;
        case 'crypto':
            apiEndpoint = '/api/crypto-trends';
            params = '?limit=25';
            break;
        case 'movie':
            apiEndpoint = '/api/movie-trends';
            params = '?country=JP';
            break;
        case 'book':
            apiEndpoint = '/api/book-trends';
            params = '?country=JP';
            break;
        case 'github':
            apiEndpoint = '/api/github-trends';
            params = '?language=all&limit=25';
            break;
        case 'appstore':
            apiEndpoint = '/api/appstore-trends';
            params = '?country=JP&category=all&limit=25';
            break;
        case 'cnn':
            apiEndpoint = '/api/cnn-trends';
            params = '?limit=25';
            break;
        case 'producthunt':
            apiEndpoint = '/api/producthunt-trends';
            params = '?limit=25&sort=votes';
            break;
        default:
            console.warn(`⚠️ 未知のプラットフォーム: ${platform}`);
            return;
    }
    
    // タイムアウトを設定（3秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト')), 3000);
    });
    
    // キャッシュ情報を取得（日本のセクション用）
    Promise.race([
        fetch('/api/cache/data-freshness?country=JP'),
        timeoutPromise
    ])
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.data) {
                // プラットフォーム名をdata_routes.pyのdisplay_nameにマッピング
                // data_routes.pyのget_data_freshness関数で返されるdisplay_nameと一致させる
                const platformNameMap = {
                    'NHK ニュース': 'NHK ニュース',
                    'World News': 'World News',
                    'Google Trends': 'Google Trends',
                    'YouTube': 'YouTube',
                    'はてなブックマーク': 'はてなブックマーク',
                    'Qiita トレンド': 'Qiita トレンド',
                    'Zenn': 'Zenn',
                    'Note': 'Note (総合)',  // data_routes.pyでは'Note (総合)'として登録
                    'Note (総合)': 'Note (総合)',
                    'IPA': 'IPA',
                    'IPA注意喚起': 'IPA',
                    'JPCERT/CC': 'JPCERT/CC',
                    'GitHub': 'GitHub',
                    'App Store': 'App Store',
                    '株価トレンド': '株価トレンド',
                    '仮想通貨トレンド': '仮想通貨トレンド',
                    '映画トレンド': '映画トレンド',
                    '本トレンド': '本トレンド',
                    'Spotify': 'Spotify',
                    'Podcast': 'Podcast',
                    '楽天': '楽天',
                    'Twitch': 'Twitch'
                };
                
                const displayName = platformNameMap[platformName] || platformName;
                const cacheInfo = data.data[displayName];
                
                if (cacheInfo) {
                    let lastUpdate = '不明';
                       if (cacheInfo.last_updated && cacheInfo.last_updated !== 'None' && cacheInfo.last_updated !== null) {
                           try {
                               // データベースの時刻をUTCとして解釈（タイムゾーン情報がない場合はZを付与）
                               let timeString = String(cacheInfo.last_updated);
                               
                               // マイクロ秒（6桁以上）をミリ秒（3桁）に変換
                               if (timeString.includes('.')) {
                                   const parts = timeString.split('.');
                                   if (parts.length === 2) {
                                       const integerPart = parts[0];
                                       const decimalPart = parts[1];
                                       if (decimalPart.length >= 6) {
                                           timeString = integerPart + '.' + decimalPart.substring(0, 3);
                                       } else if (decimalPart.length > 3) {
                                           timeString = integerPart + '.' + decimalPart.substring(0, 3);
                                       }
                                   }
                               }
                               
                               // タイムゾーン情報がない場合はUTCとして扱うために'Z'を付与
                               const dateString = timeString.match(/[Z+-]\d{2}:?\d{2}$/)
                                   ? timeString
                                   : `${timeString}Z`;
                               
                               const date = new Date(dateString);
                               
                               if (isNaN(date.getTime())) {
                                   console.error('Invalid date after conversion:', {
                                       original: cacheInfo.last_updated,
                                       converted: timeString,
                                       dateString: dateString
                                   });
                                   throw new Error('Invalid date');
                               }
                               
                               // JSTで表示
                               lastUpdate = date.toLocaleString('ja-JP', {
                                   year: 'numeric',
                                   month: '2-digit',
                                   day: '2-digit',
                                   hour: '2-digit',
                                   minute: '2-digit',
                                   second: '2-digit',
                                   timeZone: 'Asia/Tokyo'
                               });
                           } catch (e) {
                               console.error('Error parsing date:', cacheInfo.last_updated, e);
                               lastUpdate = '不明';
                           }
                       }
                    const fetchedCount = cacheInfo.data_count || 0; // 取得件数
                    const status = fetchedCount > 0 ? '取得済み' : '未取得';
                    
                    // DOM要素を更新
                    lastUpdateElement.textContent = lastUpdate;
                    statusElement.textContent = status;
                    statusElement.className = fetchedCount > 0 ? 'badge bg-success' : 'badge bg-secondary';
                    
                    // すべてのトレンドで表示件数と取得件数を分けて表示
                    if (fetchedCount > 0 && apiEndpoint) {
                        // APIを呼び出して表示件数を取得
                        const forceRefreshParam = params.includes('?') ? '&force_refresh=false' : '?force_refresh=false';
                        const fullEndpoint = apiEndpoint + params + forceRefreshParam;
                        
                        fetch(fullEndpoint)
                            .then(response => response.json())
                            .then(apiData => {
                                const displayCount = (apiData.success && apiData.data && Array.isArray(apiData.data)) 
                                    ? apiData.data.length 
                                    : fetchedCount;
                                
                                // 表示件数と取得件数を分けて表示（日英併記）
                                if (displayCount === fetchedCount) {
                                    // 表示件数と取得件数が同じ場合は取得件数のみ表示（日英併記）
                                    dataCountElement.textContent = `${fetchedCount}件 / ${fetchedCount}`;
                                } else {
                                    // 表示件数と取得件数が異なる場合は「表示件数25件 (取得件数60件) / Display: 25 (Fetched: 60)」の形式で表示
                                    dataCountElement.textContent = `表示件数${displayCount}件 (取得件数${fetchedCount}件) / Display: ${displayCount} (Fetched: ${fetchedCount})`;
                                }
                            })
                            .catch(error => {
                                console.warn(`⚠️ ${platformName} 表示件数取得エラー:`, error);
                                // エラー時は取得件数のみ表示（日英併記）
                                dataCountElement.textContent = `${fetchedCount}件 / ${fetchedCount}`;
                            });
                    } else {
                        // APIエンドポイントがない場合や取得件数が0の場合は取得件数のみ表示（日英併記）
                        dataCountElement.textContent = `${fetchedCount}件 / ${fetchedCount}`;
                    }
                } else {
                    // キャッシュ情報が見つからない場合
                    console.warn(`⚠️ ${platformName}: キャッシュ情報が見つかりません`, {
                        platformName: platformName,
                        displayName: displayName,
                        availableKeys: Object.keys(data.data)
                    });
                    
                    // フォールバック: 直接APIエンドポイントを呼び出してデータを確認
                    if (apiEndpoint) {
                        // すべてのトレンドでforce_refresh=falseを追加（外部APIを呼び出さないようにする）
                        const forceRefreshParam = params.includes('?') ? '&force_refresh=false' : '?force_refresh=false';
                        const fullEndpoint = apiEndpoint + params + forceRefreshParam;
                        
                        fetch(fullEndpoint)
                            .then(response => response.json())
                            .then(apiData => {
                                if (apiData.success && apiData.data && apiData.data.length > 0) {
                                    const apiDataCount = apiData.data.length;
                                    lastUpdateElement.textContent = 'データあり（キャッシュ情報なし）';
                                    dataCountElement.textContent = `${apiDataCount}件 / ${apiDataCount}`;
                                    statusElement.textContent = '取得済み';
                                    statusElement.className = 'badge bg-success';
                                } else {
                                    lastUpdateElement.textContent = 'データなし';
                                    dataCountElement.textContent = '0件 / 0';
                                    statusElement.textContent = '未取得';
                                    statusElement.className = 'badge bg-secondary';
                                }
                            })
                            .catch(error => {
                                console.error(`❌ ${platformName} API呼び出しエラー:`, error);
                                lastUpdateElement.textContent = 'データなし';
                                dataCountElement.textContent = '0件 / 0';
                                statusElement.textContent = '未取得';
                                statusElement.className = 'badge bg-secondary';
                            });
                    } else {
                        lastUpdateElement.textContent = 'データなし';
                        dataCountElement.textContent = '0件 / 0';
                        statusElement.textContent = '未取得';
                        statusElement.className = 'badge bg-secondary';
                    }
                }
            } else {
                // エラー時またはデータが存在しない場合
                console.warn(`⚠️ ${platformName}: キャッシュ情報の取得に失敗しました`, {
                    success: data.success,
                    data: data.data
                });
                
                // フォールバック: 直接APIエンドポイントを呼び出してデータを確認
                if (apiEndpoint) {
                    // すべてのトレンドでforce_refresh=falseを追加（外部APIを呼び出さないようにする）
                    const forceRefreshParam = params.includes('?') ? '&force_refresh=false' : '?force_refresh=false';
                    const fullEndpoint = apiEndpoint + params + forceRefreshParam;
                    
                    fetch(fullEndpoint)
                        .then(response => response.json())
                        .then(apiData => {
                            if (apiData.success && apiData.data && apiData.data.length > 0) {
                                const apiDataCount = apiData.data.length;
                                lastUpdateElement.textContent = 'データあり（キャッシュ情報なし）';
                                dataCountElement.textContent = `${apiDataCount}件 / ${apiDataCount}`;
                                statusElement.textContent = '取得済み';
                                statusElement.className = 'badge bg-success';
                            } else {
                                lastUpdateElement.textContent = 'エラー';
                                dataCountElement.textContent = '0件 / 0';
                                statusElement.textContent = 'エラー';
                                statusElement.className = 'badge bg-danger';
                            }
                        })
                        .catch(error => {
                            console.error(`❌ ${platformName} API呼び出しエラー:`, error);
                            lastUpdateElement.textContent = 'エラー';
                            dataCountElement.textContent = '0件 / 0';
                            statusElement.textContent = 'エラー';
                            statusElement.className = 'badge bg-danger';
                        });
                } else {
                    lastUpdateElement.textContent = 'エラー';
                    dataCountElement.textContent = '0件 / 0';
                    statusElement.textContent = 'エラー';
                    statusElement.className = 'badge bg-danger';
                }
            }
        })
        .catch(error => {
            console.error(`❌ ${platformName} キャッシュ情報取得エラー:`, error);
            lastUpdateElement.textContent = 'エラー';
            dataCountElement.textContent = '0件 / 0';
            statusElement.textContent = 'エラー';
            statusElement.className = 'badge bg-danger';
        });
    
    // テキスト内容を強制的に表示
    lastUpdateElement.style.display = 'block';
    lastUpdateElement.style.visibility = 'visible';
    lastUpdateElement.style.opacity = '1';
    lastUpdateElement.style.color = 'inherit';
    
    dataCountElement.style.display = 'block';
    dataCountElement.style.visibility = 'visible';
    dataCountElement.style.opacity = '1';
    dataCountElement.style.color = 'inherit';
    
    statusElement.style.display = 'inline-block';
    statusElement.style.visibility = 'visible';
    statusElement.style.opacity = '1';
}

// データ鮮度情報を更新する関数（外部から呼び出し用）
function refreshDataFreshnessExternal() {
    // 各プラットフォームのデータ鮮度を更新（キャッシュのみ、API呼び出しなし）
    // トレンドページの順序に合わせる: NHK → World News → Google → YouTube → はてな → Qiita → 株価 → 仮想通貨 → Spotify → Podcast → 映画 → 本 → 楽天 → Twitch
    updatePlatformStatusExternal('nhk', 'NHK ニュース');
    updatePlatformStatusExternal('news', 'World News');
    updatePlatformStatusExternal('google', 'Google Trends');
    updatePlatformStatusExternal('youtube', 'YouTube');
    updatePlatformStatusExternal('hatena', 'はてなブックマーク');
    updatePlatformStatusExternal('qiita', 'Qiita トレンド');
    updatePlatformStatusExternal('zenn', 'Zenn');
    updatePlatformStatusExternal('note', 'Note');
    updatePlatformStatusExternal('ipa', 'IPA注意喚起');
    updatePlatformStatusExternal('jpcert', 'JPCERT/CC');
    updatePlatformStatusExternal('stock', '株価トレンド');
    updatePlatformStatusExternal('crypto', '仮想通貨トレンド');
    updatePlatformStatusExternal('spotify', 'Spotify');
    updatePlatformStatusExternal('podcast', 'Podcast');
    updatePlatformStatusExternal('movie', '映画トレンド');
    updatePlatformStatusExternal('book', '本トレンド');
    updatePlatformStatusExternal('github', 'GitHub');
    updatePlatformStatusExternal('appstore', 'App Store');
    updatePlatformStatusExternal('rakuten', '楽天');
    updatePlatformStatusExternal('twitch', 'Twitch');
    
    // テキスト要素を強制的に表示
    setTimeout(() => {
        // 日本トレンドページの順序に合わせる
        const platforms = ['nhk', 'news', 'google', 'youtube', 'hatena', 'qiita', 'zenn', 'note', 'ipa', 'jpcert', 'github', 'appstore', 'stock', 'crypto', 'movie', 'book', 'spotify', 'podcast', 'rakuten', 'twitch'];
        platforms.forEach(platform => {
            const lastUpdateElement = document.getElementById(`${platform}LastUpdate`);
            const dataCountElement = document.getElementById(`${platform}DataCount`);
            const statusElement = document.getElementById(`${platform}Status`);
            
            if (lastUpdateElement) {
                lastUpdateElement.style.display = 'block';
                lastUpdateElement.style.visibility = 'visible';
                lastUpdateElement.style.opacity = '1';
                lastUpdateElement.style.color = '#000';
                lastUpdateElement.style.fontSize = '14px';
                lastUpdateElement.style.fontWeight = 'bold';
            }
            
            if (dataCountElement) {
                dataCountElement.style.display = 'block';
                dataCountElement.style.visibility = 'visible';
                dataCountElement.style.opacity = '1';
                dataCountElement.style.color = '#000';
                dataCountElement.style.fontSize = '14px';
                dataCountElement.style.fontWeight = 'bold';
            }
            
            if (statusElement) {
                statusElement.style.display = 'inline-block';
                statusElement.style.visibility = 'visible';
                statusElement.style.opacity = '1';
            }
        });
        
        const dataStatusTab = document.getElementById('data-status');
        if (dataStatusTab) {
            // 強制的に表示
            dataStatusTab.style.display = 'block';
            dataStatusTab.style.visibility = 'visible';
            dataStatusTab.style.opacity = '1';
            dataStatusTab.style.height = 'auto';
            dataStatusTab.style.minHeight = '500px';
            dataStatusTab.classList.add('show', 'active');
            
            // 全てのテキスト要素を強制的に表示
            const allTextElements = dataStatusTab.querySelectorAll('*');
            allTextElements.forEach(element => {
                element.style.display = 'block';
                element.style.visibility = 'visible';
                element.style.opacity = '1';
                element.style.color = 'inherit';
            });
            
            // インライン要素を適切に設定
            const inlineElements = dataStatusTab.querySelectorAll('.text-muted, .badge, small');
            inlineElements.forEach(element => {
                element.style.display = 'inline-block';
            });
            
            // カードグリッドの高さも確保
            const cardGrid = dataStatusTab.querySelector('.row.g-3');
            if (cardGrid) {
                cardGrid.style.minHeight = '400px';
                cardGrid.style.display = 'flex';
                cardGrid.style.flexWrap = 'wrap';
            }
            
            // 各カードの高さも確保
            const cards = dataStatusTab.querySelectorAll('.card.h-100');
            cards.forEach(card => {
                card.style.minHeight = '200px';
                card.style.height = '100%';
            });
        }
    }, 1000);
}

// テスト用のシンプルなデータ表示関数（開発用、本番では使用しない）
function testDataFreshnessDisplay() {
    const platforms = ['google', 'youtube', 'spotify', 'news', 'podcast', 'rakuten', 'hatena', 'twitch'];
    
    platforms.forEach(platform => {
        const lastUpdateElement = document.getElementById(`${platform}LastUpdate`);
        const dataCountElement = document.getElementById(`${platform}DataCount`);
        const statusElement = document.getElementById(`${platform}Status`);
        
        if (lastUpdateElement) {
            lastUpdateElement.textContent = 'テスト時刻';
        }
        
        if (dataCountElement) {
            dataCountElement.textContent = '10件';
        }
        
        if (statusElement) {
            statusElement.textContent = 'テスト';
            statusElement.className = 'badge bg-success';
        }
    });
}

// windowオブジェクトに関数を設定（外部から呼び出し可能にする）
window.refreshDataFreshnessExternal = refreshDataFreshnessExternal;
window.updatePlatformStatusExternal = updatePlatformStatusExternal;
window.testDataFreshnessDisplay = testDataFreshnessDisplay;

// プラットフォームのステータスを更新（外部から呼び出し用）
function updatePlatformStatusExternal(platform, platformName) {
    const lastUpdateElement = document.getElementById(`${platform}LastUpdate`);
    const dataCountElement = document.getElementById(`${platform}DataCount`);
    const statusElement = document.getElementById(`${platform}Status`);
    
    if (!lastUpdateElement || !dataCountElement || !statusElement) {
        console.warn(`⚠️ ${platformName}のDOM要素が見つかりません`);
        return;
    }
    
    // データ件数を取得（テーブルの行数をカウント）
    // Spotifyの場合は特別にmusicTrendsTableBodyを使用
    let tableBodyId = `${platform}TrendsTableBody`;
    if (platform === 'spotify') {
        tableBodyId = 'musicTrendsTableBody';
    }
    
    const tableBody = document.getElementById(tableBodyId);
    let dataCount = 0;
    if (tableBody && tableBody.children.length > 0) {
        dataCount = tableBody.children.length;
    }
    
    // キャッシュの実際の最終更新時刻を取得
    getCacheLastUpdate(platform, platformName, lastUpdateElement, dataCountElement, statusElement, dataCount);
    
    if (dataCount > 0) {
        statusElement.textContent = '取得済み';
        statusElement.className = 'badge bg-success';
    } else {
        statusElement.textContent = '未取得';
        statusElement.className = 'badge bg-secondary';
    }
    
    // テキスト内容を強制的に表示
    lastUpdateElement.style.display = 'block';
    lastUpdateElement.style.visibility = 'visible';
    lastUpdateElement.style.opacity = '1';
    lastUpdateElement.style.color = 'inherit';
    
    dataCountElement.style.display = 'block';
    dataCountElement.style.visibility = 'visible';
    dataCountElement.style.opacity = '1';
    dataCountElement.style.color = 'inherit';
    
    statusElement.style.display = 'inline-block';
    statusElement.style.visibility = 'visible';
    statusElement.style.opacity = '1';
}

// 一括取得ボタンの処理（外部から呼び出し用）
function triggerBulkFetchExternal() {
    // 各プラットフォームのデータを順次取得
    const fetchPromises = [];
    
    // Google Trends
    fetchPromises.push(
        fetch('/api/google-trends?country=JP')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayGoogleResults(data);
                }
            })
            .catch(error => console.error('Google Trends取得エラー:', error))
    );
    
    // YouTube Trends
    fetchPromises.push(
        fetch('/api/youtube-trends?region=JP')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayYouTubeResults(data);
                }
            })
            .catch(error => console.error('YouTube Trends取得エラー:', error))
    );
    
    // 音楽トレンド
    fetchPromises.push(
        fetch('/api/music-trends?service=spotify')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayMusicResults(data);
                }
            })
            .catch(error => console.error('音楽トレンド取得エラー:', error))
    );
    
    // ニューストレンド
    fetchPromises.push(
        fetch('/api/worldnews-trends?country=jp&category=general')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayWorldNewsResults(data);
                }
            })
            .catch(error => console.error('ニューストレンド取得エラー:', error))
    );
    
    // 楽天トレンド
    fetchPromises.push(
        fetch('/api/rakuten-trends')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayRakutenResults(data);
                }
            })
            .catch(error => console.error('楽天トレンド取得エラー:', error))
    );
    
    // はてなブックマークトレンド
    fetchPromises.push(
        fetch('/api/hatena-trends?category=all&limit=25&type=hot')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayHatenaResults(data);
                }
            })
            .catch(error => console.error('はてなブックマークトレンド取得エラー:', error))
    );
    
    // Twitchトレンド
    fetchPromises.push(
        fetch('/api/twitch-trends?type=games')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayTwitchResults(data);
                }
            })
            .catch(error => console.error('Twitchトレンド取得エラー:', error))
    );
    
    // 全ての取得が完了したらデータ鮮度を更新
    Promise.allSettled(fetchPromises).then(() => {
        refreshDataFreshnessExternal();
    });
}
