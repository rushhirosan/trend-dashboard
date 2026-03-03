/**
 * 全部入りタブ: 各カードヘッダにデータ鮮度（更新時刻・件数）を表示
 * /api/cache/data-freshness から取得して .all-freshness 要素を更新
 */
(function() {
    'use strict';

    // data-source → APIのdisplay_nameマッピング（data_routes.pyのcache_key_mapに準拠）
    const SOURCE_TO_DISPLAY_NAME = {
        // 日本トレンド
        nhk: 'NHK ニュース',
        news: 'World News',
        wikipedia: 'Wikipedia 人気記事 (日本語)',
        google: 'Google Trends',
        youtube: 'YouTube',
        qiita: 'Qiita トレンド',
        hatena: 'はてなブックマーク',
        zenn: 'Zenn',
        note: 'Note (総合)',
        github: 'GitHub',
        ipa: 'IPA',
        jpcert: 'JPCERT/CC',
        crypto: '仮想通貨トレンド',
        stock: '株価トレンド',
        prtimes_hatena: 'PR TIMES × はてブ',
        appstore: 'App Store',
        music: 'Spotify',
        podcast: 'Podcast',
        movie: '映画トレンド',
        book: '本トレンド',
        rakuten: '楽天',
        twitch: 'Twitch',
        // USトレンド
        cnn: 'CNN News',
        worldnews: 'World News',
        hackernews: 'Hacker News',
        producthunt: 'Product Hunt',
        devto: 'DEV.to',
        medium: 'Medium',
        cisakev: 'CISA KEV',
        thehackernews: 'The Hacker News',
        globenewswire: 'GlobeNewswire',
        spotify: 'Spotify',
        ebay: 'eBay Popular/Trending'
    };

    function parseLastUpdated(raw) {
        if (!raw || raw === 'None' || raw === null) return null;
        try {
            let timeString = String(raw);
            if (timeString.includes('.')) {
                const parts = timeString.split('.');
                if (parts.length === 2 && parts[1].length >= 6) {
                    timeString = parts[0] + '.' + parts[1].substring(0, 3);
                }
            }
            const dateString = timeString.match(/[Z+-]\d{2}:?\d{2}$/) ? timeString : `${timeString}Z`;
            const date = new Date(dateString);
            return isNaN(date.getTime()) ? null : date;
        } catch (e) {
            return null;
        }
    }

    function formatTimeShort(date) {
        return date.toLocaleString('ja-JP', {
            month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit',
            timeZone: 'Asia/Tokyo'
        });
    }

    function formatTimeFull(date) {
        return date.toLocaleString('ja-JP', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            timeZone: 'Asia/Tokyo'
        });
    }

    function updateAllFreshness(country) {
        const container = document.getElementById('all-trends-container');
        if (!container) return;

        const countryParam = country ? `?country=${country}` : '';
        const isUs = country === 'US';
        fetch(`/api/cache/data-freshness${countryParam}`)
            .then(function(res) { return res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status)); })
            .then(function(data) {
                if (!data.success || !data.data) return;
                const freshnessData = data.data;

                const isUsPage = document.body && document.body.id === 'trends-us';
                container.querySelectorAll('.all-freshness[data-source]').forEach(function(span) {
                    const source = span.getAttribute('data-source');
                    let displayName = SOURCE_TO_DISPLAY_NAME[source];
                    if (source === 'wikipedia') {
                        displayName = isUs ? 'Wikipedia 人気記事 (英語)' : 'Wikipedia 人気記事 (日本語)';
                    } else if (!displayName) {
                        displayName = source;
                    }
                    const info = freshnessData[displayName];

                    if (!info) {
                        span.textContent = '—';
                        span.title = '';
                        return;
                    }

                    const date = parseLastUpdated(info.last_updated);

                    let timeStr = '—';
                    let fullStr = '';
                    if (date) {
                        timeStr = formatTimeShort(date);
                        fullStr = formatTimeFull(date);
                    }

                    const timeLabel = isUsPage ? 'Updated ' : '更新時刻 ';
                    span.textContent = timeLabel + timeStr;
                    span.title = fullStr ? fullStr + ' (JST)' : '';
                });
            })
            .catch(function(err) {
                console.warn('all-freshness: データ鮮度取得に失敗', err);
            });
    }

    function init() {
        const country = (document.body && document.body.id === 'trends-us') ? 'US' : 'JP';
        updateAllFreshness(country);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.updateAllFreshness = updateAllFreshness;
})();
