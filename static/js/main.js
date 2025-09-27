// メインのJavaScriptファイル
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 ページ読み込み完了、データの鮮度情報取得開始');
    
    // タブ制御の初期化
    initTabControl();
    
    // サブスクリプション機能の初期化
    initSubscription();
    
    // 初期状態でデータ鮮度情報を更新（キャッシュのみ）
    setTimeout(() => {
        console.log('🔄 初期化時のデータ鮮度情報更新を開始（キャッシュのみ）...');
        refreshDataFreshnessFromCache();
    }, 500);
    
    // ボタンのイベントリスナーを設定
    setupButtonEventListeners();
    
    // キャッシュデータを自動読み込み
    loadCachedData();
    
    // 初期化完了
});

// タブ制御の初期化
function initTabControl() {
    const trendsJpTab = document.getElementById('trends-jp-tab');
    const trendsUsTab = document.getElementById('trends-us-tab');
    const dataStatusTab = document.getElementById('data-status-tab');
    const subscriptionTab = document.getElementById('subscription-tab');
    const trendsJpContent = document.getElementById('trends-jp');
    const trendsUsContent = document.getElementById('trends-us');
    const dataStatusContent = document.getElementById('data-status');
    const subscriptionContent = document.getElementById('subscription');
    
    console.log('🔍 タブ要素の確認:', {
        trendsJpTab: trendsJpTab ? '見つかった' : '見つからない',
        trendsUsTab: trendsUsTab ? '見つかった' : '見つからない',
        dataStatusTab: dataStatusTab ? '見つかった' : '見つからない',
        subscriptionTab: subscriptionTab ? '見つかった' : '見つからない',
        trendsJpContent: trendsJpContent ? '見つかった' : '見つからない',
        trendsUsContent: trendsUsContent ? '見つかった' : '見つからない',
        dataStatusContent: dataStatusContent ? '見つかった' : '見つからない',
        subscriptionContent: subscriptionContent ? '見つかった' : '見つからない'
    });
    
    // 初期状態を設定
    showTab('trends-jp');
    
    // タブクリック時の処理
    if (trendsJpTab) {
        trendsJpTab.addEventListener('click', function(e) {
            e.preventDefault();
            showTab('trends-jp');
        });
    }
    
    if (trendsUsTab) {
        trendsUsTab.addEventListener('click', function(e) {
            e.preventDefault();
            showTab('trends-us');
        });
    }
    
    if (dataStatusTab) {
        dataStatusTab.addEventListener('click', function(e) {
            e.preventDefault();
            showTab('data-status');
        });
    }
    
    if (subscriptionTab) {
        subscriptionTab.addEventListener('click', function(e) {
            e.preventDefault();
            showTab('subscription');
        });
    }
}

