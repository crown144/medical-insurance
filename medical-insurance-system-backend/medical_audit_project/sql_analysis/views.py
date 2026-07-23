from datetime import date
from urllib.parse import quote

from django.db import transaction
from django.db.models import Count, IntegerField, Max, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from openpyxl import Workbook
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import SQLExecution, SQLRule
from .serializers import (
    SQLExecutionSerializer,
    SQLRuleExecutionDetailSerializer,
    SQLRuleExecutionSummarySerializer,
    SQLRuleSerializer,
)
from .services import SQLExecutionError, execute_sql_rule, paginate_queryset


def _success(data=None, message='ok', response_status=status.HTTP_200_OK):
    payload = {
        'code': 0,
        'message': message,
        'data': data,
        'result': data,
        'type': 'success',
    }
    return Response(payload, status=response_status)


def _error(message, response_status=status.HTTP_400_BAD_REQUEST, code=1):
    normalized_message = message
    if isinstance(message, dict):
        parts = []
        for key, value in message.items():
            if isinstance(value, list):
                parts.append(f'{key}: {"; ".join(str(item) for item in value)}')
            else:
                parts.append(f'{key}: {value}')
        normalized_message = '; '.join(parts)
    return Response(
        {
            'code': code,
            'message': normalized_message,
            'error': normalized_message,
            'data': None,
            'result': None,
            'type': 'error',
        },
        status=response_status,
    )


