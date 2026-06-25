import logging
from datetime import datetime

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError

from data_adapter.source_db import get_source_sqlalchemy_url


logger = logging.getLogger(__name__)


class QueryParameterError(ValueError):
    pass


def _next_month(value):
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)


def _parse_month(value, field_name):
    try:
        return datetime.strptime(value, '%Y-%m')
    except (TypeError, ValueError) as exc:
        raise QueryParameterError(f'{field_name} 必须使用 YYYY-MM 格式') from exc


def _build_query(request):
    start_value = (request.GET.get('start_date') or '').strip()
    end_value = (request.GET.get('end_date') or '').strip()
    drug_name = (request.GET.get('drug_name') or '').strip()
    mdc_org_cd = (request.GET.get('mdc_org_cd') or settings.SOURCE_MDC_ORG_CD or '').strip()
    if not mdc_org_cd:
        raise QueryParameterError('请提供医疗机构代码')
    if not start_value and not drug_name:
        raise QueryParameterError('请至少提供开始月份或药品名称')
    if end_value and not start_value:
        raise QueryParameterError('填写结束月份时必须同时填写开始月份')
    if drug_name and len(drug_name) < 2:
        raise QueryParameterError('药品名称至少需要 2 个字符')

    params = {'mdc_org_cd': mdc_org_cd}
    conditions = []
    date_range = None
    if start_value:
        start_date = _parse_month(start_value, '开始月份')
        end_month = _parse_month(end_value, '结束月份') if end_value else start_date
        if end_month < start_date:
            raise QueryParameterError('结束月份不能早于开始月份')
        month_count = (
            (end_month.year - start_date.year) * 12
            + end_month.month - start_date.month + 1
        )
        if month_count > settings.INHOS_QUERY_MAX_MONTHS:
            raise QueryParameterError(
                f'查询范围不能超过 {settings.INHOS_QUERY_MAX_MONTHS} 个月'
            )
        params.update({
            'start_datetime': start_date,
            'end_datetime': _next_month(end_month),
        })
        conditions.extend([
            'h.DSCG_DT_TM >= :start_datetime',
            'h.DSCG_DT_TM < :end_datetime',
            'h.MDC_ORG_CD = :mdc_org_cd',
        ])
        date_range = f'{start_value} 至 {end_value or start_value}'

    if start_value and drug_name:
        filter_type = 'date_and_drug'
        params['drug_name'] = f'%{drug_name}%'
        conditions.append('t.DRG_NM LIKE :drug_name')
        sql = f'''SELECT DISTINCT h.INHOS_NO
                  FROM ods_fact_mdc_rcd_hmpg h
                  INNER JOIN ods_fact_trtmt_dos_rcd t
                    ON t.INHOS_NO = h.INHOS_NO
                   AND t.MDC_ORG_CD = h.MDC_ORG_CD
                  WHERE {' AND '.join(conditions)}
                  ORDER BY h.INHOS_NO'''
    elif start_value:
        filter_type = 'date_only'
        sql = f'''SELECT DISTINCT h.INHOS_NO
                  FROM ods_fact_mdc_rcd_hmpg h
                  WHERE {' AND '.join(conditions)}
                  ORDER BY h.INHOS_NO'''
    else:
        filter_type = 'drug_only'
        params['drug_name'] = f'%{drug_name}%'
        sql = '''SELECT DISTINCT t.INHOS_NO
                 FROM ods_fact_trtmt_dos_rcd t
                 WHERE t.DRG_NM LIKE :drug_name
                   AND t.MDC_ORG_CD = :mdc_org_cd
                 ORDER BY t.INHOS_NO'''
    return sql, params, filter_type, date_range, drug_name or None


def _execute_query(sql, params):
    limit = settings.INHOS_QUERY_MAX_RESULTS
    timeout_ms = settings.INHOS_QUERY_TIMEOUT_MS
    engine = create_engine(
        get_source_sqlalchemy_url(),
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={'connection_timeout': max(1, timeout_ms // 1000)},
    )
    results = []
    try:
        with engine.connect() as connection:
            connection.execute(
                text('SET SESSION MAX_EXECUTION_TIME = :timeout_ms'),
                {'timeout_ms': timeout_ms},
            )
            cursor = connection.execution_options(stream_results=True).execute(
                text(f'{sql}\nLIMIT {limit + 1}'), params
            )
            while len(results) <= limit:
                rows = cursor.fetchmany(min(100, limit + 1 - len(results)))
                if not rows:
                    break
                results.extend(str(row[0]) for row in rows if row[0] is not None)
    finally:
        engine.dispose()
    return results[:limit], len(results) > limit


def _database_error_status(exc):
    message = str(getattr(exc, 'orig', exc)).lower()
    orig_args = getattr(getattr(exc, 'orig', None), 'args', ())
    error_code = orig_args[0] if orig_args and isinstance(orig_args[0], int) else None
    if error_code in {1044, 1045, 1142} or 'denied' in message:
        return status.HTTP_403_FORBIDDEN, '无权访问原始医疗数据库'
    if isinstance(exc, OperationalError) or any(
        marker in message for marker in ('timeout', 'timed out', 'max_execution_time')
    ):
        return status.HTTP_504_GATEWAY_TIMEOUT, '数据库连接或查询超时'
    return status.HTTP_500_INTERNAL_SERVER_ERROR, '数据库查询失败'


class InhosNumbersAPIView(APIView):
    def get(self, request):
        try:
            sql, params, filter_type, date_range, drug_filter = _build_query(request)
            inhos_numbers, truncated = _execute_query(sql, params)
            limit = settings.INHOS_QUERY_MAX_RESULTS
            warning = (
                f'结果超过单次返回上限 {limit} 条，请缩小月份范围或增加药品条件'
                if truncated else None
            )
            result = {
                'success': True,
                'inhos_numbers': inhos_numbers,
                'count': len(inhos_numbers),
                'truncated': truncated,
                'limit': limit,
                'filter_type': filter_type,
            }
            if date_range:
                result['date_range'] = date_range
            if drug_filter:
                result['drug_filter'] = drug_filter
            if warning:
                result['warning'] = warning
            return Response({'code': 0, 'result': result})
        except QueryParameterError as exc:
            return Response(
                {'code': 400, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (DBAPIError, OSError) as exc:
            logger.exception('查询住院号时数据库访问失败')
            response_status, message = _database_error_status(exc)
            return Response(
                {'code': response_status, 'message': message},
                status=response_status,
            )
        except Exception:
            logger.exception('查询住院号时发生未预期异常')
            return Response(
                {'code': 500, 'message': '服务器内部错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
