"""Evidence-aware execution of a compiled binding plan.

This module does not parse policy text or infer field names. It evaluates only
the physical paths and operations supplied by the compiler.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _values(ctx: Any, path: str):
    """Yield physical paths and values without discarding list indices."""
    def walk(value, keys, current):
        if not keys:
            if isinstance(value, list):
                for index, item in enumerate(value):
                    yield from walk(item, [], f'{current}[{index}]')
            elif value is not None and str(value).strip():
                yield current, value
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                yield from walk(item, keys, f'{current}[{index}]')
        elif isinstance(value, dict) and keys[0] in value:
            next_path = f'{current}.{keys[0]}' if current else keys[0]
            yield from walk(value[keys[0]], keys[1:], next_path)
    return list(walk(ctx, path.split('.'), ''))


def _sources(binding):
    runtime = binding.get('runtime') or {}
    sources = binding.get('evidence_sources') or runtime.get('evidence_sources')
    if sources is not None:
        return sources
    paths = runtime.get('context_paths')
    if paths is None:
        roots = runtime.get('source_paths') or [runtime.get('source_path')]
        field = runtime.get('field_path')
        paths = [f'{root}.{field}' for root in roots if root and field]
    return [{'path': path} for path in paths]


def llm_evidence(sources, question):
    """Ask for a three-state answer and verify every quote against its source."""
    paths = [source['path'] for source in sources]
    if not sources:
        return {'value': False, 'insufficient_evidence': True, 'evidence': [],
                'reason': 'No clinical text was available.', 'searched_paths': paths}
    prompt = (
        'Assess the question using only the provided clinical passages. '
        'Do not infer lack of prior treatment from absent records. '
        'Return JSON with status satisfied, unsatisfied, or unknown; quote, '
        'source_path, and reason. A satisfied or unsatisfied answer requires a '
        'verbatim quote and its exact source_path. If unclear use unknown.\n'
        + json.dumps({'question': question, 'sources': sources}, ensure_ascii=False)
    )
    try:
        response = requests.post('http://localhost:9033/v1/chat/completions', json={
            'model': 'Qwen3-8b', 'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0, 'max_tokens': 512,
        }, timeout=10)
        response.raise_for_status()
        raw = response.json()['choices'][0]['message']['content'].strip()
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I)
        answer = json.loads(raw)
        state, quote, path = answer.get('status'), answer.get('quote'), answer.get('source_path')
        verified = bool(quote and path and any(
            source['path'] == path and str(quote) in source['text'] for source in sources
        ))
        if state not in ('satisfied', 'unsatisfied') or not verified:
            raise ValueError('The answer has no verifiable supporting quotation.')
        return {'value': state == 'satisfied', 'insufficient_evidence': False,
                'evidence': [{'source_path': path, 'text': quote, 'match_type': 'quotation'}],
                'reason': str(answer.get('reason') or ''), 'searched_paths': paths}
    except (ValueError, KeyError, TypeError, requests.RequestException) as exc:
        logger.warning('Structured clinical assessment unavailable: %s', exc)
        return {'value': False, 'insufficient_evidence': True, 'evidence': [],
                'reason': 'Clinical evidence could not be verified.', 'searched_paths': paths}


def _compare(value, op, threshold):
    try:
        a, b = float(value), float(threshold)
        return {'>': a > b, '>=': a >= b, '<': a < b, '<=': a <= b, '==': a == b}[op]
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def evaluate_binding(ctx, binding, llm=None):
    runtime = binding.get('runtime') or {}
    mode = runtime.get('mode', 'list_filter')
    entries = [(path, value) for source in _sources(binding)
               for path, value in _values(ctx, source['path'])]
    evidence = []
    insufficient = False
    reason = ''
    if mode == 'llm_bool':
        passages = [{'path': path, 'text': str(value)} for path, value in entries]
        answer = (llm or llm_evidence)(passages, runtime['question'])
        value = bool(answer.get('value'))
        insufficient = bool(answer.get('insufficient_evidence', True))
        evidence = answer.get('evidence', [])
        reason = answer.get('reason', '')
    elif mode == 'numeric_comparison':
        comparisons = runtime.get('comparisons') or []
        outcomes = [(path, raw, [_compare(raw, op, threshold) for op, threshold in comparisons])
                    for path, raw in entries]
        valid = [item for item in outcomes if item[2] and None not in item[2]]
        insufficient = not valid
        value = any(all(item[2]) for item in valid)
        evidence = [{'source_path': path, 'text': str(raw), 'match_type': 'comparison',
                     'comparisons': comparisons} for path, raw, _ in valid]
        reason = 'Compared the recorded value.' if valid else 'No comparable value was available.'
    elif mode in ('list_filter', 'list_membership'):
        terms = runtime.get('match_values') or runtime.get('expected_values') or []
        for path, raw in entries:
            if any(str(term).casefold() in str(raw).casefold() for term in terms):
                evidence.append({'source_path': path, 'text': str(raw), 'match_type': 'keyword'})
        value = bool(evidence)
        insufficient = not entries
        reason = 'Matching record found.' if value else ('No matching record was found.' if entries else 'No records were available.')
    else:
        return {'value': False, 'insufficient_evidence': True, 'status': 'insufficient_evidence',
                'evidence': [], 'reason': f'Unsupported execution mode: {mode}'}
    checked_records = ([{'source_path': path, 'text': str(raw)} for path, raw in entries]
                       if mode in ('list_filter', 'list_membership') else [])
    return {'value': value, 'insufficient_evidence': insufficient,
            'status': 'insufficient_evidence' if insufficient else ('satisfied' if value else 'unsatisfied'),
            'function': binding.get('audit_function'), 'evidence': evidence, 'reason': reason,
            'searched_paths': [item['path'] for item in _sources(binding)],
            'checked_records': checked_records}


def execute_compiled_plan(ctx, plan):
    bindings = {item['atomic_constraint_id']: item for item in plan['constraints']}
    results, trace = {}, []
    applicability = evaluate_binding(ctx, plan['applicability'])
    app_unknown = applicability['insufficient_evidence']
    applicable = applicability['value']

    def cost(node):
        if isinstance(node, str):
            return 1 if (bindings[node].get('runtime') or {}).get('mode') == 'llm_bool' else 0
        return max((cost(child) for child in next(iter(node.values()))), default=0)

    def visit(node, branch='root'):
        if isinstance(node, str):
            if node not in results:
                results[node] = evaluate_binding(ctx, bindings[node])
                results[node]['normalized_constraint'] = bindings[node].get('normalized_constraint', '')
                trace.append({'atomic_id': node, 'branch': branch, 'status': results[node]['status']})
            result = results[node]
            state = None if result['insufficient_evidence'] else result['value']
            return state, [node], branch
        operator, children = next(iter(node.items()))
        if operator == 'not':
            state, ids, selected = visit(children[0], branch)
            return (None if state is None else not state), ids, selected
        evaluated = []
        for index, child in sorted(enumerate(children), key=lambda pair: cost(pair[1])):
            child_branch = f'{branch}.{index + 1}' if operator == 'or' else branch
            item = visit(child, child_branch)
            evaluated.append(item)
            if operator == 'and' and item[0] is False:
                return False, [atom for _, ids, _ in evaluated for atom in ids], branch
            if operator == 'or' and item[0] is True:
                return item
        if operator == 'and':
            return (None if any(item[0] is None for item in evaluated) else True), [atom for _, ids, _ in evaluated for atom in ids], branch
        state = None if any(item[0] is None for item in evaluated) else False
        candidates = [item for item in evaluated if item[0] is None] if state is None else evaluated
        selected = max(candidates, key=lambda item: (
            sum(results[atom]['value'] for atom in item[1]),
            -sum(results[atom]['status'] == 'unsatisfied' for atom in item[1]),
        ))
        return state, selected[1], selected[2]

    if applicable and not app_unknown:
        state, selected_ids, selected = visit(plan['logic'])
    else:
        state, selected_ids, selected = (None if app_unknown else True), [], None
    negative_ids = set()
    def collect_negations(node, negated=False):
        if isinstance(node, str):
            if negated:
                negative_ids.add(node)
            return
        operator, children = next(iter(node.items()))
        for child in children:
            collect_negations(child, not negated if operator == 'not' else negated)
    collect_negations(plan['logic'])
    failed = [item for item in selected_ids if state is False and (
        (item in negative_ids and results[item]['status'] == 'satisfied') or
        (item not in negative_ids and results[item]['status'] == 'unsatisfied')
    )]
    insufficient_ids = [item for item in selected_ids if results[item]['insufficient_evidence']]
    status = 'needs_review' if state is None else ('not_applicable' if not applicable else ('compliant' if state else 'violation'))
    reason = ('Insufficient evidence / Pending manual review' if status == 'needs_review'
              else '; '.join(
                  f"{item}: " + ('A prohibited condition was found.' if item in negative_ids
                                  else results[item]['reason']) for item in failed))
    highlights = [{'field_path': '$.' + entry['source_path'], 'highlighted_text': entry['text']}
                  for result in [applicability, *results.values()] for entry in result.get('evidence', [])
                  if entry.get('source_path') and entry.get('text')]
    return {'is_applicable': applicable or app_unknown, 'is_compliant': state is True,
            'failure_message': reason, 'review_status': status,
            'evidence': {'applicability': applicability, 'atomic_results': results,
                         'highlights': highlights, 'evaluated_atomic_ids': list(results),
                         'skipped_atomic_ids': [item for item in bindings if item not in results],
                         'selected_branch': selected, 'evaluation_trace': trace,
                         'failed_atomic_ids': failed, 'insufficient_atomic_ids': insufficient_ids,
                         'insufficient_evidence': status == 'needs_review'}}