// タブを表示する関数
function showTab(tabName) {
    console.log(`🔄 ${tabName}タブを表示中...`);
    
    // 全てのコンテンツを非表示
    const trendsJpContent = document.getElementById('trends-jp');
    const trendsUsContent = document.getElementById('trends-us');
    const dataStatusContent = document.getElementById('data-status');
    const subscriptionContent = document.getElementById('subscription');
    
    if (trendsJpContent) {
        trendsJpContent.style.display = 'none';
        trendsJpContent.style.visibility = 'hidden';
    }
    if (trendsUsContent) {
        trendsUsContent.style.display = 'none';
        trendsUsContent.style.visibility = 'hidden';
    }
    if (dataStatusContent) {
        dataStatusContent.style.display = 'none';
        dataStatusContent.style.visibility = 'hidden';
    }
    if (subscriptionContent) {
        subscriptionContent.style.display = 'none';
        subscriptionContent.style.visibility = 'hidden';
    }
    
    // 全てのタブボタンのハイライトをリセット
    const trendsJpTab = document.getElementById('trends-jp-tab');
    const trendsUsTab = document.getElementById('trends-us-tab');
    const dataStatusTab = document.getElementById('data-status-tab');
    const subscriptionTab = document.getElementById('subscription-tab');
    
    if (trendsJpTab) {
        trendsJpTab.classList.remove('active', 'btn-primary');
        trendsJpTab.classList.add('btn-outline-primary');
    }
    if (trendsUsTab) {
        trendsUsTab.classList.remove('active', 'btn-primary');
        trendsUsTab.classList.add('btn-outline-primary');
    }
    if (dataStatusTab) {
        dataStatusTab.classList.remove('active', 'btn-secondary');
        dataStatusTab.classList.add('btn-outline-secondary');
    }
    if (subscriptionTab) {
        subscriptionTab.classList.remove('active', 'btn-info');
        subscriptionTab.classList.add('btn-outline-info');
    }
    
    // 指定されたタブを表示
    if (tabName === 'trends-jp') {
        if (trendsJpContent) {
            trendsJpContent.style.display = 'block';
            trendsJpContent.style.visibility = 'visible';
            trendsJpContent.style.opacity = '1';
        }
        if (trendsJpTab) {
            trendsJpTab.classList.add('active', 'btn-primary');
            trendsJpTab.classList.remove('btn-outline-primary');
        }
        document.body.classList.remove('data-status-active', 'subscription-active');
        console.log('✅ トレンド一覧（日本）タブを表示しました');
        
        // 日本タブが表示された時にキャッシュデータを読み込み
        console.log('🔄 日本タブ表示時のキャッシュデータ読み込み開始');
        showJapanTabContent();
        loadCachedData();
        
    } else if (tabName === 'trends-us') {
        if (trendsUsContent) {
            trendsUsContent.style.display = 'block';
            trendsUsContent.style.visibility = 'visible';
            trendsUsContent.style.opacity = '1';
        }
        if (trendsUsTab) {
            trendsUsTab.classList.add('active', 'btn-primary');
            trendsUsTab.classList.remove('btn-outline-primary');
        }
        document.body.classList.remove('data-status-active', 'subscription-active');
        console.log('✅ トレンド一覧（アメリカ）タブを表示しました');
        
        // アメリカタブでは日本タブのコンテンツ全体を非表示にする
        console.log('🚫 アメリカタブでは日本のカテゴリとデータをすべて非表示にします');
        hideJapanTabContent();
        
    } else if (tabName === 'data-status') {
        if (dataStatusContent) {
            dataStatusContent.style.display = 'block';
            dataStatusContent.style.visibility = 'visible';
            dataStatusContent.style.opacity = '1';
            dataStatusContent.style.height = 'auto';
            dataStatusContent.style.minHeight = '500px';
        }
        if (dataStatusTab) {
            dataStatusTab.classList.add('active', 'btn-secondary');
            dataStatusTab.classList.remove('btn-outline-secondary');
        }
        document.body.classList.add('data-status-active');
        document.body.classList.remove('subscription-active');
        console.log('✅ データ鮮度情報タブを表示しました');
        
        // データ鮮度情報を更新（キャッシュのみ）
        console.log('🔄 データ鮮度情報タブ表示後、キャッシュデータを表示...');
        setTimeout(() => {
            console.log('🔄 refreshDataFreshnessFromCache関数を呼び出し中...');
            refreshDataFreshnessFromCache();
        }, 100);
        
        // 追加でテストテキストを強制表示
        setTimeout(() => {
            console.log('🧪 追加のテストテキスト表示を実行中...');
            testDataFreshnessDisplay();
            
            // さらに強制的に全てのテキスト要素を表示
            const allTextElements = dataStatusContent.querySelectorAll('*');
            allTextElements.forEach(element => {
                element.style.display = 'block';
                element.style.visibility = 'visible';
                element.style.opacity = '1';
                element.style.color = '#000';
                element.style.position = 'static';
                element.style.zIndex = 'auto';
                element.style.overflow = 'visible';
                element.style.clip = 'auto';
                element.style.clipPath = 'none';
                element.style.transform = 'none';
                element.style.filter = 'none';
                element.style.backdropFilter = 'none';
                element.style.mask = 'none';
                element.style.webkitMask = 'none';
            });
            
            // インライン要素を適切に設定
            const inlineElements = dataStatusContent.querySelectorAll('.text-muted, .badge, small');
            inlineElements.forEach(element => {
                element.style.display = 'inline-block';
            });
            
            console.log('🔧 全てのテキスト要素を強制的に表示しました');
        }, 500);
        
    } else if (tabName === 'subscription') {
        if (subscriptionContent) {
            subscriptionContent.style.display = 'block';
            subscriptionContent.style.visibility = 'visible';
            subscriptionContent.style.opacity = '1';
        }
        if (subscriptionTab) {
            subscriptionTab.classList.add('active', 'btn-info');
            subscriptionTab.classList.remove('btn-outline-info');
        }
        document.body.classList.add('subscription-active');
        document.body.classList.remove('data-status-active');
        console.log('✅ サブスクリプションタブを表示しました');
    }
}


