"""输出解析与入库层

  - save_extracted_rules: 算法输出(List[Dict]) -> ExtractedRule 暂存表
  - import_to_rule_library: 选中的 ExtractedRule -> 正式规则库 rules.Rule

入库映射不修改 rules.Rule 表结构，仅写入既有字段。
"""

import logging

from django.db import transaction

from rules.models import Rule

from ..models import ExtractedRule

logger = logging.getLogger(__name__)

# 算法英文枚举 -> 系统中文规则类型（rules.Rule.type 用中文）
RULE_TYPE_MAP = {
    "DRUG_RESTRICTION": "超限定用药",
    "FREQUENCY_LIMIT": "超频次收费",
    "DUPLICATE_CHARGE": "重复收费",
    "PRICE_LIMIT": "超标准收费",
    "CONSUMABLE_RESTRICTION": "耗材超限定",
    "OVER_EXAMINATION": "过度医疗",
    "OTHER": "其他",
}


def save_extracted_rules(task, rules):
    """把算法输出的规则列表落入 ExtractedRule 暂存表。

    Args:
        task: RuleImportTask 实例
        rules: discover_rules 的返回（List[Dict]）

    Returns:
        创建的条数
    """
    # 重跑场景：先清空旧的暂存结果，避免重复
    task.rules.all().delete()

    objs = []
    for r in rules:
        objs.append(ExtractedRule(
            import_task=task,
            seq=r.get("rule_id", 0) or 0,
            rule_type=str(r.get("rule_type", ""))[:40],
            constrained_object=str(r.get("constrained_object", ""))[:255],
            constraint_value=str(r.get("constraint_value", "")),
            evidence=r.get("evidence", {}) or {},
            source=r.get("source", {}) or {},
        ))

    if objs:
        ExtractedRule.objects.bulk_create(objs, batch_size=500)
    logger.info("[importer] 任务 %s 落库抽取规则 %s 条", task.id, len(objs))
    return len(objs)


@transaction.atomic
def import_to_rule_library(task, rule_ids=None, select_all=False):
    """把选中的 ExtractedRule 写入正式规则库 rules.Rule。

    Args:
        task: RuleImportTask 实例
        rule_ids: 要入库的 ExtractedRule id 列表
        select_all: 为 True 时入库该任务下全部尚未入库的规则

    Returns:
        dict: {imported, skipped, rule_ids}
    """
    qs = task.rules.filter(is_imported=False)
    if not select_all:
        qs = qs.filter(id__in=rule_ids or [])

    imported = 0
    skipped = 0
    imported_rule_ids = []

    for er in qs:
        if not er.constrained_object and not er.constraint_value:
            skipped += 1
            continue

        # 生成稳定且唯一的业务规则号
        rule_id = f"imp_{task.id}_{er.seq or er.id}"
        rule_type_cn = RULE_TYPE_MAP.get(er.rule_type, er.rule_type or "其他")

        Rule.objects.update_or_create(
            rule_id=rule_id,
            defaults={
                "drug_name": er.constrained_object[:255],
                "description": er.constraint_value or er.constrained_object,
                "type": rule_type_cn[:50],
                "match_field": "收费项目名称",
                "match_value": er.constrained_object[:255],
                "status": True,
            },
        )

        er.is_imported = True
        er.imported_rule_id = rule_id
        er.save(update_fields=["is_imported", "imported_rule_id"])
        imported_rule_ids.append(rule_id)
        imported += 1

    # 更新任务已入库统计
    task.imported_count = task.rules.filter(is_imported=True).count()
    task.save(update_fields=["imported_count", "updated_at"])

    logger.info("[importer] 任务 %s 入库 %s 条, 跳过 %s 条",
                task.id, imported, skipped)
    return {"imported": imported, "skipped": skipped,
            "rule_ids": imported_rule_ids}
