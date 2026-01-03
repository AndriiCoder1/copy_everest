import os

# Путь к файлу перевода
po_file = "locale/de/LC_MESSAGES/django.po"

# Список переводов для добавления
missing_translations = {
    # tributes
    "For moderation": "Zur Moderation",
    "Approved": "Genehmigt",
    "Rejected": "Abgelehnt",
    "partner moderator": "Partner-Moderator",
    "Tribute": "Kondolenz",
    "Tributes": "Kondolenzen",
    
    # memorials (если нужно)
    "Memorial": "Gedenkseite",
    "Memorials": "Gedenkseiten",
    "Family Invite": "Familieneinladung",
    "Family Invites": "Familieneinladungen",
    "Language Override": "Sprachüberschreibung",
    "Language Overrides": "Sprachüberschreibungen",
    "QR Code": "QR-Code",
    "QR Codes": "QR-Codes",
    "Short Link": "Kurzlink",
    "Short Links": "Kurzlinks",
    
    # partners
    "Partner": "Partner",
    "Partners": "Partner",
    "Partner User": "Partner-Benutzer",
    "Partner Users": "Partner-Benutzer",
    
    # assets
    "Media Asset": "Medienasset",
    "Media Assets": "Medienassets",
    "Media Thumbnail": "Medienvorschaubild",
    "Media Thumbnails": "Medienvorschaubilder",
    
    # audits
    "Audit Log": "Audit-Protokoll",
    "Audit Logs": "Audit-Protokolle",
}

# Читаем файл
with open(po_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Добавляем отсутствующие переводы
for en, de in missing_translations.items():
    # Ищем msgid
    pattern = f'msgid "{en}"'
    if pattern in content:
        # Находим строку с msgstr
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if pattern in line:
                # Следующая строка должна быть msgstr
                if i+1 < len(lines) and lines[i+1].startswith('msgstr ""'):
                    lines[i+1] = f'msgstr "{de}"'
                    print(f"✓ Добавлен перевод для: {en}")
                elif i+1 < len(lines) and lines[i+1].startswith('msgstr'):
                    print(f"⚠ Перевод уже есть для: {en}")
                break
        content = '\n'.join(lines)
    else:
        print(f"✗ Не найден msgid: {en}")

# Записываем обратно
with open(po_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nГотово! Теперь выполните:")
print("python manage.py compilemessages -l de")