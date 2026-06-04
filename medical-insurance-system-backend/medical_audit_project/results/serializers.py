# results/serializers.py (完整最终版)

from rest_framework import serializers
from .models import Result, Highlight
from rules.serializers import RuleSerializer # 确保从 rules app 导入

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
            'highlights' # <-- 确保 'highlights' 在这里
        ]