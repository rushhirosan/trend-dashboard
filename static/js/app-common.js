// 共通: テーブル行クリックで別タブでURLを開く（ニュースタブと同様の動作を全タブに適用）
// モバイル: tabindex=-1 で1回タップで開く（フォーカス経由の2回タップを回避）、touch-action: manipulation でタップ遅延を解消
function makeTableRowClickable(row, linkUrl, ariaLabel) {
    if (!row || !linkUrl || linkUrl === '#' || (typeof linkUrl === 'string' && linkUrl.trim() === '')) return;

    row.setAttribute('role', 'button');
    row.setAttribute('tabindex', '-1');
    row.classList.add('row-clickable');
    if (ariaLabel) row.setAttribute('aria-label', ariaLabel);
    row.style.cursor = 'pointer';
    row.style.touchAction = 'manipulation';

    const openInNewTab = function () {
        window.open(linkUrl, '_blank', 'noopener,noreferrer');
    };

    var touchHandled = false;
    var touchStartX = 0, touchStartY = 0;
    row.addEventListener('touchstart', function (e) {
        var t = e.touches && e.touches[0];
        if (t) { touchStartX = t.clientX; touchStartY = t.clientY; }
    }, { passive: true });
    row.addEventListener('touchend', function (e) {
        var t = e.changedTouches && e.changedTouches[0];
        if (!t) return;
        var dx = Math.abs(t.clientX - touchStartX);
        var dy = Math.abs(t.clientY - touchStartY);
        if (dx > 20 || dy > 20) return;
        touchHandled = true;
        e.preventDefault();
        openInNewTab();
        setTimeout(function () { touchHandled = false; }, 400);
    }, { passive: false });

    row.addEventListener('click', function (e) {
        if (touchHandled) { e.preventDefault(); e.stopPropagation(); return; }
        e.preventDefault();
        e.stopPropagation();
        openInNewTab();
    }, true);

    row.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openInNewTab();
        }
    });
}
if (typeof window !== 'undefined') {
    window.makeTableRowClickable = makeTableRowClickable;
}

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
    return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="${className}">
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
// アクセシビリティ対応: テーブル行をクリック可能にする
// ============================================

/**
 * テーブル行をクリック可能にする（アクセシビリティ対応）
 * @param {HTMLTableRowElement} row - テーブル行要素
 * @param {string} linkUrl - クリック時に遷移するURL
 * @param {string} ariaLabel - スクリーンリーダー用のラベル（オプション）
 */
function isPlaceholderUrl(url) {
    if (!url || url === '#') return true;
    try {
        const u = typeof url === 'string' ? url : (url.href || '');
        return u.indexOf('example.com') !== -1;
    } catch (_) { return true; }
}
// ダミー用 example.com リンクの直接クリックで遷移しない（キャッシュに古いダミーが残っている場合）
document.addEventListener('DOMContentLoaded', function() {
    document.body.addEventListener('click', function(e) {
        var a = e.target && e.target.closest ? e.target.closest('a[href*="example.com"]') : null;
        if (a) {
            e.preventDefault();
        }
    }, true);

    // ヘッダー説明のツールチップ初期化
    if (typeof bootstrap !== 'undefined') {
        document.querySelectorAll('.header-desc-info-btn[data-bs-toggle="tooltip"]').forEach(function(el) {
            new bootstrap.Tooltip(el, { container: 'body', customClass: 'header-desc-tooltip' });
        });
    }
});

// ============================================
// トレンド選択の保存・復元（localStorage）
// ============================================

var TREND_PREF_PREFIX = 'trend_pref_';

// ============================================
// Safe JSON fetch (SEO/UX: avoid noisy errors)
// ============================================

