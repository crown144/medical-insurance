from django.conf import settings
from django.db import models


class OptionalSchemaBooleanField(models.BooleanField):
    """Keep a new flag out of SQL while running against the original schema.

    Schema mode is chosen at process startup. Migration state always contains
    a regular BooleanField, so the optional upgrade remains reproducible.
    """

    def get_attname_column(self):
        name, column = super().get_attname_column()
        if getattr(settings, 'LEGACY_DATABASE_COMPATIBILITY', True):
            column = None
        return name, column

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        if not self.concrete:
            setattr(cls, self.attname, False)

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.db.models.BooleanField', args, kwargs

    def clone(self):
        _name, _path, args, kwargs = self.deconstruct()
        return models.BooleanField(*args, **kwargs)

    def formfield(self, **kwargs):
        if not self.concrete:
            return None
        return super().formfield(**kwargs)
