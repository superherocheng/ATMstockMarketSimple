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
