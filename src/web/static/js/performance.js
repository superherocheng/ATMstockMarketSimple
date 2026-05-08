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
