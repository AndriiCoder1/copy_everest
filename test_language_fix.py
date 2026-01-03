# test_language_fix.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'everest.settings')
django.setup()

from django.test import RequestFactory
from django.conf import settings

print("=== ТЕСТ СИСТЕМЫ ЯЗЫКА ===")

# Проверяем настройки
print(f"1. LANGUAGE_CODE: {settings.LANGUAGE_CODE}")
print(f"2. LANGUAGES: {settings.LANGUAGES}")
print(f"3. USE_I18N: {settings.USE_I18N}")

# Проверяем middleware
print(f"\n4. MIDDLEWARE (первые 8):")
for i, mw in enumerate(settings.MIDDLEWARE[:8]):
    print(f"   {i}: {mw}")

# Проверяем ForceLanguageMiddleware
has_force = 'everest.middleware.ForceLanguageMiddleware' in settings.MIDDLEWARE
print(f"\n5. ForceLanguageMiddleware: {'✅ ПРИСУТСТВУЕТ' if has_force else '❌ ОТСУТСТВУЕТ'}")

# Тест перевода
from django.utils.translation import activate, gettext as _
print(f"\n6. Тест переводов:")
activate('de')
print(f"   Немецкий: 'Memorial' -> '{_('Memorial')}'")
activate('fr')
print(f"   Французский: 'Memorial' -> '{_('Memorial')}'")
activate('it')
print(f"   Итальянский: 'Memorial' -> '{_('Memorial')}'")

print("\n=== ТЕСТ ЗАВЕРШЕН ===")