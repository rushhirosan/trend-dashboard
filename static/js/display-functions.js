// 結果表示関数群に関するJavaScriptファイル

// 共通の日時フォーマット関数（USトレンドページでも使用）
function formatDate(dateString, locale = 'ja-JP') {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return dateString;
        return new Intl.DateTimeFormat(locale, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).format(date);
    } catch (e) {
        return dateString;
    }
}

// 共通のテキスト切り詰め関数（USトレンドページでも使用）
function truncateText(text, maxLength = 100) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

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

            const articleUrl = item.url || '#';
            const articleTitle = item.title || 'N/A';

            // リンクを追加（他のセクションと同じ形式）
            const articleLink = articleUrl !== '#' ?
                `<br><a href="${articleUrl}" target="_blank" class="btn btn-sm btn-outline-warning mt-1">
                    <i class="fas fa-external-link-alt"></i> 記事を読む
                </a>` : '';

            row.innerHTML = `
                <td><span class="badge bg-warning">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${articleUrl}" target="_blank">${articleTitle}</a></strong>${articleLink}
                </td>
                <td><strong>${bookmarkInfo}</strong></td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, articleUrl, `${articleTitle}の記事を開く`);
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
        const podcastUrl = item.listennotes_url || item.url || '#';
        const podcastTitle = item.title || 'N/A';
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${podcastUrl}" target="_blank">${podcastTitle}</a></td>
            <td>${item.publisher || 'N/A'}</td>
            <td>${item.score || item.total_episodes || 'N/A'}</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, podcastUrl, `${podcastTitle}のポッドキャストを開く`);
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
                    <i class="fas fa-shopping-cart"></i> Amazonで見る
                   </a>`
                : '';

            const movieTitle = item.title || 'N/A';
            row.innerHTML = `
                <td><span class="badge bg-primary">${item.rank || index + 1}</span></td>
                <td>
                    ${posterUrl ? `<img src="${posterUrl}" alt="${movieTitle}" style="width: 50px; height: 75px; object-fit: cover; margin-right: 10px; float: left;">` : ''}
                    <strong><a href="${tmdbLink}" target="_blank">${movieTitle}</a></strong>
                    ${item.original_title && item.original_title !== item.title ? `<br><small class="text-muted">${item.original_title}</small>` : ''}
                    ${amazonButton}
                </td>
                <td>${rating}</td>
                <td>${releaseDate}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, tmdbLink, `${movieTitle}の映画情報を開く`);
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
        // リンクの優先順位: amazon_link > affiliate_url > item_url
        const bookLink = item.amazon_link || item.affiliate_url || item.item_url || '#';
            const imageUrl = item.image_url || '';

            const bookTitle = item.title || 'N/A';
            row.innerHTML = `
                <td><span class="badge bg-info">${item.rank || index + 1}</span></td>
                <td>
                    ${imageUrl ? `<img src="${imageUrl}" alt="${bookTitle}" style="width: 40px; height: 60px; object-fit: cover; margin-right: 10px; float: left;">` : ''}
                    <strong><a href="${bookLink}" target="_blank">${bookTitle}</a></strong>
                </td>
                <td>${author}</td>
                <td>${price}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, bookLink, `${bookTitle}の本を開く`);
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

// GitHubトレンド結果表示関数
function displayGitHubResults(data) {
    console.log('📊 GitHub Results表示開始', data);
    const tableBody = document.getElementById('githubTrendsTableBody');
    const statusMessage = document.getElementById('githubStatusMessage');

    if (!tableBody) {
        console.error('❌ GitHub DOM要素が見つかりません');
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

            // stars_countまたはstarsのどちらかを使用（互換性のため）
            const starsValue = item.stars_count !== undefined ? item.stars_count : (item.stars !== undefined ? item.stars : 0);
            const stars = starsValue ? starsValue.toLocaleString() : '0';
            const language = item.language || 'N/A';
            const repoUrl = item.url || '#';
            const repoName = item.full_name || item.name || 'N/A';

            row.innerHTML = `
                <td><span class="badge bg-dark">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${repoUrl}" target="_blank">${repoName}</a></strong>
                    ${item.description ? `<br><small class="text-muted">${item.description}</small>` : ''}
                </td>
                <td>${language}</td>
                <td>⭐ ${stars}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, repoUrl, `${repoName}のリポジトリを開く`);
            tableBody.appendChild(row);
        });
    }

    // 結果セクションを表示
    const resultsElement = document.getElementById('githubResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ GitHub Results表示完了');
}

// App Storeトレンド結果表示関数
function displayAppStoreResults(data) {
    console.log('📊 App Store Results表示開始', data);
    const tableBody = document.getElementById('appstoreTrendsTableBody');
    const statusMessage = document.getElementById('appstoreStatusMessage');

    if (!tableBody) {
        console.error('❌ App Store DOM要素が見つかりません');
        return;
    }

    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    // テーブルを更新
    tableBody.innerHTML = '';
    console.log('📊 App Store: データ件数:', data.data ? data.data.length : 0);
    if (data.data && data.data.length > 0) {
        console.log('📊 App Store: データ表示開始（全' + data.data.length + '件）');
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            const rating = item.average_user_rating ? (typeof item.average_user_rating === 'number' ? item.average_user_rating.toFixed(1) : parseFloat(item.average_user_rating).toFixed(1)) : 'N/A';
            const developer = item.artist_name || 'N/A';
            const appUrl = item.url || '#';
            const iconUrl = item.artwork_url_100 || item.artwork_url_60 || '';

            const appName = item.name || 'N/A';
            row.innerHTML = `
                <td><span class="badge bg-success">${item.rank || index + 1}</span></td>
                <td>
                    ${iconUrl ? `<img src="${iconUrl}" alt="${appName}" style="width: 50px; height: 50px; object-fit: cover; margin-right: 10px; float: left; border-radius: 10px;">` : ''}
                    <strong><a href="${appUrl}" target="_blank">${appName}</a></strong>
                </td>
                <td>${developer}</td>
                <td>${rating !== 'N/A' ? `⭐ ${rating}` : 'N/A'}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, appUrl, `${appName}のアプリを開く`);
            tableBody.appendChild(row);
            if (index < 3) {
                console.log(`📊 App Store: 行${index + 1}追加完了 (${item.name}, 評価: ${rating})`);
            }
        });
        console.log('📊 App Store: 全' + data.data.length + '件のデータをテーブルに追加しました');
    } else {
        console.warn('📊 App Store: 表示するデータがありません');
    }

    // 結果セクションを表示
    const resultsElement = document.getElementById('appstoreResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ App Store Results表示完了');
}

