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
