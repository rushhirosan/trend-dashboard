// US Trends JavaScript for US version

// Global variables
let currentGoogleChart = null;
let currentYouTubeChart = null;

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

// Stock Trends data fetch for US
async function fetchStockTrendsUS() {
    const loadingElement = document.getElementById('stockLoading');
    const resultsElement = document.getElementById('stockResults');
    const errorElement = document.getElementById('stockErrorMessage');
    const tableBody = document.getElementById('stockTrendsTableBody');
    
    if (!resultsElement || !errorElement || !tableBody) {
        console.error('Required DOM elements not found');
        return;
    }
    
    try {
        // Show loading
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
        resultsElement.style.display = 'none';
        errorElement.style.display = 'none';
        
        // API call (US stocks)
        const response = await fetchWithRetry('/api/stock-trends?market=US&limit=25');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        if (!data.data || !Array.isArray(data.data)) {
            throw new Error('Data format is incorrect');
        }
        
        // Hide loading
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // Display data
        displayStockResultsUS(data);
        
    } catch (error) {
        console.error('Stock Trends fetch error:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        showStockErrorUS('Failed to fetch stock trends: ' + error.message);
    }
}

// Display Stock Results (US)
function displayStockResultsUS(data) {
    const tableBody = document.getElementById('stockTrendsTableBody');
    const resultsElement = document.getElementById('stockResults');
    const errorElement = document.getElementById('stockErrorMessage');
    
    if (!tableBody || !resultsElement) {
        console.error('❌ Stock DOM elements not found');
        return;
    }
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Handle empty data
    if (!data.data || data.data.length === 0 || data.status === 'cache_not_found') {
        if (errorElement) {
            errorElement.textContent = 'No trading today';
            errorElement.style.display = 'block';
        }
        // Display empty message row
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = '<td colspan="4" class="text-center text-muted py-4">No trading today</td>';
        tableBody.appendChild(emptyRow);
        resultsElement.style.setProperty('display', 'block', 'important');
        return;
    }
    
    // Hide error message
    if (errorElement) {
        errorElement.style.display = 'none';
    }
    
    // Sort by absolute change percentage (descending)
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
        
        // Stock link generation (US stocks use Yahoo Finance US)
        const market = data.market || 'US';
        const symbol = item.symbol || '';
        const jpSymbol = symbol.includes('.') ? symbol : `${symbol}.T`;
        const stockUrl = market === 'JP' 
            ? `https://finance.yahoo.co.jp/quote/${jpSymbol}`
            : `https://finance.yahoo.com/quote/${symbol}`;
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${stockUrl}" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><strong>${item.name || 'N/A'}</strong><br><small class="text-muted">${item.symbol || 'N/A'}</small></a></td>
            <td>$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            <td class="${changeClass}"><strong>${changeSymbol} ${Math.abs(changePercent).toFixed(2)}%</strong></td>
        `;
        tableBody.appendChild(row);
    });
    
    // Display results
    resultsElement.style.setProperty('display', 'block', 'important');
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('stockTrendsTableBody', 'all-stockTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('✅ Stock Results display completed');
}

function showStockErrorUS(message) {
    const errorElement = document.getElementById('stockErrorMessage');
    const resultsElement = document.getElementById('stockResults');
    const tableBody = document.getElementById('stockTrendsTableBody');
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}

// Cryptocurrency Trends data fetch
async function fetchCryptoTrendsUS() {
    console.log('=== Cryptocurrency Trends fetch started ===');
    
    const loadingElement = document.getElementById('cryptoLoading');
    const resultsElement = document.getElementById('cryptoResults');
    const errorElement = document.getElementById('cryptoErrorMessage');
    const tableBody = document.getElementById('cryptoTrendsTableBody');
    
    if (!resultsElement || !errorElement || !tableBody) {
        console.error('Required DOM elements not found');
        return;
    }
    
    try {
        // Show loading
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
        resultsElement.style.display = 'none';
        errorElement.style.display = 'none';
        
        // API call
        const response = await fetchWithRetry('/api/crypto-trends?limit=25');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        if (!data.data || !Array.isArray(data.data)) {
            throw new Error('Data format is incorrect');
        }
        
        // Hide loading
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // Display data
        displayCryptoResultsUS(data);
        
    } catch (error) {
        console.error('Cryptocurrency Trends fetch error:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        showCryptoErrorUS('Failed to fetch cryptocurrency trends: ' + error.message);
    }
}

// Display Crypto Results (US)
function displayCryptoResultsUS(data) {
    const tableBody = document.getElementById('cryptoTrendsTableBody');
    const resultsElement = document.getElementById('cryptoResults');
    
    if (!tableBody || !resultsElement) {
        console.error('❌ Crypto DOM elements not found');
        return;
    }
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Sort by market cap rank (ascending)
    const sortedData = [...data.data].sort((a, b) => {
        const rankA = a.market_cap_rank || 999999;
        const rankB = b.market_cap_rank || 999999;
        return rankA - rankB;
    });
    
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
            
            // Cryptocurrency link generation (CoinGecko)
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
            console.error(`Crypto row ${index + 1} processing error:`, error, item);
        }
    });
    
    // Display results
    resultsElement.style.setProperty('display', 'block', 'important');
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('cryptoTrendsTableBody', 'all-cryptoTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
}

// Movie Trends data fetch for US
async function fetchMovieTrendsUS() {
    
    const loadingElement = document.getElementById('movieLoading');
    const resultsElement = document.getElementById('movieResults');
    const tableBody = document.getElementById('movieTrendsTableBody');
    
    if (!resultsElement || !tableBody) {
        console.error('Required DOM elements not found');
        return;
    }
    
    try {
        // Show loading
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
        resultsElement.style.display = 'none';
        
        // API call (US movies)
        const response = await fetchWithRetry('/api/movie-trends?country=US&limit=25');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        if (!data.data || !Array.isArray(data.data)) {
            throw new Error('Data format is incorrect');
        }
        
        // Hide loading
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // Display data
        displayMovieResultsUS(data);
        
    } catch (error) {
        console.error('Movie Trends fetch error:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        resultsElement.style.display = 'block';
    }
}

// Display Movie Results (US)
function displayMovieResultsUS(data) {
    const tableBody = document.getElementById('movieTrendsTableBody');
    const resultsElement = document.getElementById('movieResults');
    
    if (!tableBody || !resultsElement) {
        console.error('❌ Movie DOM elements not found');
        return;
    }
    
    // Clear table
    tableBody.innerHTML = '';
    
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            
            let rating = 'N/A';
            if (item.vote_average) {
                const voteAvg = typeof item.vote_average === 'number' ? item.vote_average : parseFloat(item.vote_average);
                if (!isNaN(voteAvg)) {
                    rating = voteAvg.toFixed(1);
                }
            }
            const releaseDate = item.release_date || 'N/A';
            const posterUrl = item.poster_url || '';
            
            // TMDBリンクを生成（タイトルは常にTMDBリンク）
            const movieId = item.id || item.movie_id;
            let tmdbLink = item.item_url;
            if (!tmdbLink && movieId) {
                tmdbLink = `https://www.themoviedb.org/movie/${movieId}`;
            }
            if (!tmdbLink) {
                tmdbLink = '#';
            }
            
            // Amazonリンクが存在する場合は「Amazonで見る」ボタンを追加
            const amazonButton = item.amazon_link 
                ? `<br><a href="${item.amazon_link}" target="_blank" class="btn btn-sm btn-warning mt-1" style="font-size: 0.75rem;">
                    <i class="fas fa-shopping-cart"></i> View on Amazon
                   </a>`
                : '';
            
            row.innerHTML = `
                <td>${item.rank || index + 1}</td>
                <td>
                    ${posterUrl ? `<img src="${posterUrl}" alt="${item.title}" style="width: 50px; height: 75px; object-fit: cover; margin-right: 10px; float: left;">` : ''}
                    <strong><a href="${tmdbLink}" target="_blank">${item.title || 'N/A'}</a></strong>
                    ${item.original_title && item.original_title !== item.title ? `<br><small class="text-muted">${item.original_title}</small>` : ''}
                    ${amazonButton}
                </td>
                <td>${rating}</td>
                <td>${releaseDate}</td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    // Display results
    resultsElement.style.setProperty('display', 'block', 'important');
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('movieTrendsTableBody', 'all-movieTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
}

// Book Trends data fetch for US
async function fetchBookTrendsUS() {
    
    const loadingElement = document.getElementById('bookLoading');
    const resultsElement = document.getElementById('bookResults');
    const statusMessage = document.getElementById('bookStatusMessage');
    const tableBody = document.getElementById('bookTrendsTableBody');
    
    if (!resultsElement || !tableBody) {
        console.error('Required DOM elements not found');
        return;
    }
    
    try {
        // Show loading
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
        resultsElement.style.display = 'none';
        if (statusMessage) {
            statusMessage.style.display = 'none';
        }
        
        let category = 'all';
        const bookCategorySelectUS = document.getElementById('bookCategorySelectUS');
        if (bookCategorySelectUS) category = bookCategorySelectUS.value || 'all';
        const response = await fetchWithRetry('/api/book-trends?country=US&limit=25&category=' + encodeURIComponent(category));
        const data = await response.json();
        
        // Hide loading
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        if (!data.data || !Array.isArray(data.data)) {
            throw new Error('Data format is incorrect');
        }
        
        if (data.data.length === 0) {
            if (statusMessage) {
                statusMessage.className = 'alert alert-info status-message';
                statusMessage.textContent = 'ℹ️ データがありません。しばらく待ってから再度お試しください。';
                statusMessage.style.display = 'block';
            }
            tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">データがありません</td></tr>';
            resultsElement.style.display = 'block';
            return;
        }
        
        // Display data
        displayBookResultsUS(data);
        
    } catch (error) {
        console.error('Book Trends fetch error:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        if (statusMessage) {
            statusMessage.className = 'alert alert-danger status-message';
            statusMessage.textContent = `❌ エラー: ${error.message || 'データの取得に失敗しました'}`;
            statusMessage.style.display = 'block';
        }
        if (tableBody) {
            tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">エラー: ${error.message || 'データの取得に失敗しました'}</td></tr>`;
        }
        resultsElement.style.display = 'block';
    }
}

