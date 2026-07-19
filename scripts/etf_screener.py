"""ETF Screener: Select 30+ quality ETFs via Tushare API.

Filters: liquidity >= 50M daily turnover, exclude broad-market, deduplicate sectors.
Output: Industry 12-15, QDII 8-10, Bond 6-8.
"""
import sys
import os
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

import tushare as ts
# ponytail: no hardcoded fallback — a leaked default token lived in this tracked
# file for the repo's whole history. TUSHARE_TOKEN MUST come from the env (.env);
# missing = fail loud instead of silently using a baked-in secret.
_token = os.environ.get("TUSHARE_TOKEN")
if not _token:
    raise RuntimeError("TUSHARE_TOKEN env var is required (etf_screener cannot run without it)")
ts.set_token(_token)
pro = ts.pro_api()

# Broad-market ETFs to EXCLUDE
BROAD_MARKET_KW = [
    "沪深300", "中证500", "中证1000", "创业板指", "科创50", "上证50",
    "中证800", "双创", "国证2000", "中证全指", "万得全A",
    "中证100", "MSCI中国", "富时中国", "A500", "创业板50",
    "科创板", "北证50", "上证指数", "深证100", "深证成指",
]

# Bond keywords
BOND_KW = ["国债", "政金债", "信用债", "可转债", "短融", "公司债", "利率债",
            "国开债", "地方债", "金融债", "城投债", "同业存单", "债", "利率",
            "短债", "长债", "中短债", "政金"]

# QDII cross-border keywords
QDII_KW = ["纳斯达克", "标普", "恒生科技", "日经", "德国DAX", "法国CAC",
            "英国富时", "越南", "印度", "东南亚", "沙特", "恒生互联网",
            "中概互联", "恒生医疗", "恒生指数", "恒生国企", "纳斯达克生物",
            "金砖", "全球", "美国", "日本", "港股通", "港股创新药", "恒生医药",
            "标普500", "道琼斯", "日经225", "韩国"]

# Sector dedup: map similar index names to one canonical group
SECTOR_GROUPS = {
    "半导体": ["半导体", "芯片", "集成电路", "中华半导体"],
    "证券": ["证券", "券商"],
    "港股科技": ["恒生科技", "恒生互联网"],
    "银行": ["银行"],
    "医药": ["医药", "生物医药", "医疗", "创新药", "中药"],
    "白酒": ["白酒", "食品饮料"],
    "军工": ["军工", "国防"],
    "有色": ["有色金属", "有色"],
    "煤炭": ["煤炭"],
    "新能源车": ["新能源车", "电动车", "智能汽车"],
    "光伏": ["光伏", "新能源"],
    "通信": ["通信", "5G", "信息"],
    "传媒": ["传媒", "影视", "游戏", "动漫"],
    "电力": ["电力", "公用事业"],
    "钢铁": ["钢铁"],
    "化工": ["化工"],
    "石油": ["石油", "油气"],
    "消费": ["消费", "商贸"],
    "家电": ["家电"],
    "机器人": ["机器人", "人工智能", "AI"],
    "房地产": ["房地产", "地产"],
    "保险": ["保险"],
    "黄金": ["黄金"],
    "农业": ["农业", "养殖"],
    "汽车": ["汽车"],
    "电子": ["电子"],
    "计算机": ["计算机"],
    "环保": ["环保", "低碳"],
    "建材": ["建材", "基建"],
    "旅游": ["旅游"],
    "卫星": ["卫星", "航天", "商业航天"],
}


def step1_get_etf_list():
    """Step 1: Get all listed ETFs."""
    print("Step 1: Fetching all listed ETFs...")
    df = pro.etf_basic(list_status='L', fields='ts_code,extname,index_code,index_name,exchange,etf_type')
    print(f"  Total listed ETFs: {len(df)}")
    return df


