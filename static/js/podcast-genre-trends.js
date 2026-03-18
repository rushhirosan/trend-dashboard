// Podcast ジャンル選択 UI + トレンド取得（日本版）
// Listen Notes API の /genres を経由してセレクトボックスを動的生成し、
// createDropdownTrendsManager + localStorage で前回選択を記憶する。

(function () {
    if (typeof createDropdownTrendsManager !== 'function') {
        console.warn('createDropdownTrendsManager が見つからないため、Podcast ジャンル選択は無効化されます。');
        return;
    }

    function populatePodcastGenres() {
        const selectEl = document.getElementById('podcastGenreSelect');
        if (!selectEl) return;

        // すでにオプションが追加されている場合は二重取得を避ける
        if (selectEl.dataset.genresLoaded === 'true') {
            return;
        }

        fetch('/api/podcast-genres')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (!data || !Array.isArray(data.data)) {
                    console.warn('Podcast ジャンル一覧の取得に失敗しました。', data);
                    return;
                }

                // 既定の「すべてのジャンル」以外をクリアしてから追加
                const firstOption = selectEl.querySelector('option[value=""]');
                selectEl.innerHTML = '';
                if (firstOption) {
                    selectEl.appendChild(firstOption);
                } else {
                    const allOpt = document.createElement('option');
                    allOpt.value = '';
                    allOpt.textContent = 'すべてのジャンル';
                    selectEl.appendChild(allOpt);
                }

                data.data.forEach(function (genre) {
                    // Listen Notes の genres レスポンスは { id, name, parent_id } などを想定
                    if (!genre || genre.id == null) return;
                    const opt = document.createElement('option');
                    opt.value = String(genre.id);
                    opt.textContent = genre.name || ('ID ' + genre.id);
                    selectEl.appendChild(opt);
                });

                selectEl.dataset.genresLoaded = 'true';

                // 前回選択値を復元（存在すれば）しつつ、初回ロードをトリガー
                if (typeof getTrendPreference === 'function') {
                    var saved = getTrendPreference('podcastGenre');
                    if (saved != null) {
                        var value = typeof saved === 'object' ? (saved.value != null ? saved.value : null) : String(saved);
                        if (value) {
                            const exists = Array.from(selectEl.options).some(function (o) { return o.value === value; });
                            if (exists) {
                                selectEl.value = value;
                            }
                        }
                    }
                }

                // マネージャーから初回取得を実行
                if (window.podcastGenreManager && typeof window.podcastGenreManager.fetchTrends === 'function') {
                    window.podcastGenreManager.fetchTrends();
                }
            })
            .catch(function (err) {
                console.error('Podcast ジャンル一覧取得エラー:', err);
            });
    }

    function initPodcastGenreManager() {
        // Podcast 用ドロップダウンマネージャーを作成
        window.podcastGenreManager = createDropdownTrendsManager({
            serviceName: 'podcast',
            selectId: 'podcastGenreSelect',
            apiEndpoint: '/api/podcast-trends',
            defaultValue: '',
            paramName: 'genre_id',
            storageKey: 'podcastGenre',
            uiIds: {
                loading: 'podcastLoading',
                results: 'podcastResults',
                tableBody: 'podcastTrendsTableBody',
                statusMessage: 'podcastStatusMessage',
                errorMessage: 'podcastErrorMessage'
            },
            displayFunction: function (data) {
                // 既存の Podcast 表示ロジックに合わせて表示
                if (typeof displayPodcastResults === 'function') {
                    displayPodcastResults(data);
                } else if (typeof window.displayPodcastTrendsFromCache === 'function') {
                    // フォールバック: キャッシュ表示関数があれば利用
                    window.displayPodcastTrendsFromCache(data);
                } else {
                    console.warn('displayPodcastResults 関数が見つからないため、Podcast データを表示できません。');
                }
            },
            getParams: function () {
                // 日本版を対象にする（region=jp）。genre_id は paramName で付与される。
                return {
                    trend_type: 'best_podcasts',
                    region: 'jp',
                    force_refresh: 'false'
                };
            },
            allPaneSync: {
                mainTableBodyId: 'podcastTrendsTableBody',
                allTableBodyId: 'all-podcastTrendsTableBody',
                limit: 5,
                targetTabId: 'tab-entertainment'
            }
        });

        populatePodcastGenres();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPodcastGenreManager);
    } else {
        initPodcastGenreManager();
    }
})();