function _normalizeUserFacingFetchErrorMessage(message) {
    var m = (message || '').toString();
    if (!m) return '一時的に取得できませんでした';
    // Hide low-level browser/engine errors from UI (esp. Google Live Test)
    if (m.indexOf('Unexpected end of JSON input') !== -1) return '一時的に取得できませんでした';
    if (m.indexOf('Failed to execute') !== -1 && m.indexOf('json') !== -1) return '一時的に取得できませんでした';
    if (m.indexOf('HTTP 499') !== -1 || m.indexOf('Client Closed Request') !== -1) return '一時的に取得できませんでした';
    return m;
}

async function safeFetchJson(url, options) {
    options = options || {};
    var timeoutMs = typeof options.timeoutMs === 'number' ? options.timeoutMs : 6000;
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = null;
    if (controller) {
        timer = setTimeout(function () { try { controller.abort(); } catch (_) {} }, timeoutMs);
    }
    try {
        var fetchOpts = Object.assign({}, options.fetchOptions || {});
        if (controller) fetchOpts.signal = controller.signal;
        var res = await fetch(url, fetchOpts);
        var contentType = (res.headers && res.headers.get) ? (res.headers.get('content-type') || '') : '';
        var text = await res.text();
        if (!res.ok) {
            var errMsg = 'HTTP ' + res.status;
            try {
                if (contentType.indexOf('application/json') !== -1 && text) {
                    var j = JSON.parse(text);
                    if (j && (j.error || j.message)) errMsg = j.error || j.message;
                }
            } catch (_) {}
            throw new Error(errMsg);
        }
        if (contentType.indexOf('application/json') === -1) {
            // Sometimes proxies return HTML error pages with 200; treat as failure.
            throw new Error('non_json_response');
        }
        if (!text || !text.trim()) {
            throw new Error('empty_response');
        }
        return JSON.parse(text);
    } finally {
        if (timer) clearTimeout(timer);
    }
}

if (typeof window !== 'undefined') {
    window.safeFetchJson = safeFetchJson;
    window._normalizeUserFacingFetchErrorMessage = _normalizeUserFacingFetchErrorMessage;
}

/**
 * 指定ソースの前回選択値を取得する
 * @param {string} serviceName - サービス名（例: 'hatena', 'rakuten', 'page'）
 *   - 'page': 最後に開いたページ（'jp' | 'us'）。ルート(/)訪問時のリダイレクトに使用。
 * @returns {string|object|null} 保存値（文字列またはJSONオブジェクト）。無い場合は null
 */
function getTrendPreference(serviceName) {
    try {
        var raw = localStorage.getItem(TREND_PREF_PREFIX + serviceName);
        if (raw == null || raw === '') return null;
        if (raw.startsWith('{')) {
            return JSON.parse(raw);
        }
        return raw;
    } catch (e) {
        return null;
    }
}

/**
 * 指定ソースの選択値を保存する
 * @param {string} serviceName - サービス名
 * @param {string|object} value - 保存する値（オブジェクトの場合はJSONで保存）
 */
