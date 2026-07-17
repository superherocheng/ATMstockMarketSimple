(function() {
// Source: error-handler.js
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
      'background:#FFF7E6;color:#AD6800;padding:10px 16px;' +
      'text-align:center;font-size:14px;' +
      'border-bottom:1px solid #FFD591;' +
      'display:flex;align-items:center;justify-content:center;gap:12px;';
    banner.innerHTML =
      '<span>⚠️ Some features failed to load, please ' +
      '<a href="javascript:location.reload()" ' +
      'style="color:#AD6800;text-decoration:underline;font-weight:bold;margin:0 4px;">Refresh</a></span>' +
      '<button onclick="this.parentElement.remove()" ' +
      'style="background:none;border:none;cursor:pointer;font-size:18px;' +
      'color:#AD6800;line-height:1;padding:0 4px;" ' +
      'title="Close" aria-label="Close warning">×</button>';
    nav.insertAdjacentElement('afterend', banner);
  }

  // ── attach listeners ────────────────────────────────────────────
  window.addEventListener('error', onError);
  window.addEventListener('unhandledrejection', onRejection);
})();

})();

/* ── Auto-highlight active nav link ── */
(function() {
    var path = location.pathname;
    document.querySelectorAll('.nav-link, .bottom-nav-item').forEach(function(link) {
        var href = link.getAttribute('href');
        if (href && (href === path || (path.startsWith(href) && href !== '/'))) {
            link.classList.add('active');
        } else if (href === '/' && path === '/') {
            link.classList.add('active');
        }
    });
})();

/* ── Sidebar auto-collapse on detail pages ── */
// Removed: sidebar stays full-width on all pages for better navigation

/* ── Data freshness bar (fetches market timing) ── */
(function() {
    var bar = document.getElementById('freshness-bar');
    if (!bar) return;
    fetch('/api/market-timing').then(function(r) { return r.json(); }).then(function(d) {
        if (d.error) { bar.innerHTML = '📅 Data date: ' + (d.date || '--'); return; }
        var adj = (d.adjustment || 0) * 100;
        var icon = adj > 5 ? '📈' : (adj < -5 ? '📉' : '➡️');
        bar.innerHTML = '📅 Data as of ' + (d.date || '--') +
            ' &nbsp;|&nbsp; ' + icon + ' Market timing: ' + (d.regime_cn || 'Neutral') +
            ' <span style="opacity:0.6">(Adj. ' + (adj >= 0 ? '+' : '') + Math.round(adj) + '%)</span>';
    }).catch(function() {
        bar.innerHTML = '📅 Loading data...';
    });
})();

/* ── Skeleton system replaced by hard-skeleton CSS class ── */

/* ── Anonymous telemetry beacon ── */
(function() {
    if (navigator.doNotTrack === '1') return;
    try {
        var payload = JSON.stringify({
            path: location.pathname,
            ref: document.referrer.slice(0, 200),
            ts: Date.now(),
            w: screen.width,
            ua: navigator.userAgent.slice(0, 120)
        });
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/api/telemetry', payload);
        }
    } catch(e) {}
})();

