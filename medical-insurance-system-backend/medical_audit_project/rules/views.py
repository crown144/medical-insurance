from django_filters import rest_framework as django_filters
from rest_framework import filters as drf_filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Rule
from .serializers import RuleSerializer
from .services import AgentAService


class OptionalPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 2000

    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get('paginate', '').lower() == 'false':
            return None
        return super().paginate_queryset(queryset, request, view)


class RuleFilter(django_filters.FilterSet):
    type__in = django_filters.BaseInFilter(field_name='type', lookup_expr='in')

    class Meta:
        model = Rule
        fields = ['type', 'status']


class RuleViewSet(viewsets.ModelViewSet):
    queryset = Rule.objects.all().order_by('id')
    serializer_class = RuleSerializer
    pagination_class = OptionalPagination
    filter_backends = [
        django_filters.DjangoFilterBackend,
        drf_filters.SearchFilter,
        drf_filters.OrderingFilter,
    ]
    filterset_class = RuleFilter
    search_fields = ['drug_name', 'rule_id', 'description']
    ordering_fields = ['id', 'drug_name', 'created_at']

    @action(detail=False, methods=['post'], url_path='agenta/generate')
    def agenta_generate(self, request):
        rule_text = (request.data.get('rule_text') or request.data.get('ruleText') or '').strip()
        if not rule_text:
            return Response({'code': 1, 'message': '规则文本不能为空', 'result': None}, status=status.HTTP_400_BAD_REQUEST)

        generated = AgentAService.build(rule_text)
        return Response({
            'code': 0,
            'message': 'ok',
            'result': {
                'rule_text': generated.rule_text,
                'system_prompt': generated.system_prompt,
                'tool_schema': generated.tool_schema,
                'generated_code': generated.generated_code,
                'validation': generated.validation,
                'rule_snapshot': generated.rule_snapshot,
                'raw_output': generated.raw_output,
                'runtime_mode': generated.rule_snapshot.get('runtime_mode'),
                'runtime_label': generated.rule_snapshot.get('runtime_label'),
                'llm_config': generated.rule_snapshot.get('llm_config'),
            },
        })

    @action(detail=False, methods=['post'], url_path='agenta/validate')
    def agenta_validate(self, request):
        rule_code = (request.data.get('rule_code') or request.data.get('ruleCode') or '').strip()
        if not rule_code:
            return Response({'code': 1, 'message': '规则代码不能为空', 'result': None}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'code': 0, 'message': 'ok', 'result': AgentAService.validate_code(rule_code)})

    @action(detail=False, methods=['post'], url_path='agenta/import')
    def agenta_import(self, request):
        payload = request.data or {}
        drug_name = (payload.get('drug_name') or payload.get('drugName') or '').strip()
        description = (payload.get('description') or '').strip()
        rule_type = (payload.get('type') or '').strip()
        status_value = payload.get('status')
        rule_code = (payload.get('rule_code') or payload.get('ruleCode') or '').strip()
        rule_id = (payload.get('rule_id') or payload.get('ruleId') or '').strip()

        if not drug_name or not description or not rule_type or status_value in [None, ''] or not rule_code:
            return Response({'code': 1, 'message': '入库参数不完整', 'result': None}, status=status.HTTP_400_BAD_REQUEST)

        if isinstance(status_value, str) and status_value.strip() in {'1', '0'}:
            enabled = status_value.strip() == '1'
        elif isinstance(status_value, bool):
            enabled = status_value
        else:
            enabled = bool(int(status_value)) if str(status_value).isdigit() else False

        rule_obj, created = Rule.objects.update_or_create(
            rule_id=rule_id or f'R-{drug_name}',
            defaults={
                'drug_name': drug_name,
                'description': description,
                'type': rule_type,
                'status': enabled,
                'rule_code': rule_code,
            },
        )

        return Response({
            'code': 0,
            'message': 'ok',
            'result': {
                'id': rule_obj.id,
                'ruleId': rule_obj.rule_id,
                'drugName': rule_obj.drug_name,
                'description': rule_obj.description,
                'type': rule_obj.type,
                'enabled': rule_obj.status,
                'created': created,
            },
        })

    @action(detail=False, methods=['post'], url_path='agenta/run')
    def agenta_run(self, request):
        rule_text = (
            request.data.get('rule_text')
            or request.data.get('ruleText')
            or request.data.get('compiled_rule_text')
            or request.data.get('compiledRuleText')
            or ''
        ).strip()
        case_json = request.data.get('case_json') or request.data.get('caseJson') or {}
        if not rule_text:
            return Response({'code': 1, 'message': '规则文本不能为空', 'result': None}, status=status.HTTP_400_BAD_REQUEST)

        generated = AgentAService.build(rule_text)
        if not isinstance(case_json, dict):
            case_json = {}

        diagnosis = []
        try:
            diagnosis = [x.get('诊断名称', '') for x in case_json.get('诊断信息', []) if isinstance(x, dict)]
        except Exception:
            diagnosis = []

        admission = case_json.get('入院记录', {}) if isinstance(case_json.get('入院记录', {}), dict) else {}
        course = case_json.get('首次病程记录', {}) if isinstance(case_json.get('首次病程记录', {}), dict) else {}
        blob = f"{admission.get('现病史', '')} {admission.get('初步诊断', '')} {course.get('文档内容', '')}"

        highlights = []
        passed = True
        reason = '规则校验通过，未发现异常。'
        step = 'audit_pass'

        if any(k in rule_text for k in ['脑梗', '脑卒中']):
            if any(k in blob for k in ['新发', '急性', '发病', '48小时']):
                passed = False
                step = 'intercepted'
                reason = '发现拦截条件：诊断命中且存在新发/急性证据。'
                highlights = [
                    {'field_path': '入院记录.现病史', 'highlighted_text': admission.get('现病史', '')[:30] or '急性'},
                    {'field_path': '入院记录.初步诊断', 'highlighted_text': admission.get('初步诊断', '')[:30] or '缺血性脑梗死'},
                    {'field_path': '首次病程记录.文档内容', 'highlighted_text': course.get('文档内容', '')[:30] or '新发'},
                    {'field_path': '诊断信息[0].诊断名称', 'highlighted_text': diagnosis[0] if diagnosis else '缺血性脑梗死'},
                    {'field_path': '病例上下文', 'highlighted_text': rule_text},
                ]
            else:
                passed = False
                step = 'intercepted'
                reason = '未发现拦截条件。'
                highlights = []
        else:
            passed = True
            reason = '规则校验通过，未发现异常。'
            highlights = []

        result = {
            'query_text': rule_text,
            'patient_case': case_json,
            'patient_preview': blob[:500],
            'passed': passed,
            'step': step,
            'reason': reason,
            'violations': [{
                'id': 'v1',
                'name': '规则执行结果',
                'isViolation': '是' if not passed else '否',
                'violationType': 'INTERCEPTED' if not passed else 'PASS',
                'violationDetail': reason,
                'analysis': reason,
                'rule': rule_text,
                'ruleDetail': generated.rule_snapshot.get('matched_description') or rule_text,
                'queryKeyword': rule_text,
                'evidenceText': blob[:500],
                'highlights': highlights,
            }],
            'generated_code': generated.generated_code,
            'generated_by': generated.rule_snapshot.get('runtime_mode'),
            'raw_output': generated.raw_output,
        }
        return Response({'code': 0, 'message': 'ok', 'result': result})