// データ鮮度情報を更新する関数（外部ファイルの関数を呼び出し）
function refreshDataFreshness() {
    console.log('🔄 データ鮮度情報を更新中...');
    
    // データ鮮度情報のコンテナを確認
    const dataStatusContent = document.getElementById('data-status');
    if (dataStatusContent) {
        console.log('📊 データ鮮度情報コンテナの内容:', dataStatusContent.innerHTML.length, '文字');
        if (dataStatusContent.innerHTML.trim() === '') {
            console.warn('⚠️ データ鮮度情報の内容が空です');
        }
        
        // データ鮮度情報が表示されているか確認
        const computedStyle = window.getComputedStyle(dataStatusContent);
        console.log('📊 データ鮮度情報の表示状態:', {
            display: computedStyle.display,
            visibility: computedStyle.visibility,
            opacity: computedStyle.opacity,
            height: computedStyle.height,
            width: computedStyle.width
        });
    } else {
        console.error('❌ データ鮮度情報コンテナが見つかりません！');
    }
    
    // まずテスト用のテキストを強制的に表示して切り分け
    console.log('🧪 テスト用のテキストを強制的に表示中...');
    testDataFreshnessDisplay();
    
    // 外部ファイルのrefreshDataFreshness関数を直接呼び出し（無限ループ回避）
    if (typeof refreshDataFreshnessExternal === 'function') {
        console.log('🔄 直接refreshDataFreshnessExternal関数を呼び出し中...');
        refreshDataFreshnessExternal();
    } else if (typeof window.refreshDataFreshnessExternal === 'function') {
        console.log('🔄 外部ファイルのrefreshDataFreshnessExternal関数を呼び出し中...');
        window.refreshDataFreshnessExternal();
    } else {
        console.warn('⚠️ refreshDataFreshnessExternal関数が見つかりません');
        console.log('🔍 利用可能な関数:', Object.keys(window).filter(key => key.includes('refresh')));
        console.error('❌ refreshDataFreshnessExternal関数が利用できません');
        console.log('🔍 利用可能な関数:', Object.keys(window).filter(key => key.includes('Data')));
    }
}

// データ鮮度情報をキャッシュから表示する関数（API呼び出しなし）
function refreshDataFreshnessFromCache() {
    console.log('📊 データ鮮度情報をキャッシュから表示中（API呼び出しなし）...');
    
    // データ鮮度情報のコンテナを確認
    const dataStatusContent = document.getElementById('data-status');
    if (dataStatusContent) {
        console.log('📊 データ鮮度情報コンテナの内容:', dataStatusContent.innerHTML.length, '文字');
        if (dataStatusContent.innerHTML.trim() === '') {
            console.warn('⚠️ データ鮮度情報の内容が空です');
        }
    } else {
        console.error('❌ データ鮮度情報のコンテナが見つかりません');
    }
    
    // テスト用のテキストを強制的に表示
    console.log('🧪 テスト用のテキストを強制的に表示中...');
    testDataFreshnessDisplay();
    
    // キャッシュデータのみを表示（API呼び出しなし）
    console.log('📊 キャッシュデータのみを表示します（API呼び出しなし）');
}

// プラットフォームのステータスを更新（外部ファイルの関数を呼び出し）
function updatePlatformStatus(platform, platformName) {
    // 外部ファイルのupdatePlatformStatus関数を直接呼び出し（無限ループ回避）
    if (typeof window.updatePlatformStatusExternal === 'function') {
        window.updatePlatformStatusExternal(platform, platformName);
    } else {
        console.log(`✅ ${platformName}のステータス更新（外部ファイル）`);
    }
}

// ボタンのイベントリスナーを設定
function setupButtonEventListeners() {
    // データ鮮度更新ボタンのイベントリスナー
    const refreshDataFreshnessButton = document.getElementById('refreshDataFreshnessButton');
    if (refreshDataFreshnessButton) {
        refreshDataFreshnessButton.addEventListener('click', function() {
            console.log('🔄 データ鮮度更新ボタンがクリックされました');
            // 外部ファイルのrefreshDataFreshnessExternal関数を呼び出し
            if (typeof window.refreshDataFreshnessExternal === 'function') {
                window.refreshDataFreshnessExternal();
            } else {
                console.log('データ鮮度更新処理（外部ファイル）');
            }
        });
        console.log('✅ データ鮮度更新ボタンのイベントリスナー設定完了');
    } else {
        console.error('❌ データ鮮度更新ボタンが見つかりません');
    }
}

