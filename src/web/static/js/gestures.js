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
