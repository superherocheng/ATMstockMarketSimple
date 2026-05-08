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
