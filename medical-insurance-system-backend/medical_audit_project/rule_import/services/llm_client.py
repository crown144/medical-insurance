"""LLM 客户端封装

把原 rule-import/extractor.py 与 convert-v2.py 中硬编码的
api_key / base_url / model 全部收敛到这里，统一从 Django settings 读取
（settings 再从环境变量读取），并提供：
  - 超时控制
  - 失败重试
  - 清晰日志

注意：openai SDK 采用惰性导入，未安装该依赖时本模块仍可被导入，
只有真正调用 call_llm() 时才会 import，便于在无网络/无依赖环境跑单测。
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "你是一个严谨的医保规则解析助手。"


def _get_client():
    """构造 OpenAI 客户端（惰性导入 openai）。"""
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的清晰报错
        raise RuntimeError(
            "未安装 openai 依赖，无法调用 LLM。请先 pip install openai。"
        ) from exc

    # 自部署的 OpenAI 兼容模型通常不校验密钥；OpenAI SDK 又要求 api_key 非空，
    # 故未配置时回退占位串 'EMPTY'，既能直连本地模型，也可由环境变量覆盖。
    api_key = getattr(settings, 'RULE_IMPORT_LLM_API_KEY', '') or 'EMPTY'
    base_url = getattr(settings, 'RULE_IMPORT_LLM_BASE_URL', '')
    if not base_url:
        raise RuntimeError(
            "未配置 RULE_IMPORT_LLM_BASE_URL，请在环境变量中设置模型服务地址。"
        )

    timeout = getattr(settings, 'RULE_IMPORT_LLM_TIMEOUT', 60)
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def get_header_model() -> str:
    return getattr(settings, 'RULE_IMPORT_LLM_MODEL_HEADER', 'qwen')


def get_extract_model() -> str:
    return getattr(settings, 'RULE_IMPORT_LLM_MODEL_EXTRACT', 'qwen')


def call_llm(prompt: str, model: str = None, temperature: float = 0) -> str:
    """调用 LLM。

    与原算法不同：失败时**抛出异常**而不是静默返回空串，
    由上层（Celery 任务）统一捕获并落库 error_detail，保证过程可观测。
    内部对单次请求做有限次重试。
    """
    if model is None:
        model = get_extract_model()

    client = _get_client()
    max_retries = getattr(settings, 'RULE_IMPORT_LLM_MAX_RETRIES', 2)

    last_exc = None
    for attempt in range(1, max_retries + 2):  # 首次 + 重试
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception as exc:  # noqa: BLE001 - 需要兜住所有 SDK/网络异常
            last_exc = exc
            logger.warning(
                "LLM 调用失败 (model=%s, 第 %s/%s 次): %s",
                model, attempt, max_retries + 1, exc,
            )

    raise RuntimeError(f"LLM 调用在重试 {max_retries + 1} 次后仍失败: {last_exc}")
