// 共通のエラー表示関数
function hideError() {
    const errorElement = document.getElementById('errorMessage');
    if (errorElement) {
        errorElement.style.display = 'none';
    }
}

// 共通のローディング表示関数
function showLoading(loadingId) {
    const loadingElement = document.getElementById(loadingId);
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
}

function hideLoading(loadingId) {
    const loadingElement = document.getElementById(loadingId);
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
}

// 共通の結果表示関数
function showResults(resultsId) {
    const resultsElement = document.getElementById(resultsId);
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}

function hideResults(resultsId) {
    const resultsElement = document.getElementById(resultsId);
    if (resultsElement) {
        resultsElement.style.display = 'none';
    }
}

// 共通のエラーメッセージ表示関数
function showErrorMessage(message, errorId = 'errorMessage') {
    const errorElement = document.getElementById(errorId);
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
}

// 共通のステータスメッセージ表示関数
function showStatusMessage(message, type = 'info', statusId = 'statusMessage') {
    const statusElement = document.getElementById(statusId);
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.className = `alert alert-${type}`;
        statusElement.style.display = 'block';
    }
}

// デバッグ用のログ関数
function logDebug(message, data = null) {
    console.log(`[DEBUG] ${message}`, data);
}

function logError(message, error = null) {
    console.error(`[ERROR] ${message}`, error);
}

