# results/serializers.py (完整最终版)

from rest_framework import serializers
import json
from .models import Result, Highlight
from rules.serializers import RuleSerializer # 确保从 rules app 导入
from rules.services.readable_renderer import compiled_plan_from_code

class HighlightSerializer(serializers.ModelSerializer):
    """
    这个 Serializer 负责将 Highlight 对象转换为 JSON。
    """
    class Meta:
        model = Highlight
        # 我们只需要这两个字段给前端
        fields = ['field_path', 'highlighted_text']

class ResultSerializer(serializers.ModelSerializer):
    """
    这个 Serializer 负责将 Result 对象转换为 JSON。
    """
    # 嵌套序列化关联的 Rule 对象
    rule = RuleSerializer(read_only=True)
    
    # --- 核心修正点：在这里嵌套序列化 Highlight 对象 ---
    # 'highlights' 这个名字必须和 Highlight 模型中 ForeignKey 的 related_name 一致
    # 我们之前在 models.py 里定义了 related_name='highlights'
    highlights = HighlightSerializer(many=True, read_only=True)
    current_rule_conditions = serializers.SerializerMethodField()
    audit_evidence = serializers.SerializerMethodField()

    def get_audit_evidence(self, obj):
        try:
            snapshot = json.loads(obj.violation_item or '{}')
        except (TypeError, ValueError):
            return None
        evidence = snapshot.get('audit_evidence') if isinstance(snapshot, dict) else None
        return evidence if isinstance(evidence, dict) else None

    def get_current_rule_conditions(self, obj):
        """Descriptions are from the current rule, not a historical result snapshot."""
        code = getattr(obj.rule, 'rule_code', '') if obj.rule_id else ''
        if not code:
            return {}
        try:
            plan = compiled_plan_from_code(code)
        except (ValueError, SyntaxError, TypeError):
            return {}
        return {
            str(item['atomic_constraint_id']): str(item['normalized_constraint'])
            for item in plan.get('constraints', [])
            if isinstance(item, dict) and item.get('atomic_constraint_id')
            and item.get('normalized_constraint')
        }

    class Meta:
        model = Result
        # 在 fields 列表里加入 'highlights'
        fields = [
            'id', 
            'task',  # Added task field
            'hospitalization_id', 
            'violation_item', 
            'reason', 
            'created_at', 
            'discharge_date', # Added discharge_date
            'rule', 
            'highlights',
            'current_rule_conditions',
            'audit_evidence',
        ]
