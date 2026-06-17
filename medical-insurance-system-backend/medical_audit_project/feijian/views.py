from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from tasks.models import Task
from tasks.serializers import TaskSerializer
from tasks.tasks import run_audit_task

from .models import FeiJianImportBatch, FeiJianRawRecord
from .serializers import (
    BuildAuditTaskSerializer,
    ColumnMappingSerializer,
    FeiJianImportBatchSerializer,
    FeiJianRawRecordSerializer,
    FileUploadSerializer,
    PreviewRequestSerializer,
)
from .services.alignment import align_batch_results
from .services.importer import FeiJianImporter


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
        execute = serializer.validated_data.get('execute', True)
        task_name = serializer.validated_data.get('name') or (
            f'飞检自动审查-{batch.file_name}-批次{batch.id}'
        )

        with transaction.atomic():
            task = Task.objects.create(
                name=task_name[:255],
                hospitalization_ids=hospitalization_ids,
                selected_schemas=selected_schemas,
                summary=(
                    f'由飞检导入批次 {batch.id} 自动构建，'
                    f'共 {len(hospitalization_ids)} 个住院号。'
                ),
            )
            if rule_ids:
                task.rules.set(rule_ids)
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