function setTrendPreference(serviceName, value) {
    try {
        var toSave = typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value);
        localStorage.setItem(TREND_PREF_PREFIX + serviceName, toSave);
    } catch (e) {
        console.warn('setTrendPreference failed:', e);
    }
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
 * @param {string} config.storageKey - 保存キー（省略時は serviceName）。指定時のみ保存・復元する
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
        storageKey = null,
        uiIds,
        displayFunction,
        getParams = () => ({}),
        allPaneSync
    } = config;

    const prefKey = storageKey != null ? storageKey : serviceName;

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
                        // 全部入りタブへ同期
                        if (allPaneSync && typeof syncToAllPane === 'function') {
                            setTimeout(() => syncToAllPane(allPaneSync.mainTableBodyId, allPaneSync.allTableBodyId, allPaneSync.limit || 5), 0);
                        }
                        // 5行+アコーディオンを適用（はてな・Note等のドロップダウン型）
                        if (typeof applyCategoryAccordionForAllTables === 'function') {
                            setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
                        }
                        // displayFunction内でshowResults/showErrorが呼ばれるので、ここでは呼ばない
                    } else {
                        console.error(`display${serviceName.charAt(0).toUpperCase() + serviceName.slice(1)}Results関数が見つかりません`);
                        showError(`表示関数が見つかりません`);
                    }
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

    // 保存値の復元（select に反映）
    const restorePreference = () => {
        const selectElement = document.getElementById(selectId);
        if (!selectElement || typeof getTrendPreference !== 'function') return;
        const saved = getTrendPreference(prefKey);
        if (saved == null) return;
        const value = typeof saved === 'object' ? (saved.value != null ? saved.value : null) : String(saved);
        if (!value) return;
        const options = selectElement.querySelectorAll('option');
        for (var i = 0; i < options.length; i++) {
            if (options[i].value === value) {
                selectElement.value = value;
                return;
            }
        }
    };

    // イベントリスナーの設定（復元 → changeで保存＋取得）
    const setupEventListener = () => {
        const selectElement = document.getElementById(selectId);
        if (selectElement) {
            restorePreference();
            selectElement.addEventListener('change', function() {
                if (typeof setTrendPreference === 'function') {
                    setTrendPreference(prefKey, selectElement.value);
                }
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
// ソース別メタ（基準時刻・説明）表示
// ============================================

function escapeHtmlTrendMeta(s) {
    if (s == null || s === '') return '';
    var div = document.createElement('div');
    div.textContent = String(s);
    return div.innerHTML;
}

/**
 * API の cache_as_of（ISO）を表示用の短い表記にする
 * @param {string} isoStr
 * @param {Object} [options] - timeZone（既定 Asia/Tokyo）, locale, timeZoneName 等
 */
function formatTrendCacheAsOf(isoStr, options) {
    if (!isoStr) return null;
    options = options || {};
    var timeZone = options.timeZone || 'Asia/Tokyo';
    var locale = options.locale || 'ja-JP';
    var fmt = {
        timeZone: timeZone,
        month: 'numeric',
        day: 'numeric',
        minute: '2-digit'
    };
    if (options.timeZoneName) {
        fmt.timeZoneName = options.timeZoneName;
        fmt.hour = options.hour != null ? options.hour : 'numeric';
    } else {
        fmt.hour = '2-digit';
    }
    try {
        var d = new Date(isoStr);
        if (Number.isNaN(d.getTime())) return null;
        return new Intl.DateTimeFormat(locale, fmt).format(d);
    } catch (e) {
        return null;
    }
}

/**
 * body[data-trend-meta-tz] があればその IANA タイムゾーンで US 表示（英語・略称 TZ）
 */
function getTrendMetaTimeLabels(override) {
    var tz =
        (override && override.timeZone) ||
        (typeof document !== 'undefined' && document.body && document.body.getAttribute('data-trend-meta-tz')) ||
        '';
    if (!tz) {
        return {
            prefix: 'データ取得: ',
            suffix: '（日本時間）',
            refreshPrefix: '基準日: ',
            format: { timeZone: 'Asia/Tokyo', locale: 'ja-JP' }
        };
    }
    return {
        prefix: 'Data as of: ',
        suffix: '',
        refreshPrefix: 'As of date: ',
        format: {
            timeZone: tz,
            locale: 'en-US',
            timeZoneName: 'short',
            hour: 'numeric'
        }
    };
}

/**
 * トレンドカード内に「データ取得時刻」と「一言説明」を挿入する
 * @param {string} containerId - #googleResults 等の結果ラッパー要素の id
 * @param {Object} payload - API JSON（cache_as_of, display_note, refresh_date 等）
 * @param {Object} [metaOverride] - 省略時は body[data-trend-meta-tz] に従う（US ページ等）
 */
function updateTrendMetaDisplay(containerId, payload, metaOverride) {
    if (typeof containerId !== 'string' || !payload || typeof payload !== 'object') return;
    var container = document.getElementById(containerId);
    if (!container) return;

    var row = container.querySelector('.trend-cache-meta');
    if (!row) {
        row = document.createElement('div');
        row.className = 'trend-cache-meta small text-muted mb-2';
        row.setAttribute('role', 'status');
        container.insertBefore(row, container.firstChild);
    }

    var labels = getTrendMetaTimeLabels(metaOverride || {});
    var parts = [];
    var asOfLabel = formatTrendCacheAsOf(payload.cache_as_of, labels.format);
    if (asOfLabel) {
        parts.push(
            '<span class="trend-meta-asof">' +
                labels.prefix +
                '<time datetime="' +
                escapeHtmlTrendMeta(payload.cache_as_of) +
                '">' +
                escapeHtmlTrendMeta(asOfLabel) +
                '</time>' +
                labels.suffix +
                '</span>'
        );
    } else if (payload.refresh_date) {
        parts.push(
            '<span class="trend-meta-asof">' +
                labels.refreshPrefix +
                escapeHtmlTrendMeta(String(payload.refresh_date)) +
                '</span>'
        );
    }

    if (payload.display_note) {
        parts.push(
            '<span class="trend-meta-note d-block mt-1 text-body-secondary">' +
                escapeHtmlTrendMeta(payload.display_note) +
                '</span>'
        );
    }

    row.innerHTML = parts.join('');
    row.style.display = parts.length ? 'block' : 'none';
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
        timeout = 30000,
        alwaysCallDisplay = false,
        forceRefresh = false
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

    // パラメータにforce_refreshを追加
    const queryParams = {
        ...params,
        force_refresh: forceRefresh
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

            if (uiIds.results && typeof updateTrendMetaDisplay === 'function') {
                updateTrendMetaDisplay(uiIds.results, data);
            }

            const hasData = data.data && data.data.length > 0;
            if (hasData || alwaysCallDisplay) {
                console.log(`${serviceName} Trends データ表示開始`, hasData ? `(${data.data.length}件)` : '(空)');
                if (typeof displayFunction === 'function') {
                    displayFunction(data);
                } else {
                    console.error(`display${serviceName.charAt(0).toUpperCase() + serviceName.slice(1)}Results関数が見つかりません`);
                }
                // カテゴリタブの5行+アコーディオンを適用（表示直後に確実に実行）
                if (typeof applyCategoryAccordionForAllTables === 'function') {
                    setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
                }
                // 全部入り（All）タブ用: メイン表の先頭10行をAll用tbodyへ同期
                const allPaneSync = config.allPaneSync;
                if (allPaneSync && typeof syncToAllPane === 'function' && hasData) {
                    setTimeout(function() {
                        syncToAllPane(allPaneSync.mainTableBodyId, allPaneSync.allTableBodyId, allPaneSync.limit || 5);
                    }, 0);
                }
            } else {
                console.log(`${serviceName} Trends データなし（表示はメタ情報のみ）:`, data);
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

/**
 * バッチ読み込みの共通実行（日本・US で統一）
 * @param {Function[]} loadFunctions - 読み込み関数の配列
 * @param {Object} options - { batchSize: number, delayMs: number }
 */
function runBatchLoad(loadFunctions, options) {
    const batchSize = (options && options.batchSize) || 4;
    const delayMs = (options && options.delayMs) != null ? options.delayMs : 200;
    if (!Array.isArray(loadFunctions) || loadFunctions.length === 0) return;

    function executeBatch(batchIndex) {
        if (batchIndex >= loadFunctions.length) {
            console.log('✅ 全バッチの実行完了');
            return;
        }
        const batchEnd = Math.min(batchIndex + batchSize, loadFunctions.length);
        const batch = loadFunctions.slice(batchIndex, batchEnd);
        const batchNumber = Math.floor(batchIndex / batchSize) + 1;
        console.log('📦 バッチ ' + batchNumber + ' 実行中 (' + batch.map(function(f) { return f.name; }).join(', ') + ')');
        batch.forEach(function(loadFn) {
            try {
                console.log('🚀 実行中: ' + loadFn.name);
                loadFn();
            } catch (err) {
                console.error('❌ ' + loadFn.name + ' 実行エラー:', err);
            }
        });
        if (batchEnd < loadFunctions.length) {
            setTimeout(function() { executeBatch(batchEnd); }, delayMs);
        } else {
            console.log('✅ 全バッチの実行完了');
        }
    }
    executeBatch(0);
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
    const isMobile = isMobileViewport();
    // 全部入りタブは常にトップN件のみ表示（デスクトップでもlimitを適用）
    const toCopy = dataRows.slice(0, limit);
    const topCount = 3;
    const visibleRows = toCopy.slice(0, topCount);
    const hiddenRows = toCopy.slice(topCount);
    const moreTbodyId = `all-more-${allTableBodyId}`;

    // 旧方式の残骸を削除
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
        // クローンはイベントリスナーを引き継がないため、行クリックで別タブ表示を再適用
        const firstLink = cloned.querySelector('a[href]');
        if (firstLink && firstLink.href && typeof makeTableRowClickable === 'function') {
            const href = firstLink.href;
            if (href !== '#' && href.indexOf('example.com') === -1) {
                const isUsPage = document.body && document.body.id === 'trends-us';
                const label = (firstLink.textContent || '').trim() + (isUsPage ? ' - Open' : 'を開く');
                makeTableRowClickable(cloned, href, label || (isUsPage ? 'Open link' : 'リンクを開く'));
            }
        }
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
        hiddenClone.style.display = wasOpen ? 'table-row' : 'none';
        allTbody.appendChild(hiddenClone);
    });

    if (hiddenRows.length > 0 && cardBody) {
        allTbody.classList.add('has-more');
        if (wasOpen) {
            allTbody.classList.add('more-rows-open');
        }
        allTbody.dataset.moreOpen = wasOpen ? 'true' : 'false';
        const isUsPage = document.body && document.body.id === 'trends-us';
        const moreText = isUsPage ? 'Show more' : '続きを表示';
        const lessText = isUsPage ? 'Show less' : '閉じる';
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'btn btn-sm btn-outline-secondary w-100 mt-2 all-more-toggle';
        toggle.setAttribute('aria-expanded', wasOpen ? 'true' : 'false');
        toggle.setAttribute('data-all-more-toggle', moreTbodyId);
        toggle.textContent = wasOpen ? lessText : moreText;
        toggle.addEventListener('click', function () {
            const isOpen = allTbody.classList.toggle('more-rows-open');
            allTbody.dataset.moreOpen = isOpen ? 'true' : 'false';
            allTbody.querySelectorAll('.more-row').forEach(row => {
                row.style.display = isOpen ? 'table-row' : 'none';
            });
            this.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            this.textContent = isOpen ? lessText : moreText;
        });
        cardBody.appendChild(toggle);
    }
}

// ============================================
// カテゴリタブ（メイン表）: モバイルで先頭N件＋続きを表示
// ============================================

function isMobileViewport() {
    return window.matchMedia && window.matchMedia('(max-width: 991.98px)').matches;
}

// 行クリックでリンクを開くテーブル: tbody.innerHTML のクリアを避け、CSSのみでアコーディオン（リンクが壊れない）
const ACCORDION_CSS_ONLY_TBODYS = new Set([
    'nhkTrendsTableBody', 'newsTrendsTableBody', 'prtimesHatenaTrendsTableBody', 'prtimesTrendsTableBody',
    'googleTrendsTableBody', 'youtubeTrendsTableBody', 'wikipediaTrendsTableBody',
    'hatenaTrendsTableBody', 'qiitaTrendsTableBody', 'zennTrendsTableBody', 'noteTrendsTableBody',
    'ipaTrendsTableBody', 'jpcertTrendsTableBody', 'githubTrendsTableBody', 'appstoreTrendsTableBody',
    'stockTrendsTableBody', 'cryptoTrendsTableBody', 'movieTrendsTableBody', 'bookTrendsTableBody',
    'musicTrendsTableBody', 'podcastTrendsTableBody', 'rakutenTrendsTableBody', 'openalexTrendsTableBody', 'twitchTrendsTableBody',
    'blueskyTrendsTableBody',
    'cnnTrendsTableBody', 'worldnewsTrendsTableBody', 'hackernewsTrendsTableBody', 'producthuntTrendsTableBody',
    'devtoTrendsTableBody', 'mediumTrendsTableBody', 'cisaKevTrendsTableBody', 'thehackernewsTrendsTableBody',
    'globenewswireTrendsTableBody', 'spotifyTrendsTableBody', 'ebayTrendsTableBody',
    'kkjCasesTrendsTableBody'
]);

function applyCategoryRowAccordion(tbodyId, limit = 5) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody || tbodyId.startsWith('all-') || tbodyId.startsWith('more-')) return;
    const table = tbody.closest('table');
    if (!table) return;

    const cardBody = table.closest('.card-body') || table.parentElement;
    const moreTbodyId = `more-${tbodyId}`;
    const existingMoreList = table.querySelectorAll(`tbody[data-more-for="${tbodyId}"]`);
    const existingToggleList = cardBody ? cardBody.querySelectorAll(`[data-more-toggle="${moreTbodyId}"]`) : [];

    const mainRows = Array.from(tbody.querySelectorAll('tr:not(.skeleton-row)'));
    const moreRows = existingMoreList.length
        ? Array.from(existingMoreList).flatMap(node => Array.from(node.querySelectorAll('tr:not(.skeleton-row)')))
        : [];
    const allRows = mainRows.concat(moreRows);
    if (allRows.length === 0) return;

    const useCssOnlyAccordion = ACCORDION_CSS_ONLY_TBODYS.has(tbodyId);

    if (useCssOnlyAccordion) {
        // リンクテーブル: DOM操作せずCSSのみで5行+アコーディオン（リンクが壊れない）
        const wasOpenCss = table.dataset.moreOpen === 'true' || tbody.classList.contains('more-rows-open') ||
            Array.from(existingToggleList).some(node => node.getAttribute('aria-expanded') === 'true');
        existingToggleList.forEach(node => node.remove());
        if (!isMobileViewport()) {
            tbody.classList.remove('has-more', 'more-rows-open');
            allRows.forEach(tr => {
                tr.classList.remove('more-row', 'more-row-start', 'more-row-end');
                tr.style.display = '';
            });
            return;
        }
        if (allRows.length <= limit) {
            tbody.classList.remove('has-more', 'more-rows-open');
            allRows.forEach(tr => {
                tr.classList.remove('more-row', 'more-row-start', 'more-row-end');
                tr.style.display = '';
            });
            return;
        }
        tbody.classList.add('has-more');
        if (wasOpenCss) {
            tbody.classList.add('more-rows-open');
            table.dataset.moreOpen = 'true';
        } else {
            tbody.classList.remove('more-rows-open');
            table.dataset.moreOpen = 'false';
        }
        allRows.forEach(tr => tr.classList.remove('more-row', 'more-row-start', 'more-row-end'));
        allRows.forEach(function (tr, index) {
            if (index >= limit) {
                tr.classList.add('more-row');
                if (index === limit) tr.classList.add('more-row-start');
                tr.style.display = wasOpenCss ? 'table-row' : 'none';
            } else if (index === limit - 1) {
                tr.classList.add('more-row-end');
            }
        });
        if (cardBody) {
            const isUsPage = document.body && document.body.id === 'trends-us';
            const moreText = isUsPage ? 'Show more' : '続きを表示';
            const lessText = isUsPage ? 'Show less' : '閉じる';
            const toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'btn btn-sm btn-outline-secondary w-100 mt-2 category-more-toggle';
            toggle.setAttribute('aria-expanded', wasOpenCss ? 'true' : 'false');
            toggle.setAttribute('data-more-toggle', moreTbodyId);
            toggle.textContent = wasOpenCss ? lessText : moreText;
            toggle.addEventListener('click', function () {
                const isOpen = tbody.classList.toggle('more-rows-open');
                tbody.querySelectorAll('.more-row').forEach(row => {
                    row.style.display = isOpen ? 'table-row' : 'none';
                });
                this.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
                this.textContent = isOpen ? lessText : moreText;
                table.dataset.moreOpen = isOpen ? 'true' : 'false';
            });
            cardBody.appendChild(toggle);
        }
        return;
    }

    // 通常テーブル: tbodyをクリアして再構築
    tbody.innerHTML = '';
    existingMoreList.forEach(node => node.remove());
    existingToggleList.forEach(node => node.remove());

    // PC表示: 全件表示、アコーディオンなし
    if (!isMobileViewport()) {
        tbody.classList.remove('has-more', 'more-rows-open');
        allRows.forEach(tr => {
            tr.classList.remove('more-row', 'more-row-start', 'more-row-end');
            tr.style.display = '';
            tbody.appendChild(tr);
        });
        return;
    }

    const wasOpen = (
        table.dataset.moreOpen === 'true' ||
        tbody.classList.contains('more-rows-open') ||
        Array.from(existingToggleList).some(node => node.getAttribute('aria-expanded') === 'true')
    );

    if (allRows.length <= limit) {
        tbody.classList.remove('has-more', 'more-rows-open');
        allRows.forEach(tr => {
            tr.classList.remove('more-row', 'more-row-start', 'more-row-end');
            tbody.appendChild(tr);
        });
        return;
    }

    const visibleRows = allRows.slice(0, limit);
    const hiddenRows = allRows.slice(limit);
    tbody.classList.add('has-more');
    if (wasOpen) {
        tbody.classList.add('more-rows-open');
        table.dataset.moreOpen = 'true';
    } else {
        tbody.classList.remove('more-rows-open');
        table.dataset.moreOpen = 'false';
    }

    allRows.forEach(tr => tr.classList.remove('more-row', 'more-row-start', 'more-row-end'));
    visibleRows.forEach((tr, index) => {
        if (index === visibleRows.length - 1 && hiddenRows.length > 0) {
            tr.classList.add('more-row-end');
        }
        tbody.appendChild(tr);
    });
    hiddenRows.forEach((tr, index) => {
        tr.classList.add('more-row');
        if (index === 0) tr.classList.add('more-row-start');
        tr.style.display = wasOpen ? 'table-row' : 'none';
        tbody.appendChild(tr);
    });

    if (cardBody) {
        const isUsPage = document.body && document.body.id === 'trends-us';
        const moreText = isUsPage ? 'Show more' : '続きを表示';
        const lessText = isUsPage ? 'Show less' : '閉じる';
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'btn btn-sm btn-outline-secondary w-100 mt-2 category-more-toggle';
        toggle.setAttribute('aria-expanded', wasOpen ? 'true' : 'false');
        toggle.setAttribute('data-more-toggle', moreTbodyId);
        toggle.textContent = wasOpen ? lessText : moreText;
        toggle.addEventListener('click', function () {
            const isOpen = tbody.classList.toggle('more-rows-open');
            tbody.querySelectorAll('.more-row').forEach(row => {
                row.style.display = isOpen ? 'table-row' : 'none';
            });
            this.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            this.textContent = isOpen ? lessText : moreText;
            table.dataset.moreOpen = isOpen ? 'true' : 'false';
        });
        cardBody.appendChild(toggle);
    }
}

function applyCategoryAccordionForAllTables(limit = 5) {
    // 日本・US両方: 全トレンドテーブルに5行+アコーディオン適用
    // 1) id付き: trendCategoryTabContent内（pane-all以外）の TrendsTableBody
    let tbodys = document.querySelectorAll('#trendCategoryTabContent .tab-pane:not(#pane-all) tbody[id$="TrendsTableBody"]:not([id^="all-"]):not([id^="more-"])');
    // 2) id付き: フォールバックで document 全体から検索
    if (tbodys.length === 0) {
        tbodys = document.querySelectorAll('tbody[id$="TrendsTableBody"]:not([id^="all-"]):not([id^="more-"])');
    }
    // 3) .trend-table tbody（Gov Data等の動的生成テーブル含む）を追加
    const trendTableTbodys = document.querySelectorAll('#trends .trend-table tbody:not([id^="all-"]):not([id^="more-"])');
    const allTbodys = new Set([].slice.call(tbodys));
    trendTableTbodys.forEach(function(t) { allTbodys.add(t); });
    allTbodys.forEach(function(tbody) {
        if (tbody.closest('#pane-all')) return;
        var id = tbody.id;
        if (!id) {
            id = 'accordion-tbody-' + (tbody.getAttribute('data-accordion-id') || Math.random().toString(36).slice(2, 10));
            tbody.setAttribute('data-accordion-id', id);
            tbody.id = id;
        }
        applyCategoryRowAccordion(id, limit);
    });
}

function setupCategoryAccordionObserver(limit = 5) {
    const container = document.getElementById('trendCategoryTabContent');
    let timer = null;
    const schedule = () => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => applyCategoryAccordionForAllTables(limit), 50);
    };
    if (container) {
        const observer = new MutationObserver((mutations) => {
            if (mutations.some(m => m.type === 'childList')) {
                schedule();
            }
        });
        observer.observe(container, { childList: true, subtree: true });
    }
    schedule();
    setTimeout(schedule, 100);
    setTimeout(schedule, 500);
    setTimeout(schedule, 1500);
    setTimeout(schedule, 3000);
    window.addEventListener('resize', schedule);
    window.addEventListener('load', schedule);

    // 起動直後25秒間、1秒ごとにアコーディオンを適用（遅延読み込み・US Gov Data等の全テーブルを確実にカバー）
    const pollInterval = 1000;
    const pollDuration = (document.body && document.body.id === 'trends-us') ? 25000 : 15000;
    let pollElapsed = 0;
    const pollTimer = setInterval(function() {
        pollElapsed += pollInterval;
        applyCategoryAccordionForAllTables(limit);
        if (typeof reSyncAllPanes === 'function') reSyncAllPanes();
        if (pollElapsed >= pollDuration) {
            clearInterval(pollTimer);
        }
    }, pollInterval);

    // タブ切り替え時にも再適用（非表示タブでデータが後から読み込まれる場合に対応）
    const tabNav = document.getElementById('trendCategoryTabs');
    if (tabNav) {
        tabNav.addEventListener('shown.bs.tab', function (e) {
            schedule();
            setTimeout(schedule, 300);
            // 全部入りタブ表示時: メインテーブル→All用tbodyへ再同期（非同期読み込みの競合で同期漏れした場合の救済）
            if (e.target && (e.target.id === 'tab-all' || (e.target.getAttribute && e.target.getAttribute('data-bs-target') === '#pane-all'))) {
                reSyncAllPanes();
            }
        });
    }
}

/**
 * 全部入りタブ用: 全メインテーブルからAll用tbodyへ再同期
 * 非同期読み込みの競合でsyncToAllPaneが空の状態で実行された場合の救済
 */
function reSyncAllPanes() {
    if (typeof syncToAllPane !== 'function') return;
    const allTbodys = document.querySelectorAll('#pane-all tbody[id^="all-"][id$="TrendsTableBody"]');
    allTbodys.forEach(function (allTbody) {
        const allId = allTbody.id;
        const mainId = allId.replace(/^all-/, '');
        const mainTbody = document.getElementById(mainId);
        if (mainTbody && mainTbody.querySelectorAll('tr:not(.skeleton-row)').length > 0) {
            syncToAllPane(mainId, allId, 5);
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setupCategoryAccordionObserver(5));
} else {
    setupCategoryAccordionObserver(5);
}
