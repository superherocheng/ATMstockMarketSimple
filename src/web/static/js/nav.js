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
    var isOpen = forceClose ? false : navLinks.classList.toggle('open');
    if (forceClose) {
        navLinks.classList.remove('open');
        overlay.classList.remove('active');
    } else {
        overlay.classList.toggle('active');
    }
    if (btn) {
        btn.setAttribute('aria-expanded', isOpen.toString());
        btn.setAttribute('aria-label', isOpen ? '关闭菜单' : '打开菜单');
    }
    if (isOpen) {
        navLinks.querySelector('a')?.focus();
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

// ── P3.3: Anomaly badge on ETF nav links ──
ATMNav.loadAnomalyBadge = function() {
    // Only check on ETF/overview pages to avoid unnecessary requests
    fetch('/api/barra/summary').then(function(r) { return r.json(); }).then(function(d) {
        var count = (d.industry_risk_count || 0) + (d.stock_risk_count || 0);
        var etfLink = document.querySelector('.nav-link[href="/etf"], a[href="/etf"]');
        if (etfLink && count > 0) {
            var badge = etfLink.querySelector('.anomaly-badge');
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'anomaly-badge';
                etfLink.appendChild(badge);
            }
            badge.textContent = count;
            badge.title = count + ' 个异常信号';
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
