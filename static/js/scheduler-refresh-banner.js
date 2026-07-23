/**
 * 定時スケジューラ更新中バナー
 * /api/scheduler/lock-status の holder_id を見て表示（テーブル描画には干渉しない）
 */
(function () {
  'use strict';

  var POLL_MS = 45000;
  var ENDPOINT = '/api/scheduler/lock-status';
  var DISMISS_KEY = 'scheduler_refresh_banner_dismissed_lock';

  var banner = null;
  var timerId = null;
  var inFlight = false;

  function getBanner() {
    if (!banner) banner = document.getElementById('scheduler-refresh-banner');
    return banner;
  }

  function isLockActive(lock) {
    if (!lock || !lock.holder_id) return false;
    if (!lock.lock_until) return true;
    try {
      var until = new Date(lock.lock_until);
      if (isNaN(until.getTime())) return true;
      // 期限切れロックはバナーを出さない（張り付き防止）
      return until.getTime() > Date.now();
    } catch (e) {
      return true;
    }
  }

  function dismissToken(lock) {
    return String(lock.locked_at || lock.holder_id || '');
  }

  function isDismissedFor(lock) {
    try {
      return sessionStorage.getItem(DISMISS_KEY) === dismissToken(lock);
    } catch (e) {
      return false;
    }
  }

  function setDismissed(lock) {
    try {
      sessionStorage.setItem(DISMISS_KEY, dismissToken(lock));
    } catch (e) { /* ignore */ }
  }

  function clearDismissed() {
    try {
      sessionStorage.removeItem(DISMISS_KEY);
    } catch (e) { /* ignore */ }
  }

  function showBanner() {
    var el = getBanner();
    if (!el) return;
    el.classList.remove('d-none');
    el.removeAttribute('hidden');
  }

  function hideBanner() {
    var el = getBanner();
    if (!el) return;
    el.classList.add('d-none');
    el.setAttribute('hidden', '');
  }

  function applyLock(lock) {
    if (!isLockActive(lock)) {
      clearDismissed();
      hideBanner();
      return;
    }
    if (isDismissedFor(lock)) {
      hideBanner();
      return;
    }
    showBanner();
  }

  function poll() {
    if (document.hidden || inFlight) return;
    inFlight = true;
    fetch(ENDPOINT, { credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (!data || !data.success) {
          hideBanner();
          return;
        }
        applyLock(data.lock || null);
      })
      .catch(function () {
        // 取得失敗時は表示を変えない（ちらつき・誤表示防止）
      })
      .finally(function () {
        inFlight = false;
      });
  }

  function start() {
    if (!getBanner()) return;
    var closeBtn = banner.querySelector('.scheduler-refresh-banner__close');
    if (closeBtn && !closeBtn._bound) {
      closeBtn._bound = true;
      closeBtn.addEventListener('click', function () {
        // 直近の poll 結果がない場合でも閉じる
        fetch(ENDPOINT, { credentials: 'same-origin' })
          .then(function (res) { return res.ok ? res.json() : null; })
          .then(function (data) {
            if (data && data.lock) setDismissed(data.lock);
            hideBanner();
          })
          .catch(function () {
            hideBanner();
          });
      });
    }
    poll();
    timerId = setInterval(poll, POLL_MS);
  }

  function onVisibility() {
    if (!document.hidden) poll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
  document.addEventListener('visibilitychange', onVisibility);
})();
