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

})();

(function() {
// Source: utils.js
var ATM = ATM || {};

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
    return parseFloat(v).toLocaleString('zh-CN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
};

ATM.formatAmount = function(val) {
    if (!val) return '--';
    var v = parseFloat(val);
    if (Math.abs(v) >= 100000000) return (v / 100000000).toFixed(2) + '亿';
    if (Math.abs(v) >= 10000) return (v / 10000).toFixed(0) + '万';
    return v.toFixed(0);
};

ATM.formatVol = function(val) {
    if (!val) return '--';
    var v = parseFloat(val);
    if (v >= 100000000) return (v / 100000000).toFixed(2) + '亿手';
    if (v >= 10000) return (v / 10000).toFixed(0) + '万手';
    return v.toFixed(0) + '手';
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
    if (v >= 10000) return (v / 10000).toFixed(1) + '万亿';
    if (v >= 100) return (v / 100).toFixed(1) + '百亿';
    return v.toFixed(0) + '亿';
};

ATM.rankBadge = function(i) {
    var cls = i < 3 ? 'rank-' + (i + 1) : 'rank-other';
    return '<span class="rank-badge ' + cls + '">' + (i + 1) + '</span>';
};

ATM.dataStatus = function(d) {
    if (!d.exists || d.count === 0) return { tag: '空', color: 'var(--c-up)', need: true };
    if (!d.max_date) return { tag: '有数据', color: 'var(--c-gold)', need: false };
    var maxD = ATM._parseDate(d.max_date);
    var now = new Date();
    var tradingToday = ATM._lastTradingDate(now);
    var diffTrading = ATM._tradingDaysBetween(maxD, tradingToday);
    if (diffTrading === 0) return { tag: '最新', color: 'var(--c-down)', need: false };
    if (diffTrading <= 1) return { tag: '最新', color: 'var(--c-down)', need: false };
    if (diffTrading <= 5) return { tag: '滞后' + diffTrading + '个交易日', color: 'var(--c-gold)', need: true };
    return { tag: '过期', color: 'var(--c-up)', need: true };
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
    return {
        backgroundColor: 'transparent',
        textStyle: {
            color: '#6b6560',
            fontFamily: '"Noto Serif SC", "Source Han Serif SC", Georgia, serif'
        },
        title: {
            textStyle: {
                color: '#3a3632',
                fontWeight: 700
            }
        },
        legend: {
            textStyle: {
                color: '#6b6560',
                fontSize: 12
            },
            icon: 'roundRect',
            itemWidth: 14,
            itemHeight: 8
        },
        tooltip: {
            backgroundColor: 'rgba(50, 46, 42, 0.94)',
            borderColor: 'rgba(107, 143, 163, 0.3)',
            borderWidth: 1,
            textStyle: {
                color: '#f5f0e6',
                fontSize: 12
            },
            extraCssText: 'box-shadow:0 4px 16px rgba(58,54,50,0.15);border-radius:4px;'
        },
        splitLineColor: 'rgba(212, 207, 196, 0.6)',
        axisLabelColor: '#9e9689',
        axisLineColor: 'rgba(212, 207, 196, 0.5)',
        upColor: '#c45c5c',
        upColor0: 'rgba(196, 92, 92, 0.12)',
        downColor: '#5a9470',
        downColor0: 'rgba(90, 148, 112, 0.12)',
        accentColor: '#6b8fa3',
        accentLight: 'rgba(107, 143, 163, 0.15)',
        seriesColors: [
            '#6b8fa3', '#8cb89c', '#b8845a', '#a08070',
            '#c45c5c', '#5a9470', '#7a9078', '#9c8a7a'
        ]
    };
};

})();