def step2_filter_liquidity(df):
    """Step 2: Filter by liquidity (avg daily amount >= 50M over recent trading days)."""
    print("\nStep 2: Checking liquidity (this may take a few minutes)...")
    results = []
    codes = df['ts_code'].tolist()

    batch_size = 50
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        for code in batch:
            try:
                daily = pro.fund_daily(ts_code=code, start_date='20250401', end_date='20260531',
                                       fields='trade_date,amount')
                if daily is not None and len(daily) >= 10:
                    avg_amt = daily['amount'].mean() * 1000  # Convert to yuan
                    latest = daily.sort_values('trade_date').iloc[-1]['trade_date']
                    results.append({
                        'ts_code': code,
                        'avg_amount': avg_amt,
                        'latest_date': latest,
                        'n_days': len(daily),
                    })
            except Exception:
                pass
        if (i // batch_size) % 5 == 0:
            print(f"  Progress: {min(i+batch_size, len(codes))}/{len(codes)} ETFs checked")

    liq_df = pd.DataFrame(results)
    liq_df = liq_df[liq_df['avg_amount'] >= 50_000_000]
    print(f"  ETFs passing liquidity filter (>=5000wan/day): {len(liq_df)}")
    return liq_df


def step3_classify(df, liq_df):
    """Step 3: Merge and classify ETFs into industry/QDII/bond."""
    merged = df.merge(liq_df[['ts_code', 'avg_amount']], on='ts_code', how='inner')

    # Exclude broad-market ETFs - check BOTH index_name and extname
    def is_broad_market(row):
        name = str(row.get('index_name', ''))
        extname = str(row.get('extname', ''))
        for kw in BROAD_MARKET_KW:
            if kw in name or kw in extname:
                return True
        return False

    merged = merged[~merged.apply(is_broad_market, axis=1)]

    # Classify - check both fields
    def classify(row):
        name = str(row.get('index_name', ''))
        extname = str(row.get('extname', ''))
        etf_type = str(row.get('etf_type', ''))
        combined = name + extname

        # Bond ETFs - check combined name
        if any(kw in combined for kw in BOND_KW):
            return "债券"
        # Also check etf_type for bond
        if '债券' in etf_type or '债' in etf_type:
            return "债券"

        # QDII
        if 'QDII' in etf_type or '跨境' in etf_type:
            return "跨境"
        if any(kw in combined for kw in QDII_KW):
            return "跨境"

        return "行业"

    merged['category'] = merged.apply(classify, axis=1)
    return merged


def step4_dedup(merged):
    """Step 4: Deduplicate similar sector ETFs, keep highest liquidity."""
    def get_sector_group(name):
        if pd.isna(name):
            return name
        for group, kws in SECTOR_GROUPS.items():
            for kw in kws:
                if kw in name:
                    return group
        return name

    merged['sector_group'] = merged['index_name'].apply(get_sector_group)
    selected = merged.sort_values('avg_amount', ascending=False).groupby(['category', 'sector_group']).first().reset_index()
    return selected


def step5_final_selection(selected):
    """Step 5: Final selection with type quotas."""
    industry = selected[selected['category'] == '行业'].sort_values('avg_amount', ascending=False)
    cross = selected[selected['category'] == '跨境'].sort_values('avg_amount', ascending=False)
    bond = selected[selected['category'] == '债券'].sort_values('avg_amount', ascending=False)

    print(f"\n  Available after dedup:")
    print(f"    行业ETF: {len(industry)}")
    print(f"    跨境ETF: {len(cross)}")
    print(f"    债券ETF: {len(bond)}")

    # Print all available for review
    print(f"\n  ALL AVAILABLE 行业 ETFs (sorted by liquidity):")
    for _, r in industry.iterrows():
        amt_yi = r['avg_amount'] / 100000000
        print(f"    {r['ts_code']} {str(r.get('extname', '')):<20s} | {r.get('index_name', ''):<20s} | {amt_yi:.2f}亿 | {r.get('sector_group', '')}")

    print(f"\n  ALL AVAILABLE 跨境 ETFs (sorted by liquidity):")
    for _, r in cross.iterrows():
        amt_yi = r['avg_amount'] / 100000000
        print(f"    {r['ts_code']} {str(r.get('extname', '')):<20s} | {r.get('index_name', ''):<20s} | {amt_yi:.2f}亿")

    print(f"\n  ALL AVAILABLE 债券 ETFs (sorted by liquidity):")
    for _, r in bond.iterrows():
        amt_yi = r['avg_amount'] / 100000000
        print(f"    {r['ts_code']} {str(r.get('extname', '')):<20s} | {r.get('index_name', ''):<20s} | {amt_yi:.2f}亿")

    n_industry = min(15, len(industry))
    n_cross = min(10, len(cross))
    n_bond = min(8, len(bond))

    final = pd.concat([
        industry.head(n_industry),
        cross.head(n_cross),
        bond.head(n_bond),
    ]).sort_values(['category', 'avg_amount'], ascending=[True, False])

    return final


def main():
    # Step 1
    etf_list = step1_get_etf_list()

    # Step 2
    liq_df = step2_filter_liquidity(etf_list)

    # Step 3
    merged = step3_classify(etf_list, liq_df)
    print(f"\n  After classification:")
    print(merged.groupby('category').size())

    # Step 4
    selected = step4_dedup(merged)

    # Step 5
    final = step5_final_selection(selected)

    # Output
    print(f"\n{'='*100}")
    print(f"  FINAL ETF SELECTION: {len(final)} ETFs")
    print(f"{'='*100}")

    for i, (_, row) in enumerate(final.iterrows(), 1):
        code = row['ts_code']
        name = row.get('extname', row.get('index_name', ''))
        cat = row['category']
        idx_name = row.get('index_name', '-')
        amt_wan = row['avg_amount'] / 10000

        if cat == "行业":
            group = row.get('sector_group', idx_name)
            reason = f"行业-{group}, 流动性好"
        elif cat == "跨境":
            reason = f"跨境配置, 流动性好"
        else:
            reason = f"债券配置, 流动性好"

        print(f"  {i:>2}. [{cat:>2}] {code} {name:<20s} | {idx_name:<20s} | {amt_wan:.0f}万 | {reason}")

    # Python dict output
    print(f"\n  EXPANDED_ETF_CODES = {{")
    for _, row in final.iterrows():
        print(f"    \"{row['ts_code']}\": \"{row.get('extname', row.get('index_name', ''))}\",")
    print(f"  }}")


if __name__ == "__main__":
    main()
