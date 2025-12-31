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
    console.log('=== Stock Trends fetch started (US) ===');
    
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
    console.log('📊 Stock Results display started', data);
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
        console.log('✅ Stock Results display completed (no data)');
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
        const stockUrl = market === 'JP' 
            ? `https://finance.yahoo.co.jp/quote/${symbol}.T`
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
    console.log('✅ Stock Results display completed');
}

function showStockErrorUS(message) {
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
    console.log('📊 Crypto Results display started', data);
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
    
    console.log('📊 Crypto: Rows added to table:', tableBody.children.length);
    
    // Display results
    resultsElement.style.setProperty('display', 'block', 'important');
    console.log('✅ Crypto Results display completed');
}

// Movie Trends data fetch for US
async function fetchMovieTrendsUS() {
    console.log('=== Movie Trends fetch started (US) ===');
    
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
    console.log('📊 Movie Results display started', data);
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
            // item_urlが存在しない場合は、idまたはmovie_idから生成
            let movieLink = item.item_url;
            const movieId = item.id || item.movie_id;
            if (!movieLink && movieId) {
                movieLink = `https://www.themoviedb.org/movie/${movieId}`;
            }
            if (!movieLink) {
                movieLink = '#';
            }
            
            row.innerHTML = `
                <td>${item.rank || index + 1}</td>
                <td>
                    ${posterUrl ? `<img src="${posterUrl}" alt="${item.title}" style="width: 50px; height: 75px; object-fit: cover; margin-right: 10px; float: left;">` : ''}
                    <strong><a href="${movieLink}" target="_blank">${item.title || 'N/A'}</a></strong>
                    ${item.original_title && item.original_title !== item.title ? `<br><small class="text-muted">${item.original_title}</small>` : ''}
                </td>
                <td>${rating}</td>
                <td>${releaseDate}</td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    // Display results
    resultsElement.style.setProperty('display', 'block', 'important');
    console.log('✅ Movie Results display completed');
}

// Book Trends data fetch for US
async function fetchBookTrendsUS() {
    console.log('=== Book Trends fetch started (US) ===');
    
    const loadingElement = document.getElementById('bookLoading');
    const resultsElement = document.getElementById('bookResults');
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
        
        // API call (US books)
        const response = await fetchWithRetry('/api/book-trends?country=US&limit=25');
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
        displayBookResultsUS(data);
        
    } catch (error) {
        console.error('Book Trends fetch error:', error);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        resultsElement.style.display = 'block';
    }
}

// Display Book Results (US)
function displayBookResultsUS(data) {
    console.log('📊 Book Results display started', data);
    const tableBody = document.getElementById('bookTrendsTableBody');
    const resultsElement = document.getElementById('bookResults');
    
    if (!tableBody || !resultsElement) {
        console.error('❌ Book DOM elements not found');
        return;
    }
    
    // Clear table
    tableBody.innerHTML = '';
    
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            
            const author = item.author || (item.authors && item.authors.length > 0 ? item.authors.join(', ') : 'N/A') || 'N/A';
            let rating = 'N/A';
            if (item.average_rating) {
                const avgRating = typeof item.average_rating === 'number' ? item.average_rating : parseFloat(item.average_rating);
                if (!isNaN(avgRating)) {
                    rating = avgRating.toFixed(1);
                }
            }
            const bookLink = item.info_link || item.preview_link || item.buy_link || '#';
            // 画像URLの優先順位: image_url > thumbnail > small_thumbnail
            const imageUrl = item.image_url || item.thumbnail || item.small_thumbnail || '';
            
            row.innerHTML = `
                <td><span class="badge bg-info">${item.rank || index + 1}</span></td>
                <td>
                    ${imageUrl ? `<img src="${imageUrl}" alt="${item.title}" style="width: 40px; height: 60px; object-fit: cover; margin-right: 10px; float: left;">` : ''}
                    <strong><a href="${bookLink}" target="_blank">${item.title || 'N/A'}</a></strong>
                </td>
                <td>${author}</td>
                <td>${rating}</td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    // Display results
    resultsElement.style.setProperty('display', 'block', 'important');
    console.log('✅ Book Results display completed');
}

// Load Movie Trends from Cache (US)
function loadMovieTrendsFromCacheUS() {
    console.log('📊 Movie Trends cache data loading (US)');
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
            const resultsElement = document.getElementById('movieResults');
            if (resultsElement) {
                resultsElement.style.display = 'block';
            }
        });
}

