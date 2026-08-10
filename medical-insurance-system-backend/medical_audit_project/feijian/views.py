from django.db import transaction
from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from tasks.models import Task
from tasks.serializers import TaskSerializer
from tasks.tasks import run_audit_task
from rules.models import Rule
from rules.services import AgentAService

from .models import FeiJianImportBatch, FeiJianRawRecord
from .serializers import (
    BuildAuditTaskSerializer,
    ColumnMappingSerializer,
    ConfirmGeneratedIndicatorsSerializer,
    FeiJianImportBatchSerializer,
    FeiJianRawRecordSerializer,
    FileUploadSerializer,
    PreviewRequestSerializer,
    GenerateIndicatorsSerializer,
)
from .services.alignment import UNMATCHED, align_batch_results, canonical_category, normalize_text
from .services.importer import FeiJianImporter


def _suggest_rule_name(issue_category, issue_description):
    """为候选规则提供可人工编辑的初始名称。"""
    category = (issue_category or '').strip()
    description = (issue_description or '').strip()
    if category and category not in {'其他', '其他问题', '违规', '问题'}:
        return category[:255]
    return (description or '飞检新增指标')[:255]


def _build_indicator_rule_text(*, issue_category, issue_description):
    """把飞检问题表达为规则编译器可理解、但不虚构条件的自然语言。"""
    category = (issue_category or '未分类问题').strip()
    description = (issue_description or '').strip()
    return (
        '请根据以下飞检发现生成一条可执行的医保审查规则。'
        '只能依据问题描述中明确出现的项目、次数、金额、日期、诊断或病历字段构造判断；'
        '描述不够明确时，应保守处理，不得虚构阈值或医学条件。\n'
        f'飞检问题类别：{category}\n'
        f'飞检问题描述：{description}'
    )


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class FeiJianImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """导入批次视图集"""
    queryset = FeiJianImportBatch.objects.all()
    serializer_class = FeiJianImportBatchSerializer
    pagination_class = StandardPagination

    @action(detail=True, methods=['post'], url_path='build-audit-task')
    def build_audit_task(self, request, pk=None):
        """基于当前飞检导入批次识别出的住院号创建自动审查任务。"""
        batch = self.get_object()
        serializer = BuildAuditTaskSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        records = batch.records.exclude(hospitalization_no='').order_by('row_index')
        hospitalization_ids = []
        seen = set()
        for hos_id in records.values_list('hospitalization_no', flat=True):
            hos_id = str(hos_id).strip()
            if hos_id and hos_id not in seen:
                seen.add(hos_id)
                hospitalization_ids.append(hos_id)

        if not hospitalization_ids:
            return Response(
                {'error': '当前导入批次没有可用于审查的住院号'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selected_schemas = serializer.validated_data.get('selectedSchemas') or [
            '超限定用药',
            '重复收费',
            '超标准收费',
        ]
        rule_ids = serializer.validated_data.get('rule_ids') or []
        if not rule_ids:
            return Response(
                {'rule_ids': ['请至少选择一条需要执行的规则。']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 仅允许将已启用、且属于所选审查方案的规则加入任务，避免页面选择
        # 与实际执行范围不一致。
        selected_rules = list(
            Rule.objects.filter(id__in=set(rule_ids), status=True).order_by('id')
        )
        if len(selected_rules) != len(set(rule_ids)):
            return Response(
                {'rule_ids': ['存在不存在或未启用的规则，请刷新后重新选择。']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invalid_rules = [rule.rule_id for rule in selected_rules if rule.type not in selected_schemas]
        if invalid_rules:
            return Response(
                {'rule_ids': [f'规则 {", ".join(invalid_rules)} 不属于已选审查方案。']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        execute = serializer.validated_data.get('execute', True)
        mdc_org_cd = (
            str(serializer.validated_data.get('mdc_org_cd') or getattr(settings, 'SOURCE_MDC_ORG_CD', '')).strip()
        )
        task_name = serializer.validated_data.get('name') or (
            f'飞检自动审查-{batch.file_name}-批次{batch.id}'
        )

        with transaction.atomic():
            task = Task.objects.create(
                name=task_name[:255],
                hospitalization_ids=hospitalization_ids,
                mdc_org_cd=mdc_org_cd,
                selected_schemas=selected_schemas,
                summary=(
                    f'由飞检导入批次 {batch.id} 自动构建，'
                    f'共 {len(hospitalization_ids)} 个住院号。'
                ),
            )
            task.rules.set(selected_rules)
            batch.records.update(audit_task_id=str(task.id))

        queued = False
        if execute:
            run_audit_task.delay(task.id)
            task.status = Task.Status.PENDING
            task.summary = (
                f'由飞检导入批次 {batch.id} 自动构建，'
                f'共 {len(hospitalization_ids)} 个住院号；任务已加入执行队列。'
            )
            task.save(update_fields=['status', 'summary'])
            queued = True

        return Response(
            {
                'task': TaskSerializer(task).data,
                'batch': FeiJianImportBatchSerializer(batch).data,
                'hospitalization_count': len(hospitalization_ids),
                'queued': queued,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get', 'post'], url_path='align-results')
    def align_results(self, request, pk=None):
        """对齐当前飞检批次与系统审查结果。"""
        batch = self.get_object()
        payload = request.data if request.method == 'POST' else request.query_params
        raw_task_id = (
            payload.get('task_id')
            if request.method == 'POST'
            else payload.get('task_id')
        )
        task_id = None
        if raw_task_id not in [None, '']:
            try:
                task_id = int(raw_task_id)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'task_id 必须是数字'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        use_llm = str(payload.get('use_llm', '')).strip().lower() in {
            '1',
            'true',
            'yes',
            'on',
        }
        result = align_batch_results(batch, task_id=task_id, use_llm=use_llm)
        total = len(result.get('items', []))
        try:
            page = max(int(payload.get('page', 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(payload.get('page_size', 10))
        except (TypeError, ValueError):
            page_size = 10
        page_size = min(max(page_size, 1), 100)
        start = (page - 1) * page_size
        end = start + page_size
        result['items'] = result.get('items', [])[start:end]
        result['pagination'] = {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': (total + page_size - 1) // page_size if total else 0,
        }
        return Response(result)

    @action(detail=True, methods=['post'], url_path='generate-indicators')
    def generate_indicators(self, request, pk=None):
        """把选中的“仅飞检发现”项转换为待人工确认的新规则候选。"""
        batch = self.get_object()
        serializer = GenerateIndicatorsSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        record_ids = list(dict.fromkeys(serializer.validated_data['record_ids']))
        task_id = serializer.validated_data.get('task_id')
        alignment = align_batch_results(batch, task_id=task_id, use_llm=False)
        unmatched_ids = {
            item.get('feijianRecordId')
            for item in alignment.get('items', [])
            if item.get('matchStatus') == UNMATCHED and item.get('feijianRecordId')
        }
        invalid_ids = sorted(set(record_ids) - unmatched_ids)
        if invalid_ids:
            return Response(
                {'record_ids': [f'记录 {", ".join(map(str, invalid_ids))} 不是“仅飞检发现”项，不能生成新指标。']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        records = list(batch.records.filter(id__in=record_ids).order_by('row_index', 'id'))
        found_ids = {record.id for record in records}
        missing_ids = sorted(set(record_ids) - found_ids)
        if missing_ids:
            return Response(
                {'record_ids': [f'当前批次不存在记录：{", ".join(map(str, missing_ids))}']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 同一批次中相同问题只生成一条候选规则，避免重复入库。
        groups = {}
        for record in records:
            issue_text = (record.issue_description or record.issue_category or '').strip()
            group_key = normalize_text(f'{record.issue_category} {issue_text}') or str(record.id)
            groups.setdefault(group_key, []).append(record)

        candidates = []
        for grouped_records in groups.values():
            representative = grouped_records[0]
            issue_description = (representative.issue_description or representative.issue_category or '').strip()
            issue_category = (representative.issue_category or '').strip()
            rule_type = canonical_category(f'{issue_category} {issue_description}') or '其他类型'
            rule_name = _suggest_rule_name(issue_category, issue_description)
            rule_text = _build_indicator_rule_text(
                issue_category=issue_category,
                issue_description=issue_description,
            )
            candidate = {
                'source_record_ids': [record.id for record in grouped_records],
                'source_hospitalization_nos': [record.hospitalization_no for record in grouped_records],
                'rule_name': rule_name,
                'description': issue_description,
                'type': rule_type,
                'rule_text': rule_text,
                'rule_code': '',
                'validation': {'valid': False, 'errors': []},
            }
            try:
                generated = AgentAService.build(rule_text)
                candidate['rule_code'] = generated.generated_code
                candidate['validation'] = generated.validation
                candidate['generation_message'] = '模型已生成候选执行函数，请人工复核后入库。'
            except Exception as exc:
                candidate['generation_message'] = f'模型生成失败：{str(exc)}'
                candidate['validation'] = {'valid': False, 'errors': [str(exc)]}
            candidates.append(candidate)

        return Response({
            'batch_id': batch.id,
            'task_id': alignment.get('task_id'),
            'candidates': candidates,
            'message': '候选指标仅供人工复核；确认入库后默认停用。',
        })

    @action(detail=True, methods=['post'], url_path='confirm-generated-indicators')
    def confirm_generated_indicators(self, request, pk=None):
        """将人工确认的飞检候选指标写入正式规则库，始终默认停用。"""
        batch = self.get_object()
        serializer = ConfirmGeneratedIndicatorsSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        created_rules = []
        errors = []
        with transaction.atomic():
            for index, candidate in enumerate(serializer.validated_data['candidates'], start=1):
                record_ids = candidate.get('source_record_ids') or []
                try:
                    record_ids = sorted({int(value) for value in record_ids})
                except (TypeError, ValueError):
                    record_ids = []
                source_records = list(batch.records.filter(id__in=record_ids).order_by('id'))
                if not source_records or len(source_records) != len(record_ids):
                    errors.append({'index': index, 'error': '来源飞检记录无效或不属于当前批次。'})
                    continue

                rule_name = str(candidate.get('rule_name') or '').strip()
                description = str(candidate.get('description') or '').strip()
                rule_type = str(candidate.get('type') or '其他类型').strip()
                rule_code = str(candidate.get('rule_code') or '').strip()
                if not rule_name or not description or not rule_code:
                    errors.append({'index': index, 'error': '规则名称、规则描述和执行函数均不能为空。'})
                    continue
                validation = AgentAService.validate_code(rule_code)
                if not validation.get('valid'):
                    errors.append({'index': index, 'error': '执行函数校验失败。', 'details': validation.get('errors', [])})
                    continue

                source_ids = ','.join(str(record.id) for record in source_records)
                rule_id = f'FJ-{batch.id}-{source_records[0].id}'
                source_note = f'【飞检自动生成候选｜批次{batch.id}｜原始记录{source_ids}｜默认停用】'
                rule_obj, created = Rule.objects.get_or_create(
                    rule_id=rule_id,
                    defaults={
                        'drug_name': rule_name[:255],
                        'description': f'{description}\n{source_note}',
                        'type': rule_type[:50],
                        'rule_code': rule_code,
                        'status': False,
                    },
                )
                created_rules.append({
                    'id': rule_obj.id,
                    'ruleId': rule_obj.rule_id,
                    'ruleName': rule_obj.drug_name,
                    'created': created,
                    'enabled': rule_obj.status,
                })

        response_status = status.HTTP_201_CREATED if created_rules else status.HTTP_400_BAD_REQUEST
        return Response({
            'created_rules': created_rules,
            'errors': errors,
            'message': '已入库的候选规则均为停用状态，请在规则库复核后手工启用。',
        }, status=response_status)


class FeiJianRawRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """原始记录视图集"""
    serializer_class = FeiJianRawRecordSerializer
    pagination_class = StandardPagination
    filterset_fields = ['import_batch', 'hospitalization_no', 'issue_category']

    def get_queryset(self):
        qs = FeiJianRawRecord.objects.all()
        import_batch = self.request.query_params.get('import_batch')
        if import_batch:
            qs = qs.filter(import_batch_id=import_batch)
        hospitalization_no = self.request.query_params.get('hospitalization_no')
        if hospitalization_no:
            qs = qs.filter(hospitalization_no__icontains=hospitalization_no)
        return qs


class FileUploadView(APIView):
    """
    上传飞检文件并自动分析列结构

    POST /api/feijian/upload/
    Body: multipart/form-data, key=file

    Response:
    {
        "batch": { ... },
        "analysis": {
            "columns": ["A", "B", ...],
            "sample_rows": [{...}, ...],
            "mappings": [
                {"field_key": "hospitalization_no", "field_label": "住院号",
                 "column_name": "A", "confidence": 0.95, "method": "regex+data"},
                ...
            ],
            "unmapped_fields": ["audit_date"],
            "unmapped_columns": ["备注"],
            "llm_analysis": "..."
        }
    }
    """

    def post(self, request):
        serializer = FileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data['file']

        # 检查文件类型
        ext = uploaded_file.name.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.name else ''
        if ext not in ('xlsx', 'xls', 'csv'):
            return Response(
                {'error': '不支持的文件类型，请上传 .xlsx / .xls / .csv 文件'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            importer = FeiJianImporter(enable_llm=True)
            batch, analysis = importer.upload_and_analyze(uploaded_file)

            return Response({
                'batch': FeiJianImportBatchSerializer(batch).data,
                'analysis': {
                    'columns': analysis.columns,
                    'sample_rows': analysis.sample_rows,
                    'mappings': [
                        {
                            'field_key': m.field_key,
                            'field_label': m.field_label,
                            'column_name': m.column_name,
                            'column_index': m.column_index,
                            'confidence': round(m.confidence, 2),
                            'method': m.method,
                        }
                        for m in analysis.mappings
                    ],
                    'unmapped_fields': analysis.unmapped_fields,
                    'unmapped_columns': analysis.unmapped_columns,
                    'llm_analysis': analysis.llm_analysis,
                },
            })

        except Exception as e:
            return Response(
                {'error': f'文件分析失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PreviewImportView(APIView):
    """
    预览导入结果

    POST /api/feijian/preview/
    Body: {"batch_id": 1, "column_mapping": {"hospitalization_no": "A", ...}}
    """

    def post(self, request):
        serializer = PreviewRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        batch_id = serializer.validated_data['batch_id']
        column_mapping = serializer.validated_data['column_mapping']
        limit = serializer.validated_data['limit']

        try:
            batch = FeiJianImportBatch.objects.get(id=batch_id)
        except FeiJianImportBatch.DoesNotExist:
            return Response(
                {'error': '批次不存在'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            importer = FeiJianImporter()
            preview = importer.get_preview(batch, column_mapping, limit)
            return Response({
                'preview': preview,
                'totalRows': batch.record_count or len(preview),
            })
        except Exception as e:
            return Response(
                {'error': f'预览失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ConfirmImportView(APIView):
    """
    确认列映射并执行导入

    POST /api/feijian/confirm-import/
    Body: {"batch_id": 1, "column_mapping": {"hospitalization_no": "A", ...}}
    """

    def post(self, request):
        serializer = ColumnMappingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        batch_id = serializer.validated_data['batch_id']
        column_mapping = serializer.validated_data['column_mapping']

        try:
            batch = FeiJianImportBatch.objects.get(id=batch_id)
        except FeiJianImportBatch.DoesNotExist:
            return Response(
                {'error': '批次不存在'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            importer = FeiJianImporter()
            batch = importer.import_with_mapping(batch, column_mapping)

            return Response({
                'batch': FeiJianImportBatchSerializer(batch).data,
                'summary': {
                    'total': batch.record_count,
                    'success': batch.success_count,
                    'error': batch.error_count,
                },
            })

        except Exception as e:
            return Response(
                {'error': f'导入失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FeiJianStatsView(APIView):
    """
    获取飞检统计数据

    GET /api/feijian/stats/
    """

    def get(self, request):
        total_imports = FeiJianImportBatch.objects.filter(
            status=FeiJianImportBatch.Status.SUCCESS,
        ).count()
        total_raw = FeiJianRawRecord.objects.count()
        latest_batch = FeiJianImportBatch.objects.filter(
            records__audit_task_id__gt='',
        ).distinct().order_by('-updated_at').first()
        alignment_summary = None
        if latest_batch:
            alignment_summary = align_batch_results(latest_batch).get('summary')

        return Response({
            'totalImports': total_imports,
            'totalRawRecords': total_raw,
            'auditTaskCount': FeiJianRawRecord.objects.exclude(
                audit_task_id='',
            ).values('audit_task_id').distinct().count(),
            'alignmentRate': alignment_summary.get('alignmentRate', 0) if alignment_summary else 0,
            'diffCount': alignment_summary.get('diffCount', 0) if alignment_summary else 0,
            'unresolvedDiffCount': alignment_summary.get('unresolvedDiffCount', 0) if alignment_summary else 0,
        })