// Display Book Results (US)
function displayBookResultsUS(data) {
    const tableBody = document.getElementById('bookTrendsTableBody');
    const resultsElement = document.getElementById('bookResults');
    
    if (!tableBody || !resultsElement) {
        console.error('❌ Book DOM elements not found', { tableBody: !!tableBody, resultsElement: !!resultsElement });
        return;
    }
    
    // Clear table
    tableBody.innerHTML = '';
    
    // データ構造を確認
    const bookData = data.data || data.books || data;
    console.log('📊 Book data array:', bookData, 'Length:', Array.isArray(bookData) ? bookData.length : 'not an array');
    
    if (bookData && Array.isArray(bookData) && bookData.length > 0) {
        console.log('📊 Processing', bookData.length, 'book items');
        bookData.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            
            const author = item.author || (item.authors && item.authors.length > 0 ? item.authors.join(', ') : 'N/A') || 'N/A';
            const price = item.price ? `$${parseFloat(item.price).toFixed(2)}` : 'N/A';
            // リンクの優先順位: amazon_link > buy_link > info_link > preview_link
            const bookLink = item.amazon_link || item.buy_link || item.info_link || item.preview_link || '#';
            // 画像URLの優先順位: image_url > thumbnail > small_thumbnail
            const imageUrl = item.image_url || item.thumbnail || item.small_thumbnail || '';
            
            row.innerHTML = `
                <td><span class="badge bg-info">${item.rank || index + 1}</span></td>
                <td>
                    ${imageUrl ? `<img src="${imageUrl}" alt="${item.title}" style="width: 40px; height: 60px; object-fit: cover; margin-right: 10px; float: left;">` : ''}
                    <strong><a href="${bookLink}" target="_blank">${item.title || 'N/A'}</a></strong>
                </td>
                <td>${author}</td>
                <td>${price}</td>
            `;
            tableBody.appendChild(row);
        });
    } else {
        console.warn('📊 No book data to display', { bookData, isArray: Array.isArray(bookData), length: Array.isArray(bookData) ? bookData.length : 'N/A' });
        tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">データがありません</td></tr>';
    }
    
    // Display results
    resultsElement.style.setProperty('display', 'block', 'important');
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('bookTrendsTableBody', 'all-bookTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
}