// IPA注意喚起結果表示関数
function displayIPAResults(data) {
    console.log('📊 IPA Results表示開始', data);
    const tableBody = document.getElementById('ipaTrendsTableBody');
    const statusMessage = document.getElementById('ipaStatusMessage');

    if (!tableBody) {
        console.error('❌ IPA DOM要素が見つかりません');
        return;
    }

    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            const title = item.title || 'N/A';
            const url = item.url || '#';
            const publishedDate = item.published_date ? formatDate(item.published_date) : 'N/A';

            row.innerHTML = `
                <td><span class="badge bg-danger">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${url}" target="_blank">${title}</a></strong>
                    ${item.description ? `<br><small class="text-muted">${truncateText(item.description, 100)}</small>` : ''}
                </td>
                <td>${publishedDate}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `${title}のIPA注意喚起情報を開く`);
            tableBody.appendChild(row);
        });
    }

    const resultsElement = document.getElementById('ipaResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ IPA Results表示完了');
}

// JPCERT/CC結果表示関数
function displayJPCERTResults(data) {
    console.log('📊 JPCERT/CC Results表示開始', data);
    const tableBody = document.getElementById('jpcertTrendsTableBody');
    const statusMessage = document.getElementById('jpcertStatusMessage');

    if (!tableBody) {
        console.error('❌ JPCERT/CC DOM要素が見つかりません');
        return;
    }

    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            const title = item.title || 'N/A';
            const url = item.url || '#';
            const publishedDate = item.published_date ? formatDate(item.published_date) : 'N/A';

            row.innerHTML = `
                <td><span class="badge bg-warning">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${url}" target="_blank">${title}</a></strong>
                    ${item.description ? `<br><small class="text-muted">${truncateText(item.description, 100)}</small>` : ''}
                </td>
                <td>${publishedDate}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `${title}のJPCERT/CC情報を開く`);
            tableBody.appendChild(row);
        });
    }

    const resultsElement = document.getElementById('jpcertResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ JPCERT/CC Results表示完了');
}

// Zenn結果表示関数
function displayZennResults(data) {
    console.log('📊 Zenn Results表示開始', data);
    const tableBody = document.getElementById('zennTrendsTableBody');
    const statusMessage = document.getElementById('zennStatusMessage');

    if (!tableBody) {
        console.error('❌ Zenn DOM要素が見つかりません');
        return;
    }

    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            const title = item.title || 'N/A';
            const url = item.url || '#';
            const publishedDate = item.published_date ? formatDate(item.published_date) : 'N/A';

            row.innerHTML = `
                <td><span class="badge bg-primary">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${url}" target="_blank">${title}</a></strong>
                    ${item.description ? `<br><small class="text-muted">${truncateText(item.description, 100)}</small>` : ''}
                </td>
                <td>${publishedDate}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `${title}のZenn記事を開く`);
            tableBody.appendChild(row);
        });
    }

    const resultsElement = document.getElementById('zennResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ Zenn Results表示完了');
}

// Note結果表示関数
function displayNoteResults(data) {
    console.log('📊 Note Results表示開始', data);
    const tableBody = document.getElementById('noteTrendsTableBody');
    const statusMessage = document.getElementById('noteStatusMessage');

    if (!tableBody) {
        console.error('❌ Note DOM要素が見つかりません');
        return;
    }

    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            const title = item.title || 'N/A';
            const url = item.url || '#';
            const publishedDate = item.published_date ? formatDate(item.published_date) : 'N/A';

            row.innerHTML = `
                <td><span class="badge bg-secondary">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${url}" target="_blank">${title}</a></strong>
                    ${item.description ? `<br><small class="text-muted">${truncateText(item.description, 100)}</small>` : ''}
                </td>
                <td>${publishedDate}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `${title}の記事を開く`);
            tableBody.appendChild(row);
        });
    }

    const resultsElement = document.getElementById('noteResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ Note Results表示完了');
}