(function() {
// Source: nav.js
var ATMNav = ATMNav || {};

ATMNav.render = function(activePage) {
    var links = [
        { href: '/stock/', label: '个股查询', id: 'stock', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>' },
        { href: '/etf', label: '指数ETF', id: 'etf', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>' },
        { href: '/sector', label: '行业ETF', id: 'sector', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>' },
        { href: '/concept', label: '概念轮动', id: 'concept', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>' },
        { href: '/industry', label: '申万行业', id: 'industry', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>' },
        { href: '/stocks', label: '个股排行', id: 'stocks', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/></svg>' },
        { href: '/barra', label: 'BARRA分析', id: 'barra', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>' }
    ];

    var navLinksHtml = links.map(function(l) {
        var isActive = l.id === activePage;
        var cls = 'nav-link' + (isActive ? ' active' : '');
        var ariaCurrent = isActive ? ' aria-current="page"' : '';
        return '<a href="' + l.href + '" class="' + cls + '"' + ariaCurrent + '>' + l.label + '</a>';
    }).join('');

    var bottomNavItems = [
        { href: '/', label: '首页', id: 'home', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>' },
        { href: '/etf', label: 'ETF', id: 'etf', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>' },
        { href: '/sector', label: '行业', id: 'sector', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>' },
        { href: '/stocks', label: '排行', id: 'stocks', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/></svg>' },
        { href: 'javascript:void(0)', label: '更多', id: 'more', icon: '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>', isMore: true }
    ];

    var bottomNavHtml = bottomNavItems.map(function(item) {
        var isActive = item.id === activePage;
        var cls = 'bottom-nav-item' + (isActive ? ' active' : '');
        var ariaCurrent = isActive ? ' aria-current="page"' : '';
        var clickHandler = item.isMore ? ' onclick="ATMNav.toggleMobile(); return false;"' : '';
        return '<a href="' + item.href + '" class="' + cls + '"' + ariaCurrent + clickHandler + '>' +
            '<span class="bottom-nav-icon" aria-hidden="true">' + item.icon + '</span>' +
            '<span class="bottom-nav-label">' + item.label + '</span>' +
        '</a>';
    }).join('');

    return '<nav role="navigation" aria-label="主导航">' +
        '<div class="nav-container">' +
            '<a href="/" class="nav-logo" aria-label="ATMstockMarket 首页">' +
                '<div class="nav-logo-icon" aria-hidden="true">A</div>' +
                '<span>ATM<span style="color:var(--c-accent);">stock</span>Market</span>' +
            '</a>' +
            '<span id="nav-freshness" class="nav-freshness" style="display:none;"></span>' +
            '<button class="mobile-menu-btn" onclick="ATMNav.toggleMobile()" aria-label="打开菜单" aria-expanded="false" aria-controls="nav-links" id="mobile-menu-btn">' +
                '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>' +
            '</button>' +
            '<div class="nav-links" id="nav-links" role="menubar" aria-label="页面导航">' + navLinksHtml + '</div>' +
        '</div>' +
    '</nav>' +
    '<div class="mobile-overlay" id="mobile-overlay" onclick="ATMNav.toggleMobile()" role="presentation"></div>' +
    '<nav class="bottom-nav" role="navigation" aria-label="移动端主导航">' + bottomNavHtml + '</nav>';
};

ATMNav.toggleMobile = function(forceClose) {
    var navLinks = document.getElementById('nav-links');
    var overlay = document.getElementById('mobile-overlay');
    var btn = document.getElementById('mobile-menu-btn');
    // Guard: bail if nav-links is missing (page may have errored)
    if (!navLinks) { console.warn('nav-links element not found'); return; }
    var isOpen = forceClose ? false : navLinks.classList.toggle('open');
    if (forceClose) {
        navLinks.classList.remove('open');
        if (overlay) overlay.classList.remove('active');
    } else {
        if (overlay) overlay.classList.toggle('active');
    }
    if (btn) {
        btn.setAttribute('aria-expanded', isOpen.toString());
        btn.setAttribute('aria-label', isOpen ? '关闭菜单' : '打开菜单');
    }
    if (isOpen) {
        var firstLink = navLinks.querySelector('a');
        if (firstLink) firstLink.focus();
    }
    // Prevent body scroll when overlay is active
    document.body.style.overflow = isOpen ? 'hidden' : '';
};

ATMNav.handleKeydown = function(e) {
    if (e.key === 'Escape') {
        var navLinks = document.getElementById('nav-links');
        if (navLinks && navLinks.classList.contains('open')) {
            ATMNav.toggleMobile();
            document.getElementById('mobile-menu-btn')?.focus();
        }
    }
};

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        ATMNav.handleKeydown(e);
    }
});

// Close mobile menu on navigation
document.addEventListener('click', function(e) {
    var navLink = e.target.closest('.nav-link, .bottom-nav-item');
    if (navLink) {
        var overlay = document.getElementById('mobile-overlay');
        if (overlay && overlay.classList.contains('active')) {
            ATMNav.toggleMobile(true);
        }
    }
});

// Re-attach after any AJAX refresh
document.addEventListener('DOMContentLoaded', function() {
    var overlay = document.getElementById('mobile-overlay');
    if (overlay) {
        overlay.addEventListener('click', function() { ATMNav.toggleMobile(true); });
    }
});

ATMNav.insert = function(containerId, activePage) {
    var el = document.getElementById(containerId);
    if (el) {
        el.innerHTML = this.render(activePage);
        ATMNav.applyTheme();
        ATMNav.loadFreshness();
        // Re-attach overlay close
        var overlay = document.getElementById('mobile-overlay');
        if (overlay) {
            overlay.addEventListener('click', function() { ATMNav.toggleMobile(true); });
        }
    }
};

// ── P3.2: Data freshness badge ──
ATMNav.loadFreshness = function() {
    fetch('/health').then(function(r) { return r.json(); }).then(function(d) {
        var el = document.getElementById('nav-freshness');
        if (!el) return;
        var dbMax = (d.checks && d.checks.data_freshness && d.checks.data_freshness.db_max_date) || '';
        if (dbMax) {
            el.textContent = '数据: ' + (dbMax.slice(0,4)+'-'+dbMax.slice(4,6)+'-'+dbMax.slice(6,8));
            el.style.display = '';
            el.style.color = d.checks.data_freshness.status === 'ok'
                ? 'var(--c-down)' : 'var(--c-gold)';
        }
    }).catch(function() {});
};

// ── P3.1: Theme toggle with localStorage persistence ──
ATMNav.THEME_KEY = 'atm-theme';

ATMNav.getTheme = function() {
    var stored = localStorage.getItem(ATMNav.THEME_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

ATMNav.applyTheme = function() {
    var theme = ATMNav.getTheme();
    document.documentElement.dataset.theme = theme;
    var btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.innerHTML = theme === 'dark'
            ? '<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path stroke-linecap="round" d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
            : '<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>';
        btn.setAttribute('aria-label', theme === 'dark' ? '切换到浅色模式' : '切换到深色模式');
    }
};

ATMNav.toggleTheme = function() {
    var current = localStorage.getItem(ATMNav.THEME_KEY) || 'light';
    var next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem(ATMNav.THEME_KEY, next);
    ATMNav.applyTheme();
    // Notify other scripts
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: next }));
};

})();

(function() {
// Source: theme.js
var ATMTheme = ATMTheme || {};

ATMTheme.init = function() {
    var saved = localStorage.getItem('atm-theme');
    var preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    var theme = saved || preferred;
    document.documentElement.dataset.theme = theme;
    this._updateIcon(theme);

    var self = this;
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (!localStorage.getItem('atm-theme')) {
            var t = e.matches ? 'dark' : 'light';
            document.documentElement.dataset.theme = t;
            self._updateIcon(t);
            self._notifyCharts();
        }
    });
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
        btn.setAttribute('title', '切换到亮色模式');
    } else {
        btn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>';
        btn.setAttribute('title', '切换到暗色模式');
    }
};

ATMTheme._notifyCharts = function() {
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: { theme: this.get() } }));
};

ATMTheme.init();

})();

