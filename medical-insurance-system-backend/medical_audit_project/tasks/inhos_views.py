from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import mysql.connector
from mysql.connector import Error
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

class InhosNumbersAPIView(APIView):
    """
    根据出院年月查询住院号的API接口
    """
    
    def get(self, request):
        """
        GET /api/inhos-numbers/?start_date=2024-01&end_date=2024-12&drug_name=阿司匹林
        
        参数:
        - start_date: 开始年月 (可选) 格式: YYYY-MM
        - end_date: 结束年月 (可选) 格式: YYYY-MM，如果不提供则查询start_date之后的所有数据
        - drug_name: 药品名称 (可选) 支持模糊查询
        
        筛选逻辑:
        - 仅选择日期时：按日期范围筛选病例
        - 仅输入药品名称时：使用SQL模糊查询筛选病例
        - 同时选择日期和药品时：组合使用日期范围和药品名称进行筛选
        
        返回:
        {
            "success": true,
            "inhos_numbers": ["ZY010000483837", "ZY010000483838", ...],
            "count": 100,
            "date_range": "2024-01 to 2024-12",
            "drug_filter": "阿司匹林",
            "filter_type": "date_and_drug"
        }
        """
        try:
            # 获取请求参数
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            drug_name = request.GET.get('drug_name')
            
            # 验证至少提供一个筛选条件
            if not start_date and not drug_name:
                return Response({
                    'success': False,
                    'error': '请至少提供一个筛选条件：日期范围(start_date)或药品名称(drug_name)'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 验证日期格式（如果提供了日期参数）
            if start_date:
                try:
                    datetime.strptime(start_date, '%Y-%m')
                    if end_date:
                        datetime.strptime(end_date, '%Y-%m')
                except ValueError:
                    return Response({
                        'success': False,
                        'error': '日期格式错误，请使用 YYYY-MM 格式'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # 验证药品名称格式（如果提供了药品参数）
            if drug_name:
                # 清理药品名称，移除特殊字符防止SQL注入
                drug_name = re.sub(r'[^\w\u4e00-\u9fff\s]', '', drug_name.strip())
                if len(drug_name) < 2:
                    return Response({
                        'success': False,
                        'error': '药品名称至少需要2个字符'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # 原配置（可快速恢复）
            # 真实数据库连接配置 (生产环境)
            # user = 'root'
            # password = 'hainan'
            # host = 'localhost:3306'
            # database = 'sys'
            
            # 测试数据库连接配置 (测试环境) - 保留用于测试
            user = 'root'
            password = '271572'
            host = '127.0.0.1:3306'
            database = 'medical_audit_test'
            
            try:
                # 创建数据库连接（添加连接池配置）
                # 注意：SQLAlchemy 连接字符串格式为 mysql+mysqlconnector://user:password@host/database
                # 这里我们使用 host 变量，它已经包含了端口信息（如果是 127.0.0.1:3306）
                # 或者我们需要解析 host 和 port。为了简单起见，我们假设 host 可能包含端口，也可能不包含。
                # 但 create_engine 的 url 格式通常是 host:port。
                
                if ':' in host:
                    db_host, db_port = host.split(':')
                else:
                    db_host = host
                    db_port = '3306'

                engine = create_engine(
                    f'mysql+mysqlconnector://{user}:{password}@{db_host}:{db_port}/{database}',
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600
                )
                
                # 构建优化的SQL查询语句
                sql_conditions = []
                join_clauses = []
                
                # 确定筛选类型和描述信息
                filter_type = ""
                date_range = ""
                drug_filter = ""
                
                # 根据筛选条件选择最优查询策略
                if start_date and drug_name:
                    # 日期+药品组合筛选：使用内连接优化
                    filter_type = "date_and_drug"
                    drug_filter = drug_name
                    
                    if end_date:
                        sql_conditions.append(f"DATE_FORMAT(h.DSCG_DT_TM, '%Y-%m') BETWEEN '{start_date}' AND '{end_date}'")
                        date_range = f"{start_date} to {end_date}"
                    else:
                        sql_conditions.append(f"DATE_FORMAT(h.DSCG_DT_TM, '%Y-%m') >= '{start_date}'")
                        date_range = f"{start_date} onwards"
                    
                    sql_conditions.append(f"t.DRG_NM LIKE '%{drug_name}%'")
                    
                    sql = f'''
                    SELECT DISTINCT t.INHOS_NO 
                    FROM FACT_TRTMT_DOS_RCD t
                    INNER JOIN FACT_MDC_RCD_HMPG h ON t.INHOS_NO = h.INHOS_NO
                    WHERE {' AND '.join(sql_conditions)}
                    ORDER BY t.INHOS_NO
                    '''
                    
                elif start_date:
                    # 仅日期筛选：优化日期查询
                    filter_type = "date_only"
                    
                    if end_date:
                        sql_conditions.append(f"DATE_FORMAT(h.DSCG_DT_TM, '%Y-%m') BETWEEN '{start_date}' AND '{end_date}'")
                        date_range = f"{start_date} to {end_date}"
                    else:
                        sql_conditions.append(f"DATE_FORMAT(h.DSCG_DT_TM, '%Y-%m') >= '{start_date}'")
                        date_range = f"{start_date} onwards"
                    
                    sql = f'''
                    SELECT DISTINCT h.INHOS_NO 
                    FROM fact_mdc_rcd_hmpg h
                    WHERE {' AND '.join(sql_conditions)}
                    ORDER BY h.INHOS_NO
                    '''
                    
                elif drug_name:
                    # 仅药品筛选：直接查询药品表
                    filter_type = "drug_only"
                    drug_filter = drug_name
                    sql_conditions.append(f"t.DRG_NM LIKE '%{drug_name}%'")
                    
                    sql = f'''
                    SELECT DISTINCT t.INHOS_NO 
                    FROM fact_trtmt_dos_rcd t
                    WHERE {' AND '.join(sql_conditions)}
                    ORDER BY t.INHOS_NO
                    '''
                else:
                    # 无筛选条件，返回错误
                    return Response({
                        'success': False,
                        'error': '请至少提供一个筛选条件（日期或药品名称）'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info(f"执行SQL查询: {sql}")
                
                # 执行查询
                df = pd.read_sql(sql, engine)
                inhos_numbers = df['INHOS_NO'].dropna().astype(str).tolist()
                
                # 关闭数据库连接
                engine.dispose()
                
                logger.info(f"筛选类型: {filter_type}, 日期范围: {date_range}, 药品筛选: {drug_filter}, 找到住院号数量: {len(inhos_numbers)}")
                
                # 构建响应数据
                response_data = {
                    'success': True,
                    'inhos_numbers': inhos_numbers,
                    'count': len(inhos_numbers),
                    'filter_type': filter_type
                }
                
                # 添加日期范围信息（如果有）
                if date_range:
                    response_data['date_range'] = date_range
                
                # 添加药品筛选信息（如果有）
                if drug_filter:
                    response_data['drug_filter'] = drug_filter
                
                return Response(response_data, status=status.HTTP_200_OK)
                
            except Exception as db_error:
                logger.error(f"数据库查询错误: {str(db_error)}")
                return Response({
                    'success': False,
                    'error': f'数据库查询失败: {str(db_error)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            logger.error(f"API调用错误: {str(e)}")
            return Response({
                'success': False,
                'error': f'服务器内部错误: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)