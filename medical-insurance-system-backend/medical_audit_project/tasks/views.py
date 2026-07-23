from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend # 导入
from django.conf import settings
from .models import Task
from .serializers import TaskSerializer
from .tasks import get_patient_data, run_audit_task
from results.report_generator import ReportGenerator
import json
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile
from accounts.auth import get_request_profile
# Case 模型默认映射到 cases_case（不是 case_case）。
from cases.models import Case
from results.models import Result # 直接导入 Result 模型
from results.word_generator import generate_task_report_docx # 导入我们的新函数


MAX_RESULT_CASE_DOWNLOAD = 20


def _is_developer_request(request) -> bool:
    profile = get_request_profile(request)
    return bool(profile and profile.role == 'developer')


def _case_download_filename(hospitalization_id: str) -> str:
    """将住院号转换为安全的 ZIP 内 JSON 文件名。"""
    safe_id = ''.join(
        char if char.isalnum() or char in ('-', '_') else '_'
        for char in str(hospitalization_id)
    )
    return f'{safe_id or "unknown"}.json'


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all().order_by('-created_at')
    serializer_class = TaskSerializer
    
    # --- 新增过滤配置 ---
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    # 'name' 对应前端的 “任务名称”
    search_fields = ['name'] 
    # 'id' 对应 “任务ID”, 'status' 对应 “任务状态”
    filterset_fields = ['id', 'status'] 

    @action(detail=True, methods=['post'], url_path='execute')
    def execute_task(self, request, pk=None):
        """
        触发执行一个任务
        """
        try:
            task = self.get_object()
            if task.status == 'running':
                return Response({'error': '任务正在运行中，请勿重复执行'}, status=status.HTTP_400_BAD_REQUEST)

            # 调用 Celery 异步任务
            run_audit_task.delay(task.id)

            # 更新任务状态为 'pending' (待处理)，表示已接收
            task.status = 'pending'
            task.summary = '任务已加入队列，等待执行...'
            task.save()

            return Response({'status': '任务已成功加入执行队列'}, status=status.HTTP_202_ACCEPTED)
        except Task.DoesNotExist:
            return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)
           # --- 新增下载 JSON 报告的 action ---
    
    @action(detail=True, methods=['get'], url_path='download-json-report')
    def download_json_report(self, request, pk=None):
        """下载指定任务的 JSON 格式违规报告。"""
        print("--- V4: 正在运行视图内嵌版的 download_json_report! ---")
        task = self.get_object()
        
        # --- 把 ReportGenerator 的逻辑直接搬到这里 ---
        results = Result.objects.filter(task_id=task.id).select_related('rule')
        violations_data = []
        for result in results:
            violations_data.append({
                "违规项目": result.violation_item,
                "违规原因": result.reason,
                "有关依据": result.rule.description if result.rule else "N/A"
            })
        json_string = json.dumps(violations_data, ensure_ascii=False, indent=2)
        response = HttpResponse(json_string, content_type='application/json; charset=utf-8')
        filename = f"违规报告_任务{task.id}.json"
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(filename)}"
        return response

    @action(detail=True, methods=['get'], url_path='download-result-cases')
    def download_result_cases(self, request, pk=None):
        """开发用户下载任务内所有病历 JSON，不受违规命中情况影响。"""
        if not _is_developer_request(request):
            return Response(
                {'error': '仅 developer 账号可下载任务病历。'},
                status=status.HTTP_403_FORBIDDEN,
            )

        task = self.get_object()
        raw_hospitalization_ids = task.hospitalization_ids or []
        hospitalization_ids = list(dict.fromkeys(
            str(hospitalization_id).strip()
            for hospitalization_id in raw_hospitalization_ids
            if str(hospitalization_id or '').strip()
        ))
        case_count = len(hospitalization_ids)
        if case_count == 0:
            return Response(
                {'error': '该任务未配置可下载的病历。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if case_count > MAX_RESULT_CASE_DOWNLOAD:
            return Response(
                {
                    'error': (
                        f'该任务包含 {case_count} 份病历，'
                        f'单次最多允许下载 {MAX_RESULT_CASE_DOWNLOAD} 份。'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        org_code = (task.mdc_org_cd or getattr(settings, 'SOURCE_MDC_ORG_CD', '') or '').strip()
        cache_keys = {
            hospitalization_id: (
                f'{org_code}:{hospitalization_id}' if org_code else hospitalization_id
            )
            for hospitalization_id in hospitalization_ids
        }
        cases_by_key = Case.objects.in_bulk(cache_keys.values())

        # 兼容机构编码上线前写入的旧缓存键；不会向源系统补拉病历。
        # 通过 Case ORM 查询，实际数据表为 cases_case。
        missing_ids = [
            hospitalization_id
            for hospitalization_id, cache_key in cache_keys.items()
            if cache_key not in cases_by_key
        ]
        legacy_cases = Case.objects.in_bulk(missing_ids) if org_code and missing_ids else {}

        case_payloads = []
        unresolved_ids = []
        for hospitalization_id in hospitalization_ids:
            case = (
                cases_by_key.get(cache_keys[hospitalization_id])
                or legacy_cases.get(hospitalization_id)
            )
            if case is not None:
                case_payloads.append((hospitalization_id, case.json_content))
                continue

            # 历史任务可能在病例缓存机制上线前执行；此时按任务住院号补取，
            # 不能因为没有违规结果或缓存未命中而拒绝下载。
            try:
                case_payload = get_patient_data(hospitalization_id, org_code or None)
            except Exception:
                unresolved_ids.append(hospitalization_id)
                continue
            if case_payload is None:
                unresolved_ids.append(hospitalization_id)
                continue
            case_payloads.append((hospitalization_id, case_payload))

        if unresolved_ids:
            return Response(
                {
                    'error': '部分任务病历获取失败，无法下载。',
                    'missingHospitalizationIds': unresolved_ids,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if case_count == 1:
            hospitalization_id, case_payload = case_payloads[0]
            response = HttpResponse(
                json.dumps(case_payload, ensure_ascii=False, indent=2),
                content_type='application/json; charset=utf-8',
            )
            filename = f'任务病历_任务{task.id}_{hospitalization_id}.json'
            response['Content-Disposition'] = (
                f"attachment; filename*=utf-8''{quote(filename)}"
            )
            return response

        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, mode='w', compression=ZIP_DEFLATED) as archive:
            for hospitalization_id, case_payload in case_payloads:
                archive.writestr(
                    _case_download_filename(hospitalization_id),
                    json.dumps(case_payload, ensure_ascii=False, indent=2),
                )
        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        filename = f'任务病历_任务{task.id}_{case_count}份.zip'
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(filename)}"
        return response

    @action(detail=True, methods=['get'], url_path='download-txt-report')
    def download_txt_report(self, request, pk=None):
        """下载指定任务的 TXT 格式文本报告。"""
        print("--- V4: 正在运行视图内嵌版的 download_txt_report! ---")
        task = self.get_object()

        # --- 把 ReportGenerator 的逻辑直接搬到这里 ---
        results = Result.objects.filter(task_id=task.id).select_related('rule')
        if not results.exists():
            report_content = "此任务未发现违规情况。"
        else:
            report_lines = ["医保审核报告", "=" * 50]
            for index, result in enumerate(results, 1):
                report_lines.append(f"\n--- 违规项 {index} ---")
                report_lines.append(f"项目: {result.violation_item}")
                report_lines.append(f"规则: {result.rule.description if result.rule else 'N/A'}")
                report_lines.append(f"违规原因: {result.reason}")
            report_lines.append("\n" + "=" * 50)
            report_lines.append(f"总结: 共发现 {results.count()} 项违规")
            report_lines.append("=" * 50)
            report_content = "\n".join(report_lines)
        
        response = HttpResponse(report_content, content_type='text/plain; charset=utf-8')
        filename = f"审核报告_任务{task.id}.txt"
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(filename)}"
        return response
    @action(detail=True, methods=['get'], url_path='download-report')
    def download_report(self, request, pk=None):
        """
        下载指定任务的 Word 报告。
        可以接收一个 'issue_number' 的查询参数。
        """
        task = self.get_object()
        issue_number = request.query_params.get('issue_number', 'X')
        
        response = generate_task_report_docx(task.id, issue_number)
        
        return response
