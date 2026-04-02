/**
 * All / ジャンルタブ: カード並び・非表示を localStorage に保存
 * Keys: trend_pref_view_jp | trend_pref_view_us
 */
(function () {
    'use strict';

    var STORAGE_SUFFIX = 'view_';
    var DRAG_THRESHOLD_PX = 10;

    var GENRE_PANE_IDS_JP = ['pane-news', 'pane-search', 'pane-tech', 'pane-market', 'pane-entertainment', 'pane-admin'];
    var GENRE_PANE_IDS_US = ['pane-news', 'pane-search', 'pane-tech', 'pane-market', 'pane-entertainment', 'pane-govdata'];

    var I18N = {
        jp: {
            editLayout: 'レイアウトを編集',
            doneEdit: '編集を終了',
            dragHandle: 'ドラッグして並べ替え',
            hideCard: '非表示（一覧・タブ共通）',
            moveLeft: '左へ（同じ段）',
            moveRight: '右へ（同じ段）',
            moveRowUp: '上の段へ',
            moveRowDown: '下の段へ',
            rowMajorHint: '並びは左から右へ、上の段から順です。四方向ボタンは画面の列に合わせて動きます。',
            hiddenHeading: '非表示のソース',
            restore: '表示',
            resetLayout: '保存したレイアウトを消去',
            resetConfirm: '保存した並びと非表示設定を消去して再読み込みします。よろしいですか？'
        },
        us: {
            editLayout: 'Edit layout',
            doneEdit: 'Done',
            dragHandle: 'Drag to reorder',
            hideCard: 'Hide (All tabs)',
            moveLeft: 'Move left',
            moveRight: 'Move right',
            moveRowUp: 'Move up a row',
            moveRowDown: 'Move down a row',
            rowMajorHint: 'Order is left to right, top row first. Arrows follow the current column count for this screen size.',
            hiddenHeading: 'Hidden sources',
            restore: 'Show',
            resetLayout: 'Clear saved layout',
            resetConfirm: 'Clear saved order and hidden cards, then reload?'
        }
    };

    function t(region, key) {
        var pack = I18N[region] || I18N.us;
        return pack[key] || key;
    }

    function getGenrePaneIds(region) {
        return region === 'jp' ? GENRE_PANE_IDS_JP : GENRE_PANE_IDS_US;
    }

    /** US エンタメ等: テンプレに置いたマウント（常に DOM に存在）へツールバーを入れる */
    function getGenreToolbarMount(pane, paneId) {
        if (!pane || !paneId) return null;
        try {
            return pane.querySelector(':scope > [data-genre-toolbar-mount="' + paneId + '"]');
        } catch (e) {
            for (var i = 0; i < pane.children.length; i++) {
                var ch = pane.children[i];
                if (ch.getAttribute && ch.getAttribute('data-genre-toolbar-mount') === paneId) return ch;
            }
            return null;
        }
    }

    function loadPrefs(region) {
        if (typeof getTrendPreference !== 'function') return null;
        var raw = getTrendPreference(STORAGE_SUFFIX + region);
        if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
        return raw;
    }

    function savePrefs(region, obj) {
        if (typeof setTrendPreference !== 'function') return;
        setTrendPreference(STORAGE_SUFFIX + region, obj);
    }

    function normalizePrefs(raw) {
        var p = raw && typeof raw === 'object' ? raw : {};
        if (!p.genrePaneOrder || typeof p.genrePaneOrder !== 'object') p.genrePaneOrder = {};
        p.version = 2;
        if (!p.allCardOrder) p.allCardOrder = [];
        if (!p.hiddenAllCardSlugs) p.hiddenAllCardSlugs = [];
        return p;
    }

    function mergeOrder(domSlugs, savedOrder) {
        var result = [];
        var seen = {};
        (savedOrder || []).forEach(function (s) {
            if (domSlugs.indexOf(s) !== -1 && !seen[s]) {
                result.push(s);
                seen[s] = true;
            }
        });
        domSlugs.forEach(function (s) {
            if (!seen[s]) {
                result.push(s);
                seen[s] = true;
            }
        });
        return result;
    }

    /** source-nhk → nhk, source-prtimes-hatena → prtimes_hatena */
    function sourceIdToSlug(id) {
        if (!id || id.indexOf('source-') !== 0) return '';
        return id.slice(7).replace(/-/g, '_');
    }

    function slugToSourceId(slug) {
        return 'source-' + String(slug).replace(/_/g, '-');
    }

    function getCardColumns(container) {
        var out = [];
        for (var i = 0; i < container.children.length; i++) {
            var ch = container.children[i];
            if (ch.getAttribute && ch.getAttribute('data-all-card')) out.push(ch);
        }
        return out;
    }

    function getVisibleCardColumns(container) {
        return getCardColumns(container).filter(function (col) {
            return !col.classList.contains('all-card-col-user-hidden');
        });
    }

    /**
     * ジャンルタブの「ソース1枚＝カラム」要素（並べ替え・非表示の対象）。
     * ペイン内の article/div#source-* を常に列挙する（.row 直下のみだと col ラッパー配下のカードを取りこぼし、
     * ツールバー初期化がスキップされることがある）。id で重複除去。
     */
    function getGenreArticlesInPane(pane) {
        if (!pane) return [];
        var seen = {};
        var out = [];
        var nodes = pane.querySelectorAll('article[id^="source-"], div[id^="source-"]');
        Array.prototype.forEach.call(nodes, function (el) {
            if (!el.id || seen[el.id]) return;
            // 行政タブ: e-Stat 指標カードは #estat-full-body 内のグリッド。政府調達は #admin-kkj-body 内の2カラム。
            // いずれも「ジャンル用カード」として外の .row へ移すと元のコンテナが空になり白抜けになる。
            if (el.closest && el.closest('#estat-full-body')) return;
            if (el.closest && el.closest('#admin-kkj-body')) return;
            seen[el.id] = true;
            out.push(el);
        });
        return out;
    }

    /** ペイン直下の空 .row だけ削除（カード内のネストした .row を誤って消さない） */
    function removeEmptyDirectChildRowsExcept(pane, keepRow) {
        if (!pane) return;
        var remove = [];
        for (var i = 0; i < pane.children.length; i++) {
            var ch = pane.children[i];
            if (!ch.classList || !ch.classList.contains('row')) continue;
            if (ch === keepRow) continue;
            // 行政タブ: API 完了前に空のまま refresh されると、ここで #estat-full-body が消え
            // その後 admin-trends が getElementById で取れず e-Stat カードが永遠に出ない。
            if (ch.id === 'estat-full-body') continue;
            if (!ch.querySelector('article[id^="source-"], div[id^="source-"]') && ch.children.length === 0) {
                remove.push(ch);
            }
        }
        remove.forEach(function (r) {
            try {
                r.remove();
            } catch (e) {}
        });
    }

    function getVisibleGenreArticles(container) {
        return getGenreArticlesInPane(container).filter(function (art) {
            return !art.classList.contains('all-card-col-user-hidden');
        });
    }

    /** All タブ: col-lg-4 前提 */
    function getColumnsPerRow() {
        if (typeof window.matchMedia === 'function') {
            if (window.matchMedia('(min-width: 992px)').matches) return 3;
            if (window.matchMedia('(min-width: 768px)').matches) return 2;
        }
        return 1;
    }

    /** ジャンルタブ: col のクラスに合わせる */
    function getColumnsPerRowForArticle(el) {
        if (!el) return getColumnsPerRow();
        if (el.classList.contains('col-lg-4')) {
            if (window.matchMedia('(min-width: 992px)').matches) return 3;
            if (window.matchMedia('(min-width: 768px)').matches) return 2;
            return 1;
        }
        if (el.classList.contains('col-md-4') && !el.classList.contains('col-lg-4')) {
            if (window.matchMedia('(min-width: 768px)').matches) return 3;
            return 1;
        }
        if (window.matchMedia('(min-width: 768px)').matches) return 2;
        return 1;
    }

    function indexOfSlugAll(visible, slug) {
        for (var i = 0; i < visible.length; i++) {
            if (visible[i].getAttribute('data-all-card') === slug) return i;
        }
        return -1;
    }

    function indexOfSlugGenre(visible, slug) {
        for (var i = 0; i < visible.length; i++) {
            if (sourceIdToSlug(visible[i].id) === slug) return i;
        }
        return -1;
    }

    function swapElements(a, b) {
        if (a === b) return;
        var p = a.parentNode;
        if (!p || p !== b.parentNode) return;
        var t = document.createTextNode('');
        p.insertBefore(t, a);
        p.insertBefore(a, b);
        p.insertBefore(b, t);
        p.removeChild(t);
    }

    function applyPrefsAll(container, prefs) {
        if (!prefs || typeof prefs !== 'object') return;
        var cols = getCardColumns(container);
        var domSlugs = cols.map(function (c) {
            return c.getAttribute('data-all-card');
        });
        var map = {};
        cols.forEach(function (c) {
            map[c.getAttribute('data-all-card')] = c;
        });
        var order = mergeOrder(domSlugs, prefs.allCardOrder || []);
        order.forEach(function (slug) {
            var el = map[slug];
            if (el) container.appendChild(el);
        });
    }

    /** ジャンルタブ内の article を1つの .row に集約 */
    function consolidateGenrePane(pane) {
        var articles = getGenreArticlesInPane(pane);
        if (articles.length === 0) return null;
        var row = articles[0].closest('.row');
        if (!row) {
            row = document.createElement('div');
            row.className = 'row g-3 mb-3';
            var pid = pane.id || '';
            var mount = pid ? getGenreToolbarMount(pane, pid) : null;
            if (mount) {
                if (mount.nextSibling) {
                    pane.insertBefore(row, mount.nextSibling);
                } else {
                    pane.appendChild(row);
                }
            } else if (pane.id === 'pane-admin') {
                // 景気・行政（e-Stat）ブロックの直下に政府調達を置く（説明文直後だと順序が逆になる）
                var estatBody = pane.querySelector('#estat-full-body');
                if (estatBody) {
                    if (estatBody.nextSibling) {
                        pane.insertBefore(row, estatBody.nextSibling);
                    } else {
                        pane.appendChild(row);
                    }
                } else {
                    var introAd = pane.querySelector('p.text-muted.small.mb-3');
                    if (introAd && introAd.nextSibling) pane.insertBefore(row, introAd.nextSibling);
                    else pane.insertBefore(row, pane.firstChild);
                }
            } else {
                var tb = pane.querySelector('.all-layout-toolbar');
                if (tb && tb.nextSibling) {
                    pane.insertBefore(row, tb.nextSibling);
                } else {
                    var intro = pane.querySelector('p.text-muted.small.mb-3');
                    if (intro && intro.nextSibling) pane.insertBefore(row, intro.nextSibling);
                    else pane.insertBefore(row, pane.firstChild);
                }
            }
        }
        articles.forEach(function (a) {
            row.appendChild(a);
        });
        // 行政タブ: 既存 .row の位置が古い場合も、e-Stat の直下に揃える
        if (pane.id === 'pane-admin' && row && row.parentNode === pane) {
            var estatAnchor = pane.querySelector('#estat-full-body');
            if (estatAnchor && estatAnchor !== row) {
                var afterEstat = estatAnchor.nextSibling;
                if (afterEstat !== row) {
                    if (afterEstat) {
                        pane.insertBefore(row, afterEstat);
                    } else {
                        pane.appendChild(row);
                    }
                }
            }
        }
        removeEmptyDirectChildRowsExcept(pane, row);
        return row;
    }

    function applyGenrePaneOrder(pane, paneId, prefs) {
        var row = consolidateGenrePane(pane);
        if (!row) return;
        var articles = getGenreArticlesInPane(pane);
        var domSlugs = articles.map(function (a) {
            return sourceIdToSlug(a.id);
        });
        var map = {};
        articles.forEach(function (a) {
            map[sourceIdToSlug(a.id)] = a;
        });
        var order = mergeOrder(domSlugs, (prefs.genrePaneOrder || {})[paneId] || []);
        order.forEach(function (slug) {
            var el = map[slug];
            if (el) row.appendChild(el);
        });
    }

    /** hiddenAllCardSlugs を All の col と各タブの article の両方に反映 */
    function applyGlobalHidden(prefs) {
        var hidden = {};
        (prefs.hiddenAllCardSlugs || []).forEach(function (s) {
            hidden[s] = true;
        });
        document.querySelectorAll('[data-all-card]').forEach(function (el) {
            var s = el.getAttribute('data-all-card');
            if (hidden[s]) el.classList.add('all-card-col-user-hidden');
            else el.classList.remove('all-card-col-user-hidden');
        });
        document.querySelectorAll('#trendCategoryTabContent .tab-pane:not(#pane-all) [id^="source-"]').forEach(function (el) {
            var s = sourceIdToSlug(el.id);
            if (hidden[s]) el.classList.add('all-card-col-user-hidden');
            else el.classList.remove('all-card-col-user-hidden');
        });
    }

    function collectHiddenSlugsFromDom() {
        var set = {};
        document.querySelectorAll('[data-all-card].all-card-col-user-hidden').forEach(function (el) {
            set[el.getAttribute('data-all-card')] = true;
        });
        document.querySelectorAll('#trendCategoryTabContent .tab-pane:not(#pane-all) [id^="source-"].all-card-col-user-hidden').forEach(function (el) {
            set[sourceIdToSlug(el.id)] = true;
        });
        return Object.keys(set);
    }

    function gatherFullState(region) {
        var p = normalizePrefs(loadPrefs(region));
        var allC = document.getElementById('all-trends-container');
        if (allC) {
            var cols = getCardColumns(allC);
            p.allCardOrder = cols.map(function (c) {
                return c.getAttribute('data-all-card');
            });
        }
        p.hiddenAllCardSlugs = collectHiddenSlugsFromDom();
        getGenrePaneIds(region).forEach(function (pid) {
            var pane = document.getElementById(pid);
            if (!pane) return;
            var row = consolidateGenrePane(pane);
            if (!row) return;
            var arts = getGenreArticlesInPane(pane);
            p.genrePaneOrder[pid] = arts.map(function (a) {
                return sourceIdToSlug(a.id);
            });
        });
        p.version = 2;
        return p;
    }

    function moveInGridAll(container, slug, direction) {
        var visible = getVisibleCardColumns(container);
        var ix = indexOfSlugAll(visible, slug);
        if (ix < 0) return;
        var cpr = getColumnsPerRow();
        var a = visible[ix];
        var b = null;
        if (direction === 'left') {
            if (ix <= 0) return;
            b = visible[ix - 1];
        } else if (direction === 'right') {
            if (ix >= visible.length - 1) return;
            b = visible[ix + 1];
        } else if (direction === 'up') {
            var ti = ix - cpr;
            if (ti < 0) return;
            b = visible[ti];
        } else if (direction === 'down') {
            var ti = ix + cpr;
            if (ti >= visible.length) return;
            b = visible[ti];
        } else {
            return;
        }
        swapElements(a, b);
    }

    function moveInGridGenre(container, slug, direction) {
        var visible = getVisibleGenreArticles(container);
        var ix = indexOfSlugGenre(visible, slug);
        if (ix < 0) return;
        var cpr = getColumnsPerRowForArticle(visible[0]);
        var a = visible[ix];
        var b = null;
        if (direction === 'left') {
            if (ix <= 0) return;
            b = visible[ix - 1];
        } else if (direction === 'right') {
            if (ix >= visible.length - 1) return;
            b = visible[ix + 1];
        } else if (direction === 'up') {
            var ti = ix - cpr;
            if (ti < 0) return;
            b = visible[ti];
        } else if (direction === 'down') {
            var ti = ix + cpr;
            if (ti >= visible.length) return;
            b = visible[ti];
        } else {
            return;
        }
        swapElements(a, b);
    }

    function updateHiddenStripFromSlugs(region, stripEl, hiddenSlugs) {
        if (!stripEl) return;
        stripEl.innerHTML = '';
        if (!hiddenSlugs || hiddenSlugs.length === 0) {
            stripEl.classList.add('d-none');
            return;
        }
        stripEl.classList.remove('d-none');
        var label = document.createElement('span');
        label.className = 'small text-muted me-2';
        label.textContent = t(region, 'hiddenHeading') + ':';
        stripEl.appendChild(label);
        hiddenSlugs.forEach(function (slug) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-sm btn-outline-secondary me-1 mb-1';
            btn.setAttribute('data-restore-slug', slug);
            btn.textContent = t(region, 'restore') + ' · ' + slug;
            stripEl.appendChild(btn);
        });
    }

    function syncAllHiddenStrips(region) {
        var state = gatherFullState(region);
        var hidden = state.hiddenAllCardSlugs || [];
        document.querySelectorAll('.all-layout-hidden-strip').forEach(function (strip) {
            updateHiddenStripFromSlugs(region, strip, hidden);
        });
    }

    function persistGlobal(region) {
        var state = gatherFullState(region);
        savePrefs(region, state);
        syncAllHiddenStrips(region);
    }

    function restoreSlugEverywhere(slug) {
        var esc = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(slug) : slug.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        var col = document.querySelector('[data-all-card="' + esc + '"]');
        if (col) col.classList.remove('all-card-col-user-hidden');
        var sid = slugToSourceId(slug);
        var art = document.getElementById(sid);
        if (art) art.classList.remove('all-card-col-user-hidden');
    }

    function initAllTabLayoutPreferences(region) {
        var paneAll = document.getElementById('pane-all');
        var container = document.getElementById('all-trends-container');
        if (!paneAll || !container) return;

        var editMode = false;

        var toolbar = document.createElement('div');
        toolbar.className = 'all-layout-toolbar d-flex flex-wrap align-items-center gap-2 mb-2';
        toolbar.setAttribute('role', 'region');
        toolbar.setAttribute('aria-label', t(region, 'editLayout'));

        var editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'btn btn-sm btn-outline-secondary';
        editBtn.setAttribute('aria-pressed', 'false');
        editBtn.textContent = t(region, 'editLayout');

        var resetBtn = document.createElement('button');
        resetBtn.type = 'button';
        resetBtn.className = 'btn btn-sm btn-outline-danger';
        resetBtn.textContent = t(region, 'resetLayout');

        var hint = document.createElement('p');
        hint.className = 'small text-muted mb-0 w-100 all-layout-edit-hint d-none';
        hint.textContent = t(region, 'rowMajorHint');

        var hiddenStrip = document.createElement('div');
        hiddenStrip.className = 'all-layout-hidden-strip border rounded px-2 py-1 bg-light d-none flex-wrap align-items-center';

        toolbar.appendChild(editBtn);
        toolbar.appendChild(resetBtn);
        toolbar.appendChild(hint);
        toolbar.appendChild(hiddenStrip);

        var intro = paneAll.querySelector('p.text-muted.small.mb-3');
        if (intro && intro.nextSibling) {
            paneAll.insertBefore(toolbar, intro.nextSibling);
        } else {
            paneAll.insertBefore(toolbar, container);
        }

        syncAllHiddenStrips(region);

        function setEditMode(on) {
            editMode = on;
            paneAll.classList.toggle('all-layout-edit-mode', on);
            editBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
            editBtn.textContent = on ? t(region, 'doneEdit') : t(region, 'editLayout');
            hint.classList.toggle('d-none', !on);
        }

        function makeMoveBtn(ariaKey, symbol, dir, cardSlug) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-sm btn-outline-secondary all-card-move-btn py-0 px-1';
            btn.setAttribute('aria-label', t(region, ariaKey));
            btn.title = t(region, ariaKey);
            btn.innerHTML = symbol;
            btn.addEventListener('click', function () {
                moveInGridAll(container, cardSlug, dir);
                persistGlobal(region);
            });
            return btn;
        }

        function attachPointerDragAll(handle, col) {
            var state = null;

            function findDropTarget(clientX, clientY) {
                var el = document.elementFromPoint(clientX, clientY);
                var drop = el && el.closest && el.closest('[data-all-card]');
                if (!drop || !container.contains(drop)) return null;
                if (drop.classList.contains('all-card-col-user-hidden')) return null;
                if (drop === col) return null;
                return drop;
            }

            function onPointerUp(e) {
                if (!state || state.pointerId !== e.pointerId) return;
                window.removeEventListener('pointermove', onPointerMove);
                window.removeEventListener('pointerup', onPointerUp);
                window.removeEventListener('pointercancel', onPointerUp);
                try {
                    handle.releasePointerCapture(e.pointerId);
                } catch (err) {}
                col.classList.remove('all-card-dragging');
                if (state.moved && editMode) {
                    var drop = findDropTarget(e.clientX, e.clientY);
                    if (drop) {
                        try {
                            container.insertBefore(col, drop);
                            persistGlobal(region);
                        } catch (err) {}
                    }
                }
                state = null;
            }

            function onPointerMove(e) {
                if (!state || state.pointerId !== e.pointerId) return;
                var dx = e.clientX - state.x;
                var dy = e.clientY - state.y;
                if (dx * dx + dy * dy > DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) {
                    state.moved = true;
                    col.classList.add('all-card-dragging');
                }
            }

            handle.addEventListener('pointerdown', function (e) {
                if (!editMode || e.button !== 0) return;
                e.preventDefault();
                state = { pointerId: e.pointerId, x: e.clientX, y: e.clientY, moved: false };
                try {
                    handle.setPointerCapture(e.pointerId);
                } catch (err) {}
                window.addEventListener('pointermove', onPointerMove);
                window.addEventListener('pointerup', onPointerUp);
                window.addEventListener('pointercancel', onPointerUp);
            });
        }

        function ensureControls(col) {
            if (col.querySelector('.all-card-layout-controls')) return;
            col.classList.add('position-relative');
            var bar = document.createElement('div');
            bar.className = 'all-card-layout-controls align-items-center gap-1 flex-wrap';
            bar.setAttribute('role', 'group');

            var handle = document.createElement('span');
            handle.className = 'all-card-drag-handle badge bg-secondary';
            handle.setAttribute('aria-label', t(region, 'dragHandle'));
            handle.innerHTML = '<i class="fas fa-grip-vertical" aria-hidden="true"></i>';

            var hideBtn = document.createElement('button');
            hideBtn.type = 'button';
            hideBtn.className = 'btn btn-sm btn-outline-danger all-card-hide-btn py-0 px-1';
            hideBtn.textContent = t(region, 'hideCard');

            var slug = col.getAttribute('data-all-card');

            bar.appendChild(handle);
            bar.appendChild(hideBtn);
            bar.appendChild(makeMoveBtn('moveLeft', '&larr;', 'left', slug));
            bar.appendChild(makeMoveBtn('moveRight', '&rarr;', 'right', slug));
            bar.appendChild(makeMoveBtn('moveRowUp', '&uarr;', 'up', slug));
            bar.appendChild(makeMoveBtn('moveRowDown', '&darr;', 'down', slug));

            col.insertBefore(bar, col.firstChild);

            attachPointerDragAll(handle, col);

            hideBtn.addEventListener('click', function () {
                col.classList.add('all-card-col-user-hidden');
                var sid = slugToSourceId(slug);
                var art = document.getElementById(sid);
                if (art) art.classList.add('all-card-col-user-hidden');
                persistGlobal(region);
            });
        }

        getCardColumns(container).forEach(ensureControls);

        editBtn.addEventListener('click', function () {
            setEditMode(!editMode);
        });

        resetBtn.addEventListener('click', function () {
            if (!window.confirm(t(region, 'resetConfirm'))) return;
            try {
                localStorage.removeItem('trend_pref_view_' + region);
            } catch (e) {}
            window.location.reload();
        });

        hiddenStrip.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-restore-slug]');
            if (!btn) return;
            var s = btn.getAttribute('data-restore-slug');
            restoreSlugEverywhere(s);
            persistGlobal(region);
        });
    }

    /** ジャンルタブのレイアウトUIを外す（動的コンテンツ後の再初期化用） */
    function teardownGenrePaneLayout(pane) {
        if (!pane) return;
        var tb = pane.querySelector('.all-layout-toolbar');
        if (tb) tb.remove();
        pane.querySelectorAll('.all-card-layout-controls').forEach(function (n) {
            n.remove();
        });
        pane.classList.remove('genre-layout-edit-mode');
    }

    /**
     * 行政・Gov など DOM が後から入るタブ用。保存済みの並び・非表示を当て直してからツールバーとカード操作を付け直す。
     */
    function refreshTrendViewGenrePane(paneId) {
        var body = document.body;
        if (!body) return;
        var bid = body.id;
        if (bid !== 'trends-jp' && bid !== 'trends-us') return;
        var region = bid === 'trends-jp' ? 'jp' : 'us';
        if (getGenrePaneIds(region).indexOf(paneId) === -1) return;
        var pane = document.getElementById(paneId);
        if (!pane) return;
        var prefs = normalizePrefs(loadPrefs(region));
        teardownGenrePaneLayout(pane);
        applyGenrePaneOrder(pane, paneId, prefs);
        applyGlobalHidden(prefs);
        initGenrePaneLayoutPreferences(region, paneId);
        syncAllHiddenStrips(region);
    }

    function initGenrePaneLayoutPreferences(region, paneId) {
        var pane = document.getElementById(paneId);
        if (!pane) return;
        // 複数 .row やマークアップ差のあとでも 1 段に寄せてから数える（早期 return 誤爆を防ぐ）
        consolidateGenrePane(pane);
        var mount = getGenreToolbarMount(pane, paneId);
        var articleCount = getGenreArticlesInPane(pane).length;
        if (articleCount === 0 && !mount) return;

        var editMode = false;
        var rowRef = consolidateGenrePane(pane);

        var toolbar = document.createElement('div');
        toolbar.className = 'all-layout-toolbar d-flex flex-wrap align-items-center gap-2 mb-2';
        toolbar.setAttribute('role', 'region');
        toolbar.setAttribute('aria-label', t(region, 'editLayout') + ' (' + paneId + ')');

        var editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'btn btn-sm btn-outline-secondary';
        editBtn.setAttribute('aria-pressed', 'false');
        editBtn.textContent = t(region, 'editLayout');

        var resetBtn = document.createElement('button');
        resetBtn.type = 'button';
        resetBtn.className = 'btn btn-sm btn-outline-danger';
        resetBtn.textContent = t(region, 'resetLayout');

        var hint = document.createElement('p');
        hint.className = 'small text-muted mb-0 w-100 all-layout-edit-hint d-none';
        hint.textContent = t(region, 'rowMajorHint');

        var hiddenStrip = document.createElement('div');
        hiddenStrip.className = 'all-layout-hidden-strip border rounded px-2 py-1 bg-light d-none flex-wrap align-items-center';

        toolbar.appendChild(editBtn);
        toolbar.appendChild(resetBtn);
        toolbar.appendChild(hint);
        toolbar.appendChild(hiddenStrip);

        if (mount) {
            mount.innerHTML = '';
            mount.appendChild(toolbar);
        } else {
            var intro = pane.querySelector('p.text-muted.small.mb-3');
            if (intro && intro.nextSibling) {
                pane.insertBefore(toolbar, intro.nextSibling);
            } else {
                pane.insertBefore(toolbar, pane.firstChild);
            }
        }

        syncAllHiddenStrips(region);

        function getRow() {
            rowRef = consolidateGenrePane(pane) || rowRef;
            return rowRef;
        }

        function setEditMode(on) {
            editMode = on;
            pane.classList.toggle('genre-layout-edit-mode', on);
            editBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
            editBtn.textContent = on ? t(region, 'doneEdit') : t(region, 'editLayout');
            hint.classList.toggle('d-none', !on);
        }

        function makeMoveBtn(ariaKey, symbol, dir, cardSlug) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-sm btn-outline-secondary all-card-move-btn py-0 px-1';
            btn.setAttribute('aria-label', t(region, ariaKey));
            btn.title = t(region, ariaKey);
            btn.innerHTML = symbol;
            btn.addEventListener('click', function () {
                moveInGridGenre(pane, cardSlug, dir);
                persistGlobal(region);
            });
            return btn;
        }

        function attachPointerDragGenre(handle, artEl) {
            var state = null;

            function findDropTarget(clientX, clientY) {
                var el = document.elementFromPoint(clientX, clientY);
                var drop = el && el.closest && el.closest('[id^="source-"]');
                if (!drop || !pane.contains(drop)) return null;
                if (drop.classList.contains('all-card-col-user-hidden')) return null;
                if (drop === artEl) return null;
                return drop;
            }

            function onPointerUp(e) {
                if (!state || state.pointerId !== e.pointerId) return;
                window.removeEventListener('pointermove', onPointerMove);
                window.removeEventListener('pointerup', onPointerUp);
                window.removeEventListener('pointercancel', onPointerUp);
                try {
                    handle.releasePointerCapture(e.pointerId);
                } catch (err) {}
                artEl.classList.remove('all-card-dragging');
                if (state.moved && editMode) {
                    var drop = findDropTarget(e.clientX, e.clientY);
                    if (drop) {
                        try {
                            getRow().insertBefore(artEl, drop);
                            persistGlobal(region);
                        } catch (err) {}
                    }
                }
                state = null;
            }

            function onPointerMove(e) {
                if (!state || state.pointerId !== e.pointerId) return;
                var dx = e.clientX - state.x;
                var dy = e.clientY - state.y;
                if (dx * dx + dy * dy > DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) {
                    state.moved = true;
                    artEl.classList.add('all-card-dragging');
                }
            }

            handle.addEventListener('pointerdown', function (e) {
                if (!editMode || e.button !== 0) return;
                e.preventDefault();
                state = { pointerId: e.pointerId, x: e.clientX, y: e.clientY, moved: false };
                try {
                    handle.setPointerCapture(e.pointerId);
                } catch (err) {}
                window.addEventListener('pointermove', onPointerMove);
                window.addEventListener('pointerup', onPointerUp);
                window.addEventListener('pointercancel', onPointerUp);
            });
        }

        function ensureControlsArticle(art) {
            if (art.querySelector('.all-card-layout-controls')) return;
            art.classList.add('position-relative');
            var bar = document.createElement('div');
            bar.className = 'all-card-layout-controls align-items-center gap-1 flex-wrap';
            bar.setAttribute('role', 'group');

            var handle = document.createElement('span');
            handle.className = 'all-card-drag-handle badge bg-secondary';
            handle.setAttribute('aria-label', t(region, 'dragHandle'));
            handle.innerHTML = '<i class="fas fa-grip-vertical" aria-hidden="true"></i>';

            var hideBtn = document.createElement('button');
            hideBtn.type = 'button';
            hideBtn.className = 'btn btn-sm btn-outline-danger all-card-hide-btn py-0 px-1';
            hideBtn.textContent = t(region, 'hideCard');

            var slug = sourceIdToSlug(art.id);

            bar.appendChild(handle);
            bar.appendChild(hideBtn);
            bar.appendChild(makeMoveBtn('moveLeft', '&larr;', 'left', slug));
            bar.appendChild(makeMoveBtn('moveRight', '&rarr;', 'right', slug));
            bar.appendChild(makeMoveBtn('moveRowUp', '&uarr;', 'up', slug));
            bar.appendChild(makeMoveBtn('moveRowDown', '&darr;', 'down', slug));

            art.insertBefore(bar, art.firstChild);

            attachPointerDragGenre(handle, art);

            hideBtn.addEventListener('click', function () {
                art.classList.add('all-card-col-user-hidden');
                var esc = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(slug) : slug.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
                var allCol = document.querySelector('[data-all-card="' + esc + '"]');
                if (allCol) allCol.classList.add('all-card-col-user-hidden');
                persistGlobal(region);
            });
        }

        getGenreArticlesInPane(pane).forEach(ensureControlsArticle);

        if (articleCount === 0) {
            editBtn.disabled = true;
        }

        editBtn.addEventListener('click', function () {
            setEditMode(!editMode);
        });

        resetBtn.addEventListener('click', function () {
            if (!window.confirm(t(region, 'resetConfirm'))) return;
            try {
                localStorage.removeItem('trend_pref_view_' + region);
            } catch (e) {}
            window.location.reload();
        });

        hiddenStrip.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-restore-slug]');
            if (!btn) return;
            var s = btn.getAttribute('data-restore-slug');
            restoreSlugEverywhere(s);
            persistGlobal(region);
        });
    }

    function applyInitialLayout(region) {
        var prefs = normalizePrefs(loadPrefs(region));
        var allC = document.getElementById('all-trends-container');
        if (allC) {
            applyPrefsAll(allC, prefs);
        }
        getGenrePaneIds(region).forEach(function (pid) {
            var pane = document.getElementById(pid);
            if (!pane) return;
            applyGenrePaneOrder(pane, pid, prefs);
        });
        applyGlobalHidden(prefs);
    }

    function boot() {
        var body = document.body;
        if (!body) return;
        var id = body.id;
        if (id !== 'trends-jp' && id !== 'trends-us') return;
        var region = id === 'trends-jp' ? 'jp' : 'us';

        applyInitialLayout(region);

        initAllTabLayoutPreferences(region);
        getGenrePaneIds(region).forEach(function (pid) {
            initGenrePaneLayoutPreferences(region, pid);
        });
    }

    function scheduleBoot() {
        var run = function () {
            setTimeout(boot, 0);
        };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', run);
        } else {
            run();
        }
    }
    scheduleBoot();

    window.refreshTrendViewGenrePane = refreshTrendViewGenrePane;
})();
