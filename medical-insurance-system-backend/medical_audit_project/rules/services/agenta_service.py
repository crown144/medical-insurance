from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from django.conf import settings
from openai import OpenAI

from .binding_resolver import (
    resolve_applicability_binding,
    resolve_constraint_bindings,
)
from .deterministic_compiler import compile_rule, validate_generated_code
from .semantic_decomposer import (
    SYSTEM_PROMPT,
    build_messages,
    expand_supported_compound_atoms,
    fallback_decomposition,
    ground_source_spans,
    has_supported_fallback,
    parse_decomposition,
    render_logic_expression,
)


TEMP_DISABLE_LLM_ENV = 'AGENTA_DISABLE_LLM_TEST'
APPROVED_AUDIT_FUNCTIONS = {
    'get_val', 'filter_list', 'calc_stats', 'list_contains',
    'is_compare', 'llm_bool', 'submit_result',
}
SAFE_BUILTINS = {
    'all', 'any', 'bool', 'dict', 'enumerate', 'float', 'int', 'len',
    'list', 'max', 'min', 'range', 'set', 'str', 'sum',
}


@dataclass
class AgentAGenerationResult:
    rule_text: str
    system_prompt: dict[str, Any]
    tool_schema: list[str]
    generated_code: str
    validation: dict[str, Any]
    rule_snapshot: dict[str, Any]
    irr: dict[str, str]
    atomic_constraints: list[dict[str, str]]
    logic_tree: dict[str, Any] | str
    logical_expression: str
    applicability_binding: dict[str, Any]
    constraint_bindings: list[dict[str, Any]]
    execution_bindings: list[dict[str, Any]]
    raw_output: str | None = None
    finish_reason: str | None = None


