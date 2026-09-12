/**
 * AIサマリー PAY.JP v2 お試し（JP → Checkout Session → hosted 決済へリダイレクト）
 * Events: checkout_start, checkout_error, checkout_success
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

  function bindCheckoutRoot(root) {
    if (!root || root.getAttribute('data-checkout-enabled') !== 'true') return;

    var btn = root.querySelector('.ai-summary-checkout-btn');
    var emailInput = root.querySelector('.ai-summary-email');
    if (!btn || !emailInput || btn.getAttribute('data-bound') === '1') return;
    btn.setAttribute('data-bound', '1');

    var msgError = root.getAttribute('data-checkout-error') || 'Payment failed.';
    var msgEmail = root.getAttribute('data-email-required') || 'Email is required.';
    var prefix = root.getAttribute('data-checkout-form-prefix') || 'ai-summary';

    btn.addEventListener('click', function () {
      hideError(root);
      var email = (emailInput.value || '').trim();
      if (!email) {
        showError(root, msgEmail);
        return;
      }

      sendGa('checkout_start', {
        region_plan: 'jp',
        location: prefix,
        provider: 'payjp_v2',
      });
      btn.disabled = true;
      btn.setAttribute('aria-busy', 'true');

      fetch('/api/billing/ai-summary/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email }),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.data || !result.data.success || !result.data.redirect_url) {
            var errMsg = (result.data && result.data.error) || msgError;
            showError(root, errMsg);
            sendGa('checkout_error', {
              region_plan: 'jp',
              location: prefix,
              provider: 'payjp_v2',
            });
            btn.disabled = false;
            btn.removeAttribute('aria-busy');
            return;
          }
          sendGa('checkout_success', {
            region_plan: 'jp',
            location: prefix,
            provider: 'payjp_v2',
          });
          window.location.href = result.data.redirect_url;
        })
        .catch(function () {
          showError(root, msgError);
          sendGa('checkout_error', {
            region_plan: 'jp',
            location: prefix,
            provider: 'payjp_v2',
            reason: 'network',
          });
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