(function() {
// Source: utils.js
window.ATM = window.ATM || {};

ATM.escapeHtml = function(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
};

ATM.pctColor = function(v) {
    if (v === null || v === undefined || v === '') return 'var(--c-zero)';
    var n = parseFloat(v);
    return n > 0 ? 'var(--c-up)' : n < 0 ? 'var(--c-down)' : 'var(--c-zero)';
};

ATM.pctColorRaw = function(v) {
    if (v === null || v === undefined || v === '') return '#9e9689';
    var n = parseFloat(v);
    var cs = getComputedStyle(document.documentElement);
    return n > 0 ? cs.getPropertyValue('--c-up').trim()
         : n < 0 ? cs.getPropertyValue('--c-down').trim()
         : cs.getPropertyValue('--c-zero').trim();
};

ATM.pctText = function(v) {
    if (v === null || v === undefined || v === '') return '--';
    var n = parseFloat(v);
    return (n > 0 ? '+' : '') + n.toFixed(2) + '%';
};

ATM.formatNum = function(v, decimals) {
    if (decimals === undefined) decimals = 2;
    if (v === null || v === undefined || v === '') return '--';
    return parseFloat(v).toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
};

ATM.formatAmount = function(val) {
    if (!val) return '--';
    var v = parseFloat(val);
    if (Math.abs(v) >= 100000000) return (v / 100000000).toFixed(2) + 'B';
    if (Math.abs(v) >= 10000) return (v / 10000).toFixed(0) + 'K';
    return v.toFixed(0);
};

ATM.formatVol = function(val) {
    if (!val) return '--';
    var v = parseFloat(val);
    if (v >= 100000000) return (v / 100000000).toFixed(2) + 'B lots';
    if (v >= 10000) return (v / 10000).toFixed(0) + 'K lots';
    return v.toFixed(0) + ' lots';
};

ATM.fmtDate = function(s) {
    if (!s || s.length !== 8) return s || '-';
    return s.slice(0, 4) + '/' + s.slice(4, 6) + '/' + s.slice(6, 8);
};

ATM.fmtDateDash = function(s) {
    if (!s || s.length !== 8) return s || '-';
    return s.slice(0, 4) + '-' + s.slice(4, 6) + '-' + s.slice(6, 8);
};

ATM.fmtMV = function(v) {
    if (!v) return '--';
    v = parseFloat(v);
    if (v >= 10000) return (v / 10000).toFixed(1) + 'T';
    if (v >= 100) return v.toFixed(0) + 'B';
    return v.toFixed(0) + 'B';
};

ATM.rankBadge = function(i) {
    var cls = i < 3 ? 'rank-' + (i + 1) : 'rank-other';
    return '<span class="rank-badge ' + cls + '">' + (i + 1) + '</span>';
};

ATM.dataStatus = function(d) {
    if (!d.exists || d.count === 0) return { tag: 'Empty', color: 'var(--c-up)', need: true };
    if (!d.max_date) return { tag: 'Has data', color: 'var(--c-gold)', need: false };
    var maxD = ATM._parseDate(d.max_date);
    var now = new Date();
    var tradingToday = ATM._lastTradingDate(now);
    var diffTrading = ATM._tradingDaysBetween(maxD, tradingToday);
    if (diffTrading === 0) return { tag: 'Latest', color: 'var(--c-down)', need: false };
    if (diffTrading <= 1) return { tag: 'Latest', color: 'var(--c-down)', need: false };
    if (diffTrading <= 5) return { tag: 'Behind by ' + diffTrading + ' trading days', color: 'var(--c-gold)', need: true };
    return { tag: 'Outdated', color: 'var(--c-up)', need: true };
};

ATM._parseDate = function(s) {
    return new Date(parseInt(s.slice(0,4)), parseInt(s.slice(4,6))-1, parseInt(s.slice(6,8)));
};

ATM._lastTradingDate = function(d) {
    var result = new Date(d);
    var dow = result.getDay();
    if (dow === 0) result.setDate(result.getDate() - 2);
    else if (dow === 6) result.setDate(result.getDate() - 1);
    return result;
};

ATM._tradingDaysBetween = function(start, end) {
    var count = 0;
    var cur = new Date(start);
    cur.setDate(cur.getDate() + 1);
    var endD = new Date(end);
    endD.setHours(23, 59, 59);
    while (cur <= endD) {
        var dow = cur.getDay();
        if (dow !== 0 && dow !== 6) count++;
        cur.setDate(cur.getDate() + 1);
    }
    return count;
};

ATM.sparklineSVG = function(prices, color) {
    if (!prices || prices.length < 2) return '';
    var w = 80, h = 24, pad = 2;
    var min = Math.min.apply(null, prices), max = Math.max.apply(null, prices);
    var range = (max - min) || 1;
    var pts = prices.map(function(p, i) {
        return (pad + i * ((w - 2 * pad) / (prices.length - 1))) + ',' + (h - pad - ((p - min) / range) * (h - 2 * pad));
    }).join(' ');
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '" style="display:block;">' +
        '<polyline points="' + pts + '" fill="none" stroke="' + color + '" stroke-width="1.5" ' +
        'stroke-linecap="round" stroke-linejoin="round" opacity="0.6"/></svg>';
};

ATM.SECTOR_ICONS = {
    '半导体': '⚡', '新能源车': '🚗',
    '医药': '💊', '银行': '🏦',
    '证券': '📊', '消费': '🛒', '通信': '📡',
    '卫星': '🛰️', '煤炭': '⛏️', '有色': '💎',
    '机器人': '🤖'
};

// English name map for all 32 sector ETFs — used where r.code is available
// (rotation & recommendation tables) to show English names instead of Chinese.
// Keyed by ts_code for the reverse-lookups that powers the 2026-07 English-first UI.
ATM.ETF_ENGLISH = {
    "512480.SH": "Semiconductor ETF",
    "515030.SH": "NEV ETF",
    "512010.SH": "Pharma ETF",
    "512800.SH": "Banking ETF",
    "512880.SH": "Securities ETF",
    "159928.SZ": "Consumer ETF",
    "515880.SH": "Telecom ETF",
    "159206.SZ": "Satellite ETF",
    "515220.SH": "Coal ETF",
    "512400.SH": "Metals ETF",
    "562500.SH": "Robotics ETF",
    "512690.SH": "Baijiu ETF",
    "159611.SZ": "Power ETF",
    "512980.SH": "Media ETF",
    "515210.SH": "Steel ETF",
    "159870.SZ": "Chemicals ETF",
    "561360.SH": "Oil ETF",
    "512710.SH": "Defense ETF",
    "515790.SH": "Solar ETF",
    "159934.SZ": "Gold ETF",
    "159865.SZ": "Farming ETF",
    "159766.SZ": "Tourism ETF",
    "159852.SZ": "Software ETF",
    "159851.SZ": "Fintech ETF",
    "512170.SH": "Healthcare ETF",
    "159869.SZ": "Gaming ETF",
    "159755.SZ": "Battery ETF",
    "516150.SH": "Rare Earth ETF",
    "159638.SZ": "Hi-End Eqpt ETF",
    "159930.SZ": "Energy ETF",
    "515000.SH": "Tech ETF",
    "159326.SZ": "Grid Eqpt ETF",
};

// ── P1.4: CSV export utility ──
ATM.downloadCSV = function(rows, filename) {
    if (!rows || rows.length === 0) return;
    var BOM = '\uFEFF';
    var headers = Object.keys(rows[0]);
    var csv = BOM + headers.join(',') + '\n';
    csv += rows.map(function(row) {
        return headers.map(function(h) {
            var v = row[h];
            if (v === null || v === undefined) return '';
            var s = String(v);
            if (s.includes(',') || s.includes('"') || s.includes('\n')) {
                return '"' + s.replace(/"/g, '""') + '"';
            }
            return s;
        }).join(',');
    }).join('\n');
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename || 'export.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};

ATM.getChartTheme = function() {
    var dark = typeof ATMTheme !== 'undefined' && ATMTheme.isDark && ATMTheme.isDark();
    return {
        backgroundColor: 'transparent',
        textStyle: {
            color: dark ? '#E8EAED' : '#1A1A1A',
            fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
        },
        title: {
            textStyle: {
                color: dark ? '#E8EAED' : '#1A1A1A',
                fontWeight: 700,
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            }
        },
        legend: {
            textStyle: {
                color: dark ? '#9AA0A6' : '#666666',
                fontSize: 12,
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            icon: 'circle',
            itemWidth: 10,
            itemHeight: 10
        },
        tooltip: {
            backgroundColor: dark ? '#1A1D27' : '#FFFFFF',
            borderColor: dark ? '#2A2D37' : '#E8EAED',
            borderWidth: 1,
            textStyle: {
                color: dark ? '#E8EAED' : '#1A1A1A',
                fontSize: 12,
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            extraCssText: dark
                ? 'box-shadow: 0 4px 16px rgba(0,0,0,0.3); border-radius: 8px;'
                : 'box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-radius: 8px;'
        },
        splitLineColor: dark ? '#2A2D37' : '#F0F2F5',
        axisLabelColor: dark ? '#6B7280' : '#999999',
        axisLineColor: dark ? '#2A2D37' : '#E8EAED',
        upColor: '#FF4D4F',
        upColor0: 'rgba(255, 77, 79, 0.15)',
        downColor: '#52C41A',
        downColor0: 'rgba(82, 196, 26, 0.15)',
        accentColor: '#FF4D4F',
        accentLight: 'rgba(255, 77, 79, 0.15)',
        seriesColors: dark
            ? ['#818CF8', '#FF6B6B', '#6BCB77', '#FFD666', '#4DABF7', '#B197FC', '#3BC9DB', '#F783AC']
            : ['#4F46E5', '#FF4D4F', '#52C41A', '#FAAD14', '#1677FF', '#722ED1', '#13C2C2', '#EB2F96']
    };
};

})();



(function() {
// Source: theme.js
window.ATMTheme = window.ATMTheme || {};

ATMTheme.init = function() {
    // Follow the OS preference only (2026-07-01): the manual toggle was removed
    // to cut a user decision, so theme now tracks prefers-color-scheme live and
    // nothing is read from / written to localStorage.
    var btn = document.getElementById('theme-toggle-btn');
    if (btn) btn.style.display = 'none';   // toggle removed — theme follows OS
    var mql = window.matchMedia('(prefers-color-scheme: dark)');
    var apply = function(e) {
        var dark = (e && typeof e.matches === 'boolean') ? e.matches : mql.matches;
        var t = dark ? 'dark' : 'light';
        document.documentElement.dataset.theme = t;
        ATMTheme._updateIcon(t);
        ATMTheme._notifyCharts();
    };
    apply();
    mql.addEventListener('change', apply);
};

ATMTheme.toggle = function() {
    var current = document.documentElement.dataset.theme || 'light';
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('atm-theme', next);
    this._updateIcon(next);
    this._notifyCharts();
};

ATMTheme.get = function() {
    return document.documentElement.dataset.theme || 'light';
};

ATMTheme.isDark = function() {
    return this.get() === 'dark';
};

ATMTheme._updateIcon = function(theme) {
    var btn = document.getElementById('theme-toggle-btn');
    if (!btn) return;
    if (theme === 'dark') {
        btn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>';
        btn.setAttribute('title', 'Switch to light mode');
    } else {
        btn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>';
        btn.setAttribute('title', 'Switch to dark mode');
    }
};

ATMTheme._notifyCharts = function() {
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: { theme: this.get() } }));
};

ATMTheme.init();

})();

(function() {
// Source: cache.js
window.ATMCache = window.ATMCache || {};

ATMCache._storage = window.sessionStorage;
ATMCache._prefix = 'atm_';
ATMCache._defaultTTL = 5 * 60 * 1000;

ATMCache._getKey = function(key) {
    return ATMCache._prefix + key;
};

ATMCache.set = function(key, data, ttl) {
    try {
        var item = {
            data: data,
            timestamp: Date.now(),
            ttl: ttl || ATMCache._defaultTTL
        };
        ATMCache._storage.setItem(ATMCache._getKey(key), JSON.stringify(item));
    } catch (e) {
        console.warn('Cache set failed', e);
    }
};

ATMCache.get = function(key) {
    try {
        var itemStr = ATMCache._storage.getItem(ATMCache._getKey(key));
        if (!itemStr) return null;
        var item = JSON.parse(itemStr);
        if (Date.now() - item.timestamp > item.ttl) {
            ATMCache.remove(key);
            return null;
        }
        return item.data;
    } catch (e) {
        return null;
    }
};

ATMCache.remove = function(key) {
    try {
        ATMCache._storage.removeItem(ATMCache._getKey(key));
    } catch (e) {}
};

ATMCache.clear = function() {
    try {
        Object.keys(ATMCache._storage).forEach(function(k) {
            if (k.startsWith(ATMCache._prefix)) {
                ATMCache._storage.removeItem(k);
            }
        });
    } catch (e) {}
};

ATMCache.api = function(url, options) {
    options = options || {};
    var forceRefresh = options.forceRefresh || false;
    var ttl = options.ttl || ATMCache._defaultTTL;
    var cacheKey = 'api_' + url.replace(/[^a-zA-Z0-9]/g, '_');
    
    if (!forceRefresh) {
        var cached = ATMCache.get(cacheKey);
        if (cached !== null) {
            return Promise.resolve(cached);
        }
    }
    
    return fetch(url)
        .then(function(response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(function(data) {
            ATMCache.set(cacheKey, data, ttl);
            return data;
        });
};

window.ATMRouter = window.ATMRouter || {};

ATMRouter._initialized = false;
ATMRouter._navigating = false;
ATMRouter._isMobile = function() {
    return window.innerWidth < 640;
};

ATMRouter.init = function() {
    if (ATMRouter._initialized) return;
    ATMRouter._initialized = true;

    ATMRouter._setupNavigationCapture();
};

ATMRouter._setupNavigationCapture = function() {
    document.addEventListener('click', function(e) {
        var link = e.target.closest('a[href]');
        if (!link) return;
        var href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript') || href.startsWith('http') || href.startsWith('//')) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

        e.preventDefault();
        ATMRouter.navigate(href);
    });
};

ATMRouter.navigate = function(url) {
    if (ATMRouter._navigating) return;
    if (url === window.location.pathname) return;
    ATMRouter._navigating = true;

    // Hard snap — zero latency, no overlay, no delay
    window.location.href = url;
};

window.addEventListener('pageshow', function() {
    ATMRouter._navigating = false;
});

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ATMRouter.init);
} else {
    ATMRouter.init();
}

})();

(function() {
// Source: perf.js
window.ATMPerf = window.ATMPerf || {};

ATMPerf.debounce = function(fn, delay) {
    var timer;
    return function() {
        var ctx = this, args = arguments;
        clearTimeout(timer);
        timer = setTimeout(function() { fn.apply(ctx, args); }, delay);
    };
};

ATMPerf.throttle = function(fn, limit) {
    var last = 0;
    return function() {
        var now = Date.now();
        if (now - last >= limit) {
            last = now;
            fn.apply(this, arguments);
        }
    };
};

ATMPerf.rafThrottle = function(fn) {
    var ticking = false;
    return function() {
        if (!ticking) {
            var ctx = this, args = arguments;
            requestAnimationFrame(function() {
                fn.apply(ctx, args);
                ticking = false;
            });
            ticking = true;
        }
    };
};

ATMPerf.onVisible = function(callback) {
    if (!document.hidden) {
        callback();
        return;
    }
    var handler = function() {
        if (!document.hidden) {
            callback();
            document.removeEventListener('visibilitychange', handler);
        }
    };
    document.addEventListener('visibilitychange', handler);
};

ATMPerf.VisibilityManager = {
    _paused: false,
    _callbacks: [],
    _init: false,

    register: function(onPause, onResume) {
        this._callbacks.push({ onPause: onPause, onResume: onResume });
        if (!this._init) {
            this._init = true;
            var self = this;
            document.addEventListener('visibilitychange', function() {
                if (document.hidden) {
                    self._paused = true;
                    self._callbacks.forEach(function(cb) { if (cb.onPause) cb.onPause(); });
                } else {
                    self._paused = false;
                    self._callbacks.forEach(function(cb) { if (cb.onResume) cb.onResume(); });
                }
            });
        }
    },

    isPaused: function() { return this._paused; }
};

ATMPerf.NetworkAware = {
    _effectiveType: '4g',
    _init: false,
    _callbacks: [],

    init: function() {
        if (this._init) return;
        this._init = true;
        var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (!conn) return;
        this._effectiveType = conn.effectiveType || '4g';
        var self = this;
        conn.addEventListener('change', function() {
            var prev = self._effectiveType;
            self._effectiveType = conn.effectiveType || '4g';
            self._callbacks.forEach(function(cb) { cb(prev, self._effectiveType); });
        });
    },

    register: function(callback) {
        this._callbacks.push(callback);
    },

    getType: function() {
        var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        return conn ? (conn.effectiveType || '4g') : '4g';
    },

    isSlow: function() {
        var type = this.getType();
        return type === 'slow-2g' || type === '2g';
    }
};

ATMPerf.idleCallback = function(fn) {
    if ('requestIdleCallback' in window) {
        requestIdleCallback(fn);
    } else {
        setTimeout(fn, 1);
    }
};

})();

(function() {
// Source: performance.js
window.ATMPerf = window.ATMPerf || {};

function _isMobile() {
    return typeof ATMMobile !== 'undefined' && ATMMobile.isMobile && ATMMobile.isMobile();
}

ATMPerf.sampleDataForMobile = function(data, maxPoints) {
    if (!_isMobile() || !data || data.length <= maxPoints) {
        return data;
    }
    
    var sampled = [];
    var step = Math.ceil(data.length / maxPoints);
    
    for (var i = 0; i < data.length; i += step) {
        var chunk = data.slice(i, i + step);
        var avgPoint = {
            date: chunk[0].date,
            value: chunk.reduce(function(sum, p) { return sum + p.value; }, 0) / chunk.length
        };
        sampled.push(avgPoint);
    }
    
    return sampled;
};

ATMPerf.aggregateDataForMobile = function(data, interval) {
    if (!_isMobile() || !data || data.length === 0) {
        return data;
    }
    
    var aggregated = [];
    var currentGroup = [];
    var currentKey = null;
    
    data.forEach(function(point) {
        var key = point.date.substring(0, interval);
        
        if (key !== currentKey) {
            if (currentGroup.length > 0) {
                aggregated.push({
                    date: currentGroup[0].date,
                    open: currentGroup[0].open,
                    close: currentGroup[currentGroup.length - 1].close,
                    high: Math.max.apply(null, currentGroup.map(function(p) { return p.high; })),
                    low: Math.min.apply(null, currentGroup.map(function(p) { return p.low; })),
                    volume: currentGroup.reduce(function(sum, p) { return sum + p.volume; }, 0)
                });
            }
            currentGroup = [point];
            currentKey = key;
        } else {
            currentGroup.push(point);
        }
    });
    
    if (currentGroup.length > 0) {
        aggregated.push({
            date: currentGroup[0].date,
            open: currentGroup[0].open,
            close: currentGroup[currentGroup.length - 1].close,
            high: Math.max.apply(null, currentGroup.map(function(p) { return p.high; })),
            low: Math.min.apply(null, currentGroup.map(function(p) { return p.low; })),
            volume: currentGroup.reduce(function(sum, p) { return sum + p.volume; }, 0)
        });
    }
    
    return aggregated;
};

ATMPerf.lazyLoadImages = function() {
    var images = document.querySelectorAll('img[data-src]');
    
    if ('IntersectionObserver' in window) {
        var imageObserver = new IntersectionObserver(function(entries, observer) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    var image = entry.target;
                    image.src = image.dataset.src;
                    image.removeAttribute('data-src');
                    imageObserver.unobserve(image);
                }
            });
        }, {
            rootMargin: '50px 0px',
            threshold: 0.01
        });
        
        images.forEach(function(img) {
            imageObserver.observe(img);
        });
    } else {
        images.forEach(function(img) {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
        });
    }
};