class AgentAService:
    """Compile an existing Rule through decomposition, binding, and templates."""

    @classmethod
    def _llm_config(cls) -> dict[str, Any]:
        return {
            'base_url': cls._normalize_base_url(
                getattr(settings, 'RULE_COMPILE_LLM_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
            ),
            'model': getattr(settings, 'RULE_COMPILE_LLM_MODEL', 'qwen3.5-flash'),
            'api_key': getattr(settings, 'RULE_COMPILE_LLM_API_KEY', '') or '',
            'max_tokens': int(getattr(settings, 'RULE_COMPILE_LLM_MAX_TOKENS', 6000)),
            'timeout': int(getattr(settings, 'RULE_COMPILE_LLM_TIMEOUT', 120)),
            'trust_env': bool(getattr(settings, 'RULE_COMPILE_LLM_TRUST_ENV', False)),
        }

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base_url = (base_url or '').strip().rstrip('/')
        parsed = urlparse(base_url)
        if parsed.scheme and parsed.netloc and parsed.path in {'', '/'}:
            return f'{base_url}/v1'
        return base_url

    @classmethod
    def is_temp_llm_disabled(cls) -> bool:
        return os.environ.get(TEMP_DISABLE_LLM_ENV, '').strip().lower() in {'1', 'true', 'yes', 'on'}

    @classmethod
    def _create_client(cls) -> tuple[OpenAI, str]:
        config = cls._llm_config()
        if not config['api_key']:
            raise ValueError('RULE_COMPILE_LLM_API_KEY is not configured.')
        http_client = httpx.Client(timeout=config['timeout'], trust_env=config['trust_env'])
        client = OpenAI(
            api_key=config['api_key'],
            base_url=config['base_url'],
            timeout=config['timeout'],
            http_client=http_client,
        )
        return client, config['model']

    @classmethod
    def build(
        cls,
        rule_text: str = '',
        irr: dict[str, str] | None = None,
    ) -> AgentAGenerationResult:
        fixed_irr = cls._normalize_irr(irr, rule_text)
        finish_reason = 'stop'

        if cls.is_temp_llm_disabled():
            decomposition = fallback_decomposition(fixed_irr)
            raw_output = 'Deterministic semantic fallback used because the LLM is disabled.'
            runtime_mode = 'deterministic_fallback'
            model_config = {'disabled': True, 'provider': 'deterministic_fallback'}
        else:
            client, model = cls._create_client()
            response = client.chat.completions.create(
                model=model,
                messages=build_messages(fixed_irr),
                temperature=0,
                max_tokens=cls._llm_config()['max_tokens'],
                extra_body={'enable_thinking': False},
            )
            choice = response.choices[0]
            raw_output = choice.message.content or ''
            finish_reason = choice.finish_reason or 'stop'
            try:
                decomposition = parse_decomposition(raw_output)
                runtime_mode = 'llm_semantic_decomposition'
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                if not has_supported_fallback(fixed_irr):
                    raise
                decomposition = fallback_decomposition(fixed_irr)
                runtime_mode = 'validated_semantic_fallback'
            model_config = {
                'base_url': cls._llm_config()['base_url'],
                'model': model,
                'provider': 'aliyun_bailian_qwen',
                'max_tokens': cls._llm_config()['max_tokens'],
            }

        decomposition = expand_supported_compound_atoms(decomposition)
        atoms = ground_source_spans(
            decomposition['atomic_constraints'],
            fixed_irr['constraint_condition'],
        )
        logic_tree = decomposition['logic_tree']
        applicability_binding = resolve_applicability_binding(fixed_irr)
        constraint_bindings = resolve_constraint_bindings(atoms)
        unbound = [
            item['atomic_constraint_id']
            for item in constraint_bindings
            if item['status'] == 'unbound'
        ]
        if applicability_binding['status'] != 'bound' or unbound:
            errors = []
            if applicability_binding['status'] != 'bound':
                errors.append('Constraint Object has no approved applicability binding.')
            if unbound:
                errors.append(f"Unbound atomic constraints: {', '.join(unbound)}")
            generated_code = ''
            validation = {
                'valid': False,
                'errors': errors,
            }
        else:
            generated_code = compile_rule(
                logic_tree,
                applicability_binding,
                constraint_bindings,
            )
            validation = validate_generated_code(generated_code)

        snapshot = {
            'matched_rule_id': None,
            'matched_description': fixed_irr['constraint_condition'],
            'generated_code_length': len(generated_code),
            'runtime_mode': runtime_mode,
            'runtime_label': 'Deterministic compilation',
            'llm_config': model_config,
        }
        tools = sorted({
            binding['audit_function']
            for binding in [applicability_binding, *constraint_bindings]
            if binding['status'] == 'bound'
        } | {'get_val', 'submit_result'})
        public_applicability = {
            key: value
            for key, value in applicability_binding.items()
            if key != 'runtime'
        }
        public_constraints = [
            {key: value for key, value in binding.items() if key != 'runtime'}
            for binding in constraint_bindings
        ]
        compatibility_bindings = [
            {
                **public_applicability,
                'atomic_constraint_id': 'Applicability',
                'role': 'applicability',
            },
            *(
                {**binding, 'role': 'condition'}
                for binding in public_constraints
            ),
        ]
        return AgentAGenerationResult(
            rule_text=fixed_irr['constraint_condition'],
            system_prompt={'style': 'semantic_decomposition', 'prompt': SYSTEM_PROMPT},
            tool_schema=tools,
            generated_code=generated_code,
            validation=validation,
            rule_snapshot=snapshot,
            irr=fixed_irr,
            atomic_constraints=atoms,
            logic_tree=logic_tree,
            logical_expression=render_logic_expression(logic_tree),
            applicability_binding=public_applicability,
            constraint_bindings=public_constraints,
            execution_bindings=compatibility_bindings,
            raw_output=raw_output,
            finish_reason=finish_reason,
        )

    @staticmethod
    def _normalize_irr(irr: dict[str, str] | None, rule_text: str) -> dict[str, str]:
        if irr:
            normalized = {
                'rule_category': str(irr.get('rule_category') or '').strip(),
                'constraint_object': str(irr.get('constraint_object') or '').strip(),
                'constraint_condition': str(irr.get('constraint_condition') or '').strip(),
            }
        else:
            normalized = {
                'rule_category': '',
                'constraint_object': '',
                'constraint_condition': (rule_text or '').strip(),
            }
        if not normalized['constraint_condition']:
            raise ValueError('Constraint Condition is required.')
        return normalized

    @staticmethod
    def validate_code(rule_code: str) -> dict[str, Any]:
        try:
            tree = ast.parse(rule_code)
        except SyntaxError as exc:
            return {'valid': False, 'errors': [str(exc)]}

        errors: list[str] = []
        execute = next(
            (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'execute_rule'),
            None,
        )
        if execute is None or len(execute.args.args) != 1 or execute.args.args[0].arg != 'ctx':
            errors.append('missing execute_rule(ctx) entrypoint')
        if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)):
            errors.append('imports are not allowed')

        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        unknown = sorted(calls - APPROVED_AUDIT_FUNCTIONS - SAFE_BUILTINS)
        if unknown:
            errors.append(f"unapproved function calls: {', '.join(unknown)}")
        has_submit_return = bool(execute) and any(
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == 'submit_result'
            for node in ast.walk(execute)
        )
        if execute and not has_submit_return:
            errors.append('missing return submit_result(...)')
        return {'valid': not errors, 'errors': errors}