(function() {
// Source: cache.js
var ATMCache = ATMCache || {};

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

var ATMRouter = ATMRouter || {};

ATMRouter._initialized = false;
ATMRouter._isMobile = function() {
    return window.innerWidth < 768;
};

ATMRouter.init = function() {
    if (ATMRouter._initialized) return;
    ATMRouter._initialized = true;
    
    if (ATMRouter._isMobile()) {
        ATMRouter._setupPrefetch();
    }
    
    ATMRouter._setupPageTransition();
};

ATMRouter._setupPrefetch = function() {
    var navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(function(link) {
        link.addEventListener('touchstart', function(e) {
            var href = this.getAttribute('href');
            if (href && !href.startsWith('#')) {
                ATMRouter._prefetch(href);
            }
        }, { passive: true });
        
        link.addEventListener('mouseenter', function(e) {
            var href = this.getAttribute('href');
            if (href && !href.startsWith('#')) {
                ATMRouter._prefetch(href);
            }
        });
    });
};

ATMRouter._prefetch = function(url) {
    var cacheKey = 'prefetch_' + url.replace(/[^a-zA-Z0-9]/g, '_');
    if (ATMCache.get(cacheKey)) return;
    
    ATMCache.set(cacheKey, true, 60000);
    
    if (url.startsWith('/api/')) {
        ATMCache.api(url, { ttl: 60000 });
    }
};

ATMRouter._setupPageTransition = function() {
    document.body.classList.add('page-ready');
    
    if (ATMRouter._isMobile()) {
        document.body.classList.add('page-transition');
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ATMRouter.init);
} else {
    ATMRouter.init();
}

})();

