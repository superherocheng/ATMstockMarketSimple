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
