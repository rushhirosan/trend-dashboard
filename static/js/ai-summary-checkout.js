/**
 * AIサマリー Stripe Checkout（地域3択 → /api/billing/ai-summary/checkout）
 * Events: checkout_start, checkout_error
 */
(function () {
  function sendGa(eventName, params) {
    if (typeof gtag === 'function') {
      gtag('event', eventName, params || {});
    }
  }

  function showError(root, message) {
    var el = root.querySelector('.ai-summary-checkout-error');
    if (!el) return;
    el.textContent = message;
    el.classList.remove('d-none');
  }

  function hideError(root) {
    var el = root.querySelector('.ai-summary-checkout-error');
    if (!el) return;
    el.textContent = '';
    el.classList.add('d-none');
  }

  function selectedPlan(root) {
    var checked = root.querySelector('.ai-summary-region-plan:checked');
    return checked ? checked.value : (root.getAttribute('data-checkout-default-plan') || 'jp');
  }

  function bindCheckoutRoot(root) {
    if (!root || root.getAttribute('data-checkout-enabled') !== 'true') return;

    var btn = root.querySelector('.ai-summary-checkout-btn');
    if (!btn || btn.getAttribute('data-bound') === '1') return;
    btn.setAttribute('data-bound', '1');

    var msgError = root.getAttribute('data-checkout-error') || 'Checkout failed.';
    var prefix = root.getAttribute('data-checkout-form-prefix') || 'ai-summary';

    btn.addEventListener('click', function () {
      hideError(root);
      var regionPlan = selectedPlan(root);
      sendGa('checkout_start', { region_plan: regionPlan, location: prefix });

      btn.disabled = true;
      btn.setAttribute('aria-busy', 'true');

      fetch('/api/billing/ai-summary/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ region_plan: regionPlan }),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.data || !result.data.success || !result.data.url) {
            var errMsg = (result.data && result.data.error) || msgError;
            showError(root, errMsg);
            sendGa('checkout_error', { region_plan: regionPlan, location: prefix });
            btn.disabled = false;
            btn.removeAttribute('aria-busy');
            return;
          }
          window.location.href = result.data.url;
        })
        .catch(function () {
          showError(root, msgError);
          sendGa('checkout_error', { region_plan: regionPlan, location: prefix, reason: 'network' });
          btn.disabled = false;
          btn.removeAttribute('aria-busy');
        });
    });
  }

  function init() {
    var roots = document.querySelectorAll('.ai-summary-checkout-root');
    for (var i = 0; i < roots.length; i++) {
      bindCheckoutRoot(roots[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