// キャッシュデータを自動読み込み（外部ファイルの関数を呼び出し）
function loadCachedData() {
    console.log('📦 キャッシュデータの読み込み処理開始（main.js）');
    
    // 外部ファイルのloadCachedDataExternal関数を直接呼び出し
    if (typeof loadCachedDataExternal === 'function') {
        console.log('✅ loadCachedDataExternal関数が見つかりました');
        loadCachedDataExternal();
    } else {
        console.log('❌ loadCachedDataExternal関数が見つかりません');
        console.log('利用可能な関数:', Object.keys(window).filter(key => key.includes('load')));
    }
}

// 日本タブのコンテンツを表示する関数
function showJapanTabContent() {
    console.log('✅ 日本タブのコンテンツを表示します');
    
    const trendsJpContent = document.getElementById('trends-jp');
    if (trendsJpContent) {
        // 日本タブ全体を表示状態に戻す
        trendsJpContent.style.display = 'block';
        trendsJpContent.style.visibility = 'visible';
        trendsJpContent.style.opacity = '1';
        console.log('✅ 日本タブのコンテンツを完全に表示しました');
    }
}

// 日本タブのコンテンツを非表示にする関数
function hideJapanTabContent() {
    console.log('🚫 日本タブのコンテンツを非表示にします');
    
    const trendsJpContent = document.getElementById('trends-jp');
    console.log('🔍 trends-jp要素:', trendsJpContent);
    
    if (trendsJpContent) {
        console.log('🔍 非表示前のstyle:', {
            display: trendsJpContent.style.display,
            visibility: trendsJpContent.style.visibility
        });
        
        // 日本タブ全体を非表示にする
        trendsJpContent.style.display = 'none';
        trendsJpContent.style.visibility = 'hidden';
        
        console.log('🔍 非表示後のstyle:', {
            display: trendsJpContent.style.display,
            visibility: trendsJpContent.style.visibility
        });
        
        console.log('🚫 日本タブのコンテンツを完全に非表示にしました');
    } else {
        console.error('❌ trends-jp要素が見つかりません');
    }
}

// タブのレイアウトを強制的に修正する関数
function fixTabLayout() {
    const navTabs = document.querySelector('.nav-tabs');
    const navItems = document.querySelectorAll('.nav-tabs .nav-item');
    
    if (navTabs && navItems.length > 0) {
        console.log('🔧 タブレイアウトを修正中...');
        
        // タブコンテナのスタイルを強制設定
        navTabs.style.display = 'flex';
        navTabs.style.flexDirection = 'row';
        navTabs.style.flexWrap = 'nowrap';
        navTabs.style.width = '100%';
        navTabs.style.listStyle = 'none';
        navTabs.style.margin = '0';
        navTabs.style.padding = '0';
        
        // 各タブアイテムのスタイルを強制設定
        navItems.forEach((item, index) => {
            item.style.display = 'inline-block';
            item.style.width = '50%';
            item.style.float = 'left';
            item.style.margin = '0';
            item.style.padding = '0';
            item.style.flex = '1';
            
            const navLink = item.querySelector('.nav-link');
            if (navLink) {
                navLink.style.display = 'block';
                navLink.style.width = '100%';
                navLink.style.textAlign = 'center';
                navLink.style.padding = '0.5rem 1rem';
                navLink.style.border = 'none';
                navLink.style.background = 'transparent';
                navLink.style.color = '#495057';
                navLink.style.textDecoration = 'none';
            }
            
            console.log(`📊 タブ${index + 1}のレイアウトを修正しました`);
        });
        
        console.log('✅ タブレイアウトの修正完了');
    } else {
        console.error('❌ タブ要素が見つかりません');
    }
}

// データ鮮度情報のレイアウトを強制的に修正する関数
function fixDataFreshnessLayout() {
    const dataFreshnessContent = document.getElementById('dataFreshnessContent');
    const rows = dataFreshnessContent?.querySelectorAll('.row');
    const colMd6s = dataFreshnessContent?.querySelectorAll('.col-md-6');
    
    if (dataFreshnessContent && rows && colMd6s) {
        console.log('🔧 データ鮮度情報レイアウトを修正中...');
        
        // 行のスタイルを強制設定
        rows.forEach((row, index) => {
            row.style.display = 'flex';
            row.style.flexWrap = 'wrap';
            row.style.margin = '0';
            console.log(`📊 行${index + 1}のレイアウトを修正しました`);
        });
        
        // カラムのスタイルを強制設定
        colMd6s.forEach((col, index) => {
            col.style.flex = '0 0 50%';
            col.style.maxWidth = '50%';
            col.style.padding = '0.75rem';
            col.style.display = 'block';
            col.style.float = 'left';
            console.log(`📊 カラム${index + 1}のレイアウトを修正しました`);
        });
        
        console.log('✅ データ鮮度情報レイアウトの修正完了');
    } else {
        console.error('❌ データ鮮度情報要素が見つかりません');
    }
}

