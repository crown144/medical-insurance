"""
父子项目重复收费检测器
将1016_type1/type_1_1014.py的逻辑适配到系统：
- 从父子映射表或CSV加载映射
- 在同一时间批次内同时出现父/子项目则判定为重复收费-父子
"""

import csv
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from django.conf import settings

from .utils import ChargeDataProcessor
from .models import ParentChildRelation

logger = logging.getLogger(__name__)


class FatherChildDuplicateDetector:
    def __init__(self, csv_fallback_path: Optional[str] = None):
        self.data_processor = ChargeDataProcessor()
        # 支持通过环境变量配置CSV路径作为回退
        self.csv_fallback_path = (
            csv_fallback_path
            or os.getenv('FATHER_CHILD_CSV_PATH')
            or os.path.join(str(getattr(settings, 'BASE_DIR', '')), '1016_type1', 'father-child.csv')
        )

    def _load_relations(self) -> List[Tuple[str, str, str, str, str, str]]:
        """
        加载父子关系映射，优先使用数据库，若为空则回退到CSV。
        返回列表元素为 (parent_charge_code, parent_name, child_charge_code, child_name, parent_ins_code, child_ins_code)
        """
        relations = []
        try:
            qs = ParentChildRelation.objects.all()
            if qs.exists():
                for r in qs:
                    relations.append(
                        (
                            self.data_processor.normalize_charge_code(r.parent_charge_code),
                            r.parent_name,
                            self.data_processor.normalize_charge_code(r.child_charge_code),
                            r.child_name,
                            r.parent_insurance_code or '',
                            r.child_insurance_code or '',
                        )
                    )
                return relations
        except Exception as e:
            logger.warning(f"[FatherChildDetector] 读取数据库映射失败，尝试CSV：{e}")

        # CSV fallback
        try:
            if self.csv_fallback_path and os.path.exists(self.csv_fallback_path):
                with open(self.csv_fallback_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        parent_charge = self.data_processor.normalize_charge_code(row.get('收费编码') or row.get('父项目收费编码', ''))
                        child_charge = self.data_processor.normalize_charge_code(row.get('子项目收费编码', ''))
                        parent_name = row.get('父项目名称', '')
                        child_name = row.get('子项目名称', '')
                        parent_ins_code = row.get('医保统一编码') or row.get('父项目医保编码', '')
                        child_ins_code = row.get('子项目医保编码', '')
                        if parent_charge and child_charge:
                            relations.append(
                                (parent_charge, parent_name, child_charge, child_name, parent_ins_code or '', child_ins_code or '')
                            )
        except Exception as e:
            logger.error(f"[FatherChildDetector] 加载CSV失败: {e}")

        return relations

    def detect(self, patient_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        检测同一时间批次内出现父子项目的重复收费违规。
        输出格式遵循系统Result创建预期：
        - violation, rule{rule_id,type,drug_name,description}, reason, item, highlights
        """
        fee_data = patient_json.get('收费报告', [])
        if not fee_data:
            logger.info("[FatherChildDetector] 无收费报告数据")
            return []

        relations = self._load_relations()
        if not relations:
            logger.warning("[FatherChildDetector] 未加载到父子关系映射，跳过检测")
            return []

        # 按时间批次分组收费记录
        time_groups = self.data_processor.group_by_time_batch(fee_data)

        violations: List[Dict[str, Any]] = []
        patient_id = self.data_processor.extract_patient_id(patient_json)

        for time_batch, charges in time_groups.items():
            # 代码分组，便于快速查找
            code_groups = self.data_processor.group_charges_by_code(charges)

            for (parent_code, parent_name, child_code, child_name, parent_ins_code, child_ins_code) in relations:
                parent_list = code_groups.get(parent_code, [])
                child_list = code_groups.get(child_code, [])

                if parent_list and child_list:
                    # 在同一时间批次内同时出现父/子项目，认定为违规
                    total_amount = 0.0
                    detail_items = []
                    highlights = []

                    def add_detail(charge: Dict[str, Any]):
                        nonlocal total_amount, detail_items, highlights
                        amount = self.data_processor.calculate_charge_amount(charge)
                        total_amount += amount
                        detail_items.append({
                            '收费项目代码': charge.get('收费项目代码'),
                            '收费项目名称': charge.get('收费项目名称'),
                            '收费日期': charge.get('收费日期'),
                            'ORDER_ITEM_CODE': charge.get('ORDER_ITEM_CODE', ''),
                            '项目单价': charge.get('项目单价', 0),
                            '数量': charge.get('数量', 1),
                            '金额': amount
                        })
                        highlights.append({
                            'field_path': f"收费报告[{charges.index(charge)}]",
                            'highlighted_text': f"{charge.get('收费项目名称','')} - 父子重复 - {charge.get('收费日期','')}"
                        })

                    for c in parent_list:
                        add_detail(c)
                    for c in child_list:
                        add_detail(c)

                    amount_str = self.data_processor.format_violation_amount(total_amount)
                    reason = (
                        f"父项目'{parent_name}'(代码:{parent_code})与子项目'{child_name}'(代码:{child_code})在{time_batch}同时收费，"
                        f"疑似父子重复收费，涉及{len(parent_list)}个父项与{len(child_list)}个子项记录，合计金额:{amount_str}"
                    )

                    violation = {
                        'violation': True,
                        'rule': {
                            'rule_id': f'FATHER_CHILD_DUPLICATE_{parent_code}_{child_code}',
                            'type': '重复收费-父子',
                            'drug_name': f"{parent_name}/{child_name}",
                            'description': '检测到父子项目在同一时间批次内同时收费'
                        },
                        'reason': reason,
                        'item': {
                            '患者住院号': patient_id,
                            '父项目代码': parent_code,
                            '父项目名称': parent_name,
                            '子项目代码': child_code,
                            '子项目名称': child_name,
                            '医保统一编码(父/子)': f"{parent_ins_code}/{child_ins_code}" if (parent_ins_code or child_ins_code) else '',
                            '重复日期': time_batch,
                            '父项记录数': len(parent_list),
                            '子项记录数': len(child_list),
                            '总金额': total_amount,
                            '明细': detail_items,
                        },
                        'highlights': highlights,
                        'violation_type': 'father_child_duplicate',
                        'severity': 'medium',
                    }

                    violations.append(violation)

        logger.info(f"[FatherChildDetector] 父子重复收费检测完成，共发现 {len(violations)} 项违规")
        return violations