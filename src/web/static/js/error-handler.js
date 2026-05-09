/**
 * ATMstockMarket — Smart Error Handler
 *
 * Replaces the old blanket window.onerror that showed a warning for every
 * JS error.  Instead this handler:
 *   1. Silently collects runtime errors and unhandled rejections.
 *   2. Waits for the page to signal "healthy" (main init completed).
 *   3. Only shows the ⚠️ warning if the page stays unhealthy after a
 *      grace period OR if a critical number of errors pile up.
 *   4. Adds a dismiss (×) button so users can close the banner.
 *
 * Integration: after the page's main init script finishes successfully,
 * call  window.__atmPageReady().   Templates that use this module should
 * include it synchronously (not defer) right after the opening <head>
 * so it can catch errors from subsequent scripts.
 */
(function () {
  'use strict';

  var HEALTHY = false;
  var WARNING_SHOWN = false;
  var ERROR_COUNT = 0;
  var MAX_ERRORS = 5;          // show warning after this many errors
  var HEALTH_CHECK_MS = 4000;  // fallback health-check delay

  // ── public API called by page init scripts ──────────────────────
  window.__atmPageReady = function () {
    HEALTHY = true;
  };

  // ── error collector ─────────────────────────────────────────────
  function onError(event) {
    // Only handle JS runtime errors (ErrorEvent), not resource-load errors
    if (!(event instanceof ErrorEvent)) return;
    ERROR_COUNT++;
    if (event.message) {
      console.warn('[ATM] JS error (' + ERROR_COUNT + '):',
        event.message,
        event.filename ? 'at ' + event.filename + ':' + event.lineno : '');
    }
    maybeShow();
  }

  function onRejection(event) {
    event.preventDefault();
    ERROR_COUNT++;
    var reason = event.reason;
    var msg = reason && reason.message ? reason.message : String(reason);
    console.warn('[ATM] Unhandled rejection (' + ERROR_COUNT + '):', msg);
    maybeShow();
  }

  function maybeShow() {
    if (WARNING_SHOWN || HEALTHY) return;
    if (ERROR_COUNT >= MAX_ERRORS) showWarning();
  }

  // ── fallback timer — if nothing marks the page healthy in time ──
  setTimeout(function () {
    if (HEALTHY || WARNING_SHOWN) return;
    // Double-check: is the nav actually rendered?
    var nav = document.getElementById('nav-container');
    if (!nav || !nav.innerHTML.trim()) {
      showWarning();
    }
  }, HEALTH_CHECK_MS);

  // ── warning banner ──────────────────────────────────────────────
  function showWarning() {
    if (WARNING_SHOWN) return;
    WARNING_SHOWN = true;
    var nav = document.getElementById('nav-container');
    if (!nav) return; // nowhere to anchor
    var banner = document.createElement('div');
    banner.id = 'atm-load-warning';
    banner.setAttribute('role', 'alert');
    banner.style.cssText =
      'background:#fff3cd;color:#856404;padding:10px 16px;' +
      'text-align:center;font-size:14px;' +
      'border-bottom:1px solid #ffc107;' +
      'display:flex;align-items:center;justify-content:center;gap:12px;';
    banner.innerHTML =
      '<span>⚠️ 页面部分功能加载异常，请' +
      '<a href="javascript:location.reload()" ' +
      'style="color:#856404;text-decoration:underline;font-weight:bold;margin:0 4px;">刷新重试</a></span>' +
      '<button onclick="this.parentElement.remove()" ' +
      'style="background:none;border:none;cursor:pointer;font-size:18px;' +
      'color:#856404;line-height:1;padding:0 4px;" ' +
      'title="关闭" aria-label="关闭警告">×</button>';
    nav.insertAdjacentElement('afterend', banner);
  }

  // ── attach listeners ────────────────────────────────────────────
  window.addEventListener('error', onError);
  window.addEventListener('unhandledrejection', onRejection);
})();
