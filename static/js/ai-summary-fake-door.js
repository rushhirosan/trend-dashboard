/**
 * AIサマリー Fake door: ティーザー + Waitlist モーダル
 * Events: ai_summary_top5_click, fake_door_view, waitlist_submit, waitlist_success, waitlist_error
 */
(function () {
  function sendGa(eventName, params) {
    if (typeof gtag === 'function') {
      gtag('event', eventName, params || {});
    }
  }

  function isValidEmail(value) {
    return /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test((value || '').trim());
  }

  function showError(el, message) {
    if (!el) return;
    el.textContent = message;
    el.classList.remove('d-none');
  }

  function hideError(el) {
    if (!el) return;
    el.textContent = '';
    el.classList.add('d-none');
  }

  function resetWaitlistModal(root) {
    if (!root) return;
    var formWrap = document.getElementById('ai-summary-waitlist-form-wrap');
    var form = document.getElementById('ai-summary-waitlist-form');
    var successEl = document.getElementById('ai-summary-waitlist-success');
    var errorEl = document.getElementById('ai-summary-waitlist-error');
    var submitBtn = document.getElementById('ai-summary-waitlist-submit');
    var emailInput = document.getElementById('ai-summary-waitlist-email');

    if (formWrap) formWrap.classList.remove('d-none');
    if (form) form.classList.remove('d-none');
    if (successEl) {
      successEl.textContent = '';
      successEl.classList.add('d-none');
    }
    hideError(errorEl);
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.removeAttribute('aria-busy');
    }
    if (emailInput) emailInput.value = '';
  }

  function init() {
    var root = document.getElementById('ai-summary-fake-door-root');
    if (!root) return;

    var region = (root.getAttribute('data-fake-door-region') || 'jp').trim();
    var locale = (root.getAttribute('data-fake-door-locale') || 'ja').trim();
    var baseParams = { region: region, locale: locale, location: 'ai_summary_fake_door' };
    var msgSuccess = root.getAttribute('data-waitlist-success') || '';
    var msgError = root.getAttribute('data-waitlist-error') || '';
    var msgInvalid = root.getAttribute('data-waitlist-invalid') || '';

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
        var emailInput = document.getElementById('ai-summary-waitlist-email');
        if (emailInput) {
          window.setTimeout(function () { emailInput.focus(); }, 150);
        }
      });
      modalEl.addEventListener('hidden.bs.modal', function () {
        resetWaitlistModal(root);
      });
    }

    var form = document.getElementById('ai-summary-waitlist-form');
    if (!form) return;

    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var emailInput = document.getElementById('ai-summary-waitlist-email');
      var submitBtn = document.getElementById('ai-summary-waitlist-submit');
      var formWrap = document.getElementById('ai-summary-waitlist-form-wrap');
      var successEl = document.getElementById('ai-summary-waitlist-success');
      var errorEl = document.getElementById('ai-summary-waitlist-error');
      var email = (emailInput && emailInput.value) ? emailInput.value.trim() : '';

      hideError(errorEl);
      sendGa('waitlist_submit', Object.assign({}, baseParams, { source: 'fake_door_modal' }));

      if (!isValidEmail(email)) {
        showError(errorEl, msgInvalid);
        sendGa('waitlist_error', Object.assign({}, baseParams, { reason: 'invalid_email' }));
        if (emailInput) emailInput.focus();
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.setAttribute('aria-busy', 'true');
      }

      fetch('/api/waitlist/ai-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          region: region,
          source: 'fake_door_modal',
        }),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.data || !result.data.success) {
            var errMsg = (result.data && result.data.error) || msgError;
            showError(errorEl, errMsg);
            sendGa('waitlist_error', Object.assign({}, baseParams, { reason: 'api_error' }));
            if (submitBtn) {
              submitBtn.disabled = false;
              submitBtn.removeAttribute('aria-busy');
            }
            return;
          }
          if (formWrap) formWrap.classList.add('d-none');
          if (successEl) {
            successEl.textContent = (result.data.message || msgSuccess);
            successEl.classList.remove('d-none');
          }
          sendGa('waitlist_success', Object.assign({}, baseParams, { source: 'fake_door_modal' }));
        })
        .catch(function () {
          showError(errorEl, msgError);
          sendGa('waitlist_error', Object.assign({}, baseParams, { reason: 'network' }));
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.removeAttribute('aria-busy');
          }
        });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
