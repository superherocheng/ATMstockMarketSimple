"""
PostgreSQL 连接管理器测试
=========================
测试 PostgreSQLConnectionManager 类的功能
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd


class TestPostgreSQLConnectionManager:
    """PostgreSQL 连接管理器测试"""
    
    def test_positional_params_conversion_single(self):
        """测试单个位置参数转换"""
        from src.core.db_manager_postgresql import PostgreSQLConnectionManager
        
        manager = PostgreSQLConnectionManager()
        manager._engine = Mock()
        
        mock_conn = MagicMock()
        mock_result = Mock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        manager.get_connection = Mock(return_value=mock_conn)
        
        manager.execute("SELECT * FROM test WHERE id = %s", (1,))
        
        call_args = mock_conn.execute.call_args
        executed_sql = str(call_args[0][0])
        
        assert ":p0" in executed_sql
        assert "%s" not in executed_sql
    
    def test_positional_params_conversion_multiple(self):
        """测试多个位置参数转换"""
        from src.core.db_manager_postgresql import PostgreSQLConnectionManager
        
        manager = PostgreSQLConnectionManager()
        manager._engine = Mock()
        
        mock_conn = MagicMock()
        mock_result = Mock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        manager.get_connection = Mock(return_value=mock_conn)
        
        manager.execute(
            "SELECT * FROM test WHERE id = %s AND name = %s",
            (1, "test")
        )
        
        call_args = mock_conn.execute.call_args
        executed_sql = str(call_args[0][0])
        
        assert ":p0" in executed_sql
        assert ":p1" in executed_sql
    
    def test_question_mark_conversion(self):
        """测试问号占位符转换"""
        from src.core.db_manager_postgresql import PostgreSQLConnectionManager
        
        manager = PostgreSQLConnectionManager()
        manager._engine = Mock()
        
        mock_conn = MagicMock()
        mock_result = Mock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        manager.get_connection = Mock(return_value=mock_conn)
        
        manager.execute("SELECT * FROM test WHERE id = ?", (1,))
        
        call_args = mock_conn.execute.call_args
        executed_sql = str(call_args[0][0])
        
        assert ":p0" in executed_sql
        assert "?" not in executed_sql
    
    def test_named_params_passthrough(self):
        """测试命名参数直接传递"""
        from src.core.db_manager_postgresql import PostgreSQLConnectionManager
        
        manager = PostgreSQLConnectionManager()
        manager._engine = Mock()
        
        mock_conn = MagicMock()
        mock_result = Mock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        manager.get_connection = Mock(return_value=mock_conn)
        
        manager.execute(
            "SELECT * FROM test WHERE id = :id",
            {"id": 1}
        )
        
        call_args = mock_conn.execute.call_args
        executed_sql = str(call_args[0][0])
        
        assert ":id" in executed_sql


class TestQueryWithPositionalParams:
    """查询参数转换测试"""
    
    def test_query_with_positional_params(self):
        """测试带位置参数的查询"""
        from src.core.db_manager_postgresql import PostgreSQLConnectionManager
        
        manager = PostgreSQLConnectionManager()
        manager._engine = Mock()
        
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        manager.get_connection = Mock(return_value=mock_conn)
        
        with patch('pandas.read_sql_query') as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame({"col": [1, 2, 3]})
            
            result = manager.query("SELECT * FROM test WHERE id = %s", (1,))
            
            assert len(result) == 3
            
            call_args = mock_read_sql.call_args
            executed_sql = str(call_args[0][0])
            
            assert ":p0" in executed_sql
