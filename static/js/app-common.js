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
function makeTableRowClickable(row, linkUrl, ariaLabel = null) {
    if (!row || !linkUrl || linkUrl === '#' || isPlaceholderUrl(linkUrl)) {
        return;
    }

    // クリック可能な行としてマーク
    row.setAttribute('data-clickable', 'true');
    row.setAttribute('tabindex', '0');
    row.setAttribute('role', 'button');

    // aria-labelを設定（指定がない場合は行内のリンクテキストを使用）
    if (ariaLabel) {
        row.setAttribute('aria-label', ariaLabel);
    } else {
        // 行内の最初のリンクのテキストを取得
        const firstLink = row.querySelector('a');
        if (firstLink) {
            const linkText = firstLink.textContent.trim();
            row.setAttribute('aria-label', `${linkText}を開く`);
        }
    }

    // クリックイベント: 行全体をクリックしたときにリンクを開く
    row.addEventListener('click', function(e) {
        // リンクやボタンがクリックされた場合は、その要素の動作を優先
        if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON' || e.target.closest('a') || e.target.closest('button')) {
            return;
        }

        // 行全体がクリックされた場合は、最初のリンクを開く（ダミーURLは開かない）
        const firstLink = row.querySelector('a[href]');
        if (firstLink && firstLink.href && firstLink.href !== '#' && !isPlaceholderUrl(firstLink.href)) {
            window.open(firstLink.href, firstLink.target || '_blank');
        }
    });

    // キーボードイベント: EnterキーまたはSpaceキーでリンクを開く
    row.addEventListener('keydown', function(e) {
        // リンクやボタンがフォーカスされている場合は、その要素の動作を優先
        if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON' || e.target.closest('a') || e.target.closest('button')) {
            return;
        }

        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            const firstLink = row.querySelector('a[href]');
            if (firstLink && firstLink.href && firstLink.href !== '#' && !isPlaceholderUrl(firstLink.href)) {
                window.open(firstLink.href, firstLink.target || '_blank');
            }
        }
    });
}

// ダミー用 example.com リンクの直接クリックで遷移しない（キャッシュに古いダミーが残っている場合）
document.addEventListener('DOMContentLoaded', function() {
    document.body.addEventListener('click', function(e) {
        var a = e.target && e.target.closest ? e.target.closest('a[href*="example.com"]') : null;
        if (a) {
            e.preventDefault();
        }
    }, true);
});

// ============================================
// トレンド選択の保存・復元（localStorage）
// ============================================

var TREND_PREF_PREFIX = 'trend_pref_';

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

            const hasData = data.data && data.data.length > 0;
            if (hasData || alwaysCallDisplay) {
                console.log(`${serviceName} Trends データ表示開始`, hasData ? `(${data.data.length}件)` : '(空)');
                if (typeof displayFunction === 'function') {
                    displayFunction(data);
                } else {
                    console.error(`display${serviceName.charAt(0).toUpperCase() + serviceName.slice(1)}Results関数が見つかりません`);
                }
                // 全部入り（All）タブ用: メイン表の先頭10行をAll用tbodyへ同期
                const allPaneSync = config.allPaneSync;
                if (allPaneSync && typeof syncToAllPane === 'function' && hasData) {
                    setTimeout(function() {
                        syncToAllPane(allPaneSync.mainTableBodyId, allPaneSync.allTableBodyId, allPaneSync.limit || 5);
                    }, 0);
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
        return cloned;
    };

    if (!isMobileViewport()) {
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
    return window.matchMedia && window.matchMedia('(max-width: 767.98px)').matches;
}

function applyCategoryRowAccordion(tbodyId, limit = 5) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody || tbodyId.startsWith('all-') || tbodyId.startsWith('more-')) return;
    const table = tbody.closest('table');
    if (!table) return;

    const cardBody = table.closest('.card-body') || table.parentElement;
    const moreTbodyId = `more-${tbodyId}`;
    const existingMoreList = table.querySelectorAll(`tbody[data-more-for="${tbodyId}"]`);
    const existingToggleList = cardBody ? cardBody.querySelectorAll(`[data-more-toggle="${moreTbodyId}"]`) : [];
    const wasOpen = (
        table.dataset.moreOpen === 'true' ||
        tbody.classList.contains('more-rows-open') ||
        Array.from(existingToggleList).some(node => node.getAttribute('aria-expanded') === 'true')
    );

    const mainRows = Array.from(tbody.querySelectorAll('tr:not(.skeleton-row)'));
    const moreRows = existingMoreList.length
        ? Array.from(existingMoreList).flatMap(node => Array.from(node.querySelectorAll('tr:not(.skeleton-row)')))
        : [];
    const allRows = mainRows.concat(moreRows);
    if (allRows.length === 0) return;

    tbody.innerHTML = '';
    existingMoreList.forEach(node => node.remove());
    existingToggleList.forEach(node => node.remove());

    if (!isMobileViewport() || allRows.length <= limit) {
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
    const selector = '#trendCategoryTabContent .tab-pane:not(#pane-all) tbody[id$="TrendsTableBody"]:not([id^="more-"])';
    document.querySelectorAll(selector).forEach((tbody) => {
        if (tbody.id && !tbody.id.startsWith('all-')) {
            applyCategoryRowAccordion(tbody.id, limit);
        }
    });
}

function setupCategoryAccordionObserver(limit = 5) {
    const container = document.getElementById('trendCategoryTabContent');
    if (!container) return;
    let timer = null;
    const schedule = () => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => applyCategoryAccordionForAllTables(limit), 50);
    };
    const observer = new MutationObserver((mutations) => {
        if (mutations.some(m => m.type === 'childList')) {
            schedule();
        }
    });
    observer.observe(container, { childList: true, subtree: true });
    schedule();
    window.addEventListener('resize', schedule);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setupCategoryAccordionObserver(5));
} else {
    setupCategoryAccordionObserver(5);
}
