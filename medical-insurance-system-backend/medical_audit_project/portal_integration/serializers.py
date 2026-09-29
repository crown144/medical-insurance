from rest_framework import serializers


class PortalUserActionSerializer(serializers.Serializer):
    user_id = serializers.CharField(max_length=128, trim_whitespace=True)

    def validate_user_id(self, value):
        if not value:
            raise serializers.ValidationError('用户 ID 不能为空。')
        return value


class QueryUserStatusSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.CharField(max_length=128, trim_whitespace=True),
        allow_empty=False,
        max_length=500,
    )

    def validate_user_ids(self, value):
        if any(not item for item in value):
            raise serializers.ValidationError('用户 ID 不能为空。')
        return value
