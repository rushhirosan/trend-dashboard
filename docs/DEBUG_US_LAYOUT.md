# USページ「広大なスペース」デバッグガイド

## 実施済みの修正（効果がなかった場合）

- `us-trends.css`: align-items stretch, min-height: 0 の適用
- `data-status.css`, `subscription.css` を US ページから削除（該当セクションがないため）

## 開発者コンソールで確認すること

### 1. エラー確認
- **Console**タブを開き、赤いエラーメッセージがないか確認
- JavaScriptエラーがあるとレイアウトが崩れる場合がある

### 2. 以下をコンソールに貼り付けて実行

```javascript
// USページ レイアウト診断スクリプト（コンソールに貼り付けて実行）
(function() {
  const issues = [];
  const trends = document.getElementById('trends');
  const main = document.querySelector('main');
  const mainContent = document.getElementById('mainContent');
  
  if (!trends) { console.error('❌ #trends が見つかりません'); return; }
  
  // 1. bodyのクラス確認（hide-all-trends があるとトレンドが非表示になる）
  const bodyClasses = document.body.className;
  if (bodyClasses.includes('hide-all-trends')) {
    issues.push('⚠️ bodyに hide-all-trends クラスが付いている → #trends が非表示になる');
  }
  
  // 2. 主要要素の computed style
  const el = (id) => document.getElementById(id) || document.querySelector(id);
  const style = (elem, prop) => elem ? getComputedStyle(elem).getPropertyValue(prop) : 'N/A';
  
  console.log('=== レイアウト診断結果 ===');
  console.log('body.id:', document.body.id);
  console.log('body.className:', bodyClasses);
  console.log('');
  console.log('#trends:', { display: style(trends, 'display'), visibility: style(trends, 'visibility'), minHeight: style(trends, 'min-height') });
  console.log('main:', { display: style(main, 'display'), minHeight: style(main, 'min-height') });
  console.log('#mainContent:', { display: style(mainContent, 'display') });
  console.log('');
  
  // 3. 非アクティブなtab-paneが表示されていないか
  const panes = document.querySelectorAll('#trendCategoryTabContent > .tab-pane');
  panes.forEach((p, i) => {
    const isActive = p.classList.contains('active') && p.classList.contains('show');
    const display = getComputedStyle(p).display;
    if (!isActive && display !== 'none') {
      issues.push(`⚠️ 非アクティブな pane (${p.id}) が display:${display} で表示されている`);
    }
  });
  
  // 4. .loading 要素の min-height（200px が多数あると余白の原因）
  const loadings = document.querySelectorAll('.loading');
  if (loadings.length > 3) {
    issues.push(`⚠️ .loading 要素が ${loadings.length} 個表示中（min-height:200px が重なると余白の原因）`);
  }
  
  if (issues.length > 0) {
    console.log('🚨 検出された問題:');
    issues.forEach(i => console.log('  ', i));
  } else {
    console.log('✅ 明らかな問題は検出されませんでした。Elements タブで #trends を右クリック→検証し、Computed で min-height / flex を確認してください。');
  }
})();
```

### 3. Elements タブで確認

1. **Elements** タブで `#trends` を右クリック → **検証**
2. **Computed** パネルで以下を確認:
   - `min-height`: 大きな値（例: 500px）があれば余白の原因の可能性
   - `display`: `none` になっていないか
3. `main` や `#mainContent` も同様に確認
4. 広い余白に見える要素をクリックして、どの要素がそのスペースを占有しているか特定

### 4. 広い余白の場所を特定

- **ヘッダーとコンテンツの間** の余白 → `main` の `padding-top` または `py-4`
- **コンテンツとフッターの間** の余白 → `footer` の `margin-top` または親要素の `min-height`
- **カードとカードの間** の余白 → `.row` の `gap` または `.card` の `margin-bottom`
- **カード内の余白** → `.card-body` の `flex: 1` による伸び

---

診断結果（特に「検出された問題」や Computed の値）を共有いただければ、より正確な修正が可能です。
