#!/usr/bin/env python3
"""
通过API检查行业分析数据
"""
import requests
import json

def check_industry_api():
    """通过API检查行业数据"""
    print("=" * 60)
    print("行业分析 API 数据检查")
    print("=" * 60)
    
    try:
        # 调用行业分析API
        response = requests.get('http://localhost:8000/api/industry/analysis', timeout=10)
        
        if response.status_code != 200:
            print(f"❌ API请求失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return
        
        data = response.json()
        
        if 'error' in data and data['error']:
            print(f"❌ API返回错误: {data['error']}")
            return
        
        industries = data.get('industries', [])
        
        if not industries:
            print("⚠️  没有行业数据")
            return
        
        print(f"\n✅ 获取到 {len(industries)} 个行业")
        
        # 检查前5个行业的数据
        print("\n【前5个行业数据示例】")
        print("-" * 60)
        
        for i, ind in enumerate(industries[:5], 1):
            print(f"\n{i}. {ind['industry']} ({ind['stock_count']}只)")
            
            avg_metrics = ind.get('avg_metrics', {})
            if avg_metrics:
                avg_mv = avg_metrics.get('avg_mv', 0)
                avg_pe = avg_metrics.get('avg_pe', 0)
                avg_pb = avg_metrics.get('avg_pb', 0)
                
                print(f"   平均市值: {avg_mv if avg_mv else '--'}")
                print(f"   平均PE: {avg_pe if avg_pe else '--'}")
                print(f"   平均PB: {avg_pb if avg_pb else '--'}")
                
                if avg_mv == 0 and avg_pe == 0 and avg_pb == 0:
                    print("   ⚠️  市值、PE、PB 都为 0！")
            else:
                print("   ❌ 没有 avg_metrics 数据")
        
        # 统计有市值数据的行业数量
        industries_with_mv = sum(1 for ind in industries 
                                 if ind.get('avg_metrics', {}).get('avg_mv', 0) > 0)
        
        print("\n" + "=" * 60)
        print(f"数据统计:")
        print(f"  总行业数: {len(industries)}")
        print(f"  有市值数据的行业: {industries_with_mv}")
        print(f"  无市值数据的行业: {len(industries) - industries_with_mv}")
        
        if industries_with_mv == 0:
            print("\n⚠️  所有行业都没有市值数据！")
            print("可能的原因:")
            print("  1. stock_daily_basic 表没有数据")
            print("  2. 数据日期不匹配")
            print("  3. 股票代码不匹配")
            print("\n建议:")
            print("  1. 运行: python fetch_data.py --funda")
            print("  2. 检查数据库数据完整性")
        
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        print("请确保服务器正在运行: uvicorn app:app --reload --port 8000")
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_industry_api()
