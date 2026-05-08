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
