from rest_framework import serializers
from .models import StandardChargeItem

class StandardChargeItemSerializer(serializers.ModelSerializer):
    """
    用于 StandardChargeItem 模型的序列化器。
    它会自动处理模型字段到 JSON 格式的转换。
    """
    class Meta:
        model = StandardChargeItem
        # '__all__' 表示序列化模型的所有字段
        fields = '__all__'