(function() {
// Source: perf.js
var ATMPerf = ATMPerf || {};

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
var ATMPerf = ATMPerf || {};

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
    var criticalResources = [
        '/static/css/tokens-wiki.css',
        '/static/css/style-wiki.css',
        '/static/css/components-wiki.css'
    ];
    
    criticalResources.forEach(function(url) {
        var link = document.createElement('link');
        link.rel = 'preload';
        link.as = url.endsWith('.css') ? 'style' : 'script';
        link.href = url;
        document.head.appendChild(link);
    });
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
var ATMMobile = ATMMobile || {};

ATMMobile.isMobile = function() {
    return window.innerWidth < 768;
};

ATMMobile.isTablet = function() {
    return window.innerWidth >= 768 && window.innerWidth < 1024;
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
    filterHtml += '<span>筛选</span>';
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
    filterHtml += '<button class="btn btn-secondary" onclick="ATMMobile.resetFilter(\'' + containerId + '\')">重置</button>';
    filterHtml += '<button class="btn btn-primary" onclick="ATMMobile.applyFilter(\'' + containerId + '\')">应用</button>';
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
// Source: gestures.js
var ATMGesture = ATMGesture || {};

ATMGesture.isTouchDevice = function() {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
};

ATMGesture.SwipeDetector = function(element, options) {
    var self = this;
    this.element = typeof element === 'string' ? document.getElementById(element) : element;
    this.options = Object.assign({
        threshold: 50,
        velocityThreshold: 0.3,
        preventDefaultTouch: false,
        onSwipeLeft: null,
        onSwipeRight: null,
        onSwipeUp: null,
        onSwipeDown: null
    }, options || {});
    
    this.startX = 0;
    this.startY = 0;
    this.startTime = 0;
    
    this.handleTouchStart = function(e) {
        var touch = e.touches[0];
        self.startX = touch.clientX;
        self.startY = touch.clientY;
        self.startTime = Date.now();
        
        if (self.options.preventDefaultTouch) {
            e.preventDefault();
        }
    };
    
    this.handleTouchEnd = function(e) {
        if (e.touches.length > 0) return;
        
        var touch = e.changedTouches[0];
        var deltaX = touch.clientX - self.startX;
        var deltaY = touch.clientY - self.startY;
        var deltaTime = Date.now() - self.startTime;
        var velocityX = Math.abs(deltaX) / deltaTime;
        var velocityY = Math.abs(deltaY) / deltaTime;
        
        if (Math.abs(deltaX) > self.options.threshold && velocityX > self.options.velocityThreshold) {
            if (deltaX > 0 && self.options.onSwipeRight) {
                self.options.onSwipeRight(deltaX, velocityX);
            } else if (deltaX < 0 && self.options.onSwipeLeft) {
                self.options.onSwipeLeft(deltaX, velocityX);
            }
        }
        
        if (Math.abs(deltaY) > self.options.threshold && velocityY > self.options.velocityThreshold) {
            if (deltaY > 0 && self.options.onSwipeDown) {
                self.options.onSwipeDown(deltaY, velocityY);
            } else if (deltaY < 0 && self.options.onSwipeUp) {
                self.options.onSwipeUp(deltaY, velocityY);
            }
        }
    };
    
    this.enable = function() {
        self.element.addEventListener('touchstart', self.handleTouchStart, { passive: !self.options.preventDefaultTouch });
        self.element.addEventListener('touchend', self.handleTouchEnd, { passive: true });
    };
    
    this.disable = function() {
        self.element.removeEventListener('touchstart', self.handleTouchStart);
        self.element.removeEventListener('touchend', self.handleTouchEnd);
    };
    
    this.enable();
};

ATMGesture.PinchDetector = function(element, options) {
    var self = this;
    this.element = typeof element === 'string' ? document.getElementById(element) : element;
    this.options = Object.assign({
        threshold: 1.2,
        onPinchIn: null,
        onPinchOut: null,
        onPinchMove: null
    }, options || {});
    
    this.initialDistance = 0;
    this.lastDistance = 0;
    
    this.getDistance = function(touch1, touch2) {
        var dx = touch1.clientX - touch2.clientX;
        var dy = touch1.clientY - touch2.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    };
    
    this.handleTouchStart = function(e) {
        if (e.touches.length === 2) {
            self.initialDistance = self.getDistance(e.touches[0], e.touches[1]);
            self.lastDistance = self.initialDistance;
        }
    };
    
    this.handleTouchMove = function(e) {
        if (e.touches.length === 2) {
            var currentDistance = self.getDistance(e.touches[0], e.touches[1]);
            var scale = currentDistance / self.initialDistance;
            var deltaScale = currentDistance / self.lastDistance;
            
            if (self.options.onPinchMove) {
                self.options.onPinchMove(scale, deltaScale);
            }
            
            if (scale > self.options.threshold && self.options.onPinchOut) {
                self.options.onPinchOut(scale);
            } else if (scale < 1 / self.options.threshold && self.options.onPinchIn) {
                self.options.onPinchIn(scale);
            }
            
            self.lastDistance = currentDistance;
        }
    };
    
    this.enable = function() {
        self.element.addEventListener('touchstart', self.handleTouchStart, { passive: true });
        self.element.addEventListener('touchmove', self.handleTouchMove, { passive: true });
    };
    
    this.disable = function() {
        self.element.removeEventListener('touchstart', self.handleTouchStart);
        self.element.removeEventListener('touchmove', self.handleTouchMove);
    };
    
    this.enable();
};

ATMGesture.PullToRefresh = function(element, options) {
    var self = this;
    this.element = typeof element === 'string' ? document.getElementById(element) : element;
    this.options = Object.assign({
        threshold: 80,
        onRefresh: null,
        indicator: null
    }, options || {});
    
    this.startY = 0;
    this.pulling = false;
    this.refreshing = false;
    
    this.handleTouchStart = function(e) {
        if (self.element.scrollTop === 0 && !self.refreshing) {
            self.startY = e.touches[0].clientY;
            self.pulling = true;
        }
    };
    
    this.handleTouchMove = function(e) {
        if (!self.pulling || self.refreshing) return;
        
        var currentY = e.touches[0].clientY;
        var deltaY = currentY - self.startY;
        
        if (deltaY > 0) {
            e.preventDefault();
            
            var progress = Math.min(deltaY / self.options.threshold, 1);
            
            if (self.options.indicator) {
                self.options.indicator.style.transform = 'translateY(' + (deltaY * 0.5) + 'px)';
                self.options.indicator.style.opacity = progress;
            }
            
            if (deltaY > self.options.threshold && self.options.onRefresh) {
                self.refreshing = true;
                self.options.onRefresh().then(function() {
                    self.refreshing = false;
                    self.pulling = false;
                    if (self.options.indicator) {
                        self.options.indicator.style.transform = '';
                        self.options.indicator.style.opacity = 0;
                    }
                });
            }
        }
    };
    
    this.handleTouchEnd = function(e) {
        self.pulling = false;
        if (self.options.indicator && !self.refreshing) {
            self.options.indicator.style.transform = '';
            self.options.indicator.style.opacity = 0;
        }
    };
    
    this.enable = function() {
        self.element.addEventListener('touchstart', self.handleTouchStart, { passive: true });
        self.element.addEventListener('touchmove', self.handleTouchMove, { passive: false });
        self.element.addEventListener('touchend', self.handleTouchEnd, { passive: true });
    };
    
    this.disable = function() {
        self.element.removeEventListener('touchstart', self.handleTouchStart);
        self.element.removeEventListener('touchmove', self.handleTouchMove);
        self.element.removeEventListener('touchend', self.handleTouchEnd);
    };
    
    this.enable();
};

ATMGesture.enableChartGestures = function(chartContainerId) {
    var container = document.getElementById(chartContainerId);
    if (!container) return;
    if (typeof echarts === 'undefined') { console.warn('ECharts not loaded, gestures disabled'); return; }
    
    var pinchDetector = new ATMGesture.PinchDetector(container, {
        onPinchOut: function(scale) {
            var chart = echarts.getInstanceByDom(container);
            if (chart) {
                var option = chart.getOption();
                if (option.dataZoom && option.dataZoom.length > 0) {
                    var zoom = option.dataZoom[0];
                    var newStart = Math.max(0, zoom.start - 5);
                    var newEnd = Math.min(100, zoom.end + 5);
                    chart.dispatchAction({
                        type: 'dataZoom',
                        start: newStart,
                        end: newEnd
                    });
                }
            }
        },
        onPinchIn: function(scale) {
            var chart = echarts.getInstanceByDom(container);
            if (chart) {
                var option = chart.getOption();
                if (option.dataZoom && option.dataZoom.length > 0) {
                    var zoom = option.dataZoom[0];
                    var newStart = Math.min(50, zoom.start + 5);
                    var newEnd = Math.max(50, zoom.end - 5);
                    chart.dispatchAction({
                        type: 'dataZoom',
                        start: newStart,
                        end: newEnd
                    });
                }
            }
        }
    });
    
    var swipeDetector = new ATMGesture.SwipeDetector(container, {
        onSwipeLeft: function() {
            var chart = echarts.getInstanceByDom(container);
            if (chart) {
                chart.dispatchAction({
                    type: 'dataZoom',
                    dataRangeIndex: 0,
                    startValue: 'next'
                });
            }
        },
        onSwipeRight: function() {
            var chart = echarts.getInstanceByDom(container);
            if (chart) {
                chart.dispatchAction({
                    type: 'dataZoom',
                    dataRangeIndex: 0,
                    startValue: 'prev'
                });
            }
        }
    });
    
    return {
        pinch: pinchDetector,
        swipe: swipeDetector
    };
};

ATMGesture.enableTableGestures = function(tableContainerId) {
    var container = document.getElementById(tableContainerId);
    if (!container) return;
    
    var swipeDetector = new ATMGesture.SwipeDetector(container, {
        threshold: 30,
        onSwipeLeft: function() {
            container.scrollBy({ left: 200, behavior: 'smooth' });
        },
        onSwipeRight: function() {
            container.scrollBy({ left: -200, behavior: 'smooth' });
        }
    });
    
    return swipeDetector;
};

})();

(function() {
// Source: chart-loader.js
var ATMChart = ATMChart || {};

ATMChart._loaded = null;

ATMChart.load = function() {
    if (ATMChart._loaded) return ATMChart._loaded;
    if (typeof echarts !== 'undefined') {
        ATMChart._loaded = Promise.resolve(echarts);
        return ATMChart._loaded;
    }
    ATMChart._loaded = new Promise(function(resolve, reject) {
        var script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js';
        script.async = true;
        script.defer = true;
        script.onload = function() {
            resolve(echarts);
        };
        script.onerror = function() {
            reject(new Error('Failed to load ECharts from CDN'));
        };
        document.head.appendChild(script);
    });
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

    window.addEventListener('beforeunload', function() {
        ATMChart.disposeAll();
    });
};

ATMChart.getChartTheme = function() {
    return {
        backgroundColor: 'transparent',
        textStyle: {
            fontFamily: "'Noto Serif SC', 'Source Han Serif SC', Georgia, serif",
            fontSize: 12,
            color: '#3D3D3D'
        },
        title: {
            textStyle: {
                color: '#2C2C2C',
                fontWeight: 600,
                fontFamily: "'Noto Serif SC', serif"
            },
            subtextStyle: {
                color: '#5C5C5C'
            }
        },
        line: {
            itemStyle: {
                borderWidth: 2
            },
            lineStyle: {
                width: 2,
                shadowColor: 'rgba(60, 60, 60, 0.1)',
                shadowBlur: 4,
                shadowOffsetY: 2
            },
            symbolSize: 6,
            symbol: 'circle',
            smooth: true
        },
        bar: {
            itemStyle: {
                barBorderRadius: [4, 4, 0, 0],
                shadowColor: 'rgba(60, 60, 60, 0.08)',
                shadowBlur: 4,
                shadowOffsetY: 2
            }
        },
        pie: {
            itemStyle: {
                borderRadius: 4,
                borderColor: '#FAF6F0',
                borderWidth: 2
            }
        },
        categoryAxis: {
            axisLine: {
                lineStyle: {
                    color: 'rgba(60, 60, 60, 0.2)'
                }
            },
            axisTick: {
                lineStyle: {
                    color: 'rgba(60, 60, 60, 0.15)'
                }
            },
            axisLabel: {
                color: '#5C5C5C',
                fontFamily: "'Noto Serif SC', serif"
            },
            splitLine: {
                lineStyle: {
                    color: 'rgba(60, 60, 60, 0.06)'
                }
            },
            splitArea: {
                areaStyle: {
                    color: ['rgba(126, 184, 201, 0.03)', 'rgba(139, 201, 160, 0.03)']
                }
            }
        },
        valueAxis: {
            axisLine: {
                lineStyle: {
                    color: 'rgba(60, 60, 60, 0.2)'
                }
            },
            axisTick: {
                lineStyle: {
                    color: 'rgba(60, 60, 60, 0.15)'
                }
            },
            axisLabel: {
                color: '#5C5C5C',
                fontFamily: "'JetBrains Mono', monospace"
            },
            splitLine: {
                lineStyle: {
                    color: 'rgba(60, 60, 60, 0.06)',
                    type: 'dashed'
                }
            },
            splitArea: {
                areaStyle: {
                    color: ['rgba(212, 165, 116, 0.02)', 'rgba(184, 169, 201, 0.02)']
                }
            }
        },
        tooltip: {
            backgroundColor: 'rgba(74, 74, 74, 0.95)',
            borderColor: 'rgba(250, 246, 240, 0.2)',
            borderWidth: 1,
            textStyle: {
                color: '#FAF6F0',
                fontFamily: "'Noto Serif SC', serif"
            },
            extraCssText: 'border-radius: 8px; box-shadow: 0 4px 12px rgba(60, 60, 60, 0.15);'
        },
        legend: {
            textStyle: {
                color: '#3D3D3D',
                fontFamily: "'Noto Serif SC', serif"
            },
            pageTextStyle: {
                color: '#5C5C5C'
            }
        },
        color: [
            '#7EB8C9',
            '#D4A574',
            '#8BC9A0',
            '#B8A9C9',
            '#D4726A',
            '#6AAF7C',
            '#F0C4A0',
            '#B5D8E2',
            '#E5C9A8',
            '#D4C9DE'
        ],
        watercolorColors: {
            blue: '#7EB8C9',
            blueLight: '#B5D8E2',
            green: '#8BC9A0',
            greenLight: '#B8DFC5',
            terracotta: '#D4A574',
            terracottaLight: '#E5C9A8',
            lavender: '#B8A9C9',
            lavenderLight: '#D4C9DE',
            peach: '#F0C4A0',
            peachLight: '#F7DCC4',
            up: '#D4726A',
            upLight: '#E8A09A',
            down: '#6AAF7C',
            downLight: '#9DC9A8'
        }
    };
};

ATMChart.getChartThemeDark = ATMChart.getChartTheme;

ATMChart.getResponsiveHeight = function(baseHeight) {
    var width = window.innerWidth;
    var dpr = window.devicePixelRatio || 1;
    
    if (width < 480) {
        return Math.min(baseHeight * 0.7, 280);
    } else if (width < 768) {
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
    } else if (width < 768) {
        return Math.max(baseSize * 0.9, 11);
    }
    return baseSize;
};

ATMChart.getResponsiveOption = function(option, containerId) {
    var width = window.innerWidth;
    var isMobile = width < 768;
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

})();

(function() {
// Source: ink-wash-effects.js
/* ══════════════════════════════════════════════════
   ATMstockMarket — 江南水墨效果
   Ink Wash Painting Effects
   ══════════════════════════════════════════════════ */

(function() {
    'use strict';
    
    /* ══════════════════════════════════════════════════
       水墨晕染效果
       ══════════════════════════════════════════════════ */
    
    class InkWashEffect {
        constructor() {
            this.init();
        }
        
        init() {
            this.addRippleEffect();
            this.addParallaxEffect();
            this.addInkSpreadEffect();
            this.addScrollAnimations();
        }
        
        /* 涟漪效果 */
        addRippleEffect() {
            const rippleElements = document.querySelectorAll('.ripple-effect, .btn, .nav-link');
            
            rippleElements.forEach(el => {
                el.addEventListener('click', (e) => {
                    const rect = el.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    
                    const ripple = document.createElement('span');
                    ripple.className = 'ripple';
                    ripple.style.left = x + 'px';
                    ripple.style.top = y + 'px';
                    
                    el.appendChild(ripple);
                    
                    setTimeout(() => {
                        ripple.remove();
                    }, 600);
                });
            });
        }
        
        /* 视差滚动效果 */
        addParallaxEffect() {
            const parallaxElements = document.querySelectorAll('.ink-wash-bg, .hero-section');
            
            if (parallaxElements.length === 0) return;
            
            let ticking = false;
            
            const updateParallax = () => {
                const scrollY = window.pageYOffset;
                
                parallaxElements.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const speed = el.dataset.parallaxSpeed || 0.5;
                    const yPos = -(scrollY * speed);
                    
                    el.style.transform = `translate3d(0, ${yPos}px, 0)`;
                });
                
                ticking = false;
            };
            
            window.addEventListener('scroll', () => {
                if (!ticking) {
                    requestAnimationFrame(updateParallax);
                    ticking = true;
                }
            }, { passive: true });
        }
        
        /* 水墨扩散效果 */
        addInkSpreadEffect() {
            const cards = document.querySelectorAll('.card, .glass, .ink-card, .screen-card');
            
            const observer = new IntersectionObserver((entries) => {
                entries.forEach((entry, index) => {
                    if (entry.isIntersecting) {
                        setTimeout(() => {
                            entry.target.classList.add('ink-spread-visible');
                        }, index * 100);
                    }
                });
            }, {
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            });
            
            cards.forEach(card => {
                observer.observe(card);
            });
        }
        
        /* 滚动动画 */
        addScrollAnimations() {
            const sections = document.querySelectorAll('section');
            
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('section-visible');
                    }
                });
            }, {
                threshold: 0.1
            });
            
            sections.forEach(section => {
                section.classList.add('section-hidden');
                observer.observe(section);
            });
        }
    }
    
    /* ══════════════════════════════════════════════════
       水墨粒子效果
       ══════════════════════════════════════════════════ */
    
    class InkParticleEffect {
        constructor(container) {
            this.container = container;
            this.particles = [];
            this.maxParticles = 20;
            this.init();
        }
        
        init() {
            if (!this.container) return;
            
            this.createCanvas();
            this.animate();
        }
        
        createCanvas() {
            this.canvas = document.createElement('canvas');
            this.canvas.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                opacity: 0.3;
            `;
            this.ctx = this.canvas.getContext('2d');
            this.container.appendChild(this.canvas);
            
            this.resize();
            window.addEventListener('resize', () => this.resize());
        }
        
        resize() {
            this.canvas.width = this.container.offsetWidth;
            this.canvas.height = this.container.offsetHeight;
        }
        
        createParticle() {
            return {
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                radius: Math.random() * 2 + 1,
                opacity: Math.random() * 0.5 + 0.2,
                speedX: (Math.random() - 0.5) * 0.5,
                speedY: (Math.random() - 0.5) * 0.5,
                color: Math.random() > 0.5 ? '#3d7a8c' : '#a67c52'
            };
        }
        
        animate() {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            
            if (this.particles.length < this.maxParticles) {
                this.particles.push(this.createParticle());
            }
            
            this.particles.forEach((p, index) => {
                p.x += p.speedX;
                p.y += p.speedY;
                
                if (p.x < 0 || p.x > this.canvas.width || 
                    p.y < 0 || p.y > this.canvas.height) {
                    this.particles[index] = this.createParticle();
                }
                
                this.ctx.beginPath();
                this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                this.ctx.fillStyle = p.color;
                this.ctx.globalAlpha = p.opacity;
                this.ctx.fill();
            });
            
            this.ctx.globalAlpha = 1;
            
            requestAnimationFrame(() => this.animate());
        }
    }
    
    /* ══════════════════════════════════════════════════
       水墨文字效果
       ══════════════════════════════════════════════════ */
    
    class InkTextEffect {
        constructor() {
            this.init();
        }
        
        init() {
            const titles = document.querySelectorAll('h1, h2, h3, .calligraphy-title');
            
            titles.forEach(title => {
                title.addEventListener('mouseenter', () => {
                    title.style.textShadow = '2px 2px 4px rgba(45, 45, 45, 0.1)';
                });
                
                title.addEventListener('mouseleave', () => {
                    title.style.textShadow = 'none';
                });
            });
        }
    }
    
    /* ══════════════════════════════════════════════════
       平滑滚动
       ══════════════════════════════════════════════════ */
    
    class SmoothScroll {
        constructor() {
            this.init();
        }
        
        init() {
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', (e) => {
                    e.preventDefault();
                    const target = document.querySelector(anchor.getAttribute('href'));
                    if (target) {
                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                });
            });
        }
    }
    
    /* ══════════════════════════════════════════════════
       初始化
       ══════════════════════════════════════════════════ */
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new InkWashEffect();
            new InkTextEffect();
            new SmoothScroll();
            
            const heroSection = document.querySelector('.hero-section');
            if (heroSection) {
                new InkParticleEffect(heroSection);
            }
        });
    } else {
        new InkWashEffect();
        new InkTextEffect();
        new SmoothScroll();
        
        const heroSection = document.querySelector('.hero-section');
        if (heroSection) {
            new InkParticleEffect(heroSection);
        }
    }
    
    /* ══════════════════════════════════════════════════
       CSS 样式注入
       ══════════════════════════════════════════════════ */
    
    const style = document.createElement('style');
    style.textContent = `
        .section-hidden {
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.6s ease, transform 0.6s ease;
        }
        
        .section-visible {
            opacity: 1;
            transform: translateY(0);
        }
        
        .ink-spread-visible {
            animation: inkSpread 0.6s ease forwards;
        }
        
        @keyframes inkSpread {
            from {
                opacity: 0;
                transform: scale(0.95);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }
    `;
    document.head.appendChild(style);
    
})();

})();
