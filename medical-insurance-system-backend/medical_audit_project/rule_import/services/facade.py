"""算法门面：文件 -> 表格 -> 规则 的端到端封装

对应 rule-import/readme.txt 中的 extract_rules_from_file 范例。
本层只做“算法编排”，不触碰数据库，便于单测与复用。
"""

import logging

from .extractor import file_to_json
from .rule_discovery import discover_rules

logger = logging.getLogger(__name__)


def extract_rules_from_file(
    file_path,
    max_pdf_pages=None,
    max_rows_per_table=None,
    chunk_size=10,
    max_tables=None,
    parse_cb=None,
    progress_cb=None,
):
    """一步完成：文件 -> 表格 -> 规则。

    Args:
        file_path: 输入文件绝对路径
        max_pdf_pages / max_rows_per_table / chunk_size / max_tables: 算法参数
        parse_cb(table_count): 解析完成回调（供任务回写阶段/进度）
        progress_cb(done, total, found): 抽取进度回调

    Returns:
        dict: {tables, rules, table_count, rule_count}
    """
    logger.info("[facade] 开始解析文件: %s", file_path)
    tables = file_to_json(file_path=file_path, max_pdf_pages=max_pdf_pages,
                          save_json=False)
    table_count = len(tables)
    logger.info("[facade] 解析完成，共 %s 张表", table_count)
    if parse_cb:
        try:
            parse_cb(table_count)
        except Exception as e:  # noqa: BLE001
            logger.warning("[facade] parse_cb 回调异常(忽略): %s", e)

    rules = discover_rules(
        tables=tables,
        max_tables=max_tables,
        max_rows_per_table=max_rows_per_table,
        chunk_size=chunk_size,
        save_json=False,
        progress_cb=progress_cb,
    )
    logger.info("[facade] 规则抽取完成，共 %s 条", len(rules))

    return {
        "tables": tables,
        "rules": rules,
        "table_count": table_count,
        "rule_count": len(rules),
    }
