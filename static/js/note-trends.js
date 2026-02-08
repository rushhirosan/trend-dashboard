// Noteトレンド関連の関数（共通化）
let noteManager = null;

// ドロップダウンパターンの共通マネージャーを作成
if (typeof createDropdownTrendsManager === 'function') {
    noteManager = createDropdownTrendsManager({
        serviceName: 'note',
        selectId: 'noteCategorySelect',
        apiEndpoint: '/api/note-trends',
        defaultValue: 'all',
        paramName: 'category',
        storageKey: 'note',
        uiIds: {
            loading: 'noteLoading',
            results: 'noteResults',
            tableBody: 'noteTrendsTableBody',
            statusMessage: 'noteStatusMessage',
            errorMessage: 'noteErrorMessage'
        },
        displayFunction: displayNoteResults,
        allPaneSync: { mainTableBodyId: 'noteTrendsTableBody', allTableBodyId: 'all-noteTrendsTableBody', limit: 5 }
    });
}

// 後方互換性のため、既存の関数名も保持
function fetchNoteTrends() {
    if (noteManager) {
        noteManager.fetchTrends();
    }
}

function displayNoteResults(data) {
    const tableBody = document.getElementById('noteTrendsTableBody');
    if (!tableBody) {
        console.error('noteTrendsTableBodyが見つかりません');
        return;
    }

    tableBody.innerHTML = '';

    if (data.data && data.data.length > 0) {
        data.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.className = 'trend-card';

            // 公開日をフォーマット
            let publishedDate = 'N/A';
            if (item.published_date) {
                try {
                    const date = new Date(item.published_date);
                    publishedDate = date.toLocaleDateString('ja-JP', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit'
                    });
                } catch (e) {
                    publishedDate = item.published_date;
                }
            }

            const articleUrl = item.url || '#';
            const articleTitle = item.title || 'N/A';

            // はてな・Zennと同様にタイトルリンクのみ（余分な改行・ボタンなしで行高を揃える）
            row.innerHTML = `
                <td><span class="badge bg-secondary">${item.rank || index + 1}</span></td>
                <td><strong><a href="${articleUrl}" target="_blank">${articleTitle}</a></strong></td>
                <td>${publishedDate}</td>
            `;
            // 行全体をクリック可能にする（アクセシビリティ対応）
            makeTableRowClickable(row, articleUrl, `${articleTitle}の記事を開く`);
            tableBody.appendChild(row);
        });

        showNoteResults();
    } else {
        showNoteError('データが見つかりませんでした');
    }
}

// 後方互換性のため、既存の関数名も保持（共通マネージャーを使用）
function showNoteLoading() {
    if (noteManager) {
        noteManager.showLoading();
    } else {
        const element = document.getElementById('noteLoading');
        if (element) element.style.display = 'block';
    }
}

function hideNoteLoading() {
    if (noteManager) {
        noteManager.hideLoading();
    } else {
        const element = document.getElementById('noteLoading');
        if (element) element.style.display = 'none';
    }
}

function showNoteResults() {
    if (noteManager) {
        noteManager.showResults();
    } else {
        const element = document.getElementById('noteResults');
        if (element) element.style.display = 'block';
    }
}

function hideNoteResults() {
    if (noteManager) {
        noteManager.hideResults();
    } else {
        const element = document.getElementById('noteResults');
        if (element) element.style.display = 'none';
    }
}

function showNoteStatusMessage(message, type = 'info') {
    const statusElement = document.getElementById('noteStatusMessage');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.className = `alert alert-${type}`;
        statusElement.style.display = 'block';
    }
}

function showNoteError(message) {
    if (noteManager) {
        noteManager.showError(message);
    } else {
        showNoteStatusMessage(message, 'danger');
        showNoteResults();
    }
}

