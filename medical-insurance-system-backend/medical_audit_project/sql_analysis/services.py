import re
import time
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

import pymysql
from django.utils import timezone

from data_adapter.source_db import get_source_db_config

from .models import SQLExecution, SQLRule


SQL_PREVIEW_ROW_LIMIT = 500
SQL_QUERY_TIMEOUT_MS = 120000
QUERY_PREFIX_PATTERN = re.compile(r'^\s*(?:/\*.*?\*/\s*)*(?:--.*?$[\r\n]*)*', re.S | re.M)
STRING_LITERAL_PATTERN = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", re.S)
FORBIDDEN_SQL_PATTERN = re.compile(
    r'\b(insert|update|delete|drop|alter|truncate|create|replace|call)\b',
    re.I,
)


class SQLExecutionError(ValueError):
    pass



@contextmanager
def source_medical_cursor():
    """使用 PyMySQL 直连源库，兼容报告为 MySQL 5.7 的 OceanBase。"""
    config = get_source_db_config()
    timeout_seconds = max(1, SQL_QUERY_TIMEOUT_MS // 1000)
    connection = pymysql.connect(
        host=config["host"],
        port=int(config["port"]),
        user=config["user"],
        password=config["password"],
        database=config["database"],
        charset=config["charset"],
        autocommit=True,
        connect_timeout=10,
        read_timeout=timeout_seconds + 5,
        write_timeout=10,
    )
    try:
        with connection.cursor() as cursor:
            yield cursor
    finally:
        connection.close()


def validate_query_sql(sql: str) -> str:
    normalized = str(sql or '').strip()
    if not normalized:
        raise SQLExecutionError('SQL内容不能为空')

    normalized = normalized.rstrip(';').strip()
    if ';' in normalized:
        raise SQLExecutionError('仅支持执行单条查询SQL。')

    no_prefix = QUERY_PREFIX_PATTERN.sub('', normalized, count=1).strip()
    if not no_prefix:
        raise SQLExecutionError('SQL内容不能为空')

    leading = no_prefix.split(None, 1)[0].upper()
    if leading not in {'SELECT', 'WITH'}:
        raise SQLExecutionError('仅支持执行查询类SQL。')

    sanitized = STRING_LITERAL_PATTERN.sub("''", no_prefix)
    if FORBIDDEN_SQL_PATTERN.search(sanitized):
        raise SQLExecutionError('仅支持执行查询类SQL。')

    return normalized


def render_query_sql(sql: str, start_date: str, end_date: str) -> str:
    validated = validate_query_sql(sql)
    return (
        validated
        .replace('{{START_DATE}}', start_date)
        .replace('{{END_DATE}}', end_date)
    )


def _fetch_query_rows(sql: str) -> Tuple[List[str], int, List[Dict[str, Any]], bool]:
    preview_rows: List[Dict[str, Any]] = []
    total_rows = 0
    with source_medical_cursor() as cursor:
        try:
            cursor.execute('SET SESSION MAX_EXECUTION_TIME = %s', [SQL_QUERY_TIMEOUT_MS])
        except Exception:
            # Some MySQL-compatible deployments do not support this session variable.
            pass
        cursor.execute(sql)
        columns = [item[0] for item in (cursor.description or [])]
        while True:
            batch = cursor.fetchmany(200)
            if not batch:
                break
            for raw_row in batch:
                total_rows += 1
                if len(preview_rows) < SQL_PREVIEW_ROW_LIMIT:
                    preview_rows.append(
                        {
                            columns[index]: _serialize_cell(value)
                            for index, value in enumerate(raw_row)
                        }
                    )
    return columns, total_rows, preview_rows, total_rows > SQL_PREVIEW_ROW_LIMIT


def _serialize_cell(value: Any):
    if isinstance(value, Decimal):
        # Preserve integers as ints and fractional values as floats for JSON storage.
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, 'isoformat') and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='ignore')
    return value


def execute_sql_rule(rule: SQLRule, start_date, end_date) -> SQLExecution:
    execute_started_at = timezone.now()
    start_ts = time.perf_counter()
    rendered_sql = render_query_sql(
        rule.sql_content,
        start_date.isoformat(),
        end_date.isoformat(),
    )

    try:
        columns, row_count, preview_rows, truncated = _fetch_query_rows(rendered_sql)
        duration_ms = int((time.perf_counter() - start_ts) * 1000)
        return SQLExecution.objects.create(
            sql_rule=rule,
            start_date=start_date,
            end_date=end_date,
            execute_status=SQLExecution.ExecuteStatus.SUCCESS,
            execute_time=execute_started_at,
            duration=duration_ms,
            row_count=row_count,
            result_json={
                'columns': columns,
                'rows': preview_rows,
                'previewRowLimit': SQL_PREVIEW_ROW_LIMIT,
                'truncated': truncated,
                'renderedSql': rendered_sql,
            },
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_ts) * 1000)
        return SQLExecution.objects.create(
            sql_rule=rule,
            start_date=start_date,
            end_date=end_date,
            execute_status=SQLExecution.ExecuteStatus.FAILED,
            execute_time=execute_started_at,
            duration=duration_ms,
            row_count=0,
            result_json={
                'columns': [],
                'rows': [],
                'previewRowLimit': SQL_PREVIEW_ROW_LIMIT,
                'truncated': False,
                'renderedSql': rendered_sql,
            },
            error_message=str(exc),
        )


def paginate_queryset(queryset, page: int, page_size: int) -> Tuple[Iterable[Any], int]:
    total = queryset.count()
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return queryset[start:end], total
