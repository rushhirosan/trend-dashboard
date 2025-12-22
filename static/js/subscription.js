// サブスクリプション機能のJavaScriptファイル

// サブスクリプション機能の初期化
function initSubscription() {
    console.log('📧 サブスクリプション機能を初期化中...');
    
    // フォーム送信イベントリスナー
    const emailForm = document.getElementById('emailSubscriptionForm');
    if (emailForm) {
        emailForm.addEventListener('submit', handleSubscriptionSubmit);
    }
    
    // 登録解除ボタンイベントリスナー
    const unsubscribeBtn = document.getElementById('unsubscribeBtn');
    if (unsubscribeBtn) {
        unsubscribeBtn.addEventListener('click', handleUnsubscribe);
    }
    
    // 既存のサブスクリプション状態をチェック
    checkSubscriptionStatus();
}

// サブスクリプション登録処理
function handleSubscriptionSubmit(e) {
    e.preventDefault();
    
    const email = document.getElementById('emailInput').value;
    const frequency = document.getElementById('frequencySelect').value;
    
    // 選択されたカテゴリを取得
    const categories = [];
    const checkboxes = document.querySelectorAll('.form-check-input:checked');
    checkboxes.forEach(checkbox => {
        categories.push(checkbox.value);
    });
    
    console.log('📧 サブスクリプション登録:', { email, frequency, categories });
    
    // APIに送信
    fetch('/subscription/api/subscribe', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            email: email,
            frequency: frequency,
            categories: categories
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSubscriptionMessage('登録が完了しました！', 'success');
            showSubscriptionStatus(email, frequency);
        } else {
            showSubscriptionMessage(data.error || '登録に失敗しました', 'danger');
        }
    })
    .catch(error => {
        console.error('サブスクリプション登録エラー:', error);
        showSubscriptionMessage('登録中にエラーが発生しました', 'danger');
    });
}

// 登録解除処理
function handleUnsubscribe() {
    if (confirm('本当に登録を解除しますか？')) {
        // メールアドレスを取得（registeredEmail要素から）
        const emailElement = document.getElementById('registeredEmail');
        const email = emailElement ? emailElement.textContent.trim() : null;
        
        if (!email) {
            showSubscriptionMessage('メールアドレスが見つかりません', 'danger');
            return;
        }
        
        console.log('📧 サブスクリプション解除:', { email });
        
        fetch('/subscription/api/unsubscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSubscriptionMessage('登録を解除しました', 'info');
                showSubscriptionForm();
                // フォームのメールアドレス入力欄もクリア
                const emailInput = document.getElementById('emailInput');
                if (emailInput) {
                    emailInput.value = '';
                }
            } else {
                showSubscriptionMessage(data.error || '解除に失敗しました', 'danger');
            }
        })
        .catch(error => {
            console.error('登録解除エラー:', error);
            showSubscriptionMessage('解除中にエラーが発生しました', 'danger');
        });
    }
}

// サブスクリプション状態をチェック
function checkSubscriptionStatus() {
    // タイムアウトを設定（5秒）
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('タイムアウト')), 5000);
    });
    
    Promise.race([
        fetch('/subscription/api/status'),
        timeoutPromise
    ])
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.subscribed) {
            showSubscriptionStatus(data.email, data.frequency);
        } else {
            showSubscriptionForm();
        }
    })
    .catch(error => {
        console.error('サブスクリプション状態チェックエラー:', error);
        // エラーが発生してもフォームを表示してページを使えるようにする
        showSubscriptionForm();
    });
}

// サブスクリプションフォームを表示
function showSubscriptionForm() {
    document.getElementById('subscriptionForm').style.display = 'block';
    document.getElementById('subscriptionStatus').style.display = 'none';
}

// サブスクリプション状態を表示
function showSubscriptionStatus(email, frequency) {
    document.getElementById('registeredEmail').textContent = email;
    document.getElementById('registeredFrequency').textContent = getFrequencyText(frequency);
    document.getElementById('subscriptionForm').style.display = 'none';
    document.getElementById('subscriptionStatus').style.display = 'block';
}

// 配信頻度のテキストを取得
function getFrequencyText(frequency) {
    const frequencyMap = {
        'daily': '毎日',
        'weekly': '毎週',
        'monthly': '毎月'
    };
    return frequencyMap[frequency] || frequency;
}

// メッセージを表示
function showSubscriptionMessage(message, type) {
    const messageDiv = document.getElementById('subscriptionMessage');
    messageDiv.textContent = message;
    messageDiv.className = `alert alert-${type}`;
    messageDiv.style.display = 'block';
    
    // 3秒後に非表示
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 3000);
}

