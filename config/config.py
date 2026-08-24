"""
Tushare 配置文件
=================
请复制此文件为 config.py，并填入你的 Tushare Token。

获取方式：https://tushare.pro/register 注册后，
在「个人主页」->「接口TOKEN」中复制。

注意：部分高级接口（如资金流向 moneyflow）需要足够积分。
"""
import os
import tushare as ts
from pathlib import Path

# ============================================================
#   在这里填入你的 Token（或通过环境变量 TUSHARE_TOKEN 设置）
# ============================================================
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

# ETF 代码配置
# 指数ETF（主要宽基 + 科创）
INDEX_ETF = {
    "510300.SH": "沪深300ETF",
    "510500.SH": "中证500ETF",
    "510050.SH": "上证50ETF",
    "512100.SH": "中证1000ETF",
    "588000.SH": "科创50ETF",
}

# 行业 ETF（流动性最高的品种，覆盖主要行业板块）
SECTOR_ETF = {
    # -- 原有16只 --
    "512480.SH": "半导体ETF",
    "515030.SH": "新能源车ETF",
    "512010.SH": "医药ETF",
    "512800.SH": "银行ETF",
    "512880.SH": "证券ETF",
    "159928.SZ": "消费ETF",
    "515880.SH": "通信ETF",
    "159206.SZ": "卫星ETF",
    "515220.SH": "煤炭ETF",
    "512400.SH": "有色ETF",
    "562500.SH": "机器人ETF",
    "512690.SH": "白酒ETF",
    "159611.SZ": "电力ETF",
    "512980.SH": "传媒ETF",
    "515210.SH": "钢铁ETF",
    "159870.SZ": "化工ETF",
    "561360.SH": "石油ETF",
    # -- 新增：军工/国防 --
    "512710.SH": "军工龙头ETF",
    # -- 新增：光伏/新能源 --
    "515790.SH": "光伏ETF",
    # -- 新增：黄金/商品 --
    "159934.SZ": "黄金ETF",
    # -- 新增：农业/养殖 --
    "159865.SZ": "养殖ETF",
    # -- 新增：旅游 --
    "159766.SZ": "旅游ETF",
    # -- 新增：计算机/软件 --
    "159852.SZ": "软件ETF",
    # -- 新增：金融科技 --
    "159851.SZ": "金融科技ETF",
    # -- 新增：医疗(细分) --
    "512170.SH": "医疗ETF",
    # -- 新增：游戏/传媒细分 --
    "159869.SZ": "游戏ETF",
    # -- 新增：电池/新能源车细分 --
    "159755.SZ": "电池ETF",
    # -- 新增：稀土 --
    "516150.SH": "稀土ETF",
    # -- 新增：高端装备 --
    "159638.SZ": "高端装备ETF",
    # -- 新增：能源 --
    "159930.SZ": "能源ETF",
    # -- 新增：科技龙头 --
    "515000.SH": "科技ETF",
    # -- 新增：电网设备 --
    "159326.SZ": "电网设备ETF",
}

# 商品类ETF（无基本面财务因子，仅技术面计算）
COMMODITY_ETF_CODES = {"561360.SH", "159934.SZ"}

# ============================================================
#   同指数家族份额聚合
# ============================================================
# 单只ETF的份额 = 投资者流量 × 工具轮动（同一指数下多只ETF之间的申赎搬家，
# 例如 510300 2025-12→2026-06 份额-80% 而价格横盘，是汇金换仓而非资金离场）。
# 因此宽基ETF的份额信号必须按"同指数全部ETF家族"聚合计算。
# 名单基于 fund_basic + fund_share 实际规模核验（2026-08，剔除增强/联接/
# 行业子集如"沪深300医药"）。
INDEX_ETF_FAMILY = {
    "510300.SH": [  # 沪深300
        "510300.SH", "510310.SH", "510330.SH", "159919.SZ",
        "515330.SH", "515390.SH",
    ],
    "510500.SH": [  # 中证500
        "510500.SH", "159922.SZ", "512500.SH", "159820.SZ",
        "510580.SH", "510510.SH",
    ],
    "510050.SH": [  # 上证50
        "510050.SH", "530000.SH", "510100.SH",
    ],
    "512100.SH": [  # 中证1000
        "512100.SH", "159845.SZ", "560010.SH", "159633.SZ",
        "159629.SZ", "560110.SH",
    ],
    "588000.SH": [  # 科创50
        "588000.SH", "588080.SH", "588060.SH", "588050.SH",
        "588940.SH", "588090.SH",
    ],
}

# 家族成员中除已跟踪5只外的"份额专用"代码（只抓 etf_share，不进行情/因子流程）
FAMILY_SHARE_CODES = sorted(
    {c for members in INDEX_ETF_FAMILY.values() for c in members} - set(INDEX_ETF)
)

# 指数估值（Tushare index_dailybasic，PE/PB）— 大盘温度计的估值分位面板
INDEX_VALUATION_CODES = {
    "000300.SH": "沪深300",
    "000905.SH": "中证500",
    "000688.SH": "科创50",
    "399006.SZ": "创业板指",
}

# 回溯交易日数（约一年）
LOOKBACK_DAYS = 260

# 异常检测阈值（标准差倍数）
ANOMALY_STD_THRESHOLD = 2.0

# 周期性行业集合
CYCLICAL_INDUSTRIES = {
    "银行", "证券", "保险", "多元金融",
    "煤炭开采", "焦炭加工",
    "铝", "铜", "铅锌", "小金属", "黄金",
    "化工原料", "化纤", "塑料", "橡胶",
    "建筑工程", "其他建材", "水泥", "玻璃", "陶瓷",
    "水运", "公路", "港口", "空运", "铁路",
    "火力发电", "水力发电", "新型电力", "供气供热",
    "石油开采", "石油加工", "石油贸易",
    "矿物制品", "有色金属",
}

# 缓存配置
CACHE_MAX_SIZE = 500
CACHE_DEFAULT_TTL = 3600

# Redis 缓存配置
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
REDIS_PREFIX = os.environ.get("REDIS_PREFIX", "atm:")


def get_pro():
    """获取 tushare pro 接口"""
    if not TUSHARE_TOKEN:
        raise ValueError(
            "请先配置 Tushare Token！\n"
            "请设置环境变量 TUSHARE_TOKEN\n"
            "获取 Token: https://tushare.pro/register"
        )

    ts.set_token(TUSHARE_TOKEN)
    return ts.pro_api()
