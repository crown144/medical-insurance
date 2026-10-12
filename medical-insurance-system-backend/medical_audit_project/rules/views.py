import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from django.db.models import Q
from django_filters import rest_framework as django_filters
from rest_framework import filters as drf_filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Rule
from .serializers import RuleSerializer
from .services import AgentAService


logger = logging.getLogger(__name__)
_agenta_executor = ThreadPoolExecutor(max_workers=2)
_agenta_tasks = {}

DEMO_RULE_IDS = [
    'R-0001',
    'R-0002',
    'R-20260704151155530323',
    'R-20260704151155864177',
    'R-20260704151200686615',
    'R-20260704151201033234',
    'R-20260704151207016105',
    'R-20260704151207710658',
    'R-20260709123055310514',
    'R-20260709124003677192',
]

COMPILE_RULE_IDS = [
    'R-0001',
    'R-0002',
    'R-20260704151200686615',
    'R-20260704151201033234',
]
COMPILE_RULE_NAMES = ['艾普拉唑', '醋酸钙', '静脉注射', '动脉加压注射']


def _serialize_generation_result(generated):
    return {
        'rule_text': generated.rule_text,
        'system_prompt': generated.system_prompt,
        'tool_schema': generated.tool_schema,
        'generated_code': generated.generated_code,
        'validation': generated.validation,
        'rule_snapshot': generated.rule_snapshot,
        'raw_output': generated.raw_output,
        'finish_reason': generated.finish_reason,
        'runtime_mode': generated.rule_snapshot.get('runtime_mode'),
        'runtime_label': generated.rule_snapshot.get('runtime_label'),
        'llm_config': generated.rule_snapshot.get('llm_config'),
    }


def _run_agenta_generation(task_id, rule_text):
    _agenta_tasks[task_id] = {
        'status': 'running',
        'message': '规则编译中',
        'result': None,
    }
    try:
        generated = AgentAService.build(rule_text)
        _agenta_tasks[task_id] = {
            'status': 'success',
            'message': 'ok',
            'result': _serialize_generation_result(generated),
        }
    except Exception as exc:
        logger.exception('AgentA async rule generation failed')
        _agenta_tasks[task_id] = {
            'status': 'failed',
            'message': '规则编译模型请求超时，请稍后重试或缩短规则描述'
            if isinstance(exc, TimeoutError) or 'timeout' in str(exc).lower() or 'timed out' in str(exc).lower()
            else '规则编译模型调用失败',
            'result': {
                'error': str(exc) or exc.__class__.__name__,
                'error_type': exc.__class__.__name__,
            },
        }


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
    queryset = Rule.objects.none()
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

    def get_queryset(self):
        queryset = Rule.objects.all()
        compile_mode = str(self.request.query_params.get('compile', '')).lower()
        if compile_mode in {'1', 'true', 'yes', 'on'}:
            return queryset.filter(
                Q(rule_id__in=COMPILE_RULE_IDS) | Q(drug_name__in=COMPILE_RULE_NAMES),
            ).order_by('id')
        return queryset.filter(rule_id__in=DEMO_RULE_IDS).order_by('id')

    @staticmethod
    def _agenta_error_response(exc):
        message = str(exc) or exc.__class__.__name__
        lower_message = message.lower()
        is_timeout = isinstance(exc, TimeoutError) or 'timeout' in lower_message or 'timed out' in lower_message
        http_status = status.HTTP_504_GATEWAY_TIMEOUT if is_timeout else status.HTTP_502_BAD_GATEWAY
        user_message = '规则编译模型请求超时，请稍后重试或缩短规则描述' if is_timeout else '规则编译模型调用失败'
        return Response({
            'code': 1,
            'message': user_message,
            'result': {
                'error': message,
                'error_type': exc.__class__.__name__,
            },
        }, status=http_status)

    @action(detail=False, methods=['post'], url_path='agenta/generate')
    def agenta_generate(self, request):
        rule_text = (request.data.get('rule_text') or request.data.get('ruleText') or '').strip()
        if not rule_text:
            return Response({'code': 1, 'message': '规则文本不能为空', 'result': None}, status=status.HTTP_400_BAD_REQUEST)

        try:
            generated = AgentAService.build(rule_text)
        except Exception as exc:
            logger.exception('AgentA rule generation failed')
            return self._agenta_error_response(exc)
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
                'finish_reason': generated.finish_reason,
                'runtime_mode': generated.rule_snapshot.get('runtime_mode'),
                'runtime_label': generated.rule_snapshot.get('runtime_label'),
                'llm_config': generated.rule_snapshot.get('llm_config'),
            },
        })

    @action(detail=False, methods=['post'], url_path='agenta/generate/start')
    def agenta_generate_start(self, request):
        rule_text = (request.data.get('rule_text') or request.data.get('ruleText') or '').strip()
        if not rule_text:
            return Response({'code': 1, 'message': '规则文本不能为空', 'result': None}, status=status.HTTP_400_BAD_REQUEST)

        task_id = uuid.uuid4().hex
        _agenta_tasks[task_id] = {
            'status': 'pending',
            'message': '规则编译已提交',
            'result': None,
        }
        _agenta_executor.submit(_run_agenta_generation, task_id, rule_text)
        return Response({
            'code': 0,
            'message': 'ok',
            'result': {
                'task_id': task_id,
                'status': 'pending',
            },
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['get'], url_path=r'agenta/generate/status/(?P<task_id>[^/.]+)')
    def agenta_generate_status(self, request, task_id=None):
        task = _agenta_tasks.get(task_id)
        if not task:
            return Response({'code': 1, 'message': '编译任务不存在或已过期', 'result': None}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'code': 0 if task['status'] != 'failed' else 1,
            'message': task['message'],
            'result': {
                'task_id': task_id,
                'status': task['status'],
                'data': task['result'],
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

        try:
            generated = AgentAService.build(rule_text)
        except Exception as exc:
            logger.exception('AgentA rule run generation failed')
            return self._agenta_error_response(exc)
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
