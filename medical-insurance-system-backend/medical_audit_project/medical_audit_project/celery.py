import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_audit_project.settings')

app = Celery('medical_audit_project')
app.config_from_object('django.conf:settings', namespace='CELERY')

# --- 【重要修改】 ---
# 我们保留 autodiscover_tasks，但额外增加一个明确的 imports 设置
# 这会强制 Celery 在启动时去加载 'tasks.tasks' 这个模块
app.autodiscover_tasks()
app.conf.imports = (
    'tasks.tasks',
    # 如果未来你在其他 app (比如 'rules') 里也有 tasks.py，也可以加在这里
    # 'rules.tasks',
)


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')