// 共通のAPI呼び出し関数
async function callAPI(endpoint, params = {}) {
    try {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        
        logDebug(`API呼び出し: ${url}`);
        
        const response = await fetch(url);
        logDebug(`APIレスポンス: ${response.status} ${response.statusText}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        logDebug(`APIデータ:`, data);
        
        return data;
    } catch (error) {
        logError(`API呼び出しエラー: ${endpoint}`, error);
        throw error;
    }
}

// 共通のテーブル更新関数
function updateTable(tableBodyId, data, rowRenderer) {
    const tableBody = document.getElementById(tableBodyId);
    if (!tableBody) {
        logError(`テーブルボディが見つかりません: ${tableBodyId}`);
        return;
    }
    
    tableBody.innerHTML = '';
    
    if (data && data.length > 0) {
        data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            row.innerHTML = rowRenderer(item, index);
            tableBody.appendChild(row);
        });
    }
}

// 共通のバッジ生成関数
function createBadge(text, color = 'primary') {
    return `<span class="badge bg-${color}">${text}</span>`;
}

// 共通のリンク生成関数
function createLink(url, text, className = 'btn btn-sm btn-outline-primary') {
    return `<a href="${url}" target="_blank" class="${className}">
        <i class="fas fa-external-link-alt"></i> ${text}
    </a>`;
}

// 共通の数値フォーマット関数
function formatNumber(num, locale = 'ja-JP') {
    if (num === null || num === undefined) return 'N/A';
    return new Intl.NumberFormat(locale).format(num);
}

function formatCurrency(amount, currency = 'JPY', locale = 'ja-JP') {
    if (amount === null || amount === undefined) return '価格不明';
    return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: currency
    }).format(amount);
}

// 共通の日時フォーマット関数
function formatDate(dateString, locale = 'ja-JP') {
    if (!dateString) return '不明';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat(locale).format(date);
}

// 共通のテキスト切り詰め関数
function truncateText(text, maxLength = 100) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// ============================================
// ドロップダウンパターン用の共通関数
// ============================================

/**
 * ドロップダウンパターンのトレンドマネージャーを作成
 * @param {Object} config - 設定オブジェクト
 * @param {string} config.serviceName - サービス名（例: 'hatena', 'note', 'twitch'）
 * @param {string} config.selectId - ドロップダウンのID（例: 'hatenaCategorySelect'）
 * @param {string} config.apiEndpoint - APIエンドポイント（例: '/api/hatena-trends'）
 * @param {string} config.defaultValue - デフォルト値（例: 'all', 'games'）
 * @param {string} config.paramName - パラメータ名（例: 'category', 'type'）
 * @param {Object} config.uiIds - UI要素のID
 * @param {string} config.uiIds.loading - ローディング要素のID
 * @param {string} config.uiIds.results - 結果要素のID
 * @param {string} config.uiIds.tableBody - テーブルボディのID
 * @param {string} config.uiIds.statusMessage - ステータスメッセージ要素のID
 * @param {string} config.uiIds.errorMessage - エラーメッセージ要素のID
 * @param {Function} config.displayFunction - データ表示関数
 * @param {Function} config.getParams - 追加パラメータを取得する関数（オプション）
 */
function createDropdownTrendsManager(config) {
    const {
        serviceName,
        selectId,
        apiEndpoint,
        defaultValue,
        paramName = 'category',
        uiIds,
        displayFunction,
        getParams = () => ({})
    } = config;

    // ヘルパー関数
    const showLoading = () => {
        const element = document.getElementById(uiIds.loading);
        if (element) element.style.display = 'block';
    };

    const hideLoading = () => {
        const element = document.getElementById(uiIds.loading);
        if (element) element.style.display = 'none';
    };

    const showResults = () => {
        const element = document.getElementById(uiIds.results);
        if (element) element.style.display = 'block';
    };

    const hideResults = () => {
        const element = document.getElementById(uiIds.results);
        if (element) element.style.display = 'none';
    };

    const showStatusMessage = (message, type = 'info') => {
        const element = document.getElementById(uiIds.statusMessage);
        if (element) {
            element.textContent = message;
            element.className = `alert alert-${type}`;
            element.style.display = 'block';
        }
    };

    const showError = (message) => {
        showStatusMessage(message, 'danger');
        showResults();
    };

    // データ取得関数
    const fetchTrends = () => {
        showLoading();
        hideResults();
        
        const selectElement = document.getElementById(selectId);
        const selectedValue = selectElement ? selectElement.value : defaultValue;
        
        console.log(`🔍 ${serviceName}: ${paramName} '${selectedValue}' のデータを取得中...`);
        
        const params = {
            [paramName]: selectedValue,
            limit: 25,
            ...getParams(selectedValue)
        };
        
        const queryString = new URLSearchParams(params).toString();
        const url = `${apiEndpoint}?${queryString}`;
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                hideLoading();
                console.log(`📊 ${serviceName}: ${paramName} '${selectedValue}' のデータ取得完了`, data);
                if (data.success) {
                    if (typeof displayFunction === 'function') {
                        displayFunction(data);
                    } else {
                        console.error(`display${serviceName.charAt(0).toUpperCase() + serviceName.slice(1)}Results関数が見つかりません`);
                    }
                    showResults();
                } else {
                    showError(data.error || `${serviceName}トレンドの取得に失敗しました`);
                }
            })
            .catch(error => {
                hideLoading();
                console.error(`❌ ${serviceName}: エラー`, error);
                showError('ネットワークエラー: ' + error.message);
            });
    };

    // イベントリスナーの設定
    const setupEventListener = () => {
        const selectElement = document.getElementById(selectId);
        if (selectElement) {
            selectElement.addEventListener('change', function() {
                fetchTrends();
            });
        }
    };

    // 初期化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupEventListener);
    } else {
        setupEventListener();
    }

    // 公開API
    return {
        fetchTrends,
        showLoading,
        hideLoading,
        showResults,
        hideResults,
        showError
    };
}

// ============================================
// シンプルパターン用の共通関数
// ============================================

/**
 * シンプルパターンのキャッシュデータ読み込み関数
 * @param {Object} config - 設定オブジェクト
 * @param {string} config.serviceName - サービス名
 * @param {string} config.apiEndpoint - APIエンドポイント
 * @param {Object} config.params - APIパラメータ
 * @param {Object} config.uiIds - UI要素のID
 * @param {string} config.uiIds.loading - ローディング要素のID（オプション）
 * @param {string} config.uiIds.results - 結果要素のID（オプション）
 * @param {Function} config.displayFunction - データ表示関数
 * @param {number} config.timeout - タイムアウト時間（ミリ秒、デフォルト: 30000）
 */
function loadTrendsFromCache(config) {
    const {
        serviceName,
        apiEndpoint,
        params = {},
        uiIds = {},
        displayFunction,
        timeout = 30000
    } = config;

    console.log(`📊 ${serviceName} Trends キャッシュデータ読み込み`);
    
    // ローディング表示
    if (uiIds.loading) {
        const loadingElement = document.getElementById(uiIds.loading);
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
    }
    
    // AbortControllerを使用したタイムアウト処理
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    // パラメータにforce_refresh=falseを追加
    const queryParams = {
        ...params,
        force_refresh: false
    };
    const queryString = new URLSearchParams(queryParams).toString();
    const url = `${apiEndpoint}?${queryString}`;
    
    // キャッシュデータを取得して表示
    fetchWithRetry(url, { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log(`${serviceName} Trends API レスポンス:`, response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log(`${serviceName} Trends API データ:`, data);
            
            // ローディング表示を非表示
            if (uiIds.loading) {
                const loadingElement = document.getElementById(uiIds.loading);
                if (loadingElement) {
                    loadingElement.style.display = 'none';
                }
            }
            
            if (data.data && data.data.length > 0) {
                console.log(`${serviceName} Trends データ表示開始`);
                if (typeof displayFunction === 'function') {
                    displayFunction(data);
                } else {
                    console.error(`display${serviceName.charAt(0).toUpperCase() + serviceName.slice(1)}Results関数が見つかりません`);
                }
            } else {
                console.log(`${serviceName} Trends データなしまたはエラー:`, data);
            }
            
            // 結果エリアを表示
            if (uiIds.results) {
                const resultsElement = document.getElementById(uiIds.results);
                if (resultsElement) {
                    resultsElement.style.display = 'block';
                }
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.error(`${serviceName} Trends キャッシュ読み込みエラー: タイムアウト（${timeout / 1000}秒）`);
            } else {
                console.error(`${serviceName} Trends キャッシュ読み込みエラー:`, error);
            }
            
            // エラー時もローディング表示を非表示
            if (uiIds.loading) {
                const loadingElement = document.getElementById(uiIds.loading);
                if (loadingElement) {
                    loadingElement.style.display = 'none';
                }
            }
            
            // エラー時でも結果エリアを表示（空でも）
            if (uiIds.results) {
                const resultsElement = document.getElementById(uiIds.results);
                if (resultsElement) {
                    resultsElement.style.display = 'block';
                }
            }
        });
}