// Load Movie Trends from Cache (US)
function loadMovieTrendsFromCacheUS() {
    const loadingElement = document.getElementById('movieLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    fetchWithRetry('/api/movie-trends?country=US&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('movieTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
            
            if (data.data && data.data.length > 0) {
                displayMovieResultsUS(data);
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
                console.error('Movie Trends cache loading error: Timeout (30s)');
            } else {
                console.error('Movie Trends cache loading error:', error);
            }
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('movieTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
            
            const resultsElement = document.getElementById('movieResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// Load Book Trends from Cache (US) — 5択カテゴリ対応
// @param {boolean} forceRefresh - カテゴリ切り替え時にAPIから再取得する場合はtrue
function loadBookTrendsFromCacheUS(forceRefresh) {
    let category = 'all';
    const bookCategorySelectUS = document.getElementById('bookCategorySelectUS');
    if (bookCategorySelectUS) category = bookCategorySelectUS.value || 'all';
    console.log('📊 Book Trends cache data loading (US, category:', category + ', forceRefresh:', !!forceRefresh + ')');
    const loadingElement = document.getElementById('bookLoading');
    const resultsElement = document.getElementById('bookResults');
    const statusMessage = document.getElementById('bookStatusMessage');
    const tableBody = document.getElementById('bookTrendsTableBody');
    
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    if (resultsElement) {
        resultsElement.style.display = 'none';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    fetchWithRetry('/api/book-trends?country=US&limit=25&category=' + encodeURIComponent(category) + '&force_refresh=' + (!!forceRefresh), { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            
            if (data.error) {
                console.error('Book Trends API error:', data.error);
                if (statusMessage) {
                    statusMessage.className = 'alert alert-warning status-message';
                    statusMessage.textContent = `⚠️ ${data.error}`;
                    statusMessage.style.display = 'block';
                }
                if (tableBody) {
                    tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">データが取得できませんでした</td></tr>';
                }
                if (resultsElement) {
                    resultsElement.style.display = 'block';
                }
                return;
            }
            
            console.log('📊 Book Trends API response:', data);
            console.log('📊 Book data check:', { 
                success: data.success,
                hasData: !!data.data, 
                dataLength: data.data ? data.data.length : 0,
                dataType: typeof data.data,
                isArray: Array.isArray(data.data),
                dataKeys: data.data ? Object.keys(data.data[0] || {}) : [],
                fullData: JSON.stringify(data, null, 2)
            });
            
            // データが存在するかチェック
            if (data.success && data.data && Array.isArray(data.data) && data.data.length > 0) {
                console.log('📊 Calling displayBookResultsUS with', data.data.length, 'items');
                displayBookResultsUS(data);
                if (statusMessage) {
                    statusMessage.style.display = 'none';
                }
                if (resultsElement) {
                    resultsElement.style.display = 'block';
                }
            } else {
                console.warn('Book Trends: No data available', {
                    success: data.success,
                    hasData: !!data.data,
                    dataLength: data.data ? data.data.length : 0,
                    isArray: Array.isArray(data.data),
                    error: data.error
                });
                if (statusMessage) {
                    statusMessage.className = 'alert alert-info status-message';
                    statusMessage.textContent = data.error ? `⚠️ ${data.error}` : 'ℹ️ データがありません。しばらく待ってから再度お試しください。';
                    statusMessage.style.display = 'block';
                }
                if (tableBody) {
                    tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">データがありません</td></tr>';
                }
                if (resultsElement) {
                    resultsElement.style.display = 'block';
                }
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
            
            let errorMessage = 'データの取得に失敗しました';
            if (error.name === 'AbortError') {
                errorMessage = 'タイムアウト: データの取得に時間がかかりすぎました';
                console.error('Book Trends cache loading error: Timeout (30s)');
            } else {
                console.error('Book Trends cache loading error:', error);
                errorMessage = `エラー: ${error.message || '不明なエラー'}`;
            }
            
            if (statusMessage) {
                statusMessage.className = 'alert alert-danger status-message';
                statusMessage.textContent = `❌ ${errorMessage}`;
                statusMessage.style.display = 'block';
            }
            if (tableBody) {
                tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">${errorMessage}</td></tr>`;
            }
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

function showCryptoErrorUS(message) {
    const errorElement = document.getElementById('cryptoErrorMessage');
    const resultsElement = document.getElementById('cryptoResults');
    const tableBody = document.getElementById('cryptoTrendsTableBody');
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
}

// Google Trends data fetch for US
async function fetchGoogleTrendsUS() {
    console.log('fetchGoogleTrendsUS: Starting');
    
    const country = 'US'; // US fixed
    
    console.log('fetchGoogleTrendsUS: Parameters', { country });
    
    // Show loading
    showGoogleLoading();
    console.log('fetchGoogleTrendsUS: Loading display completed');
    
    try {
        console.log(`Google API call: /api/google-trends?country=${country}`);
        
        const response = await fetch(`/api/google-trends?country=${country}`);
        console.log('Google API response received:', response.status, response.ok);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Google API response:', data);
        console.log('Google API response keys:', Object.keys(data));
        console.log('Google API data length:', data.data ? data.data.length : 'data is undefined');
        if (data.data && data.data.length > 0) {
            console.log('First Google Trends item:', data.data[0]);
        }
        
        if (data.error) {
            console.error('Google API error:', data.error);
            showGoogleError(data.error);
            hideGoogleLoading();
            return;
        }
        
        // Data existence check
        if (!data.data || !Array.isArray(data.data)) {
            console.error('Google API data format error:', data);
            console.error('Data keys:', Object.keys(data));
            console.error('Data type:', typeof data.data);
            showGoogleError('Data format is incorrect');
            hideGoogleLoading();
            return;
        }
        
        console.log('fetchGoogleTrendsUS: Data display starting');
        displayGoogleResults(data);
        hideGoogleLoading();
        console.log('fetchGoogleTrendsUS: Completed');
        
    } catch (error) {
        console.error('Google Trends fetch error:', error);
        showGoogleError('Failed to fetch Google Trends: ' + error.message);
        hideGoogleLoading();
    }
}

// YouTube Trends data fetch for US
async function fetchYouTubeTrendsUS() {
    console.log('=== fetchYouTubeTrendsUS function called ===');
    console.log('fetchYouTubeTrendsUS: Starting');
    
    // US fixed
    const region = 'US';
    
    console.log('fetchYouTubeTrendsUS: Parameters', { region });
    
    try {
        console.log(`YouTube API call: /api/youtube-trends?region=${region}`);
        
        const response = await fetch(`/api/youtube-trends?region=${region}`);
        console.log('YouTube API response received:', response.status, response.ok);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('YouTube API response:', data);
        
        if (data.error) {
            console.error('YouTube API error:', data.error);
            showYouTubeError(data.error);
            return;
        }
        
        // Data existence check
        if (!data.data || !Array.isArray(data.data)) {
            console.error('YouTube API data format error:', data);
            console.error('Data keys:', Object.keys(data));
            console.error('Data type:', typeof data.data);
            showYouTubeError('Data format is incorrect');
            return;
        }
        
        console.log('fetchYouTubeTrendsUS: Data display starting');
        displayYouTubeResults(data);
        console.log('fetchYouTubeTrendsUS: Completed');
        
    } catch (error) {
        console.error('YouTube Trends fetch error:', error);
        showYouTubeError('Failed to fetch YouTube Trends: ' + error.message);
    }
}

// Display Google Results
function displayGoogleResults(data) {
    console.log('displayGoogleResults: Starting', data);
    
    const resultsElement = document.getElementById('googleResults');
    const statusMessage = document.getElementById('googleStatusMessage');
    const errorElement = document.getElementById('googleErrorMessage');
    const tableBody = document.getElementById('googleTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    
    // Hide status message
    statusMessage.style.display = 'none';
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Popularity（score/popularity）の降順でソート
    const sortedData = [...data.data].sort((a, b) => {
        const scoreA = a.score || a.popularity || 0;
        const scoreB = b.score || b.popularity || 0;
        return scoreB - scoreA; // 降順
    });
    
    // Add data to table
    console.log('Data structure check:', sortedData[0]); // Debug: Check first item structure
    console.log('All data keys:', Object.keys(sortedData[0] || {})); // Debug: Check all available keys
    
    sortedData.forEach((item, index) => {
        const row = document.createElement('tr');
        const keyword = item.keyword || item.term || item.name || 'N/A';
        const popularity = item.popularity || item.score || 0;
        
        // Debug: Log each item
        if (index < 3) {
            console.log(`Item ${index}:`, {
                keyword: keyword,
                popularity: popularity,
                rank: index + 1,
                allKeys: Object.keys(item)
            });
        }
        
        const googleSearchUrl = item.google_search_url || `https://www.google.com/search?q=${encodeURIComponent(keyword)}&geo=US`;
        
        // キーワードを行リンク化（Searchボタンは不要、行クリックで検索へ）
        row.innerHTML = `
            <td><span class="badge bg-primary">${index + 1}</span></td>
            <td><a href="${googleSearchUrl}" target="_blank" class="text-decoration-none"><strong>${keyword}</strong></a></td>
            <td>${Math.round(popularity).toLocaleString()}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, googleSearchUrl, `Search ${keyword} on Google`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('googleTrendsTableBody', 'all-googleTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayGoogleResults: Completed');
}

// Display YouTube Results
function displayYouTubeResults(data) {
    console.log('displayYouTubeResults: Starting', data);
    
    const resultsElement = document.getElementById('youtubeResults');
    const statusMessage = document.getElementById('youtubeStatusMessage');
    const errorElement = document.getElementById('youtubeErrorMessage');
    const tableBody = document.getElementById('youtubeTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    
    // Hide status message
    statusMessage.style.display = 'none';
    
    // 視聴回数でソート（降順）
    const sortedData = (data.data && Array.isArray(data.data))
        ? [...data.data].sort((a, b) => {
            const viewCountA = a.view_count || a.views || a.viewCount || 0;
            const viewCountB = b.view_count || b.views || b.viewCount || 0;
            return viewCountB - viewCountA; // 降順ソート
        })
        : [];
    
    // データが空のときはスケルトン（ダミー）を表示
    if (sortedData.length === 0) {
        tableBody.innerHTML = `
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
            <tr class="skeleton-row"><td><div class="skeleton skeleton-badge"></div></td><td><div class="skeleton skeleton-text skeleton-text-long"></div></td><td><div class="skeleton skeleton-text"></div></td><td><div class="skeleton skeleton-text skeleton-text-short"></div></td></tr>
        `;
        if (typeof syncToAllPane === 'function') {
            setTimeout(() => syncToAllPane('youtubeTrendsTableBody', 'all-youtubeTrendsTableBody', 5), 0);
        }
        if (typeof applyCategoryAccordionForAllTables === 'function') {
            setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
        }
        console.log('displayYouTubeResults: No data, showing skeleton');
        return;
    }
    
    // Clear table and add data
    tableBody.innerHTML = '';
    
    // Add data to table
    console.log('YouTube data structure check:', sortedData[0]); // Debug: Check first item structure
    sortedData.forEach((item, index) => {
        const row = document.createElement('tr');
        const title = item.title || item.video_title || 'N/A';
        const channel = item.channel || item.channel_name || item.channel_title || 'N/A';
        const views = item.views || item.view_count || item.viewCount || 0;
        const videoId = item.video_id || '';
        const youtubeUrl = videoId ? `https://www.youtube.com/watch?v=${videoId}` : '#';
        
        row.innerHTML = `
            <td><span class="badge bg-danger">${index + 1}</span></td>
            <td><a href="${youtubeUrl}" target="_blank" class="text-decoration-none"><strong>${title}</strong></a></td>
            <td>${channel}</td>
            <td>${formatNumber(views)}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, youtubeUrl, `Open ${title} video`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('youtubeTrendsTableBody', 'all-youtubeTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayYouTubeResults: Completed');
}

// Loading and error display functions
function showGoogleLoading() {
    const loadingElement = document.getElementById('googleLoading');
    const resultsElement = document.getElementById('googleResults');
    const errorElement = document.getElementById('googleErrorMessage');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    if (errorElement) errorElement.style.display = 'none';
}

function hideGoogleLoading() {
    const loadingElement = document.getElementById('googleLoading');
    if (loadingElement) loadingElement.style.display = 'none';
}

function showGoogleError(message) {
    const errorElement = document.getElementById('googleErrorMessage');
    const resultsElement = document.getElementById('googleResults');
    const loadingElement = document.getElementById('googleLoading');
    const tableBody = document.getElementById('googleTrendsTableBody');
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'none';
    if (loadingElement) loadingElement.style.display = 'none';
}

function showYouTubeError(message) {
    const errorElement = document.getElementById('youtubeErrorMessage');
    const resultsElement = document.getElementById('youtubeResults');
    const tableBody = document.getElementById('youtubeTrendsTableBody');
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'none';
}

// Utility functions
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// eBay用: セレクトの現在値で loadEbayFromCacheUS を呼ぶラッパー（バッチ配列用）
function loadEbayFromCacheUSWrapper() {
    var ebayCategorySelect = document.getElementById('ebayCategorySelectUS');
    var initialCategory = ebayCategorySelect ? ebayCategorySelect.value : 'cell_phones';
    loadEbayFromCacheUS(initialCategory);
}

// Load cached data for US trends（日本と同一のバッチ方式で統一・Allタブの表示順に合わせる）
function loadCachedDataUS() {
    console.log('📦 Loading cached data for US trends');
    var allCategoriesUS = [
        loadCNNFromCacheUS,
        loadWorldNewsFromCacheUS,
        loadWikipediaFromCacheUS,
        loadGoogleTrendsFromCacheUS,
        loadYouTubeTrendsFromCacheUS,
        loadHackerNewsFromCacheUS,
        loadProductHuntFromCacheUS,
        loadDevToFromCacheUS,
        loadMediumFromCacheUS,
        loadGitHubTrendsFromCacheUS,
        loadCISAKEVTrendsFromCacheUS,
        loadTheHackerNewsTrendsFromCacheUS,
        loadStockTrendsFromCacheUS,
        loadCryptoTrendsFromCacheUS,
        loadGlobeNewswireFromCacheUS,
        loadAppStoreTrendsFromCacheUS,
        loadSpotifyFromCacheUS,
        loadPodcastFromCacheUS,
        loadMovieTrendsFromCacheUS,
        loadBookTrendsFromCacheUS,
        loadEbayFromCacheUSWrapper,
        loadTwitchFromCacheUS
    ];
    if (typeof runBatchLoad === 'function') {
        runBatchLoad(allCategoriesUS, { batchSize: 4, delayMs: 200 });
    } else {
        allCategoriesUS.forEach(function(fn) { fn(); });
    }
}

// Google Trends cache data loading for US
function loadGoogleTrendsFromCacheUS() {
    console.log('📊 Google Trends cache data loading for US');
    
    fetchWithRetry('/api/google-trends?country=US&force_refresh=false')
        .then(response => {
            console.log('Google Trends API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Google Trends API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('Google Trends data display starting');
                displayGoogleResults(data);
            } else {
                console.log('Google Trends data not found or error:', data);
                showGoogleError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('Google Trends cache loading error:', error);
            showGoogleError(`Failed to load Google Trends: ${error.message}`);
        });
}

// YouTube Trends cache data loading for US (統一パターン: ラジオボタンの値に応じてエンドポイントを選択)
function loadYouTubeTrendsFromCacheUS() {
    console.log('📊 YouTube Trends cache data loading for US');
    
    const region = 'US';
    // Rising機能は削除されたため、常にtop25を使用
    const trendType = 'top25';
    const endpoint = '/api/youtube-trends';
    
    console.log(`YouTube API call: ${endpoint}?region=${region}`);
    
    fetchWithRetry(`${endpoint}?region=${region}&force_refresh=false`)
        .then(response => {
            console.log('YouTube Trends API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('YouTube Trends API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('YouTube Trends data display starting');
                displayYouTubeResults(data);
            } else {
                console.log('YouTube Trends data not found or error:', data);
                showYouTubeError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('YouTube Trends cache loading error:', error);
            showYouTubeError(`Failed to load YouTube Trends: ${error.message}`);
        });
}

// World News cache data loading for US
function loadWorldNewsFromCacheUS() {
    console.log('📊 World News cache data loading for US');
    
    fetchWithRetry('/api/worldnews-trends?country=us&category=general&force_refresh=false')
        .then(response => {
            console.log('World News API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('World News API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('World News data display starting');
                displayWorldNewsResults(data);
            } else {
                console.log('World News data not found or error:', data);
                showWorldNewsError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('World News cache loading error:', error);
            showWorldNewsError(`Failed to load World News: ${error.message}`);
        });
}

// Spotify cache data loading for US
function loadSpotifyFromCacheUS() {
    console.log('📊 Spotify cache data loading for US');
    
    fetchWithRetry('/api/music-trends?service=spotify&region=US&force_refresh=false')
        .then(response => {
            console.log('Spotify API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Spotify API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('Spotify data display starting');
                displaySpotifyResults(data);
            } else {
                console.log('Spotify data not found or error:', data);
                showSpotifyError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('Spotify cache loading error:', error);
            showSpotifyError(`Failed to load Spotify data: ${error.message}`);
        });
}

// Display World News Results
function displayWorldNewsResults(data) {
    console.log('displayWorldNewsResults: Starting', data);
    
    const resultsElement = document.getElementById('worldnewsResults');
    const statusMessage = document.getElementById('worldnewsStatusMessage');
    const errorElement = document.getElementById('worldnewsErrorMessage');
    const tableBody = document.getElementById('worldnewsTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    
    // Hide status message
    statusMessage.style.display = 'none';
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Add data to table
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const title = item.title || 'N/A';
        const publishedRaw = item.published_at || item.publish_date || '';
        // CNNと同じ日付フォーマットに統一（MM/DD/YYYY形式）
        const published = publishedRaw ? new Date(publishedRaw).toLocaleDateString('en-US') : 'N/A';
        const url = item.url || '#';
        
        row.innerHTML = `
            <td><span class="badge bg-info">${index + 1}</span></td>
            <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${title}</strong></a></td>
            <td>${published}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, url, `Open ${title} news article`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('worldnewsTrendsTableBody', 'all-worldnewsTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayWorldNewsResults: Completed');
}

// Display Spotify Results
function displaySpotifyResults(data) {
    console.log('displaySpotifyResults: Starting', data);
    
    const resultsElement = document.getElementById('spotifyResults');
    const statusMessage = document.getElementById('spotifyStatusMessage');
    const errorElement = document.getElementById('spotifyErrorMessage');
    const tableBody = document.getElementById('spotifyTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    
    // Hide status message
    statusMessage.style.display = 'none';
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Add data to table
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const title = item.title || 'N/A';
        const artist = item.artist || 'N/A';
        const album = item.album || 'N/A';
        const spotifyUrl = item.spotify_url || '#';
        
        row.innerHTML = `
            <td><span class="badge bg-success">${index + 1}</span></td>
            <td><a href="${spotifyUrl}" target="_blank" class="text-decoration-none"><strong>${title}</strong></a></td>
            <td>${artist}</td>
            <td>${album}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, spotifyUrl, `Open ${title} by ${artist} on Spotify`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('spotifyTrendsTableBody', 'all-spotifyTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displaySpotifyResults: Completed');
}

// Error display functions
function showWorldNewsError(message) {
    const errorElement = document.getElementById('worldnewsErrorMessage');
    const resultsElement = document.getElementById('worldnewsResults');
    const tableBody = document.getElementById('worldnewsTrendsTableBody');
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'none';
}

function showSpotifyError(message) {
    const errorElement = document.getElementById('spotifyErrorMessage');
    const resultsElement = document.getElementById('spotifyResults');
    const tableBody = document.getElementById('spotifyTrendsTableBody');
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'none';
}

// Reddit cache data loading for US
function loadRedditFromCacheUS() {
    console.log('📊 Reddit cache data loading for US');
    
    fetchWithRetry('/api/reddit-trends?subreddit=all&limit=25&force_refresh=false')
        .then(response => {
            console.log('Reddit API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Reddit API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('Reddit data display starting');
                displayRedditResults(data);
                // 警告メッセージがある場合は表示
                if (data.warning) {
                    console.warn('Reddit warning:', data.warning);
                    const errorElement = document.getElementById('redditErrorMessage');
                    if (errorElement) {
                        errorElement.innerHTML = `<i class="fas fa-info-circle"></i> ${data.warning}`;
                        errorElement.style.display = 'block';
                        errorElement.className = 'alert alert-info';
                    }
                }
            } else {
                console.log('Reddit data not found or error:', data);
                // 403エラーの場合は、API申請待ちメッセージを表示
                if (data.status_code === 403) {
                    showRedditAPIWaitingMessage();
                } else {
                    const errorMsg = data.error || 'No data available';
                    const suggestion = data.suggestion ? `<br><small>${data.suggestion}</small>` : '';
                    showRedditError(errorMsg + suggestion);
                }
            }
        })
        .catch(error => console.error('Reddit cache loading error:', error));
}

// Reddit API申請待ちメッセージを表示
function showRedditAPIWaitingMessage() {
    const loadingElement = document.getElementById('redditLoading');
    const errorElement = document.getElementById('redditErrorMessage');
    const resultsElement = document.getElementById('redditResults');
    
    // Hide loading
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
    
    // Show results area
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    
    // Show API申請待ちメッセージ
    if (errorElement) {
        errorElement.innerHTML = `
            <div class="alert alert-warning">
                <h6><i class="fas fa-clock"></i> Reddit API申請待ち</h6>
                <p class="mb-2">Redditのトレンドデータを表示するには、Reddit APIの申請承認が必要です。</p>
                <p class="mb-0"><small>
                    <strong>状況:</strong> Reddit API申請を提出済み（申請日: 2025年11月22日）<br>
                    <strong>現在:</strong> 承認待ち（通常1-2週間程度）<br>
                    <strong>暫定対応:</strong> 本番環境からのアクセスが制限されているため、API申請の承認を待っています。
                </small></p>
            </div>
        `;
        errorElement.style.display = 'block';
        errorElement.className = 'alert alert-warning';
    }
}

// Display Reddit Results
function displayRedditResults(data) {
    console.log('displayRedditResults: Starting', data);
    
    const resultsElement = document.getElementById('redditResults');
    const statusMessage = document.getElementById('redditStatusMessage');
    const errorElement = document.getElementById('redditErrorMessage');
    const tableBody = document.getElementById('redditTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    
    // Hide status message
    statusMessage.style.display = 'none';
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Add data to table
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const title = item.title || 'N/A';
        const subreddit = item.subreddit || 'N/A';
        const score = item.score || 0;
        const comments = item.num_comments || 0;
        const permalink = item.permalink || '#';
        
        const redditUrl = permalink.startsWith('http') ? permalink : `https://www.reddit.com${permalink}`;
        row.innerHTML = `
            <td><span class="badge bg-warning text-dark">${index + 1}</span></td>
            <td><a href="${redditUrl}" target="_blank"><strong>${title}</strong></a></td>
            <td><span class="badge bg-secondary">r/${subreddit}</span></td>
            <td>${formatNumber(score)}</td>
            <td>${formatNumber(comments)}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, redditUrl, `Open ${title} on Reddit`);
        tableBody.appendChild(row);
    });
    
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayRedditResults: Completed');
}

// Error display function
function showRedditError(message) {
    const loadingElement = document.getElementById('redditLoading');
    const errorElement = document.getElementById('redditErrorMessage');
    const resultsElement = document.getElementById('redditResults');
    const tableBody = document.getElementById('redditTrendsTableBody');
    
    // Hide loading
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    // Show error message in results area
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
}

// Podcast cache data loading for US
function loadPodcastFromCacheUS() {
    console.log('📊 Podcast cache data loading for US');
    
    const loadingElement = document.getElementById('podcastLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
    
    fetchWithRetry('/api/podcast-trends?trend_type=best_podcasts&region=us&force_refresh=false')
        .then(response => {
            console.log('Podcast API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Podcast API data:', data);
            console.log('Podcast API data.success:', data.success);
            console.log('Podcast API data.data:', data.data);
            console.log('Podcast API data.data.length:', data.data ? data.data.length : 'data.data is null/undefined');
            
            if (data.success && data.data && Array.isArray(data.data) && data.data.length > 0) {
                console.log('Podcast data display starting with', data.data.length, 'items');
                displayPodcastResults(data);
            } else {
                console.warn('Podcast data not found or error:', {
                    success: data.success,
                    hasData: !!data.data,
                    isArray: Array.isArray(data.data),
                    dataLength: data.data ? data.data.length : 'N/A',
                    error: data.error
                });
                showPodcastError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('Podcast cache loading error:', error);
            showPodcastError(`Error loading Podcast data: ${error.message}`);
        });
}

// Display Podcast Results - 日本版と同じシンプルな実装
function displayPodcastResults(data) {
    console.log('displayPodcastResults: Starting', data);
    
    const tableBody = document.getElementById('podcastTrendsTableBody');
    const statusMessage = document.getElementById('podcastStatusMessage');
    const loadingElement = document.getElementById('podcastLoading');
    
    if (!tableBody || !statusMessage) {
        console.error('Required DOM elements not found');
        return;
    }
    
    // Hide loading
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
    
    // ステータスメッセージは非表示
    if (statusMessage) {
        statusMessage.style.display = 'none';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    
    if (!data.data || !Array.isArray(data.data) || data.data.length === 0) {
        console.error('Invalid data structure:', data);
        showPodcastError('Invalid data structure');
        return;
    }
    
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
        const title = item.title || 'N/A';
        const publisher = item.publisher || 'N/A';
        const url = item.url || item.listennotes_url || '#';
        
        row.innerHTML = `
            <td><span class="badge" style="background-color: #8b5cf6; color: white;">${index + 1}</span></td>
            <td><a href="${url}" target="_blank"><strong>${title}</strong></a></td>
            <td>${publisher}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, url, `Open ${title} podcast`);
        tableBody.appendChild(row);
    });
    
    // 結果セクションを表示 - 日本版と同じシンプルな方法
    document.getElementById('podcastResults').style.setProperty('display', 'block', 'important');
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('podcastTrendsTableBody', 'all-podcastTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayPodcastResults: Completed -', tableBody.children.length, 'rows added');
}

// Error display function
function showPodcastError(message) {
    const loadingElement = document.getElementById('podcastLoading');
    const errorElement = document.getElementById('podcastErrorMessage');
    const resultsElement = document.getElementById('podcastResults');
    const tableBody = document.getElementById('podcastTrendsTableBody');
    
    // Hide loading
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'none';
}

// Twitch cache data loading for US
function loadTwitchFromCacheUS(type = 'games') {
    console.log(`📊 Twitch cache data loading for US (type: ${type})`);
    
    fetch(`/api/twitch-trends?type=${type}&limit=25&force_refresh=false`)
        .then(response => {
            console.log('Twitch API response:', response.status, response.ok);
            return response.json();
        })
        .then(data => {
            console.log('Twitch API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('Twitch data display starting');
                displayTwitchResults(data, type);
            } else {
                console.log('Twitch data not found or error:', data);
                showTwitchError(data.error || 'No data available');
            }
        })
        .catch(error => console.error('Twitch cache loading error:', error));
}

// Display Twitch Results
function displayTwitchResults(data, type = 'games') {
    console.log('displayTwitchResults: Starting', data, 'type:', type);
    
    const resultsElement = document.getElementById('twitchResults');
    const statusMessage = document.getElementById('twitchStatusMessage');
    const errorElement = document.getElementById('twitchErrorMessage');
    const tableBody = document.getElementById('twitchTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    
    // Hide status message
    statusMessage.style.display = 'none';
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Add data to table based on type
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        
        if (type === 'games') {
            const gameName = item.game_name || item.name || 'N/A';
            const viewers = item.viewer_count || 0;
            const url = item.url || (gameName !== 'N/A' ? `https://www.twitch.tv/directory/game/${encodeURIComponent(gameName)}` : '#');
            
            row.innerHTML = `
                <td><span class="badge" style="background-color: #9146FF; color: white;">${index + 1}</span></td>
                <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${gameName}</strong></a></td>
                <td>${formatNumber(viewers)}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `Open ${gameName} on Twitch`);
        } else if (type === 'streams') {
            const title = item.title || 'N/A';
            const userName = item.user_name || 'N/A';
            const viewers = item.viewer_count || 0;
            const url = item.url || (userName !== 'N/A' ? `https://www.twitch.tv/${userName}` : '#');
            
            row.innerHTML = `
                <td><span class="badge" style="background-color: #9146FF; color: white;">${index + 1}</span></td>
                <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${title}</strong><br><small>${userName}</small></a></td>
                <td>${formatNumber(viewers)}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `Open ${title} stream by ${userName} on Twitch`);
        } else if (type === 'clips') {
            const title = item.title || 'N/A';
            const creatorName = item.creator_name || 'N/A';
            const viewCount = item.view_count || 0;
            const url = item.url || '#';
            
            row.innerHTML = `
                <td><span class="badge" style="background-color: #9146FF; color: white;">${index + 1}</span></td>
                <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${title}</strong><br><small>${creatorName}</small></a></td>
                <td>${formatNumber(viewCount)}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `Open ${title} clip by ${creatorName} on Twitch`);
        }
        
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('twitchTrendsTableBody', 'all-twitchTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayTwitchResults: Completed');
}

// Error display function
function showTwitchError(message) {
    const errorElement = document.getElementById('twitchErrorMessage');
    const resultsElement = document.getElementById('twitchResults');
    const tableBody = document.getElementById('twitchTrendsTableBody');
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'none';
}

// Hacker News cache data loading for US
function loadHackerNewsFromCacheUS() {
    console.log('📊 Hacker News cache data loading for US');
    
    fetchWithRetry('/api/hackernews-trends?type=top&limit=25&force_refresh=false')
        .then(response => {
            console.log('Hacker News API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Hacker News API data:', data);
            // キャッシュがない場合は自動的にAPIから取得を試みる
            if (data.success && data.status === 'cache_not_found' && (!data.data || data.data.length === 0)) {
                console.log('Hacker News: キャッシュが見つかりません。APIから取得を試みます...');
                return fetchWithRetry('/api/hackernews-trends?type=top&limit=25&force_refresh=true')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}`);
                        }
                        return response.json();
                    });
            }
            return data;
        })
        .then(data => {
            console.log('Hacker News final data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('Hacker News data display starting');
                displayHackerNewsResults(data);
            } else {
                console.log('Hacker News data not found or error:', data);
                showHackerNewsError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('Hacker News cache loading error:', error);
            showHackerNewsError(`Failed to load Hacker News: ${error.message}`);
        });
}

// Display Hacker News Results
function displayHackerNewsResults(data) {
    console.log('displayHackerNewsResults: Starting', data);
    
    const resultsElement = document.getElementById('hackernewsResults');
    const statusMessage = document.getElementById('hackernewsStatusMessage');
    const errorElement = document.getElementById('hackernewsErrorMessage');
    const tableBody = document.getElementById('hackernewsTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found:', {
            results: !!resultsElement,
            status: !!statusMessage,
            error: !!errorElement,
            table: !!tableBody
        });
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    
    // Hide status message
    statusMessage.style.display = 'none';
    
    // Clear table
    tableBody.innerHTML = '';
    
    // スコアでソート（降順）
    const sortedData = [...data.data].sort((a, b) => {
        const scoreA = a.score || 0;
        const scoreB = b.score || 0;
        return scoreB - scoreA; // 降順ソート
    });
    
    // Add data to table
    sortedData.forEach((item, index) => {
        const row = document.createElement('tr');
        const title = item.title || 'N/A';
        const score = item.score || 0;
        const comments = item.comments || 0;
        const url = item.url || `https://news.ycombinator.com/item?id=${item.story_id}`;
        
        row.innerHTML = `
            <td><span class="badge" style="background-color: #ff6600; color: white;">${index + 1}</span></td>
            <td><a href="${url}" target="_blank"><strong>${title}</strong></a></td>
            <td>${score}</td>
            <td>${comments}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, url, `Open ${title} on Hacker News`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('hackernewsTrendsTableBody', 'all-hackernewsTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayHackerNewsResults: Completed');
}

// Error display function
function showHackerNewsError(message) {
    const errorElement = document.getElementById('hackernewsErrorMessage');
    const resultsElement = document.getElementById('hackernewsResults');
    const tableBody = document.getElementById('hackernewsTrendsTableBody');
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'none';
}

// Stock Trends cache data loading for US
function loadStockTrendsFromCacheUS() {
    console.log('📊 Stock Trends cache data loading for US');
    
    const loadingElement = document.getElementById('stockLoading');
    const resultsElement = document.getElementById('stockResults');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/stock-trends?market=US&limit=25&force_refresh=false')
        .then(response => {
            console.log('Stock API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Stock API data:', data);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // Call display function even if data is empty (to show "本日取引はありません" message)
            if (typeof displayStockResultsUS === 'function') {
                displayStockResultsUS(data);
            } else {
                console.error('displayStockResultsUS function not found');
            }
        })
        .catch(error => {
            console.error('Stock Trends cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
        });
}

// Cryptocurrency Trends cache data loading for US
function loadCryptoTrendsFromCacheUS() {
    console.log('📊 Cryptocurrency Trends cache data loading for US');
    
    const loadingElement = document.getElementById('cryptoLoading');
    const resultsElement = document.getElementById('cryptoResults');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/crypto-trends?limit=25&force_refresh=false')
        .then(response => {
            console.log('Crypto API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Crypto API data:', data);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            console.log('Crypto API response:', data);
            console.log('Crypto data count:', data.data ? data.data.length : 0);
            if (data.success && data.data && data.data.length > 0) {
                console.log('Crypto data display starting (count:', data.data.length, ')');
                if (typeof displayCryptoResultsUS === 'function') {
                    displayCryptoResultsUS(data);
                } else {
                    console.error('displayCryptoResultsUS function not found');
                }
            } else {
                console.log('Crypto data not found or error:', data);
            }
        })
        .catch(error => {
            console.error('Cryptocurrency Trends cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
        });
}

// GlobeNewswire cache data loading for US (raw RSS with tags)
function loadGlobeNewswireFromCacheUS() {
    console.log('📊 GlobeNewswire cache data loading for US');
    const loadingElement = document.getElementById('globenewswireLoading');
    const resultsElement = document.getElementById('globenewswireResults');
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';

    fetchWithRetry('/api/globenewswire-trends?limit=25&force_refresh=false')
        .then(response => {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(data => {
            if (loadingElement) loadingElement.style.display = 'none';
            if (data.success && data.data && data.data.length > 0) {
                displayGlobeNewswireResults(data);
            } else {
                showGlobeNewswireError(data.error || 'No data available');
            }
            if (resultsElement) resultsElement.style.display = 'block';
        })
        .catch(error => {
            console.error('GlobeNewswire cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            showGlobeNewswireError('Failed to load GlobeNewswire: ' + error.message);
            if (resultsElement) resultsElement.style.display = 'block';
        });
}

function displayGlobeNewswireResults(data) {
    const resultsElement = document.getElementById('globenewswireResults');
    const errorElement = document.getElementById('globenewswireErrorMessage');
    const tableBody = document.getElementById('globenewswireTrendsTableBody');
    function esc(s) {
        if (s == null) return '';
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }
    if (!resultsElement || !tableBody) return;
    tableBody.innerHTML = '';
    if (errorElement) errorElement.style.display = 'none';
    if (!data.data || data.data.length === 0) {
        showGlobeNewswireError('No data available');
        return;
    }
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const url = item.url || '#';
        const title = item.title || 'N/A';
        const publishedDate = item.published_date ? new Date(item.published_date).toLocaleDateString('en-US') : 'N/A';
        const tags = item.tags || [];
        const tagsHtml = tags.length
            ? tags.map(t => {
                const term = (t && (t.term != null ? t.term : t.label)) || '';
                return term ? '<span class="badge bg-secondary me-1">' + esc(String(term)) + '</span>' : '';
            }).filter(Boolean).join(' ')
            : '-';
        row.innerHTML =
            '<td><span class="badge bg-secondary">' + (item.rank || index + 1) + '</span></td>' +
            '<td><a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><strong>' + esc(title) + '</strong></a></td>' +
            '<td>' + publishedDate + '</td>' +
            '<td class="small">' + tagsHtml + '</td>';
        if (typeof makeTableRowClickable === 'function') {
            makeTableRowClickable(row, url, 'Open ' + title + ' article');
        }
        tableBody.appendChild(row);
    });
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('globenewswireTrendsTableBody', 'all-globenewswireTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
}

function showGlobeNewswireError(message) {
    const errorElement = document.getElementById('globenewswireErrorMessage');
    const resultsElement = document.getElementById('globenewswireResults');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'block';
}

// CNN News cache data loading for US
function loadCNNFromCacheUS() {
    console.log('📊 CNN News cache data loading for US');
    
    const loadingElement = document.getElementById('cnnLoading');
    const resultsElement = document.getElementById('cnnResults');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/cnn-trends?limit=25&force_refresh=false')
        .then(response => {
            console.log('CNN API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('CNN API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('CNN data display starting');
                displayCNNResults(data);
            } else {
                console.log('CNN data not found or error:', data);
                showCNNError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('CNN cache loading error:', error);
            showCNNError(`Error loading CNN data: ${error.message}`);
        })
        .finally(() => {
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
        });
}

// Display CNN Results
function displayCNNResults(data) {
    console.log('displayCNNResults: Starting', data);
    
    const resultsElement = document.getElementById('cnnResults');
    const statusMessage = document.getElementById('cnnStatusMessage');
    const errorElement = document.getElementById('cnnErrorMessage');
    const tableBody = document.getElementById('cnnTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found for CNN');
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    statusMessage.style.display = 'none';
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Add data to table
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const title = item.title || 'N/A';
        const url = item.url || '#';
        const publishedDate = item.published_date ? new Date(item.published_date).toLocaleDateString('en-US') : 'N/A';
        
        row.innerHTML = `
            <td><span class="badge bg-danger">${index + 1}</span></td>
            <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${title}</strong></a></td>
            <td>${publishedDate}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, url, `Open ${title} CNN article`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('cnnTrendsTableBody', 'all-cnnTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayCNNResults: Completed');
}

// Wikipedia Most Read (en) cache data loading for US
function loadWikipediaFromCacheUS() {
    console.log('📊 Wikipedia Most Read cache data loading for US');
    const loadingElement = document.getElementById('wikipediaLoading');
    const resultsElement = document.getElementById('wikipediaResults');
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';

    fetchWithRetry('/api/wikipedia-trends?lang=en&limit=25&force_refresh=false')
        .then(response => {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(data => {
            if (loadingElement) loadingElement.style.display = 'none';
            if (data.success && data.data && data.data.length > 0) {
                displayWikipediaResultsUS(data);
            } else {
                showWikipediaErrorUS(data.error || 'No data available for this period. Please try again later.');
            }
            if (resultsElement) resultsElement.style.display = 'block';
        })
        .catch(error => {
            console.error('Wikipedia cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            showWikipediaErrorUS('Failed to load Wikipedia most read: ' + error.message);
            if (resultsElement) resultsElement.style.display = 'block';
        });
}

function displayWikipediaResultsUS(data) {
    const resultsElement = document.getElementById('wikipediaResults');
    const errorElement = document.getElementById('wikipediaErrorMessage');
    const tableBody = document.getElementById('wikipediaTrendsTableBody');
    if (!resultsElement || !tableBody) return;

    if (errorElement) errorElement.style.display = 'none';
    tableBody.innerHTML = '';

    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const url = item.url || '#';
        const title = item.title || 'N/A';
        const views = item.views != null ? item.views.toLocaleString() : '-';
        row.innerHTML = `
            <td><span class="badge bg-secondary">${index + 1}</span></td>
            <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${title}</strong></a></td>
            <td>${views}</td>
        `;
        if (typeof makeTableRowClickable === 'function') {
            makeTableRowClickable(row, url, `Open ${title} on Wikipedia`);
        }
        tableBody.appendChild(row);
    });

    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('wikipediaTrendsTableBody', 'all-wikipediaTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
}

function showWikipediaErrorUS(message) {
    const errorElement = document.getElementById('wikipediaErrorMessage');
    const resultsElement = document.getElementById('wikipediaResults');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'block';
}

// Error display function for CNN
function showCNNError(message) {
    const errorElement = document.getElementById('cnnErrorMessage');
    const resultsElement = document.getElementById('cnnResults');
    const loadingElement = document.getElementById('cnnLoading');
    const tableBody = document.getElementById('cnnTrendsTableBody');
    
    if (loadingElement) loadingElement.style.display = 'none';
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (resultsElement) resultsElement.style.display = 'block';
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
}

// Product Hunt cache data loading for US
function loadProductHuntFromCacheUS() {
    console.log('📊 Product Hunt cache data loading for US');
    
    const loadingElement = document.getElementById('producthuntLoading');
    const resultsElement = document.getElementById('producthuntResults');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/producthunt-trends?limit=25&sort=votes&force_refresh=false')
        .then(response => {
            console.log('Product Hunt API response:', response.status, response.ok);
            return response.json().then(data => {
                // 401エラーの場合は認証情報がないことを示す
                if (response.status === 401) {
                    return {
                        success: false,
                        error: data.error || 'Product Hunt API認証情報が設定されていません',
                        suggestion: data.suggestion || 'キャッシュにデータがない場合は表示できません'
                    };
                }
                if (!response.ok) {
                    throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
                }
                return data;
            });
        })
        .then(data => {
            console.log('Product Hunt API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('Product Hunt data display starting');
                displayProductHuntResults(data);
            } else {
                console.log('Product Hunt data not found or error:', data);
                const errorMsg = data.error || 'No data available';
                const suggestion = data.suggestion ? `<br><br>${data.suggestion}` : '';
                showProductHuntError(errorMsg + suggestion);
            }
        })
        .catch(error => {
            console.error('Product Hunt cache loading error:', error);
            showProductHuntError(`Error loading Product Hunt data: ${error.message}`);
        })
        .finally(() => {
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
        });
}

// Display Product Hunt Results
function displayProductHuntResults(data) {
    console.log('displayProductHuntResults: Starting', data);
    
    const resultsElement = document.getElementById('producthuntResults');
    const statusMessage = document.getElementById('producthuntStatusMessage');
    const errorElement = document.getElementById('producthuntErrorMessage');
    const tableBody = document.getElementById('producthuntTrendsTableBody');
    
    if (!resultsElement || !statusMessage || !errorElement || !tableBody) {
        console.error('Required DOM elements not found for Product Hunt');
        return;
    }
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    statusMessage.style.display = 'none';
    
    // Clear table
    tableBody.innerHTML = '';
    
    // Add data to table
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const name = item.name || 'N/A';
        const tagline = item.tagline || 'N/A';
        const votes = item.votes_count || 0;
        const url = item.url || '#';
        
        row.innerHTML = `
            <td><span class="badge" style="background-color: #da552f; color: white;">${index + 1}</span></td>
            <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${name}</strong></a></td>
            <td>${tagline}</td>
            <td>${formatNumber(votes)}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, url, `Open ${name} on Product Hunt`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('producthuntTrendsTableBody', 'all-producthuntTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    console.log('displayProductHuntResults: Completed');
}

// Error display function for Product Hunt
function showProductHuntError(message) {
    const errorElement = document.getElementById('producthuntErrorMessage');
    const resultsElement = document.getElementById('producthuntResults');
    const loadingElement = document.getElementById('producthuntLoading');
    const tableBody = document.getElementById('producthuntTrendsTableBody');
    
    if (loadingElement) loadingElement.style.display = 'none';
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (resultsElement) resultsElement.style.display = 'block';
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
}

// GitHub Trends cache data loading for US
function loadGitHubTrendsFromCacheUS() {
    console.log('📊 GitHub Trends cache data loading for US');
    
    const loadingElement = document.getElementById('githubLoading');
    const resultsElement = document.getElementById('githubResults');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/github-trends?limit=25&force_refresh=false')
        .then(response => {
            console.log('GitHub Trends API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('GitHub Trends API data:', data);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('githubTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
            
            if (data.success && data.data && data.data.length > 0) {
                console.log('GitHub Trends data display starting');
                if (typeof displayGitHubResults === 'function') {
                    displayGitHubResults(data);
                    if (typeof applyCategoryAccordionForAllTables === 'function') {
                        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
                    }
                } else {
                    console.error('displayGitHubResults function not found');
                }
            } else {
                console.log('GitHub Trends data not found or error:', data);
            }
        })
        .catch(error => {
            console.error('GitHub Trends cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('githubTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
        });
}

// App Store Trends cache data loading for US
function loadAppStoreTrendsFromCacheUS() {
    console.log('📊 App Store Trends cache data loading for US');
    
    const loadingElement = document.getElementById('appstoreLoading');
    const resultsElement = document.getElementById('appstoreResults');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/appstore-trends?country=US&limit=25&force_refresh=false')
        .then(response => {
            console.log('App Store Trends API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('App Store Trends API data:', data);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('appstoreTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
            
            if (data.success && data.data && data.data.length > 0) {
                console.log('App Store Trends data display starting');
                if (typeof displayAppStoreResults === 'function') {
                    displayAppStoreResults(data);
                    if (typeof applyCategoryAccordionForAllTables === 'function') {
                        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
                    }
                } else {
                    console.error('displayAppStoreResults function not found');
                }
            } else {
                console.log('App Store Trends data not found or error:', data);
            }
        })
        .catch(error => {
            console.error('App Store Trends cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('appstoreTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
        });
}

// CISA KEV cache data loading for US
function loadCISAKEVTrendsFromCacheUS() {
    console.log('📊 CISA KEV cache data loading for US');
    const loadingElement = document.getElementById('cisaKevLoading');
    const resultsElement = document.getElementById('cisaKevResults');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/cisa-kev-trends?limit=25&force_refresh=false')
        .then(response => {
            console.log('CISA KEV API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('CISA KEV API data:', data);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('cisaKevTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
            
            if (data.success && data.data && data.data.length > 0) {
                console.log('CISA KEV data display starting');
                if (typeof displayCISAKEVResults === 'function') {
                    displayCISAKEVResults(data);
                    if (typeof applyCategoryAccordionForAllTables === 'function') {
                        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
                    }
                } else {
                    console.error('displayCISAKEVResults function not found');
                }
            } else {
                console.log('CISA KEV data not found or error:', data);
            }
        })
        .catch(error => {
            console.error('CISA KEV cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('cisaKevTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
        });
}

// The Hacker News cache data loading for US
function loadTheHackerNewsTrendsFromCacheUS() {
    console.log('📊 The Hacker News cache data loading for US');
    const loadingElement = document.getElementById('thehackernewsLoading');
    const resultsElement = document.getElementById('thehackernewsResults');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/thehackernews-trends?limit=25&force_refresh=false')
        .then(response => {
            console.log('The Hacker News API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('The Hacker News API data:', data);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('thehackernewsTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
            
            if (data.success && data.data && data.data.length > 0) {
                console.log('The Hacker News data display starting');
                if (typeof displayTheHackerNewsResults === 'function') {
                    displayTheHackerNewsResults(data);
                    if (typeof applyCategoryAccordionForAllTables === 'function') {
                        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
                    }
                } else {
                    console.error('displayTheHackerNewsResults function not found');
                }
            } else {
                console.log('The Hacker News data not found or error:', data);
            }
        })
        .catch(error => {
            console.error('The Hacker News cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // スケルトンUIをクリア（処理が走っていないように見えないようにする）
            const tableBody = document.getElementById('thehackernewsTrendsTableBody');
            if (tableBody) {
                tableBody.innerHTML = '';
            }
        });
}

// DEV.to cache data loading for US
function loadDevToFromCacheUS() {
    const loadingElement = document.getElementById('devtoLoading');
    const resultsElement = document.getElementById('devtoResults');
    
    if (!loadingElement || !resultsElement) {
        console.error('DEV.to DOM elements not found');
        return;
    }
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/devto-trends?limit=25&force_refresh=false')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            if (data.success && data.data && data.data.length > 0) {
                displayDevToResults(data);
            } else {
                showDevToError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('DEV.to cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            showDevToError('Failed to load DEV.to data');
        });
}

// Medium cache data loading for US
function loadMediumFromCacheUS() {
    const loadingElement = document.getElementById('mediumLoading');
    const resultsElement = document.getElementById('mediumResults');
    
    if (!loadingElement || !resultsElement) {
        console.error('Medium DOM elements not found');
        return;
    }
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry('/api/medium-trends?limit=25&force_refresh=false')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            if (data.success && data.data && data.data.length > 0) {
                displayMediumResults(data);
            } else {
                showMediumError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('Medium cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            showMediumError('Failed to load Medium data');
        });
}

// eBay Popular/Trending cache data loading for US
function loadEbayFromCacheUS(category = 'fashion') {
    console.log(`📊 eBay cache data loading for US (category: ${category})`);
    
    const loadingElement = document.getElementById('ebayLoading');
    const resultsElement = document.getElementById('ebayResults');
    
    if (!loadingElement || !resultsElement) {
        console.error('eBay Popular/Trending DOM elements not found');
        return;
    }
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry(`/api/ebay-trends?category=${category}&limit=25&force_refresh=false`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // カテゴリー情報を明示的に追加（APIレスポンスに含まれていない場合）
            if (data && !data.category) {
                data.category = category;
            }
            
            if (data.success && data.data && data.data.length > 0) {
                displayEbayResults(data);
            } else {
                let errorMessage = data.error || 'No data available';
                
                if (data.status === 'api_key_not_configured') {
                    errorMessage = 'eBay Client IDが設定されていません。eBay開発者プログラムでApp IDを取得して環境変数EBAY_CLIENT_IDに設定してください。';
                } else if (data.status === 'authentication_error') {
                    errorMessage = 'eBay API認証エラー。Client IDを確認するか、OAuth認証の設定が必要です。';
                } else if (data.status === 'api_error') {
                    errorMessage = `eBay APIエラー: ${data.error || '不明なエラー'}`;
                } else if (data.status === 'no_items') {
                    errorMessage = 'eBayから商品を取得できませんでした。';
                }
                
                showEbayError(errorMessage, data.status);
            }
        })
        .catch(error => {
            console.error('eBay Popular/Trending cache loading error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            showEbayError('Failed to load eBay Popular/Trending data');
        });
}

// eBay Popular/Trending data loading with refresh (force_refresh=true)
function loadEbayFromCacheUSWithRefresh(category = 'fashion') {
    const loadingElement = document.getElementById('ebayLoading');
    const resultsElement = document.getElementById('ebayResults');
    const errorElement = document.getElementById('ebayErrorMessage');
    
    if (!loadingElement || !resultsElement) {
        console.error('eBay Popular/Trending DOM elements not found');
        return;
    }
    
    if (errorElement) errorElement.style.display = 'none';
    if (loadingElement) loadingElement.style.display = 'block';
    if (resultsElement) resultsElement.style.display = 'none';
    
    fetchWithRetry(`/api/ebay-trends?category=${category}&limit=25&force_refresh=true`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (loadingElement) loadingElement.style.display = 'none';
            if (resultsElement) resultsElement.style.display = 'block';
            
            // カテゴリー情報を明示的に追加（APIレスポンスに含まれていない場合）
            if (data && !data.category) {
                data.category = category;
            }
            
            if (data.success && data.data && data.data.length > 0) {
                displayEbayResults(data);
            } else {
                let errorMessage = data.error || 'No data available';
                
                if (data.status === 'api_key_not_configured') {
                    errorMessage = 'eBay Client IDが設定されていません。eBay開発者プログラムでApp IDを取得して環境変数EBAY_CLIENT_IDに設定してください。';
                } else if (data.status === 'authentication_error') {
                    errorMessage = 'eBay API認証エラー。Client IDを確認するか、OAuth認証の設定が必要です。';
                } else if (data.status === 'api_error') {
                    errorMessage = `eBay APIエラー: ${data.error || '不明なエラー'}`;
                } else if (data.status === 'no_items') {
                    errorMessage = 'eBayから商品を取得できませんでした。';
                }
                
                showEbayError(errorMessage, data.status);
            }
        })
        .catch(error => {
            console.error('eBay Popular/Trending refresh error:', error);
            if (loadingElement) loadingElement.style.display = 'none';
            showEbayError('Failed to refresh eBay Popular/Trending data');
        });
}

// Display DEV.to Results
function displayDevToResults(data) {
    const tableBody = document.getElementById('devtoTrendsTableBody');
    const statusMessage = document.getElementById('devtoStatusMessage');
    const errorElement = document.getElementById('devtoErrorMessage');
    const resultsElement = document.getElementById('devtoResults');
    const loadingElement = document.getElementById('devtoLoading');
    
    if (!tableBody || !resultsElement) {
        console.error('DEV.to DOM elements not found');
        return;
    }
    
    if (loadingElement) loadingElement.style.display = 'none';
    if (errorElement) errorElement.style.display = 'none';
    if (statusMessage) statusMessage.style.display = 'none';
    
    tableBody.innerHTML = '';
    
    if (!data.data || !Array.isArray(data.data) || data.data.length === 0) {
        showDevToError('No data available');
        return;
    }
    
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        const title = item.title || 'N/A';
        const author = item.author || 'Unknown';
        const reactions = item.positive_reactions_count || 0;
        const url = item.url || item.canonical_url || '#';
        const rank = item.rank || (index + 1);
        
        row.innerHTML = `
            <td><span class="badge" style="background-color: #0a0e27; color: white;">${rank}</span></td>
            <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${title}</strong></a></td>
            <td>${author}</td>
            <td>${formatNumber(reactions)}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, url, `Open ${title} on DEV.to`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('devtoTrendsTableBody', 'all-devtoTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    resultsElement.style.setProperty('display', 'block', 'important');
}

// Display Medium Results
function displayMediumResults(data) {
    const tableBody = document.getElementById('mediumTrendsTableBody');
    const statusMessage = document.getElementById('mediumStatusMessage');
    const errorElement = document.getElementById('mediumErrorMessage');
    const resultsElement = document.getElementById('mediumResults');
    const loadingElement = document.getElementById('mediumLoading');
    
    if (!tableBody || !resultsElement) {
        console.error('Medium DOM elements not found');
        return;
    }
    
    if (loadingElement) loadingElement.style.display = 'none';
    if (errorElement) errorElement.style.display = 'none';
    if (statusMessage) statusMessage.style.display = 'none';
    
    tableBody.innerHTML = '';
    
    if (!data.data || !Array.isArray(data.data) || data.data.length === 0) {
        showMediumError('No data available');
        return;
    }
    
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        const title = item.title || 'N/A';
        const author = item.author || 'Unknown';
        const publishedDate = item.published_date || item.published_at || '';
        const published = publishedDate ? new Date(publishedDate).toLocaleDateString('en-US') : 'N/A';
        const url = item.url || '#';
        const rank = item.rank || (index + 1);
        
        row.innerHTML = `
            <td><span class="badge bg-dark">${rank}</span></td>
            <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${title}</strong></a></td>
            <td>${author}</td>
            <td>${published}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, url, `Open ${title} on Medium`);
        tableBody.appendChild(row);
    });
    
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('mediumTrendsTableBody', 'all-mediumTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
    resultsElement.style.setProperty('display', 'block', 'important');
}

// Display Amazon Best Sellers Results
function displayEbayResults(data) {
    const tableBody = document.getElementById('ebayTrendsTableBody');
    const statusMessage = document.getElementById('ebayStatusMessage');
    const errorElement = document.getElementById('ebayErrorMessage');
    const resultsElement = document.getElementById('ebayResults');
    const loadingElement = document.getElementById('ebayLoading');
    const categoryNameElement = document.getElementById('ebayCategoryName');
    
    if (!tableBody || !resultsElement) {
        console.error('eBay Popular/Trending DOM elements not found');
        return;
    }
    
    // カテゴリー名のマッピング
    const categoryNameMap = {
        'cell_phones': 'Cell Phones & Accessories',
        'fashion': 'Fashion',
        'home_garden': 'Home & Garden',
        'computers': 'Computers/Tablets',
        'video_games': 'Video Games & Consoles',
        'beauty': 'Beauty & Health',
        'toys': 'Toys & Hobbies',
        'sports': 'Sports & Outdoors',
        'automotive': 'Automotive Parts & Accessories'
    };
    
    if (loadingElement) loadingElement.style.display = 'none';
    if (errorElement) errorElement.style.display = 'none';
    if (statusMessage) statusMessage.style.display = 'none';
    
    // Show results area
    resultsElement.style.display = 'block';
    errorElement.style.display = 'none';
    
    // Hide status message
    statusMessage.style.display = 'none';
    
    // カテゴリー名を更新
    // APIレスポンスからカテゴリー情報を取得（data.category または data.data[0].category）
    let category = data.category;
    if (!category && data.data && data.data.length > 0 && data.data[0].category) {
        category = data.data[0].category;
    }
    
    // 選択されているカテゴリーを取得
    const ebayCategorySelect = document.getElementById('ebayCategorySelectUS');
    let selectedCategory = null;
    if (ebayCategorySelect) {
        selectedCategory = ebayCategorySelect.value;
    }
    
    // カテゴリーが取得できない場合は、選択されているカテゴリーを使用
    if (!category) {
        category = selectedCategory || 'cell_phones';
    }
    
    // 選択されているカテゴリーと表示されているデータのカテゴリーが一致しない場合に警告
    if (selectedCategory && category && selectedCategory !== category) {
        console.warn(`⚠️ eBay category mismatch: selected=${selectedCategory}, displayed=${category}`);
        // 選択されているカテゴリーに合わせてデータを再取得
        if (ebayCategorySelect) {
            console.log(`🔄 Reloading eBay data for selected category: ${selectedCategory}`);
            loadEbayFromCacheUS(selectedCategory);
            return;
        }
    }
    
    // カテゴリー名を表示
    if (categoryNameElement && category) {
        const categoryName = categoryNameMap[category] || category;
        categoryNameElement.textContent = categoryName;
        console.log(`📊 eBay category displayed: ${categoryName} (${category})`);
    }
    
    // Clear table
    tableBody.innerHTML = '';
    
    if (!data.data || !Array.isArray(data.data) || data.data.length === 0) {
        let errorMessage = data.error || 'No data available';
        
        if (data.status === 'cache_not_found') {
            errorMessage = 'キャッシュにデータがありません。更新ボタンを押してデータを取得してください。';
        } else if (data.status === 'api_key_not_configured') {
            errorMessage = 'eBay Client IDが設定されていません。eBay開発者プログラムでApp IDを取得して環境変数EBAY_CLIENT_IDに設定してください。';
        }
        
        showEbayError(errorMessage, data.status);
        return;
    }
    
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        const title = item.title || 'N/A';
        const price = item.price ? `${item.currency || 'USD'} $${item.price}` : 'N/A';
        const url = item.url || '#';
        const rank = item.rank || (index + 1);
        
        row.innerHTML = `
            <td><span class="badge" style="background-color: #0064D2; color: white;">${rank}</span></td>
            <td><a href="${url}" target="_blank" class="text-decoration-none"><strong>${title}</strong></a></td>
            <td>${price}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, url, `Open ${title} on eBay`);
        tableBody.appendChild(row);
    });
    
    resultsElement.style.setProperty('display', 'block', 'important');
    if (typeof syncToAllPane === 'function') {
        setTimeout(() => syncToAllPane('ebayTrendsTableBody', 'all-ebayTrendsTableBody', 5), 0);
    }
    if (typeof applyCategoryAccordionForAllTables === 'function') {
        setTimeout(function() { applyCategoryAccordionForAllTables(5); }, 0);
    }
}

// Error display functions
function showDevToError(message) {
    const loadingElement = document.getElementById('devtoLoading');
    const errorElement = document.getElementById('devtoErrorMessage');
    const resultsElement = document.getElementById('devtoResults');
    const tableBody = document.getElementById('devtoTrendsTableBody');
    
    if (loadingElement) loadingElement.style.display = 'none';
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'block';
}

function showMediumError(message) {
    const loadingElement = document.getElementById('mediumLoading');
    const errorElement = document.getElementById('mediumErrorMessage');
    const resultsElement = document.getElementById('mediumResults');
    const tableBody = document.getElementById('mediumTrendsTableBody');
    
    if (loadingElement) loadingElement.style.display = 'none';
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'block';
}

function showEbayError(message, status = null) {
    const loadingElement = document.getElementById('ebayLoading');
    const errorElement = document.getElementById('ebayErrorMessage');
    const resultsElement = document.getElementById('ebayResults');
    const tableBody = document.getElementById('ebayTrendsTableBody');
    
    if (loadingElement) loadingElement.style.display = 'none';
    
    // スケルトンUIをクリア（処理が走っていないように見えないようにする）
    if (tableBody) {
        tableBody.innerHTML = '';
    }
    
    if (errorElement) {
        const errorHtml = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.innerHTML = errorHtml;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'block';
}


// 表示するペインを「ナビで選択中の1つ」に固定（日本ページと同様にそのタブのデータのみ表示）
// activeTabTrigger: show.bs.tab の e.target を渡すとそのタブのペインを表示（省略時は .nav-link.active を参照）
function hideInactivePanesUS(activeTabTrigger) {
    if (document.body.id !== 'trends-us') return;
    var activePaneId = 'pane-all';
    if (activeTabTrigger && activeTabTrigger.getAttribute('data-bs-target')) {
        activePaneId = activeTabTrigger.getAttribute('data-bs-target').replace(/^#/, '');
    } else {
        const tablist = document.getElementById('trendCategoryTabs');
        if (tablist) {
            const activeButton = tablist.querySelector('.nav-link.active');
            const targetSelector = activeButton && activeButton.getAttribute('data-bs-target');
            if (targetSelector) activePaneId = targetSelector.replace(/^#/, '');
        }
    }

    const paneIds = ['pane-all', 'pane-news', 'pane-search', 'pane-tech', 'pane-market', 'pane-entertainment'];
    paneIds.forEach(function(id) {
        const pane = document.getElementById(id);
        if (!pane) return;
        const isActive = (id === activePaneId);
        if (isActive) {
            pane.classList.add('active', 'show');
            pane.style.removeProperty('display');
            pane.style.removeProperty('height');
            pane.style.removeProperty('min-height');
            pane.style.removeProperty('visibility');
            pane.style.removeProperty('overflow');
        } else {
            pane.classList.remove('active', 'show');
            pane.style.setProperty('display', 'none', 'important');
            pane.style.setProperty('height', '0', 'important');
            pane.style.setProperty('min-height', '0', 'important');
            pane.style.setProperty('visibility', 'hidden', 'important');
            pane.style.setProperty('overflow', 'hidden', 'important');
        }
    });
}

// 日本ページと同一のタブID一覧（前回タブ復元・保存で使用）
var TREND_TAB_IDS_US = ['tab-all', 'tab-news', 'tab-search', 'tab-tech', 'tab-market', 'tab-entertainment'];

function setupAllTabAccordionUS() {
    const cards = document.querySelectorAll('#pane-all [data-all-card] .card');
    cards.forEach(card => {
        const allCard = card.closest('[data-all-card]');
        const key = allCard ? allCard.getAttribute('data-all-card') : null;
        const header = card.querySelector('.card-header');
        const body = card.querySelector('.card-body');
        if (!header || !body || !key) return;

        if (!header.querySelector('.all-accordion-trigger')) {
            const title = header.querySelector('h3');
            if (title) {
                const titleWrapper = title.parentElement;
                const hasSelect = !!titleWrapper && !!titleWrapper.querySelector('.all-category-select');
                const trigger = document.createElement('div');
                trigger.className = hasSelect
                    ? 'all-accordion-trigger d-flex align-items-center'
                    : 'all-accordion-trigger d-flex align-items-center flex-grow-1 min-width-0';
                trigger.setAttribute('data-bs-toggle', 'collapse');
                trigger.setAttribute('data-bs-target', `#all-collapse-${key}`);
                trigger.setAttribute('aria-expanded', 'false');
                trigger.setAttribute('aria-controls', `all-collapse-${key}`);

                const chevron = document.createElement('i');
                chevron.className = 'fas fa-chevron-down all-accordion-chevron ms-1 flex-shrink-0';
                chevron.setAttribute('aria-hidden', 'true');

                if (hasSelect && titleWrapper) {
                    titleWrapper.insertBefore(trigger, title);
                } else {
                    const moreLink = header.querySelector('.all-more-link');
                    if (moreLink) {
                        header.insertBefore(trigger, moreLink);
                    } else {
                        header.insertBefore(trigger, header.firstChild);
                    }
                }

                trigger.appendChild(title);
                trigger.appendChild(chevron);
            }
        }

        if (!body.closest('.all-card-collapse')) {
            const collapse = document.createElement('div');
            collapse.id = `all-collapse-${key}`;
            collapse.className = 'collapse all-card-collapse';
            body.parentNode.insertBefore(collapse, body);
            collapse.appendChild(body);
        }
    });
}

// Page initialization
document.addEventListener('DOMContentLoaded', function() {
    console.log('🇺🇸 US Trends page initialization');

    // Allタブのカードヘッダーを日本ページ同様のアコーディオン構造に揃える
    setupAllTabAccordionUS();

    // USページを開いたことを記憶（次回のルート訪問時のリダイレクト用）
    if (typeof setTrendPreference === 'function') {
        setTrendPreference('page', 'us');
    }

    // 前回開いていたタブを復元（日本ページと同様・loadCachedDataUS の前に実行）
    var trendTabsEl = document.getElementById('trendCategoryTabs');
    if (trendTabsEl && typeof getTrendPreference === 'function' && typeof bootstrap !== 'undefined') {
        var savedTabId = getTrendPreference('active_tab');
        if (savedTabId && TREND_TAB_IDS_US.indexOf(savedTabId) !== -1) {
            var tabBtn = document.getElementById(savedTabId);
            if (tabBtn) {
                var tab = new bootstrap.Tab(tabBtn);
                tab.show();
            }
        }
    }

    // 非アクティブペインを確実に非表示（Bootstrap のインラインスタイルを上書き）
    hideInactivePanesUS();
    setTimeout(hideInactivePanesUS, 0);
    setTimeout(hideInactivePanesUS, 100);

    // All tab "More" link: タブ切り替え後に対象ソースのアンカーへスクロール
    var pendingMoreLinkAnchor = null;
    document.querySelectorAll('.all-more-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetTabId = this.getAttribute('data-target-tab');
            const targetAnchorId = this.getAttribute('data-target-anchor');
            if (!targetTabId) return;
            const tabEl = document.getElementById(targetTabId);
            if (tabEl && typeof bootstrap !== 'undefined') {
                pendingMoreLinkAnchor = targetAnchorId || null;
                const tab = new bootstrap.Tab(tabEl);
                tab.show();
            }
        });
    });

    // トレンドカテゴリタブ: クリック直後と表示完了時の両方で「表示ペインを1つに固定」（日本と同様にそのタブのデータのみ表示）
    if (trendTabsEl) {
        trendTabsEl.addEventListener('show.bs.tab', function(e) {
            hideInactivePanesUS(e.target);
        });
        trendTabsEl.addEventListener('shown.bs.tab', function(e) {
            hideInactivePanesUS(e.target);
            // 日本ページと同様: 選択タブを保存
            var tabId = e.target && e.target.id;
            if (tabId && typeof setTrendPreference === 'function') {
                setTrendPreference('active_tab', tabId);
            }
            // もっと見るからの遷移時のみアンカーへスクロール（日本と同一）
            if (pendingMoreLinkAnchor) {
                var anchor = document.getElementById(pendingMoreLinkAnchor);
                if (anchor) {
                    anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
                pendingMoreLinkAnchor = null;
            }
            if (typeof currentGoogleChart !== 'undefined' && currentGoogleChart) {
                try { currentGoogleChart.resize(); } catch (e) { /* ignore */ }
            }
            if (typeof currentYouTubeChart !== 'undefined' && currentYouTubeChart) {
                try { currentYouTubeChart.resize(); } catch (e) { /* ignore */ }
            }
        });
    }
    
    // Load cached data first (like Japan version)
    loadCachedDataUS();
    
    // YouTube急上昇機能は削除されたため、ラジオボタンの監視は不要
    
    // Twitch type selector event listener
    const twitchTypeSelect = document.getElementById('twitchTypeSelectUS');
    if (twitchTypeSelect) {
        twitchTypeSelect.addEventListener('change', function() {
            const selectedType = this.value;
            console.log(`Twitch type changed to: ${selectedType}`);
            loadTwitchFromCacheUS(selectedType);
        });
    }
    
    // Book category selector (US)
    const bookCategorySelectUS = document.getElementById('bookCategorySelectUS');
    if (bookCategorySelectUS) {
        bookCategorySelectUS.addEventListener('change', function() {
            console.log('Book category changed to:', this.value);
            loadBookTrendsFromCacheUS();
        });
    }
    // eBay category selector event listener
    const ebayCategorySelect = document.getElementById('ebayCategorySelectUS');
    if (ebayCategorySelect) {
        ebayCategorySelect.addEventListener('change', function() {
            const selectedCategory = this.value;
            console.log(`eBay category changed to: ${selectedCategory}`);
            loadEbayFromCacheUS(selectedCategory);
        });
    }

    // All tab category dropdown change handlers
    document.querySelectorAll('.all-category-select').forEach(select => {
        select.addEventListener('change', function() {
            const mainSelectId = this.dataset.mainSelect;
            const service = this.dataset.service;
            const mainSelect = document.getElementById(mainSelectId);
            if (mainSelect) {
                mainSelect.value = this.value;
                if (service === 'ebay') {
                    loadEbayFromCacheUS(this.value);
                } else if (service === 'twitch') {
                    loadTwitchFromCacheUS(this.value);
                } else if (service === 'book') {
                    loadBookTrendsFromCacheUS();
                }
            }
        });
    });
    // Sync main select -> All dropdown (bidirectional)
    const usSyncPairs = [
        { main: 'ebayCategorySelectUS', all: 'all-ebayCategorySelectUS' },
        { main: 'twitchTypeSelectUS', all: 'all-twitchTypeSelectUS' },
        { main: 'bookCategorySelectUS', all: 'all-bookCategorySelectUS' }
    ];
    usSyncPairs.forEach(({ main, all }) => {
        const mainEl = document.getElementById(main);
        const allEl = document.getElementById(all);
        if (mainEl && allEl) {
            allEl.value = mainEl.value;
            mainEl.addEventListener('change', () => { allEl.value = mainEl.value; });
        }
    });
    
    console.log('=== US Trends initialization completed ===');
});