ATMPerf.lazyLoadComponents = function(selector, callback) {
    var elements = document.querySelectorAll(selector);
    
    if ('IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function(entries, obs) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    callback(entry.target);
                    obs.unobserve(entry.target);
                }
            });
        }, {
            rootMargin: '100px 0px',
            threshold: 0.01
        });
        
        elements.forEach(function(el) {
            observer.observe(el);
        });
    } else {
        elements.forEach(function(el) {
            callback(el);
        });
    }
};

ATMPerf.preloadCriticalResources = function() {
    // Preload CSS removed — files no longer shipped
};

ATMPerf.deferNonCriticalJS = function() {
    var scripts = document.querySelectorAll('script[data-defer]');
    scripts.forEach(function(script) {
        script.src = script.dataset.defer;
        script.removeAttribute('data-defer');
    });
};

ATMPerf.optimizeChartRendering = function(chartInstance, data) {
    if (!chartInstance || !data) return;
    
    var optimizedData = data;
    
    if (_isMobile() && data.length > 100) {
        optimizedData = this.sampleDataForMobile(data, 100);
    } else if (_isMobile() && ATMMobile && ATMMobile.isTablet && ATMMobile.isTablet() && data.length > 200) {
        optimizedData = this.sampleDataForMobile(data, 200);
    }
    
    return optimizedData;
};