// Load Book Trends from Cache (US)
function loadBookTrendsFromCacheUS() {
    console.log('📊 Book Trends cache data loading (US)');
    const loadingElement = document.getElementById('bookLoading');
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    fetchWithRetry('/api/book-trends?country=US&limit=25&force_refresh=false', { signal: controller.signal })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.data && data.data.length > 0) {
                displayBookResultsUS(data);
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
                console.error('Book Trends cache loading error: Timeout (30s)');
            } else {
                console.error('Book Trends cache loading error:', error);
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

function showCryptoErrorUS(message) {
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
    
    // Add data to table
    console.log('Data structure check:', data.data[0]); // Debug: Check first item structure
    console.log('All data keys:', Object.keys(data.data[0] || {})); // Debug: Check all available keys
    
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        const keyword = item.keyword || item.term || item.name || 'N/A';
        const popularity = item.popularity || item.score || 'N/A';
        const rank = item.rank || (index + 1); // Fallback to index if rank is missing
        
        // Debug: Log each item
        if (index < 3) {
            console.log(`Item ${index}:`, {
                keyword: keyword,
                popularity: popularity,
                rank: rank,
                allKeys: Object.keys(item)
            });
        }
        
        const googleSearchUrl = item.google_search_url || `https://www.google.com/search?q=${encodeURIComponent(keyword)}&geo=US`;
        
        row.innerHTML = `
            <td><span class="badge bg-primary">${rank}</span></td>
            <td><a href="${googleSearchUrl}" target="_blank" class="text-decoration-none"><strong>${keyword}</strong></a></td>
            <td>${popularity}</td>
            <td>
                <a href="${googleSearchUrl}" 
                   target="_blank" class="btn btn-sm btn-outline-primary">
                    <i class="fas fa-external-link-alt"></i> Search
                </a>
            </td>
        `;
        tableBody.appendChild(row);
    });
    
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
    
    // Clear table
    tableBody.innerHTML = '';
    
    // 視聴回数でソート（降順）
    const sortedData = [...data.data].sort((a, b) => {
        const viewCountA = a.view_count || a.views || a.viewCount || 0;
        const viewCountB = b.view_count || b.views || b.viewCount || 0;
        return viewCountB - viewCountA; // 降順ソート
    });
    
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
        tableBody.appendChild(row);
    });
    
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

// Load cached data for US trends
function loadCachedDataUS() {
    console.log('📦 Loading cached data for US trends');
    
    // Load Google Trends from cache
    loadGoogleTrendsFromCacheUS();
    
    // Load YouTube Trends from cache
    loadYouTubeTrendsFromCacheUS();
    
    // Load World News from cache
    loadWorldNewsFromCacheUS();
    
    // Load Stock Trends from cache
    loadStockTrendsFromCacheUS();
    
    // Load Crypto Trends from cache
    loadCryptoTrendsFromCacheUS();
    
    // Load Spotify from cache
    loadSpotifyFromCacheUS();
    
    // Load Movie Trends from cache
    loadMovieTrendsFromCacheUS();
    
    // Load Book Trends from cache
    loadBookTrendsFromCacheUS();
    
    // Load Reddit from cache (エラーでもレイアウトを崩さないように先に実行)
    loadRedditFromCacheUS();
    
    // Load Podcast from cache (Redditと独立して表示)
    loadPodcastFromCacheUS();
    
    // Load Twitch from cache
    loadTwitchFromCacheUS();
    
    // Load Hacker News from cache
    loadHackerNewsFromCacheUS();
    
    // Load CNN News from cache
    loadCNNFromCacheUS();
    
    // Load Product Hunt from cache
    loadProductHuntFromCacheUS();
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

// YouTube Trends cache data loading for US
function loadYouTubeTrendsFromCacheUS() {
    console.log('📊 YouTube Trends cache data loading for US');
    
    fetchWithRetry('/api/youtube-trends?region=US&force_refresh=false')
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

// YouTube Rising Trends cache data loading for US
function loadYouTubeRisingTrendsFromCacheUS() {
    console.log('📊 YouTube Rising Trends cache data loading for US');
    
    fetchWithRetry('/api/youtube-rising-trends?region=US')
        .then(response => {
            console.log('YouTube Rising Trends API response:', response.status, response.ok);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('YouTube Rising Trends API data:', data);
            if (data.success && data.data && data.data.length > 0) {
                console.log('YouTube Rising Trends data display starting');
                displayYouTubeResults(data);
            } else {
                console.log('YouTube Rising Trends data not found or error:', data);
                showYouTubeError(data.error || 'No data available');
            }
        })
        .catch(error => {
            console.error('YouTube Rising Trends cache loading error:', error);
            showYouTubeError(`Failed to load YouTube Rising Trends: ${error.message}`);
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
        tableBody.appendChild(row);
    });
    
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
        tableBody.appendChild(row);
    });
    
    console.log('displaySpotifyResults: Completed');
}

// Error display functions
function showWorldNewsError(message) {
    const errorElement = document.getElementById('worldnewsErrorMessage');
    const resultsElement = document.getElementById('worldnewsResults');
    
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
    if (resultsElement) resultsElement.style.display = 'none';
}

