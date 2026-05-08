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