ATMPerf.virtualizeList = function(containerId, items, renderItem, itemHeight) {
    var container = document.getElementById(containerId);
    if (!container) return;
    
    var viewportHeight = container.clientHeight;
    var visibleCount = Math.ceil(viewportHeight / itemHeight);
    var totalHeight = items.length * itemHeight;
    
    var scrollHandler = function() {
        var scrollTop = container.scrollTop;
        var startIndex = Math.floor(scrollTop / itemHeight);
        var endIndex = Math.min(startIndex + visibleCount + 2, items.length);
        
        var visibleItems = [];
        for (var i = startIndex; i < endIndex; i++) {
            visibleItems.push(renderItem(items[i], i));
        }
        
        var content = document.createElement('div');
        content.style.height = totalHeight + 'px';
        content.style.position = 'relative';
        
        var itemsContainer = document.createElement('div');
        itemsContainer.style.position = 'absolute';
        itemsContainer.style.top = (startIndex * itemHeight) + 'px';
        itemsContainer.innerHTML = visibleItems.join('');
        
        content.appendChild(itemsContainer);
        container.innerHTML = '';
        container.appendChild(content);
    };
    
    container.addEventListener('scroll', scrollHandler);
    scrollHandler();
};

ATMPerf.init = function() {
    this.lazyLoadImages();
    this.preloadCriticalResources();
    
    if (document.readyState === 'complete') {
        this.deferNonCriticalJS();
    } else {
        window.addEventListener('load', this.deferNonCriticalJS);
    }
};