function showSpotifyError(message) {
    const errorElement = document.getElementById('spotifyErrorMessage');
    const resultsElement = document.getElementById('spotifyResults');
    
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
        
        row.innerHTML = `
            <td><span class="badge bg-warning text-dark">${index + 1}</span></td>
            <td><a href="${permalink}" target="_blank"><strong>${title}</strong></a></td>
            <td><span class="badge bg-secondary">r/${subreddit}</span></td>
            <td>${formatNumber(score)}</td>
            <td>${formatNumber(comments)}</td>
        `;
        tableBody.appendChild(row);
    });
    
    console.log('displayRedditResults: Completed');
}

// Error display function
function showRedditError(message) {
    const loadingElement = document.getElementById('redditLoading');
    const errorElement = document.getElementById('redditErrorMessage');
    const resultsElement = document.getElementById('redditResults');
    
    // Hide loading
    if (loadingElement) {
        loadingElement.style.display = 'none';
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
        // genreフィールドがない場合はcountryやlanguageを使用
        const genre = item.genre || item.country || item.language || 'N/A';
        const url = item.url || item.listennotes_url || '#';
        
        row.innerHTML = `
            <td><span class="badge" style="background-color: #8b5cf6; color: white;">${index + 1}</span></td>
            <td><a href="${url}" target="_blank"><strong>${title}</strong></a></td>
            <td>${publisher}</td>
            <td><span class="badge bg-secondary">${genre}</span></td>
        `;
        tableBody.appendChild(row);
    });
    
    // 結果セクションを表示 - 日本版と同じシンプルな方法
    document.getElementById('podcastResults').style.setProperty('display', 'block', 'important');
    console.log('displayPodcastResults: Completed -', tableBody.children.length, 'rows added');
}

// Error display function
function showPodcastError(message) {
    const loadingElement = document.getElementById('podcastLoading');
    const errorElement = document.getElementById('podcastErrorMessage');
    const resultsElement = document.getElementById('podcastResults');
    
    // Hide loading
    if (loadingElement) {
        loadingElement.style.display = 'none';
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
        }
        
        tableBody.appendChild(row);
    });
    
    console.log('displayTwitchResults: Completed');
}

// Error display function
function showTwitchError(message) {
    const errorElement = document.getElementById('twitchErrorMessage');
    const resultsElement = document.getElementById('twitchResults');
    
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
        tableBody.appendChild(row);
    });
    
    console.log('displayHackerNewsResults: Completed');
}

// Error display function
function showHackerNewsError(message) {
    const errorElement = document.getElementById('hackernewsErrorMessage');
    const resultsElement = document.getElementById('hackernewsResults');
    
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
        tableBody.appendChild(row);
    });
    
    console.log('displayCNNResults: Completed');
}

// Error display function for CNN
function showCNNError(message) {
    const errorElement = document.getElementById('cnnErrorMessage');
    const resultsElement = document.getElementById('cnnResults');
    const loadingElement = document.getElementById('cnnLoading');
    
    if (loadingElement) loadingElement.style.display = 'none';
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
        tableBody.appendChild(row);
    });
    
    console.log('displayProductHuntResults: Completed');
}

// Error display function for Product Hunt
function showProductHuntError(message) {
    const errorElement = document.getElementById('producthuntErrorMessage');
    const resultsElement = document.getElementById('producthuntResults');
    const loadingElement = document.getElementById('producthuntLoading');
    
    if (loadingElement) loadingElement.style.display = 'none';
    if (resultsElement) resultsElement.style.display = 'block';
    if (errorElement) {
        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorElement.style.display = 'block';
    }
}

// Page initialization
document.addEventListener('DOMContentLoaded', function() {
    console.log('🇺🇸 US Trends page initialization');
    
    // Load cached data first (like Japan version)
    loadCachedDataUS();
    
    // YouTube trend type buttons event listener
    const trendingTab = document.getElementById('trendingTab');
    const risingTab = document.getElementById('risingTab');
    
    if (trendingTab) {
        trendingTab.addEventListener('click', function() {
            console.log('YouTube Trending tab clicked');
            this.classList.add('active');
            if (risingTab) risingTab.classList.remove('active');
            loadYouTubeTrendsFromCacheUS();
        });
    }
    
    if (risingTab) {
        risingTab.addEventListener('click', function() {
            console.log('YouTube Rising tab clicked');
            this.classList.add('active');
            if (trendingTab) trendingTab.classList.remove('active');
            loadYouTubeRisingTrendsFromCacheUS();
        });
    }
    
    // Twitch type selector event listener
    const twitchTypeSelect = document.getElementById('twitchTypeSelectUS');
    if (twitchTypeSelect) {
        twitchTypeSelect.addEventListener('change', function() {
            const selectedType = this.value;
            console.log(`Twitch type changed to: ${selectedType}`);
            loadTwitchFromCacheUS(selectedType);
        });
    }
    
    console.log('=== US Trends initialization completed ===');
});
