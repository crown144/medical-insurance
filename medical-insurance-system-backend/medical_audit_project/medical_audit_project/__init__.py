# medical_audit_project/__init__.py

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

# 如果有 pymysql 的配置，保留它
import pymysql
pymysql.install_as_MySQLdb()

__all__ = ('celery_app',)