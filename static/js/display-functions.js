// 結果表示関数群に関するJavaScriptファイル

// はてなブックマーク結果表示関数
function displayHatenaResults(data) {
    console.log('📊 Hatena Results表示開始', data);
    const tableBody = document.getElementById('hatenaTrendsTableBody');
    const statusMessage = document.getElementById('hatenaStatusMessage');
    
    if (!tableBody || !statusMessage) {
        console.error('❌ Hatena DOM要素が見つかりません');
        return;
    }
    
    // ステータスアイコンを更新
    const statusIcon = document.getElementById('hatenaStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${item.url}" target="_blank">${item.title}</a></td>
            <td>${item.bookmark_count || 0}</td>
        `;
        tableBody.appendChild(row);
    });
    
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
    
    // ステータスアイコンを更新
    const statusIcon = document.getElementById('podcastStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    data.data.forEach((item, index) => {
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
    
    // 結果セクションを表示
    document.getElementById('podcastResults').style.display = 'block';
    console.log('✅ Podcast Results表示完了');
}

// World News結果表示関数
function displayWorldNewsResults(data) {
    console.log('📊 World News Results表示開始', data);
    const tableBody = document.getElementById('newsTrendsTableBody');
    const statusMessage = document.getElementById('newsStatusMessage');
    
    if (!tableBody || !statusMessage) {
        console.error('❌ World News DOM要素が見つかりません');
        return;
    }
    
    // ステータスアイコンを更新
    const statusIcon = document.getElementById('newsStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
    }
    
    // ステータスメッセージは非表示のまま
    if (statusMessage) {
        statusMessage.style.display = 'none !important';
    }
    
    // テーブルを更新
    tableBody.innerHTML = '';
    data.data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.className = 'trend-card';
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><a href="${item.url || '#'}" target="_blank">${item.title || 'N/A'}</a></td>
            <td>${item.published_at || item.publish_date || 'N/A'}</td>
        `;
        tableBody.appendChild(row);
    });
    
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
    
    // ステータスアイコンを更新
    const statusIcon = document.getElementById('twitchStatusIcon');
    if (statusIcon) {
        if (data.data && data.data.length > 0) {
            statusIcon.innerHTML = '<i class="fas fa-check text-white"></i>';
            statusIcon.className = 'badge bg-success';
        } else {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle text-white"></i>';
            statusIcon.className = 'badge bg-danger';
        }
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
