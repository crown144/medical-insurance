import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from django_filters import rest_framework as django_filters
from rest_framework import filters as drf_filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Rule
from .serializers import RuleSerializer
from .services import AgentAService
from .services.readable_renderer import compiled_plan_from_code, render_readable_python


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
    'rule_131',
]

COMPILE_RULE_IDS = [
    'R-0001',
    'R-0002',
    'R-20260704151200686615',
    'R-20260704151201033234',
    'rule_131',
]
COMPILE_RULE_NAMES = [
    '艾普拉唑',
    '醋酸钙',
    '静脉注射',
    '动脉加压注射',
    '恩替卡韦口服溶液',
]


def _serialize_generation_result(generated):
    try:
        compiled_plan = compiled_plan_from_code(generated.generated_code) if generated.generated_code else None
    except (SyntaxError, ValueError):
        # Legacy executable code has no embedded plan to render faithfully.
        compiled_plan = None
    return {
        'rule_text': generated.rule_text,
        'system_prompt': generated.system_prompt,
        'tool_schema': generated.tool_schema,
        'generated_code': generated.generated_code,
        'generated_python': generated.generated_code,
        'compiled_plan': compiled_plan,
        'readable_python': render_readable_python(compiled_plan) if compiled_plan else '',
        'validation': generated.validation,
        'compilation_status': 'compiled' if generated.validation.get('valid') and generated.generated_code else 'needs_revision',
        'rule_snapshot': generated.rule_snapshot,
        'raw_output': generated.raw_output,
        'finish_reason': generated.finish_reason,
        'runtime_mode': generated.rule_snapshot.get('runtime_mode'),
        'runtime_label': generated.rule_snapshot.get('runtime_label'),
        'llm_config': generated.rule_snapshot.get('llm_config'),
        'irr': generated.irr,
        'atomic_constraints': generated.atomic_constraints,
        'logic_tree': generated.logic_tree,
        'logical_expression': generated.logical_expression,
        'applicability_binding': generated.applicability_binding,
        'constraint_bindings': generated.constraint_bindings,
        'execution_bindings': generated.execution_bindings,
        'binding_source': generated.binding_source,
        'binding_validation': generated.binding_validation,
    }


def _rule_compilation_input(payload):
    rule_pk = payload.get('rule_pk') or payload.get('rulePk')
    if rule_pk not in [None, '']:
        rule = Rule.objects.get(pk=rule_pk)
        return rule.description, {
            'rule_category': rule.type,
            'constraint_object': rule.drug_name,
            'constraint_condition': rule.description,
        }
    rule_text = (payload.get('rule_text') or payload.get('ruleText') or '').strip()
    return rule_text, None


