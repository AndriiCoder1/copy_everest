import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'everest.settings')
django.setup()

from tributes.models import Tribute
from tributes.tasks import moderate_tribute_with_ai

# Найдите трибьют
tribute = Tribute.objects.get(id=19)
print(f"Тестируем трибьют {tribute.id}: {tribute.author_name}")

# Попробуйте вызвать функцию БЕЗ Celery
try:
    # Временно убираем декоратор @shared_task
    import tributes.tasks
    original_func = tributes.tasks.moderate_tribute_with_ai.__wrapped__
    result = original_func(tribute.id)
    print("Успех! Результат:", result)
except Exception as e:
    print("Ошибка:", e)
    # Альтернатива: прямой вызов apply_ai_verdict
    test_data = {
        "verdict": "approved_ai",
        "confidence": 0.85,
        "reasoning": "Ручной тест",
        "flags": []
    }
    tribute.apply_ai_verdict(test_data)
    print("Поля ИИ обновлены вручную")
    
# Проверьте
tribute.refresh_from_db()
print(f"AI поля: verdict={tribute.ai_verdict}, confidence={tribute.ai_confidence}")
