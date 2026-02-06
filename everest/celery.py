import os
from celery import Celery
from django.conf import settings

# Устанавливаем переменную окружения для настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'everest.settings')

app = Celery('everest')

# Загружаем настройки из Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')
# Если задачи выполняются синхронно, настраиваем соответствующим образом
if settings.CELERY_TASK_ALWAYS_EAGER:
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    print("Celery running in EAGER mode (synchronous)")
else:
    print("Celery running in ASYNC mode")
# Автоматически находим задачи в приложениях
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')