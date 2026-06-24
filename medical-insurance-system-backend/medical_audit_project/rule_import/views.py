import json
import logging
from urllib.parse import quote

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExtractedRule, RuleImportTask
from .serializers import (
    ConfirmImportSerializer,
    ExtractedRuleSerializer,
    RuleImportTaskSerializer,
    UploadSerializer,
)
from .services.importer import import_to_rule_library
from .tasks import run_rule_import_task

logger = logging.getLogger(__name__)


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def _file_ext(name: str) -> str:
    return name.rsplit('.', 1)[-1].lower() if '.' in name else ''


class RuleImportUploadView(APIView):
    """上传文件并异步发起“规则批量导入转换”。

    POST /api/rule-import/upload/
    Body: multipart/form-data, file=<文件> + 可选参数

    鉴权：沿用项目现状（AllowAny）。未来如启用权限，可在此挂载。
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from django.conf import settings

        serializer = UploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        uploaded_file = data['file']

        # —— 文件类型校验 ——
        ext = _file_ext(uploaded_file.name)
        allowed = getattr(settings, 'RULE_IMPORT_ALLOWED_EXTS',
                          ('pdf', 'xlsx', 'xls'))
        if ext not in allowed:
            return Response(
                {'error': f'不支持的文件类型，请上传 {"/".join(allowed)} 文件'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # —— 文件大小校验 ——
        max_size = getattr(settings, 'RULE_IMPORT_MAX_FILE_SIZE',
                           50 * 1024 * 1024)
        if uploaded_file.size and uploaded_file.size > max_size:
            return Response(
                {'error': f'文件过大，最大允许 {max_size // (1024 * 1024)}MB'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 数量类参数不传 = 不限数量(None=全部)；分块行数仅由后端配置决定
            params = {
                'max_pdf_pages': data.get('max_pdf_pages'),
                'max_rows_per_table': data.get('max_rows_per_table'),
                'chunk_size': getattr(
                    settings, 'RULE_IMPORT_DEFAULT_CHUNK_SIZE', 10),
                'max_tables': data.get('max_tables'),
            }
            task = RuleImportTask.objects.create(
                task_name=data.get('task_name') or uploaded_file.name,
                file_name=uploaded_file.name,
                file_size=uploaded_file.size or 0,
                file_type=ext,
                params=params,
                status=RuleImportTask.Status.PENDING,
            )
            # Django FileField 会自动对同名文件追加随机后缀，避免任务间互相覆盖
            task.original_file.save(uploaded_file.name, uploaded_file, save=True)

            # 复用现有异步机制：投递 Celery
            run_rule_import_task.delay(task.id)
            logger.info("[rule_import] 已创建任务 %s 并投递队列", task.id)

            return Response(
                {'task': RuleImportTaskSerializer(task).data},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("[rule_import] 创建任务失败")
            return Response(
                {'error': f'创建任务失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RuleImportTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """规则导入任务：列表 / 详情(轮询) / 抽取结果 / 确认入库 / 下载 / 取消。"""
    queryset = RuleImportTask.objects.all()
    serializer_class = RuleImportTaskSerializer
    pagination_class = StandardPagination
    permission_classes = [AllowAny]
    filterset_fields = ['status']

    def get_queryset(self):
        qs = RuleImportTask.objects.all()
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(task_name__icontains=search)
        return qs

    @action(detail=True, methods=['get'], url_path='rules')
    def extracted_rules(self, request, pk=None):
        """该任务抽取出的规则明细（分页，可按 rule_type 过滤）。"""
        task = self.get_object()
        qs = task.rules.all()
        rule_type = request.query_params.get('rule_type')
        if rule_type:
            qs = qs.filter(rule_type=rule_type)

        page = self.paginate_queryset(qs)
        serializer = ExtractedRuleSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        """把选中的抽取规则写入正式规则库 rules.Rule。"""
        task = self.get_object()
        if task.status != RuleImportTask.Status.SUCCESS:
            return Response(
                {'error': '任务尚未成功完成，无法入库'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ConfirmImportSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            result = import_to_rule_library(
                task,
                rule_ids=serializer.validated_data.get('rule_ids'),
                select_all=serializer.validated_data.get('select_all'),
            )
            return Response({
                'imported': result['imported'],
                'skipped': result['skipped'],
                'rule_ids': result['rule_ids'],
                'task': RuleImportTaskSerializer(task).data,
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("[rule_import] 任务 %s 入库失败", task.id)
            return Response(
                {'error': f'入库失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """下载该任务抽取出的规则 JSON。"""
        task = self.get_object()
        rules = list(task.rules.values(
            'seq', 'rule_type', 'constrained_object', 'constraint_value',
            'evidence', 'source',
        ))
        json_string = json.dumps(rules, ensure_ascii=False, indent=2)
        response = HttpResponse(json_string,
                                content_type='application/json; charset=utf-8')
        filename = f"规则抽取_任务{task.id}.json"
        response['Content-Disposition'] = \
            f"attachment; filename*=utf-8''{quote(filename)}"
        return response

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """取消任务（撤销 Celery 任务并置为已取消）。"""
        task = self.get_object()
        if task.status in (RuleImportTask.Status.SUCCESS,
                           RuleImportTask.Status.FAILED,
                           RuleImportTask.Status.CANCELED):
            return Response(
                {'error': '任务已结束，无法取消'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if task.celery_task_id:
            try:
                from medical_audit_project.celery import app as celery_app
                celery_app.control.revoke(task.celery_task_id, terminate=True)
            except Exception as e:  # noqa: BLE001
                logger.warning("[rule_import] 撤销 Celery 任务失败: %s", e)
        task.status = RuleImportTask.Status.CANCELED
        task.save(update_fields=['status', 'updated_at'])
        return Response({'status': '任务已取消'})
