/**
 * AIサマリー Fake door: モーダル計測（Checkout は ai-summary-checkout.js）
 */
(function () {
  function sendGa(eventName, params) {
    if (typeof gtag === 'function') {
      gtag('event', eventName, params || {});
    }
  }

  function init() {
    var root = document.getElementById('ai-summary-fake-door-root');
    if (!root) return;

    var region = (root.getAttribute('data-fake-door-region') || 'jp').trim();
    var locale = (root.getAttribute('data-fake-door-locale') || 'ja').trim();
    var baseParams = { region: region, locale: locale, location: 'ai_summary_fake_door' };

    var cta = document.getElementById('ai-summary-fake-door-cta');
    if (cta) {
      cta.addEventListener('click', function () {
        sendGa('ai_summary_top5_click', baseParams);
      });
    }

    var modalEl = document.getElementById('aiSummaryFakeDoorModal');
    if (modalEl) {
      modalEl.addEventListener('shown.bs.modal', function () {
        sendGa('fake_door_view', baseParams);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