// CISA KEV結果表示関数
function displayCISAKEVResults(data) {
    console.log('📊 CISA KEV Results表示開始', data);
    const tableBody = document.getElementById('cisaKevTrendsTableBody');
    const statusMessage = document.getElementById('cisaKevStatusMessage');

    if (!tableBody) {
        console.error('❌ CISA KEV DOM要素が見つかりません');
        return;
    }

    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            const cveId = item.cve_id || 'N/A';
            const product = item.product || 'N/A';
            const dateAdded = item.date_added ? formatDate(item.date_added) : 'N/A';
            const cveUrl = cveId !== 'N/A' ? `https://cve.mitre.org/cgi-bin/cvename.cgi?name=${cveId}` : '#';

            row.innerHTML = `
                <td><span class="badge bg-danger">${item.rank || index + 1}</span></td>
                <td><strong><a href="${cveUrl}" target="_blank">${cveId}</a></strong></td>
                <td>${product}</td>
                <td>${dateAdded}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, cveUrl, `${cveId}のCISA KEV情報を開く`);
            tableBody.appendChild(row);
        });
    }

    const resultsElement = document.getElementById('cisaKevResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ CISA KEV Results表示完了');
}

// The Hacker News結果表示関数
function displayTheHackerNewsResults(data) {
    console.log('📊 The Hacker News Results表示開始', data);
    const tableBody = document.getElementById('thehackernewsTrendsTableBody');
    const statusMessage = document.getElementById('thehackernewsStatusMessage');

    if (!tableBody) {
        console.error('❌ The Hacker News DOM要素が見つかりません');
        return;
    }

    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            const title = item.title || 'N/A';
            const url = item.url || '#';
            const publishedDate = item.published_date ? formatDate(item.published_date) : 'N/A';

            row.innerHTML = `
                <td><span class="badge bg-info">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${url}" target="_blank">${title}</a></strong>
                    ${item.description ? `<br><small class="text-muted">${truncateText(item.description, 100)}</small>` : ''}
                </td>
                <td>${publishedDate}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `${title}のThe Hacker News記事を開く`);
            tableBody.appendChild(row);
        });
    }

    const resultsElement = document.getElementById('thehackernewsResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ The Hacker News Results表示完了');
}

// Hacker Noon結果表示関数
function displayHackerNoonResults(data) {
    console.log('📊 Hacker Noon Results表示開始', data);
    const tableBody = document.getElementById('hackernoonTrendsTableBody');
    const statusMessage = document.getElementById('hackernoonStatusMessage');

    if (!tableBody) {
        console.error('❌ Hacker Noon DOM要素が見つかりません');
        return;
    }

    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }

    tableBody.innerHTML = '';
    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            const title = item.title || 'N/A';
            const url = item.url || '#';
            const author = item.author || 'N/A';
            const publishedDate = item.published_date ? formatDate(item.published_date) : 'N/A';

            row.innerHTML = `
                <td><span class="badge bg-primary">${item.rank || index + 1}</span></td>
                <td>
                    <strong><a href="${url}" target="_blank">${title}</a></strong>
                    ${item.description ? `<br><small class="text-muted">${truncateText(item.description, 100)}</small>` : ''}
                </td>
                <td>${author}</td>
                <td>${publishedDate}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, url, `${title}のHacker Noon記事を開く`);
            tableBody.appendChild(row);
        });
    }

    const resultsElement = document.getElementById('hackernoonResults');
    if (resultsElement) {
        resultsElement.style.display = 'block';
    }
    console.log('✅ Hacker Noon Results表示完了');
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

            const newsUrl = item.url || '#';
            row.innerHTML = `
                <td><span class="badge bg-info">${item.rank || index + 1}</span></td>
                <td>
                    <strong>${titleLink}</strong>
                    ${descriptionText}
                </td>
                <td><small class="text-muted">${metaInfo || '不明'}</small></td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, newsUrl, `${titleText}のニュース記事を開く`);
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
        const streamName = item.name || item.title || item.game_name || 'N/A';

        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${twitchUrl}" target="_blank" class="text-decoration-none">${streamName}</a></td>
            <td>${item.viewer_count || item.score || 0}人</td>
        `;
        // 行全体をクリック可能にする（アクセシビリティ対応）
        makeTableRowClickable(row, twitchUrl, `${streamName}のTwitch配信を開く`);
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
