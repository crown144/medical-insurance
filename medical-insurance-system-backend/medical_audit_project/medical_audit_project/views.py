import os

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from rules.services.agenta_service import AgentAService


TEMP_DISABLE_LLM_ENV = 'AGENTA_DISABLE_LLM_TEST'


def _temp_llm_disabled() -> bool:
    return os.environ.get(TEMP_DISABLE_LLM_ENV, '').strip().lower() in {'1', 'true', 'yes', 'on'}


@api_view(['GET'])
@permission_classes([AllowAny])
def user_info(request):
    return Response({
        'code': 0,
        'result': {
            'userId': '1',
            'username': 'admin',
            'realName': '系统管理员',
            'avatar': 'https://q1.qlogo.cn/g?b=qq&nk=190848757&s=640',
            'desc': 'Super Admin',
            'roles': ['super'],
            'token': 'fake-token-123',
        },
        'message': 'ok',
        'type': 'success',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def auth_login(request):
    return Response({
        'code': 0,
        'result': {
            'accessToken': 'fake-jwt-token-example',
            'token': 'fake-jwt-token-example',
            'userId': 1,
            'username': 'admin',
            'roles': ['super'],
        },
        'message': '登录成功',
        'type': 'success',
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def menu_all(request):
    return Response({'code': 0, 'result': [], 'message': 'ok', 'type': 'success'})


@api_view(['GET'])
@permission_classes([AllowAny])
def auth_codes(request):
    return Response({'code': 0, 'result': [], 'message': 'ok', 'type': 'success'})


@api_view(['POST'])
@permission_classes([AllowAny])
def audit_detect(request):
    payload = request.data or {}
    patient_data = payload.get('patient_data') or {}
    template_id = payload.get('template_id') or 'unknown'

    if _temp_llm_disabled():
        return Response({
            'code': 0,
            'message': 'ok',
            'result': {
                'mode': 'hardcoded',
                'template_id': template_id,
                'violations': [
                    {
                        'id': 'v1',
                        'name': '临时关闭大模型检测',
                        'isViolation': '否',
                        'violationType': 'PASS',
                        'violationDetail': '当前已临时关闭大模型测试，返回固定结果。',
                        'analysis': '后端已进入硬编码模式。',
                        'rule': template_id,
                        'ruleDetail': '临时禁用大模型',
                        'queryKeyword': template_id,
                        'evidenceText': '',
                        'highlights': [],
                        'rule': {
                            'description': '临时关闭大模型测试',
                            'drugName': template_id,
                            'type': '临时禁用',
                        },
                    }
                ],
            },
            'type': 'success'
        })

    diagnosis_names = []
    for item in patient_data.get('诊断信息', []):
        if isinstance(item, dict):
            diagnosis_names.append(item.get('诊断名称', ''))

    admission = patient_data.get('入院记录', {}) if isinstance(patient_data.get('入院记录', {}), dict) else {}
    course = patient_data.get('首次病程记录', {}) if isinstance(patient_data.get('首次病程记录', {}), dict) else {}
    text_blob = f"{admission.get('现病史', '')} {admission.get('初步诊断', '')} {course.get('文档内容', '')}"

    violations = []
    if template_id == 'medication_template':
        has_stroke = any('脑梗' in name or '脑卒中' in name for name in diagnosis_names)
        if has_stroke and ('新发' in text_blob or '急性' in text_blob):
            violations.append({
                'id': 'v1',
                'name': '缺血性脑梗死审查',
                'isViolation': '是',
                'violationType': 'INTERCEPTED',
                'violationDetail': '发现高风险病历，按规则拦截。',
                'analysis': '诊断信息命中脑梗死，且病程文本包含新发/急性证据，符合演示拦截结果。',
                'rule': '限新发的缺血性脑梗死，支付不超过14天',
                'ruleDetail': '新发/急性期脑梗死审查',
                'queryKeyword': '脑梗死',
                'evidenceText': text_blob[:500],
                'highlights': [
                    {'field_path': '入院记录.现病史', 'highlighted_text': '急性'},
                    {'field_path': '首次病程记录.文档内容', 'highlighted_text': '新发'},
                ],
                'rule': {
                    'description': '限新发的缺血性脑梗死，支付不超过14天',
                    'drugName': '缺血性脑梗死',
                    'type': '医保审核',
                },
            })
        else:
            violations.append({
                'id': 'v1',
                'name': '缺血性脑梗死审查',
                'isViolation': '否',
                'violationType': 'PASS',
                'violationDetail': '规则校验通过。',
                'analysis': '未发现拦截条件。',
                'rule': '限新发的缺血性脑梗死，支付不超过14天',
                'ruleDetail': '新发/急性期脑梗死审查',
                'queryKeyword': '脑梗死',
                'evidenceText': text_blob[:500],
                'highlights': [],
                'rule': {
                    'description': '限新发的缺血性脑梗死，支付不超过14天',
                    'drugName': '缺血性脑梗死',
                    'type': '医保审核',
                },
            })
    else:
        violations.append({
            'id': 'v1',
            'name': '默认审查',
            'isViolation': '否',
            'violationType': 'PASS',
            'violationDetail': '未配置模板，默认通过。',
            'analysis': '未命中已知模板。',
            'rule': template_id,
            'ruleDetail': '默认规则',
            'queryKeyword': template_id,
            'evidenceText': text_blob[:500],
            'highlights': [],
            'rule': {
                'description': template_id,
                'drugName': template_id,
                'type': '默认',
            },
        })

    return Response({'code': 0, 'message': 'ok', 'result': {'violations': violations}, 'type': 'success'})