document.addEventListener('DOMContentLoaded', function() {
    ATMPerf.init();
});

})();

(function() {
// Source: mobile.js
window.ATMMobile = window.ATMMobile || {};

ATMMobile.isMobile = function() {
    return window.innerWidth < 640;
};

ATMMobile.isTablet = function() {
    return window.innerWidth >= 640 && window.innerWidth < 1024;
};

ATMMobile.isDesktop = function() {
    return window.innerWidth >= 1024;
};

ATMMobile.getDeviceType = function() {
    if (this.isMobile()) return 'mobile';
    if (this.isTablet()) return 'tablet';
    return 'desktop';
};

ATMMobile.optimizeChartForMobile = function(chartInstance) {
    if (!this.isMobile() || !chartInstance) return;
    
    var option = chartInstance.getOption();
    
    if (option.tooltip) {
        option.tooltip.triggerOn = 'click';
        option.tooltip.confine = true;
        option.tooltip.enterable = true;
    }
    
    if (option.dataZoom && option.dataZoom.length > 0) {
        option.dataZoom.forEach(function(zoom) {
            if (zoom.type === 'inside') {
                zoom.zoomOnMouseWheel = false;
                zoom.moveOnMouseMove = true;
                zoom.zoomLock = false;
            }
        });
    }
    
    chartInstance.setOption(option);
};

ATMMobile.createMobileFilter = function(containerId, options) {
    var container = document.getElementById(containerId);
    if (!container || !this.isMobile()) return;
    
    var filterHtml = '<div class="mobile-filter-container">';
    filterHtml += '<button class="mobile-filter-toggle" onclick="ATMMobile.toggleFilter(\'' + containerId + '\')">';
    filterHtml += '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"/></svg>';
    filterHtml += '<span>Filter</span>';
    filterHtml += '</button>';
    filterHtml += '<div class="mobile-filter-content" id="' + containerId + '-filter-content">';
    
    options.forEach(function(opt, index) {
        filterHtml += '<div class="mobile-filter-item">';
        filterHtml += '<label class="mobile-filter-label">' + opt.label + '</label>';
        
        if (opt.type === 'select') {
            filterHtml += '<select class="mobile-filter-select" onchange="' + opt.onChange + '">';
            opt.options.forEach(function(option) {
                filterHtml += '<option value="' + option.value + '"' + (option.selected ? ' selected' : '') + '>' + option.label + '</option>';
            });
            filterHtml += '</select>';
        } else if (opt.type === 'date') {
            filterHtml += '<input type="date" class="mobile-filter-date" onchange="' + opt.onChange + '" value="' + (opt.value || '') + '">';
        } else if (opt.type === 'text') {
            filterHtml += '<input type="text" class="mobile-filter-text" placeholder="' + (opt.placeholder || '') + '" onchange="' + opt.onChange + '" value="' + (opt.value || '') + '">';
        }
        
        filterHtml += '</div>';
    });
    
    filterHtml += '<div class="mobile-filter-actions">';
    filterHtml += '<button class="btn btn-secondary" onclick="ATMMobile.resetFilter(\'' + containerId + '\')">Reset</button>';
    filterHtml += '<button class="btn btn-primary" onclick="ATMMobile.applyFilter(\'' + containerId + '\')">Apply</button>';
    filterHtml += '</div>';
    filterHtml += '</div>';
    filterHtml += '</div>';
    
    container.innerHTML = filterHtml;
};

ATMMobile.toggleFilter = function(containerId) {
    var content = document.getElementById(containerId + '-filter-content');
    if (content) {
        content.classList.toggle('open');
    }
};

ATMMobile.applyFilter = function(containerId) {
    var content = document.getElementById(containerId + '-filter-content');
    if (content) {
        content.classList.remove('open');
    }
};

ATMMobile.resetFilter = function(containerId) {
    var container = document.getElementById(containerId);
    if (container) {
        var inputs = container.querySelectorAll('input, select');
        inputs.forEach(function(input) {
            if (input.type === 'select-one') {
                input.selectedIndex = 0;
            } else {
                input.value = '';
            }
        });
    }
};

ATMMobile.enhanceTouchTargets = function() {
    if (!this.isMobile()) return;
    
    // Only apply once via class — skip if already enhanced
    var buttons = document.querySelectorAll('button:not(.touch-enhanced), .btn:not(.touch-enhanced), a:not(.touch-enhanced)');
    if (buttons.length === 0) return;
    buttons.forEach(function(btn) {
        btn.classList.add('touch-enhanced');
        var rect = btn.getBoundingClientRect();
        if (rect.width < 44 || rect.height < 44) {
            btn.classList.add('touch-enhanced-min');
        }
    });
};

ATMMobile.optimizeForDevice = function() {
    var deviceType = this.getDeviceType();
    
    if (deviceType === 'mobile') {
        document.body.classList.add('device-mobile');
        document.body.classList.remove('device-tablet', 'device-desktop');
        this.enhanceTouchTargets();
    } else if (deviceType === 'tablet') {
        document.body.classList.add('device-tablet');
        document.body.classList.remove('device-mobile', 'device-desktop');
    } else {
        document.body.classList.add('device-desktop');
        document.body.classList.remove('device-mobile', 'device-tablet');
    }
};

ATMMobile.init = function() {
    var self = this;
    
    this.optimizeForDevice();
    
    var resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            self.optimizeForDevice();
        }, 250);
    });
    
    if (this.isMobile()) {
        document.addEventListener('touchstart', function(e) {
            if (e.touches.length > 1) {
                e.preventDefault();
            }
        }, { passive: false });
    }
};

document.addEventListener('DOMContentLoaded', function() {
    ATMMobile.init();
});

})();


