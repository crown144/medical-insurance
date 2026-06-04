# results/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Result
from .serializers import ResultSerializer
from django.db.models import Min
from django.http import HttpResponse
from urllib.parse import quote
import json
class ResultViewSet(viewsets.ReadOnlyModelViewSet): # 只读，不允许通过API修改或删除结果
    queryset = Result.objects.all().prefetch_related('highlights').order_by('-created_at')
    serializer_class = ResultSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'task_id': ['exact'],
        'hospitalization_id': ['exact', 'icontains'],   # 支持住院号精确和模糊查询
        'rule__drug_name': ['icontains'],      # 支持药品名模糊查询
        'discharge_date': ['year', 'month'],   # 支持按出院年、月精确查询
    }
    def get_queryset(self):
        queryset = super().get_queryset() # 这会获取到上面带有 prefetch_related 的 queryset
        
        # 检查是否是多检测模式（通过task_id参数判断）
        task_id = self.request.query_params.get('task_id')
        
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        # 统一去重策略：基于 (住院号, 规则ID, 违规原因, 违规项目) 的精细化去重
        # 1. 必须先清除默认排序
        queryset_no_order = queryset.order_by()
        
        # 2. 分组并获取每组最小 ID
        # 将 violation_item 加入分组，确保不同的违规项目（即使规则相同）都被保留，
        # 同时相同的违规项目（完全重复的数据）被去除。
        values = queryset_no_order.values(
            'task_id', 
            'hospitalization_id', 
            'rule_id', 
            'reason', 
            'violation_item'  # <--- 关键修改：加入此字段
        ).annotate(min_id=Min('id'))
        
        # 3. 提取出所有这些最小的 ID
        pks_to_keep = [item['min_id'] for item in values]

        # 4. 重新构建最终的 QuerySet
        final_queryset = queryset.filter(pk__in=pks_to_keep)
        return final_queryset
    
    @action(detail=False, methods=['get'], url_path='download-json-report')
    def download_json_report(self, request):
        """下载指定任务和住院号的 JSON 格式违规报告。"""
        task_id = request.query_params.get('task_id')
        hospitalization_id = request.query_params.get('hospitalization_id')
        
        if not hospitalization_id:
            return Response({'error': '缺少hospitalization_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 构建查询条件 - 必须同时指定task_id和hospitalization_id以确保数据准确性
        if not task_id:
            return Response({'error': '缺少task_id参数'}, status=status.HTTP_400_BAD_REQUEST)
            
        filter_conditions = {
            'hospitalization_id': hospitalization_id,
            'task_id': task_id
        }
        
        # 获取指定条件的违规结果
        results = Result.objects.filter(**filter_conditions).select_related('rule')
        
        violations_data = []
        for result in results:
            violations_data.append({
                "住院号": result.hospitalization_id,
                "违规项目": result.violation_item,
                "违规原因": result.reason,
                "有关依据": result.rule.description if result.rule else "N/A"
            })
        
        json_string = json.dumps(violations_data, ensure_ascii=False, indent=2)
        response = HttpResponse(json_string, content_type='application/json; charset=utf-8')
        filename = f"违规报告_任务{task_id}_{hospitalization_id}.json"
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(filename)}"
        return response
    
    @action(detail=False, methods=['get'], url_path='download-txt-report')
    def download_txt_report(self, request):
        """下载指定任务和住院号的 TXT 格式文本报告。"""
        task_id = request.query_params.get('task_id')
        hospitalization_id = request.query_params.get('hospitalization_id')
        
        if not hospitalization_id:
            return Response({'error': '缺少hospitalization_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 构建查询条件 - 必须同时指定task_id和hospitalization_id以确保数据准确性
        if not task_id:
            return Response({'error': '缺少task_id参数'}, status=status.HTTP_400_BAD_REQUEST)
            
        filter_conditions = {
            'hospitalization_id': hospitalization_id,
            'task_id': task_id
        }
        
        # 获取指定条件的违规结果
        results = Result.objects.filter(**filter_conditions).select_related('rule')
        
        if not results.exists():
            report_content = f"住院号 {hospitalization_id} 在任务 {task_id or 'all'} 中未发现违规情况。"
        else:
            report_lines = [f"医保审核报告 - 任务{task_id or 'all'} - 住院号{hospitalization_id}", "=" * 60]
            for index, result in enumerate(results, 1):
                report_lines.append(f"\n--- 违规项 {index} ---")
                report_lines.append(f"项目: {result.violation_item}")
                report_lines.append(f"规则: {result.rule.description if result.rule else 'N/A'}")
                report_lines.append(f"违规原因: {result.reason}")
            report_lines.append("\n" + "=" * 60)
            report_lines.append(f"总结: 住院号 {hospitalization_id} 共发现 {results.count()} 项违规")
            report_lines.append("=" * 60)
            report_content = "\n".join(report_lines)
        
        response = HttpResponse(report_content, content_type='text/plain; charset=utf-8')
        filename = f"审核报告_任务{task_id}_{hospitalization_id}.txt"
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(filename)}"
        return response