from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend # 导入
from .models import Task
from .serializers import TaskSerializer
from .tasks import run_audit_task
from results.report_generator import ReportGenerator
import json
from django.http import HttpResponse
from datetime import datetime
from urllib.parse import quote
from results.models import Result # 直接导入 Result 模型
from results.word_generator import generate_task_report_docx # 导入我们的新函数
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