(function() {
// Source: chart-loader.js
window.ATMChart = window.ATMChart || {};

ATMChart._loaded = null;

ATMChart.load = function() {
    if (ATMChart._loaded) return ATMChart._loaded;
    if (typeof echarts !== 'undefined') {
        ATMChart._loaded = Promise.resolve(echarts);
        return ATMChart._loaded;
    }
    ATMChart._loaded = Promise.reject(
        new Error('ATMstockMarket: ECharts not loaded, please verify vendor.js is properly included')
    );
    return ATMChart._loaded;
};

ATMChart._instances = new WeakMap();

ATMChart.init = function(containerId) {
    var el = document.getElementById(containerId);
    if (!el) return null;
    var existing = this._instances.get(el);
    if (existing && !existing.isDisposed()) return existing;
    var chart = echarts.init(el);
    this._instances.set(el, chart);
    return chart;
};

ATMChart.dispose = function(containerId) {
    var el = document.getElementById(containerId);
    if (!el) return;
    var chart = this._instances.get(el);
    if (chart && !chart.isDisposed()) {
        chart.dispose();
    }
    this._instances.delete(el);
};

ATMChart.disposeAll = function() {
    document.querySelectorAll('[_echarts_instance_]').forEach(function(el) {
        var instance = echarts.getInstanceByDom(el);
        if (instance) instance.dispose();
    });
};

ATMChart.resizeAll = function() {
    document.querySelectorAll('[_echarts_instance_]').forEach(function(el) {
        var instance = echarts.getInstanceByDom(el);
        if (instance) instance.resize();
    });
};

ATMChart.setupResizeHandler = function() {
    var timer;
    window.addEventListener('resize', function() {
        clearTimeout(timer);
        timer = setTimeout(function() {
            ATMChart.resizeAll();
        }, 150);
    });
    if (screen.orientation) {
        screen.orientation.addEventListener('change', function() {
            setTimeout(function() {
                ATMChart.resizeAll();
            }, 300);
        });
    }
    window.addEventListener('orientationchange', function() {
        setTimeout(function() {
            ATMChart.resizeAll();
        }, 300);
    });
};

ATMChart.setupThemeHandler = function() {
    window.addEventListener('theme-changed', function() {
        setTimeout(function() {
            ATMChart.resizeAll();
            document.querySelectorAll('[_echarts_instance_]').forEach(function(el) {
                var instance = echarts.getInstanceByDom(el);
                if (instance) {
                    var theme = ATMChart.getChartTheme();
                    instance.setOption({
                        textStyle: theme.textStyle,
                        title: theme.title,
                        legend: theme.legend,
                        tooltip: theme.tooltip,
                        color: theme.color
                    });
                }
            });
        }, 100);
    });
};

ATMChart.setupVisibilityHandler = function() {
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            setTimeout(function() {
                ATMChart.resizeAll();
            }, 100);
        }
    });
};

ATMChart.initPage = function() {
    this.setupResizeHandler();
    this.setupThemeHandler();
    this.setupVisibilityHandler();

    /* Resize charts when a collapsed <details> is opened (e.g. chart groups) */
    document.addEventListener('toggle', function(e) {
        if (e.target && e.target.nodeName === 'DETAILS' && e.target.open) {
            setTimeout(function() { ATMChart.resizeAll(); }, 50);
        }
    }, true);

    window.addEventListener('beforeunload', function() {
        ATMChart.disposeAll();
    });
};