// テスト用のシンプルなデータ表示関数
function testDataFreshnessDisplay() {
    console.log('🧪 データ鮮度情報のテスト表示を開始...');
    
    const platforms = ['google', 'youtube', 'spotify', 'news', 'podcast', 'rakuten', 'hatena', 'twitch'];
    
    platforms.forEach(platform => {
        const lastUpdateElement = document.getElementById(`${platform}LastUpdate`);
        const dataCountElement = document.getElementById(`${platform}DataCount`);
        const statusElement = document.getElementById(`${platform}Status`);
        
        if (lastUpdateElement) {
            lastUpdateElement.textContent = 'テスト時刻: 2025/1/9 16:30:00';
            lastUpdateElement.style.display = 'block';
            lastUpdateElement.style.visibility = 'visible';
            lastUpdateElement.style.opacity = '1';
            lastUpdateElement.style.color = '#000';
            lastUpdateElement.style.fontSize = '14px';
            lastUpdateElement.style.fontWeight = 'bold';
            lastUpdateElement.style.position = 'static';
            lastUpdateElement.style.zIndex = 'auto';
            lastUpdateElement.style.overflow = 'visible';
            lastUpdateElement.style.clip = 'auto';
            lastUpdateElement.style.clipPath = 'none';
            lastUpdateElement.style.transform = 'none';
            lastUpdateElement.style.filter = 'none';
            lastUpdateElement.style.backdropFilter = 'none';
            lastUpdateElement.style.mask = 'none';
            lastUpdateElement.style.webkitMask = 'none';
            console.log(`✅ ${platform}LastUpdate を更新しました`);
        } else {
            console.error(`❌ ${platform}LastUpdate が見つかりません`);
        }
        
        if (dataCountElement) {
            dataCountElement.textContent = 'テスト: 25件';
            dataCountElement.style.display = 'block';
            dataCountElement.style.visibility = 'visible';
            dataCountElement.style.opacity = '1';
            dataCountElement.style.color = '#000';
            dataCountElement.style.fontSize = '14px';
            dataCountElement.style.fontWeight = 'bold';
            dataCountElement.style.position = 'static';
            dataCountElement.style.zIndex = 'auto';
            dataCountElement.style.overflow = 'visible';
            dataCountElement.style.clip = 'auto';
            dataCountElement.style.clipPath = 'none';
            dataCountElement.style.transform = 'none';
            dataCountElement.style.filter = 'none';
            dataCountElement.style.backdropFilter = 'none';
            dataCountElement.style.mask = 'none';
            dataCountElement.style.webkitMask = 'none';
            console.log(`✅ ${platform}DataCount を更新しました`);
        } else {
            console.error(`❌ ${platform}DataCount が見つかりません`);
        }
        
        if (statusElement) {
            statusElement.textContent = 'テスト成功';
            statusElement.className = 'badge bg-success';
            statusElement.style.display = 'inline-block';
            statusElement.style.visibility = 'visible';
            statusElement.style.opacity = '1';
            statusElement.style.color = '#fff';
            statusElement.style.fontSize = '12px';
            statusElement.style.backgroundColor = '#28a745';
            statusElement.style.padding = '0.25em 0.4em';
            statusElement.style.borderRadius = '0.25rem';
            statusElement.style.position = 'static';
            statusElement.style.zIndex = 'auto';
            statusElement.style.overflow = 'visible';
            statusElement.style.clip = 'auto';
            statusElement.style.clipPath = 'none';
            statusElement.style.transform = 'none';
            statusElement.style.filter = 'none';
            statusElement.style.backdropFilter = 'none';
            statusElement.style.mask = 'none';
            statusElement.style.webkitMask = 'none';
            console.log(`✅ ${platform}Status を更新しました`);
        } else {
            console.error(`❌ ${platform}Status が見つかりません`);
        }
    });
    
    console.log('🧪 テスト表示完了');
}

