// 結果表示関数群に関するJavaScriptファイル

// はてなブックマーク結果表示関数
function displayHatenaResults(data) {
    console.log('📊 Hatena Results表示開始', data);
    const tableBody = document.getElementById('hatenaTrendsTableBody');
    const statusMessage = document.getElementById('hatenaStatusMessage');
    
    if (!tableBody) {
        console.error('❌ Hatena DOM要素が見つかりません');
        return;
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            row.style.minHeight = '100px';
            
            // ブックマーク数をフォーマット
            const bookmarkCount = item.bookmark_count || 0;
            const bookmarkInfo = bookmarkCount > 0 ? `${bookmarkCount.toLocaleString()}件` : '0件';
            
            // リンクを追加（他のセクションと同じ形式）
            const articleLink = item.url ? 
                `<br><a href="${item.url}" target="_blank" class="btn btn-sm btn-outline-warning mt-1">
                    <i class="fas fa-external-link-alt"></i> 記事を読む
                </a>` : '';
            
            row.innerHTML = `
                <td><span class="badge bg-warning">${item.rank || index + 1}</span></td>
                <td>
                    <strong>${item.title || 'N/A'}</strong>${articleLink}
                </td>
                <td><strong>${bookmarkInfo}</strong></td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    // 結果セクションを表示
    document.getElementById('hatenaResults').style.display = 'block';
    console.log('✅ Hatena Results表示完了');
}

// Podcast結果表示関数
function displayPodcastResults(data) {
    console.log('📊 Podcast Results表示開始', data);
    const tableBody = document.getElementById('podcastTrendsTableBody');
    const statusMessage = document.getElementById('podcastStatusMessage');
    
    if (!tableBody || !statusMessage) {
        console.error('❌ Podcast DOM要素が見つかりません');
        return;
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    
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
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${item.listennotes_url || item.url || '#'}" target="_blank">${item.title || 'N/A'}</a></td>
            <td>${item.publisher || 'N/A'}</td>
            <td>${item.score || item.total_episodes || 'N/A'}</td>
        `;
        tableBody.appendChild(row);
    });
    
    // 結果セクションを表示（重要度付きでインラインスタイルを設定）
    document.getElementById('podcastResults').style.setProperty('display', 'block', 'important');
    console.log('✅ Podcast Results表示完了');
}

