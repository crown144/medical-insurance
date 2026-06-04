from rest_framework import serializers
from .models import ParentChildRelation


class ParentChildRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentChildRelation
        fields = [
            'id',
            'parent_insurance_code', 'parent_charge_code', 'parent_name',
            'child_insurance_code', 'child_charge_code', 'child_name',
        ]