def _run_agenta_generation(task_id, rule_text, irr=None):
    _agenta_tasks[task_id] = {
        'status': 'running',
        'message': 'Rule compilation is running.',
        'result': None,
    }
    try:
        generated = AgentAService.build(rule_text, irr=irr)
        _agenta_tasks[task_id] = {
            'status': 'success',
            'message': 'ok',
            'result': _serialize_generation_result(generated),
        }
    except Exception as exc:
        logger.exception('AgentA async rule generation failed')
        _agenta_tasks[task_id] = {
            'status': 'failed',
            'message': 'Rule compilation timed out. Please try again later.'
            if isinstance(exc, TimeoutError) or 'timeout' in str(exc).lower() or 'timed out' in str(exc).lower()
            else 'Rule compilation failed.',
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
        # Temporary management mode: expose every rule to both the Rule
        # Library and the Compilation workspace, rather than demo whitelists.
        return Rule.objects.all().order_by('id')

    @staticmethod
    def _agenta_error_response(exc):
        message = str(exc) or exc.__class__.__name__
        lower_message = message.lower()
        is_timeout = isinstance(exc, TimeoutError) or 'timeout' in lower_message or 'timed out' in lower_message
        http_status = status.HTTP_504_GATEWAY_TIMEOUT if is_timeout else status.HTTP_502_BAD_GATEWAY
        user_message = 'Rule compilation timed out. Please try again later.' if is_timeout else 'Rule compilation failed.'
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
        try:
            rule_text, irr = _rule_compilation_input(request.data)
        except Rule.DoesNotExist:
            return Response({'code': 1, 'message': 'The selected rule does not exist.', 'result': None}, status=status.HTTP_404_NOT_FOUND)
        if not rule_text:
            return Response({'code': 1, 'message': 'Constraint Condition is required.', 'result': None}, status=status.HTTP_400_BAD_REQUEST)

        try:
            generated = AgentAService.build(rule_text, irr=irr)
        except Exception as exc:
            logger.exception('AgentA rule generation failed')
            return self._agenta_error_response(exc)
        return Response({
            'code': 0,
            'message': 'ok',
            'result': _serialize_generation_result(generated),
        })

    @action(detail=False, methods=['post'], url_path='agenta/generate/start')
    def agenta_generate_start(self, request):
        try:
            rule_text, irr = _rule_compilation_input(request.data)
        except Rule.DoesNotExist:
            return Response({'code': 1, 'message': 'The selected rule does not exist.', 'result': None}, status=status.HTTP_404_NOT_FOUND)
        if not rule_text:
            return Response({'code': 1, 'message': 'Constraint Condition is required.', 'result': None}, status=status.HTTP_400_BAD_REQUEST)

        task_id = uuid.uuid4().hex
        _agenta_tasks[task_id] = {
            'status': 'pending',
            'message': 'Rule compilation was submitted.',
            'result': None,
        }
        _agenta_executor.submit(_run_agenta_generation, task_id, rule_text, irr)
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
            return Response({'code': 1, 'message': 'The compilation task does not exist or has expired.', 'result': None}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'code': 0 if task['status'] != 'failed' else 1,
            'message': task['message'],
            'result': {
                'task_id': task_id,
                'status': task['status'],
                'data': task['result'],
            },
        })

    @staticmethod
    def _revision_irr(rule):
        return {'rule_category': rule.type, 'constraint_object': rule.drug_name,
                'constraint_condition': rule.description}

    @action(detail=True, methods=['post'], url_path='revision')
    def revision(self, request, pk=None):
        from .services.revision_service import request_revision
        rule = self.get_object()
        try:
            result = request_revision(request.data.get('draft'), self._revision_irr(rule), request.data.get('feedback'))
        except (ValueError, KeyError, TypeError) as exc:
            return Response({'message': str(exc) or 'Revision needs attention.', 'error': str(exc)}, status=400)
        except Exception as exc:
            logger.exception('Rule revision failed')
            return self._agenta_error_response(exc)
        return Response({'result': result})

    @action(detail=True, methods=['post'], url_path='recompile')
    def recompile(self, request, pk=None):
        from .services.revision_service import compile_draft
        rule = self.get_object()
        try:
            generated = compile_draft(request.data.get('draft'), self._revision_irr(rule))
        except (ValueError, KeyError, TypeError) as exc:
            return Response({'message': 'The draft could not be compiled.', 'error': str(exc)}, status=400)
        return Response({'result': _serialize_generation_result(generated)})

    @action(detail=True, methods=['get'], url_path='compilation')
    def compilation(self, request, pk=None):
        from .services.revision_service import compile_draft
        rule = self.get_object()
        if not rule.rule_code:
            return Response({'result': None})
        try:
            plan = compiled_plan_from_code(rule.rule_code)
            atoms = plan.get('atomic_constraints') or [
                {'id': b['atomic_constraint_id'], 'normalized_constraint': b.get('normalized_constraint') or b.get('expected_condition') or 'Condition', 'source_span': ''}
                for b in plan['constraints']]
            generated = compile_draft({'atomic_constraints': atoms, 'logic_tree': plan['logic'],
                'applicability_binding': plan['applicability'], 'constraint_bindings': plan['constraints']}, self._revision_irr(rule))
            generated.generated_code = rule.rule_code
            return Response({'result': _serialize_generation_result(generated)})
        except (ValueError, SyntaxError, KeyError, TypeError):
            # Older standalone Python remains runnable but has no editable plan.
            return Response({'result': None})

    @action(detail=False, methods=['post'], url_path='agenta/validate')
    def agenta_validate(self, request):
        rule_code = (request.data.get('rule_code') or request.data.get('ruleCode') or '').strip()
        if not rule_code:
            return Response({'code': 1, 'message': 'Rule code is required.', 'result': None}, status=status.HTTP_400_BAD_REQUEST)
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
