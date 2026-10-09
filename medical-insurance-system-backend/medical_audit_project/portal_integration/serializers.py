from rest_framework import serializers


class StrictCharField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail('invalid')
        return super().to_internal_value(data)


class PortalUserActionSerializer(serializers.Serializer):
    user_id = StrictCharField(max_length=128, trim_whitespace=True)

    def validate_user_id(self, value):
        if not value:
            raise serializers.ValidationError('用户 ID 不能为空。')
        return value


class QueryUserStatusSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=StrictCharField(max_length=128, trim_whitespace=True),
        allow_empty=False,
        max_length=500,
    )

    def validate_user_ids(self, value):
        if any(not item for item in value):
            raise serializers.ValidationError('用户 ID 不能为空。')
        return value


class PortalUserDetailSerializer(serializers.Serializer):
    id = StrictCharField(max_length=128)
    username = StrictCharField(max_length=150)
    fullname = StrictCharField(max_length=150, allow_blank=True)
    phone = StrictCharField(max_length=100, allow_blank=True)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    organization_code = StrictCharField(max_length=128, allow_blank=True)
    department = StrictCharField(max_length=255, allow_blank=True)
    create_time = StrictCharField(max_length=100)
    update_time = StrictCharField(max_length=100)
    expired = StrictIntegerField(min_value=-1, max_value=2 ** 63 - 1)
    status = StrictIntegerField(min_value=1, max_value=2)