// 映画トレンド結果表示関数
function displayMovieResults(data) {
    console.log('📊 Movie Results表示開始', data);
    const tableBody = document.getElementById('movieTrendsTableBody');
    const statusMessage = document.getElementById('movieStatusMessage');
    
    if (!tableBody) {
        console.error('❌ Movie DOM要素が見つかりません');
        return;
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            
            const rating = item.vote_average ? (typeof item.vote_average === 'number' ? item.vote_average.toFixed(1) : parseFloat(item.vote_average).toFixed(1)) : 'N/A';
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
                <td><span class="badge bg-primary">${item.rank || index + 1}</span></td>
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
    
    // 結果セクションを表示
    const resultsElement = document.getElementById('movieResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ Movie Results表示完了');
}

// 本トレンド結果表示関数
function displayBookResults(data) {
    console.log('📊 Book Results表示開始', data);
    const tableBody = document.getElementById('bookTrendsTableBody');
    const statusMessage = document.getElementById('bookStatusMessage');
    
    if (!tableBody) {
        console.error('❌ Book DOM要素が見つかりません');
        return;
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            
            const author = item.author || (item.authors && item.authors.length > 0 ? item.authors.join(', ') : 'N/A') || 'N/A';
            const price = item.price ? `¥${parseInt(item.price).toLocaleString()}` : 'N/A';
            let rating = 'N/A';
            if (item.average_rating) {
                const avgRating = typeof item.average_rating === 'number' ? item.average_rating : parseFloat(item.average_rating);
                if (!isNaN(avgRating)) {
                    rating = avgRating.toFixed(1);
                }
            }
            const bookLink = item.item_url || '#';
            const imageUrl = item.image_url || '';
            
            row.innerHTML = `
                <td><span class="badge bg-info">${item.rank || index + 1}</span></td>
                <td>
                    ${imageUrl ? `<img src="${imageUrl}" alt="${item.title}" style="width: 40px; height: 60px; object-fit: cover; margin-right: 10px; float: left;">` : ''}
                    <strong><a href="${bookLink}" target="_blank">${item.title || 'N/A'}</a></strong>
                </td>
                <td>${author}</td>
                <td>${price !== 'N/A' ? price : rating}</td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    // 結果セクションを表示
    const resultsElement = document.getElementById('bookResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ Book Results表示完了');
}

// World News結果表示関数
function displayWorldNewsResults(data) {
    console.log('📊 World News Results表示開始', data);
    const tableBody = document.getElementById('newsTrendsTableBody');
    const statusMessage = document.getElementById('newsStatusMessage');
    
    if (!tableBody) {
        console.error('❌ World News DOM要素が見つかりません');
        return;
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';
            row.style.minHeight = '100px';
            
            // ニュースタイトルをリンク化
            const titleText = item.title || 'N/A';
            const titleLink = item.url
                ? `<a href="${item.url}" target="_blank" class="text-decoration-none">
                        ${titleText}
                        <i class="fas fa-external-link-alt ms-1"></i>
                   </a>`
                : `<span>${titleText}</span>`;
            
            // 要約（ある場合のみ表示）
            const descriptionText = item.description ? `<div class="text-muted small mt-1">${truncateText(item.description, 110)}</div>` : '';
            
            // 公開日時をフォーマット
            const publishedDateRaw = item.published_at || item.publish_date || item.publishedDate || item.published_date;
            const publishedDate = formatDate(publishedDateRaw);
            const sourceName = item.source || '';
            const metaInfoParts = [];
            if (publishedDate && publishedDate !== '不明') {
                metaInfoParts.push(publishedDate);
            }
            if (sourceName) {
                metaInfoParts.push(sourceName);
            }
            const metaInfo = metaInfoParts.join(' / ');
            
            row.innerHTML = `
                <td><span class="badge bg-info">${item.rank || index + 1}</span></td>
                <td>
                    <strong>${titleLink}</strong>
                    ${descriptionText}
                </td>
                <td><small class="text-muted">${metaInfo || '不明'}</small></td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    // 結果セクションを表示
    document.getElementById('newsResults').style.display = 'block';
    console.log('✅ World News Results表示完了');
}

// Twitch結果表示関数
function displayTwitchResults(data) {
    console.log('📊 Twitch Results表示開始', data);
    const tableBody = document.getElementById('twitchTrendsTableBody');
    const statusMessage = document.getElementById('twitchStatusMessage');
    
    if (!tableBody || !statusMessage) {
        console.error('❌ Twitch DOM要素が見つかりません');
        return;
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    // データを視聴者数で降順ソート（1位から表示）
    const sortedData = [...data.data].sort((a, b) => {
        const viewerCountA = a.viewer_count || a.score || 0;
        const viewerCountB = b.viewer_count || b.score || 0;
        return viewerCountB - viewerCountA; // 降順ソート
    });
    
    sortedData.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        // Twitchリンクを作成
        const twitchUrl = `https://www.twitch.tv/${item.user_name || item.name || ''}`;
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${twitchUrl}" target="_blank" class="text-decoration-none">${item.name || item.title || item.game_name || 'N/A'}</a></td>
            <td>${item.viewer_count || item.score || 0}人</td>
        `;
        tableBody.appendChild(row);
    });
    
    // ローディング表示を確実に非表示
    const loadingElement = document.getElementById('twitchTrendsLoading');
    if (loadingElement) {
        loadingElement.style.display = 'none !important';
        loadingElement.style.visibility = 'hidden !important';
    }
    
    // 結果セクションを表示
    document.getElementById('twitchResults').style.display = 'block';
    console.log('✅ Twitch Results表示完了');
}
