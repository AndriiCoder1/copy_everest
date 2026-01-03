# check_translations.py (ИСПРАВЛЕННЫЙ)
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'everest.settings')
django.setup()

from django.utils.translation import activate, gettext as _
from django.utils.translation.trans_real import DjangoTranslation, translation

print("=== ПРОВЕРКА ПЕРЕВОДОВ ===")

for lang_code in ['de', 'fr', 'it', 'en']:
    print(f"\n--- Проверка языка: {lang_code} ---")
    
    # Проверяем Django переводы
    try:
        trans = DjangoTranslation(lang_code, domain='django')
        print(f"Django переводы: ✅ Загружено {len(trans._catalog)} записей")
        
        # Проверяем несколько ключевых слов
        test_words = ['Memorial', 'Media Asset', 'Tribute', 'Save', 'Delete']
        for word in test_words:
            if word in trans._catalog:
                print(f"  '{word}' -> '{trans._catalog[word]}'")
            else:
                print(f"  '{word}' -> ❌ не найдено")
    except Exception as e:
        print(f"Django переводы: ❌ Ошибка: {e}")
    
    # Проверяем JavaScript переводы
    try:
        js_trans = DjangoTranslation(lang_code, domain='djangojs')
        print(f"JS переводы: ✅ Загружено {len(js_trans._catalog)} записей")
        
        # Проверяем несколько ключевых слов
        js_words = ['Save', 'Delete', 'Cancel', 'Search']
        for word in js_words:
            if word in js_trans._catalog:
                print(f"  '{word}' -> '{js_trans._catalog[word]}'")
            else:
                print(f"  '{word}' -> ❌ не найдено")
    except Exception as e:
        print(f"JS переводы: ❌ Ошибка: {e}")
    
    # Проверяем через activate
    print(f"\nТест через activate():")
    activate(lang_code)
    print(f"  'Save' -> '{_('Save')}'")
    print(f"  'Delete' -> '{_('Delete')}'")
    print(f"  'Cancel' -> '{_('Cancel')}'")