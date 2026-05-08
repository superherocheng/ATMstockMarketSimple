"""
输入验证器单元测试
==================
测试股票代码、日期、行业名称的验证逻辑
"""
import pytest
from datetime import datetime


class TestValidateTsCode:
    """股票代码验证测试"""
    
    def test_valid_sh_code(self):
        """测试有效的上海股票代码"""
        from src.web.services.validators import validate_ts_code
        assert validate_ts_code("600000.SH") == True
        assert validate_ts_code("510300.SH") == True
    
    def test_valid_sz_code(self):
        """测试有效的深圳股票代码"""
        from src.web.services.validators import validate_ts_code
        assert validate_ts_code("000001.SZ") == True
        assert validate_ts_code("159928.SZ") == True
    
    def test_valid_bj_code(self):
        """测试有效的北京股票代码"""
        from src.web.services.validators import validate_ts_code
        assert validate_ts_code("430047.BJ") == True
    
    def test_invalid_format_no_dot(self):
        """测试无效格式：无点号"""
        from src.web.services.validators import validate_ts_code
        assert validate_ts_code("600000") == False
        assert validate_ts_code("000001") == False
    
    def test_invalid_format_wrong_suffix(self):
        """测试无效格式：错误后缀"""
        from src.web.services.validators import validate_ts_code
        assert validate_ts_code("600000.SH.SZ") == False
        assert validate_ts_code("600000.XX") == False
    
    def test_invalid_format_wrong_digits(self):
        """测试无效格式：错误位数"""
        from src.web.services.validators import validate_ts_code
        assert validate_ts_code("60000.SH") == False
        assert validate_ts_code("6000000.SH") == False
    
    def test_empty_string(self):
        """测试空字符串"""
        from src.web.services.validators import validate_ts_code
        assert validate_ts_code("") == False
        assert validate_ts_code(None) == False
    
    def test_whitespace(self):
        """测试带空格的代码"""
        from src.web.services.validators import validate_ts_code
        assert validate_ts_code(" 600000.SH ") == True  # 应该trim
        assert validate_ts_code("600 000.SH") == False


class TestValidateDate:
    """日期验证测试"""
    
    def test_valid_date(self):
        """测试有效日期"""
        from src.web.services.validators import validate_date
        assert validate_date("20240101") == True
        assert validate_date("20241231") == True
    
    def test_invalid_format_with_dash(self):
        """测试无效格式：带连字符"""
        from src.web.services.validators import validate_date
        assert validate_date("2024-01-01") == False
    
    def test_invalid_month(self):
        """测试无效月份"""
        from src.web.services.validators import validate_date
        assert validate_date("20241301") == False  # 13月
        assert validate_date("20240001") == False  # 0月
    
    def test_invalid_day(self):
        """测试无效日期"""
        from src.web.services.validators import validate_date
        assert validate_date("20240132") == False  # 32日
        assert validate_date("20240100") == False  # 0日
    
    def test_empty_string(self):
        """测试空字符串"""
        from src.web.services.validators import validate_date
        assert validate_date("") == False
        assert validate_date(None) == False


class TestValidateIndustryName:
    """行业名称验证测试"""
    
    def test_valid_chinese_name(self):
        """测试有效的中文行业名"""
        from src.web.services.validators import validate_industry_name
        assert validate_industry_name("银行") == True
        assert validate_industry_name("电子") == True
    
    def test_valid_english_name(self):
        """测试有效的英文行业名"""
        from src.web.services.validators import validate_industry_name
        assert validate_industry_name("banking") == True
        assert validate_industry_name("IT") == True
    
    def test_valid_mixed_name(self):
        """测试有效的混合名称"""
        from src.web.services.validators import validate_industry_name
        assert validate_industry_name("银行_Banking") == True
        assert validate_industry_name("电子-半导体") == True
    
    def test_invalid_special_chars(self):
        """测试无效的特殊字符"""
        from src.web.services.validators import validate_industry_name
        assert validate_industry_name("银行;DROP TABLE") == False
        assert validate_industry_name("银行'OR'1'='1") == False
    
    def test_empty_string(self):
        """测试空字符串"""
        from src.web.services.validators import validate_industry_name
        assert validate_industry_name("") == False
        assert validate_industry_name(None) == False
    
    def test_too_long_name(self):
        """测试过长的名称"""
        from src.web.services.validators import validate_industry_name
        long_name = "银行" * 30  # 60个字符
        assert validate_industry_name(long_name) == False