ATMChart.getChartTheme = function() {
    return {
        backgroundColor: 'transparent',
        textStyle: {
            fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif",
            fontSize: 12,
            color: '#1A1A1A'
        },
        title: {
            textStyle: {
                color: '#1A1A1A',
                fontWeight: 700,
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            subtextStyle: {
                color: '#999999'
            }
        },
        line: {
            itemStyle: {
                borderWidth: 2
            },
            lineStyle: {
                width: 2.5,
                opacity: 0.75
            },
            symbolSize: 6,
            symbol: 'circle',
            smooth: false
        },
        bar: {
            itemStyle: {
                barBorderRadius: [4, 4, 0, 0]
            }
        },
        pie: {
            itemStyle: {
                borderRadius: 4,
                borderColor: '#FFFFFF',
                borderWidth: 2
            }
        },
        categoryAxis: {
            axisLine: {
                lineStyle: {
                    color: '#E8EAED',
                    width: 1
                }
            },
            axisTick: {
                lineStyle: {
                    color: '#E8EAED'
                }
            },
            axisLabel: {
                color: '#999999',
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            splitLine: {
                lineStyle: {
                    color: '#F0F2F5',
                    type: 'solid'
                }
            },
            splitArea: {
                show: false
            }
        },
        valueAxis: {
            axisLine: {
                lineStyle: {
                    color: '#E8EAED',
                    width: 1
                }
            },
            axisTick: {
                lineStyle: {
                    color: '#E8EAED'
                }
            },
            axisLabel: {
                color: '#999999',
                fontFamily: "'JetBrains Mono', ui-monospace, monospace"
            },
            splitLine: {
                lineStyle: {
                    color: '#F0F2F5',
                    type: 'solid'
                }
            },
            splitArea: {
                show: false
            }
        },
        tooltip: {
            backgroundColor: '#FFFFFF',
            borderColor: '#E8EAED',
            borderWidth: 1,
            textStyle: {
                color: '#1A1A1A',
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-radius: 8px;'
        },
        legend: {
            textStyle: {
                color: '#666666',
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            pageTextStyle: {
                color: '#999999'
            }
        },
        color: [
            '#4F46E5',
            '#FF4D4F',
            '#52C41A',
            '#FAAD14',
            '#1677FF',
            '#722ED1',
            '#13C2C2',
            '#EB2F96',
            '#FA8C16',
            '#A0D911'
        ],
        watercolorColors: {
            blue: '#4F46E5',
            blueLight: '#818CF8',
            neutral: '#999999',
            greenLight: '#52C41A',
            terracotta: '#FF4D4F',
            terracottaLight: '#FF7875',
            lavender: '#722ED1',
            lavenderLight: '#B37FEB',
            peach: '#FA8C16',
            peachLight: '#FFA940',
            up: '#FF4D4F',
            upLight: '#FF7875',
            down: '#52C41A',
            downLight: '#95DE64'
        }
    };
};

ATMChart.getChartThemeDark = function() {
    return {
        backgroundColor: 'transparent',
        textStyle: {
            fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif",
            fontSize: 12,
            color: '#E8EAED'
        },
        title: {
            textStyle: {
                color: '#E8EAED',
                fontWeight: 700,
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            subtextStyle: {
                color: '#6B7280'
            }
        },
        line: {
            itemStyle: {
                borderWidth: 2
            },
            lineStyle: {
                width: 2.5,
                opacity: 0.75
            },
            symbolSize: 6,
            symbol: 'circle',
            smooth: false
        },
        bar: {
            itemStyle: {
                barBorderRadius: [4, 4, 0, 0]
            }
        },
        pie: {
            itemStyle: {
                borderRadius: 4,
                borderColor: '#1A1D27',
                borderWidth: 2
            }
        },
        categoryAxis: {
            axisLine: {
                lineStyle: {
                    color: '#2A2D37',
                    width: 1
                }
            },
            axisTick: {
                lineStyle: {
                    color: '#2A2D37'
                }
            },
            axisLabel: {
                color: '#6B7280',
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            splitLine: {
                lineStyle: {
                    color: '#2A2D37',
                    type: 'solid'
                }
            },
            splitArea: {
                show: false
            }
        },
        valueAxis: {
            axisLine: {
                lineStyle: {
                    color: '#2A2D37',
                    width: 1
                }
            },
            axisTick: {
                lineStyle: {
                    color: '#2A2D37'
                }
            },
            axisLabel: {
                color: '#6B7280',
                fontFamily: "'JetBrains Mono', ui-monospace, monospace"
            },
            splitLine: {
                lineStyle: {
                    color: '#2A2D37',
                    type: 'solid'
                }
            },
            splitArea: {
                show: false
            }
        },
        tooltip: {
            backgroundColor: '#1A1D27',
            borderColor: '#2A2D37',
            borderWidth: 1,
            textStyle: {
                color: '#E8EAED',
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.3); border-radius: 8px;'
        },
        legend: {
            textStyle: {
                color: '#9AA0A6',
                fontFamily: "'Inter', 'PingFang SC', system-ui, -apple-system, sans-serif"
            },
            pageTextStyle: {
                color: '#6B7280'
            }
        },
        color: [
            '#818CF8',
            '#FF6B6B',
            '#6BCB77',
            '#FFD666',
            '#4DABF7',
            '#B197FC',
            '#3BC9DB',
            '#F783AC',
            '#FFA94D',
            '#A9E34B'
        ],
        watercolorColors: {
            blue: '#818CF8',
            blueLight: '#A5B4FC',
            neutral: '#6B7280',
            greenLight: '#6BCB77',
            terracotta: '#FF6B6B',
            terracottaLight: '#FFA8A8',
            lavender: '#B197FC',
            lavenderLight: '#D0BFFF',
            peach: '#FFA94D',
            peachLight: '#FFD8A8',
            up: '#FF6B6B',
            upLight: '#FFA8A8',
            down: '#6BCB77',
            downLight: '#A9E34B'
        }
    };
};

ATMChart.getResponsiveHeight = function(baseHeight) {
    var width = window.innerWidth;
    var dpr = window.devicePixelRatio || 1;
    
    if (width < 480) {
        return Math.min(baseHeight * 0.7, 280);
    } else if (width < 640) {
        return Math.min(baseHeight * 0.85, 350);
    } else if (width < 1024) {
        return Math.min(baseHeight * 0.9, 400);
    }
    return baseHeight;
};

ATMChart.getResponsiveFontSize = function(baseSize) {
    var width = window.innerWidth;
    
    if (width < 480) {
        return Math.max(baseSize * 0.85, 10);
    } else if (width < 640) {
        return Math.max(baseSize * 0.9, 11);
    }
    return baseSize;
};

ATMChart.getResponsiveOption = function(option, containerId) {
    var width = window.innerWidth;
    var isMobile = width < 640;
    var isSmallMobile = width < 480;
    
    var responsiveOption = JSON.parse(JSON.stringify(option));
    
    if (responsiveOption.title && responsiveOption.title.textStyle) {
        responsiveOption.title.textStyle.fontSize = this.getResponsiveFontSize(responsiveOption.title.textStyle.fontSize || 16);
    }
    
    if (responsiveOption.xAxis) {
        var xAxis = Array.isArray(responsiveOption.xAxis) ? responsiveOption.xAxis : [responsiveOption.xAxis];
        xAxis.forEach(function(axis) {
            if (axis.axisLabel) {
                axis.axisLabel.fontSize = ATMChart.getResponsiveFontSize(axis.axisLabel.fontSize || 12);
                if (isSmallMobile) {
                    axis.axisLabel.rotate = 45;
                    axis.axisLabel.interval = 'auto';
                }
            }
        });
    }
    
    if (responsiveOption.yAxis) {
        var yAxis = Array.isArray(responsiveOption.yAxis) ? responsiveOption.yAxis : [responsiveOption.yAxis];
        yAxis.forEach(function(axis) {
            if (axis.axisLabel) {
                axis.axisLabel.fontSize = ATMChart.getResponsiveFontSize(axis.axisLabel.fontSize || 12);
            }
        });
    }
    
    if (responsiveOption.legend) {
        if (responsiveOption.legend.textStyle) {
            responsiveOption.legend.textStyle.fontSize = this.getResponsiveFontSize(responsiveOption.legend.textStyle.fontSize || 12);
        }
        if (isMobile) {
            responsiveOption.legend.top = 'bottom';
            responsiveOption.legend.left = 'center';
            responsiveOption.legend.orient = 'horizontal';
        }
    }
    
    if (responsiveOption.tooltip && responsiveOption.tooltip.textStyle) {
        responsiveOption.tooltip.textStyle.fontSize = this.getResponsiveFontSize(responsiveOption.tooltip.textStyle.fontSize || 12);
    }
    
    if (responsiveOption.grid) {
        if (isMobile) {
            responsiveOption.grid.left = '8%';
            responsiveOption.grid.right = '8%';
            responsiveOption.grid.bottom = responsiveOption.legend ? '20%' : '12%';
            responsiveOption.grid.top = '15%';
        }
    }
    
    return responsiveOption;
};

ATMChart.setResponsiveHeight = function(containerId, baseHeight) {
    var el = document.getElementById(containerId);
    if (!el) return;
    
    var height = this.getResponsiveHeight(baseHeight);
    el.style.height = height + 'px';
    el.style.minHeight = height + 'px';
    
    var chart = this._instances.get(el);
    if (chart && !chart.isDisposed()) {
        chart.resize();
    }
};

ATMChart.setupResponsiveChart = function(containerId, baseHeight, option) {
    var self = this;
    
    this.setResponsiveHeight(containerId, baseHeight);
    
    var responsiveOption = this.getResponsiveOption(option, containerId);
    
    var chart = this.init(containerId);
    if (chart) {
        chart.setOption(responsiveOption);
    }
    
    var resizeTimer;
    var resizeHandler = function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            self.setResponsiveHeight(containerId, baseHeight);
            var newOption = self.getResponsiveOption(option, containerId);
            var chartInstance = self._instances.get(document.getElementById(containerId));
            if (chartInstance && !chartInstance.isDisposed()) {
                chartInstance.setOption(newOption, true);
                chartInstance.resize();
            }
        }, 150);
    };
    
    window.addEventListener('resize', resizeHandler);
    
    if (screen.orientation) {
        screen.orientation.addEventListener('change', function() {
            setTimeout(resizeHandler, 300);
        });
    }
    
    return chart;
};

ATMChart.exportImage = function(containerId, filename) {
    var el = document.getElementById(containerId);
    if (!el) return;
    var chart = this._instances.get(el);
    if (!chart || chart.isDisposed()) return;
    var url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' });
    var a = document.createElement('a');
    a.href = url;
    a.download = filename || 'chart.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
};

/**
 * Calculate moving average for K-line data.
 * @param {number} dayCount - MA period (e.g. 5, 10, 20, 60)
 * @param {Array} data - K-line data array, each item as [date, open, close, low, high, volume, ...]
 * @returns {Array} MA values (strings for insufficient data, numbers otherwise)
 */
ATMChart.calculateMA = function(dayCount, data) {
    var result = [];
    for (var i = 0, len = data.length; i < len; i++) {
        if (i < dayCount - 1) {
            result.push('-');
            continue;
        }
        var sum = 0;
        for (var j = i - dayCount + 1; j <= i; j++) {
            sum += data[j][1]; // close price
        }
        result.push(+(sum / dayCount).toFixed(2));
    }
    return result;
};

/**
 * Build a complete K-line chart option with overlayed moving averages.
 * @param {Array} klineData - K-line data array, each item as [date, open, close, low, high, volume, ...]
 * @param {Array} maDays - MA periods to display (default [5, 10, 20, 60])
 * @returns {Object} ECharts option
 */
ATMChart.buildKlineOption = function(klineData, maDays) {
    maDays = maDays || [5, 10, 20, 60];
    var theme = ATMChart.getChartTheme();
    var maColors = ['#0a0a0a', '#737373', '#a1a1a1', '#16A34A'];
    var dateData = klineData.map(function(item) { return item[0]; });
    var ohlcData = klineData.map(function(item) {
        return [item[1], item[3], item[4], item[2]]; // [open, close, low, high]
    });
    var volumeData = klineData.map(function(item) { return item[5] || 0; });

    var series = [
        {
            name: 'K-Line',
            type: 'candlestick',
            data: ohlcData,
            itemStyle: {
                color: theme.upColor,
                color0: theme.downColor,
                borderColor: theme.upColor,
                borderColor0: theme.downColor
            },
            markLine: {
                silent: true,
                symbol: 'none',
                lineStyle: { color: '#999', type: 'dashed', width: 1 }
            }
        }
    ];

    // Add MA lines
    maDays.forEach(function(day, idx) {
        series.push({
            name: 'MA' + day,
            type: 'line',
            data: ATMChart.calculateMA(day, klineData),
            smooth: true,
            lineStyle: { width: 1.5, color: maColors[idx % maColors.length] },
            symbol: 'none',
            connectNulls: false,
            z: 2
        });
    });

    return {
        backgroundColor: theme.backgroundColor,
        animation: true,
        legend: {
            data: ['K-Line'].concat(maDays.map(function(d) { return 'MA' + d; })),
            top: 3,
            left: 'center',
            textStyle: theme.legend.textStyle,
            icon: 'rect',
            itemWidth: 14,
            itemHeight: 8
        },
        grid: [
            {
                left: '6%',
                right: '6%',
                top: '12%',
                height: '55%',
                containLabel: true
            },
            {
                left: '6%',
                right: '6%',
                top: '75%',
                height: '16%',
                containLabel: true
            }
        ],
        xAxis: [
            {
                type: 'category',
                data: dateData,
                axisLine: { lineStyle: { color: theme.axisLineColor } },
                axisLabel: { color: theme.axisLabelColor, fontSize: 10 },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax',
                boundaryGap: true
            },
            {
                type: 'category',
                gridIndex: 1,
                data: dateData,
                axisLabel: { show: false },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { show: false }
            }
        ],
        yAxis: [
            {
                type: 'value',
                scale: true,
                axisLine: { lineStyle: { color: theme.axisLineColor } },
                axisLabel: { color: theme.axisLabelColor, fontSize: 10 },
                splitLine: { lineStyle: { color: theme.splitLineColor, type: 'solid' } }
            },
            {
                type: 'value',
                gridIndex: 1,
                scale: true,
                axisLabel: { show: false },
                splitLine: { show: false }
            }
        ],
        dataZoom: [
            { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
            { type: 'slider', xAxisIndex: [0, 1], start: 50, end: 100, height: 10, bottom: 2 }
        ],
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: theme.tooltip.backgroundColor,
            borderColor: theme.tooltip.borderColor,
            borderWidth: theme.tooltip.borderWidth,
            textStyle: theme.tooltip.textStyle,
            extraCssText: theme.tooltip.extraCssText,
            formatter: function(params) {
                var candlestick = params[0];
                if (!candlestick) return '';
                var d = candlestick.value || candlestick.data;
                var html = '<strong>' + candlestick.axisValue + '</strong><br/>';
                if (d && d.length >= 4) {
                    html += 'Open: ' + d[0].toFixed(2) + '<br/>';
                    html += 'Close: ' + d[1].toFixed(2) + '<br/>';
                    html += 'Low: ' + d[2].toFixed(2) + '<br/>';
                    html += 'High: ' + d[3].toFixed(2) + '<br/>';
                }
                params.slice(1).forEach(function(p) {
                    if (p.value && p.value !== '-') {
                        html += p.marker + ' ' + p.seriesName + ': ' + p.value + '<br/>';
                    }
                });
                return html;
            }
        },
        series: series
    };
};

/* ── Back to top button ── */
(function() {
    var btn = document.createElement('button');
    btn.className = 'back-to-top';
    btn.setAttribute('aria-label', 'Back to top');
    btn.setAttribute('title', 'Back to top');
    btn.innerHTML = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/></svg>';
    document.body.appendChild(btn);

    var ticking = false;
    function updateVisibility() {
        var scrollY = window.scrollY || window.pageYOffset;
        if (scrollY > 400) {
            btn.classList.add('visible');
        } else {
            btn.classList.remove('visible');
        }
        ticking = false;
    }

    window.addEventListener('scroll', function() {
        if (!ticking) {
            requestAnimationFrame(updateVisibility);
            ticking = true;
        }
    }, { passive: true });

    btn.addEventListener('click', function() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
})();

})();