def _parse_page_params(request):
    try:
        page = max(int(request.query_params.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(
            request.query_params.get('page_size', request.query_params.get('pageSize', 10))
        )
    except (TypeError, ValueError):
        page_size = 10
    page_size = min(max(page_size, 1), 100)
    return page, page_size


def _annotated_rule_queryset():
    latest_execution = SQLExecution.objects.filter(sql_rule_id=OuterRef('pk')).order_by(
        '-execute_time',
        '-id',
    )
    return SQLRule.objects.all().annotate(
        recent_execute_time=Max('executions__execute_time'),
        execution_count=Count('executions'),
        total_violation_count=Coalesce(
            Sum('executions__row_count'),
            Value(0),
            output_field=IntegerField(),
        ),
        latest_violation_count=Coalesce(
            Subquery(latest_execution.values('row_count')[:1]),
            Value(0),
            output_field=IntegerField(),
        ),
        recent_execute_status=Coalesce(
            Subquery(latest_execution.values('execute_status')[:1]),
            Value('never'),
        ),
    )


def _result_overview_stats(queryset):
    aggregated = queryset.aggregate(
        total_rules=Count('id'),
        executed_rules=Count('id', filter=Q(execution_count__gt=0)),
        total_executions=Coalesce(
            Sum('execution_count'),
            Value(0),
            output_field=IntegerField(),
        ),
        total_violations=Coalesce(
            Sum('total_violation_count'),
            Value(0),
            output_field=IntegerField(),
        ),
    )
    return {
        'totalRules': aggregated['total_rules'] or 0,
        'executedRules': aggregated['executed_rules'] or 0,
        'totalExecutions': aggregated['total_executions'] or 0,
        'totalViolations': aggregated['total_violations'] or 0,
    }


def _sanitize_filename(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    sanitized = ''.join('_' if char in invalid_chars else char for char in str(value or ''))
    sanitized = ' '.join(sanitized.split()).strip(' .')
    return sanitized or 'sql_result'


def _build_download_filename(execution: SQLExecution) -> str:
    execute_time = execution.execute_time.strftime('%Y%m%d_%H%M%S')
    rule_name = _sanitize_filename(execution.sql_rule.rule_name)
    return f'{rule_name}_{execute_time}.xlsx'


def _build_excel_response(execution: SQLExecution) -> HttpResponse:
    result_json = execution.result_json or {}
    columns = result_json.get('columns') or []
    rows = result_json.get('rows') or []

    if execution.execute_status != SQLExecution.ExecuteStatus.SUCCESS:
        raise SQLExecutionError('当前执行记录为失败状态，无法下载结果。')
    if not columns or not rows:
        raise SQLExecutionError('暂无可下载数据。')

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'SQL结果'
    worksheet.append(columns)

    for row in rows:
        worksheet.append([row.get(column) for column in columns])

    filename = _build_download_filename(execution)
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f"attachment; filename=sql_result.xlsx; filename*=UTF-8''{quote(filename)}"
    )
    workbook.save(response)
    return response


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def sql_rule_collection(request):
    if request.method == 'GET':
        queryset = SQLRule.objects.all().order_by('-updated_at', '-id')
        keyword = str(request.query_params.get('keyword') or '').strip()
        rule_type = str(
            request.query_params.get('rule_type') or request.query_params.get('ruleType') or ''
        ).strip()
        sql_status = str(
            request.query_params.get('sql_status') or request.query_params.get('sqlStatus') or ''
        ).strip()

        if keyword:
            queryset = queryset.filter(rule_name__icontains=keyword)
        if rule_type:
            queryset = queryset.filter(rule_type=rule_type)
        if sql_status == '已配置':
            queryset = queryset.exclude(sql_content='')
        elif sql_status == '未配置':
            queryset = queryset.filter(sql_content='')

        page, page_size = _parse_page_params(request)
        items, total = paginate_queryset(queryset, page, page_size)
        return _success(
            {
                'items': SQLRuleSerializer(items, many=True).data,
                'total': total,
                'page': page,
                'pageSize': page_size,
            }
        )

    serializer = SQLRuleSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _error(serializer.errors, response_status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        instance = serializer.save()
    return _success(
        SQLRuleSerializer(instance).data,
        message='保存成功',
        response_status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([AllowAny])
def sql_rule_item(request, pk: int):
    instance = get_object_or_404(SQLRule, pk=pk)

    if request.method == 'GET':
        return _success(SQLRuleSerializer(instance).data)

    if request.method == 'PUT':
        serializer = SQLRuleSerializer(instance, data=request.data or {})
        if not serializer.is_valid():
            return _error(serializer.errors, response_status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            instance = serializer.save()
        return _success(SQLRuleSerializer(instance).data, message='更新成功')

    with transaction.atomic():
        instance.delete()
    return _success(None, message='删除成功')


@api_view(['POST'])
@permission_classes([AllowAny])
def sql_execute(request):
    payload = request.data or {}
    rule_id = payload.get('sql_rule_id') or payload.get('sqlRuleId')
    start_date = payload.get('start_date') or payload.get('startDate')
    end_date = payload.get('end_date') or payload.get('endDate')

    if not rule_id:
        return _error('请选择医保规则')
    if not start_date or not end_date:
        return _error('请选择开始日期和结束日期')

    try:
        rule = SQLRule.objects.get(pk=rule_id)
    except SQLRule.DoesNotExist:
        return _error('SQL规则不存在', response_status=status.HTTP_404_NOT_FOUND)

    try:
        parsed_start = date.fromisoformat(str(start_date))
        parsed_end = date.fromisoformat(str(end_date))
    except ValueError:
        return _error('日期格式必须为 YYYY-MM-DD')
    if parsed_end < parsed_start:
        return _error('结束日期不能早于开始日期')

    try:
        execution = execute_sql_rule(rule, parsed_start, parsed_end)
    except SQLExecutionError as exc:
        return _error(str(exc), response_status=status.HTTP_400_BAD_REQUEST)

    response_status = status.HTTP_200_OK
    if execution.execute_status == SQLExecution.ExecuteStatus.FAILED:
        response_status = status.HTTP_400_BAD_REQUEST
    return _success(
        SQLExecutionSerializer(execution).data,
        message='执行完成'
        if execution.execute_status == SQLExecution.ExecuteStatus.SUCCESS
        else '执行失败',
        response_status=response_status,
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def sql_history_collection(request):
    queryset = SQLExecution.objects.select_related('sql_rule').all().order_by('-execute_time', '-id')
    rule_id = request.query_params.get('sql_rule_id') or request.query_params.get('sqlRuleId')
    if rule_id:
        queryset = queryset.filter(sql_rule_id=rule_id)

    page, page_size = _parse_page_params(request)
    items, total = paginate_queryset(queryset, page, page_size)
    return _success(
        {
            'items': SQLExecutionSerializer(items, many=True).data,
            'total': total,
            'page': page,
            'pageSize': page_size,
        }
    )


@api_view(['GET', 'DELETE'])
@permission_classes([AllowAny])
def sql_history_item(request, pk: int):
    instance = get_object_or_404(SQLExecution.objects.select_related('sql_rule'), pk=pk)

    if request.method == 'GET':
        return _success(SQLExecutionSerializer(instance).data)

    with transaction.atomic():
        instance.delete()
    return _success(None, message='删除成功')


@api_view(['GET'])
@permission_classes([AllowAny])
def sql_history_download(request, pk: int):
    instance = get_object_or_404(SQLExecution.objects.select_related('sql_rule'), pk=pk)
    try:
        return _build_excel_response(instance)
    except SQLExecutionError as exc:
        return _error(str(exc), response_status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def sql_result_rule_collection(request):
    queryset = _annotated_rule_queryset()
    keyword = str(request.query_params.get('keyword') or '').strip()
    rule_type = str(
        request.query_params.get('rule_type') or request.query_params.get('ruleType') or ''
    ).strip()
    ordering = str(request.query_params.get('ordering') or '-recentExecuteTime').strip()

    if keyword:
        queryset = queryset.filter(rule_name__icontains=keyword)
    if rule_type:
        queryset = queryset.filter(rule_type=rule_type)

    allowed_ordering = {
        'ruleName': 'rule_name',
        '-ruleName': '-rule_name',
        'ruleType': 'rule_type',
        '-ruleType': '-rule_type',
        'recentExecuteTime': 'recent_execute_time',
        '-recentExecuteTime': '-recent_execute_time',
        'executionCount': 'execution_count',
        '-executionCount': '-execution_count',
        'totalViolationCount': 'total_violation_count',
        '-totalViolationCount': '-total_violation_count',
        'updatedAt': 'updated_at',
        '-updatedAt': '-updated_at',
    }
    queryset = queryset.order_by(allowed_ordering.get(ordering, '-recent_execute_time'), '-id')

    stats = _result_overview_stats(queryset)
    page, page_size = _parse_page_params(request)
    items, total = paginate_queryset(queryset, page, page_size)
    return _success(
        {
            'stats': stats,
            'items': SQLRuleExecutionSummarySerializer(items, many=True).data,
            'total': total,
            'page': page,
            'pageSize': page_size,
        }
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def sql_result_rule_item(request, pk: int):
    rule = get_object_or_404(_annotated_rule_queryset(), pk=pk)
    execution_queryset = SQLExecution.objects.select_related('sql_rule').filter(sql_rule_id=pk).order_by(
        '-execute_time',
        '-id',
    )
    page, page_size = _parse_page_params(request)
    items, total = paginate_queryset(execution_queryset, page, page_size)
    return _success(
        {
            'rule': SQLRuleExecutionDetailSerializer(rule).data,
            'executions': {
                'items': SQLExecutionSerializer(items, many=True).data,
                'total': total,
                'page': page,
                'pageSize': page_size,
            },
        }
    )
