# 外部数据说明

本目录存放项目所需的外部数据文件，这些文件将被 Git 跟踪。

## 数据文件

| 文件 | 说明 | 更新频率 | 必需 |
|------|------|---------|------|
| ALLSYMBOL.csv | 股票分类数据 (申万行业+概念标签) | 季度更新 | 是 |
| ALLSYMBOL.meta.json | 数据元信息 (自动生成) | 自动更新 | 自动 |

## 数据格式

### ALLSYMBOL.csv

- **编码**: UTF-8
- **分隔符**: 逗号
- **概念分隔符**: `|` (竖线)

#### 必需字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| ts_code | VARCHAR | 股票代码 | 000001.SZ |
| name | VARCHAR | 股票名称 | 平安银行 |

#### 可选字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| sw_level1 | VARCHAR | 申万一级行业 | 银行 |
| sw_level2 | VARCHAR | 申万二级行业 | 银行 |
| sw_level3 | VARCHAR | 申万三级行业 | 银行 |
| concepts | VARCHAR | 概念标签 (多个用 `\|` 分隔) | 数字货币\|区块链\|金融科技 |
| area | VARCHAR | 地区 | 广东 |
| market | VARCHAR | 市场 | 深圳主板 |
| list_date | VARCHAR | 上市日期 | 19910403 |

## 数据加载

### 首次安装

1. 将 ALLSYMBOL.csv 放置到此目录
2. 运行加载脚本:

```bash
cd /path/to/ATMstockMarket
python src/data_fetchers/external_loader.py
```

### 数据更新

1. 替换 `data/external/ALLSYMBOL.csv`
2. 运行加载脚本:

```bash
python src/data_fetchers/external_loader.py
```

### 验证数据

```bash
python src/data_fetchers/external_loader.py --verify
```

## 数据来源

- **申万行业分类**: http://www.swsindex.com/
- **概念标签**: 东方财富 / 同花顺 / Wind

## 注意事项

1. CSV 文件大小建议不超过 100MB (GitHub 限制)
2. 如需使用其他概念分隔符，可使用 `--separator` 参数:

```bash
python src/data_fetchers/external_loader.py --separator ","
```

3. 元信息文件 (ALLSYMBOL.meta.json) 会在加载时自动更新

## 示例数据

```csv
ts_code,name,sw_level1,sw_level2,sw_level3,concepts,area,market,list_date
000001.SZ,平安银行,银行,银行,银行,数字货币|区块链|金融科技,广东,深圳主板,19910403
000002.SZ,万科A,房地产,房地产开发,房地产开发,租购同权|物业管理,广东,深圳主板,19910129
600519.SH,贵州茅台,食品饮料,白酒,白酒,高端白酒|机构重仓|MSCI成分,贵州,上海主板,20010827
```
