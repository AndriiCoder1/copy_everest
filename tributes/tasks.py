import json
import requests
import re
import logging
from django.conf import settings
from celery import shared_task
from django.utils import timezone
from .models import Tribute

logger = logging.getLogger(__name__)

# Анализ упоминаний имени мемориала в тексте
def analyze_name_mentions(text, memorial):
    """
    Анализирует упоминания имени мемориала в тексте.
    Возвращает словарь с результатами анализа.
    """
    text_lower = text.lower()
    full_name = f"{memorial.first_name} {memorial.last_name}".lower()
    first_name = memorial.first_name.lower()
    last_name = memorial.last_name.lower()
    
    results = {
        'full_name_mentioned': full_name in text_lower,
        'first_name_mentioned': first_name in text_lower,
        'last_name_mentioned': last_name in text_lower,
        'other_names_found': [],
        'wrong_first_name_detected': False,
        'wrong_last_name_detected': False,
        'context': 'unknown'
    }

    # Шаблон для поиска "Имя Фамилия" или "Фамилия"
    name_patterns = [
        r'\b([A-ZÄÖÜ][a-zäöüß]+)\s+([A-ZÄÖÜ][a-zäöüß]+)\b',  
        r'\b(Herr|Frau|Mr\.|Mrs\.|Ms\.)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)\b',
    ]
    
    all_name_matches = []
    for pattern in name_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                # Для "Имя Фамилия"
                name_parts = [m for m in match if m and len(m) > 1]
                if len(name_parts) >= 2:
                    found_name = ' '.join(name_parts[:2])
                    all_name_matches.append(found_name)
            else:
                # Для одиночных совпадений
                if match and len(match) > 2:
                    all_name_matches.append(match)
    
    # Анализируем найденные имена
    found_names = set()
    for name in all_name_matches:
        name_lower = name.lower()
        
        # Игнорируем общие слова
        common_words = {'herr', 'frau', 'mr', 'mrs', 'ms', 'family', 'familie', 'and', 'und', 'der', 'die', 'das'}
        
        if (len(name) > 2 and 
            name_lower not in common_words):
            
            found_names.add(name)
            
            name_words = name_lower.split()
            
            # Проверка на неправильную фамилию
            if len(name_words) >= 2:
                found_first = name_words[0]
                found_last = name_words[1]
                
                # Если нашли имя мемориала, но с другой фамилией
                if found_first == first_name and found_last != last_name:
                    results['wrong_last_name_detected'] = True
                    results['detected_wrong_name'] = name
                    results['wrong_last_name_details'] = f"Expected: {last_name}, Found: {found_last}"
                
                # Если нашли фамилию мемориала, но с другим именем
                if found_last == last_name and found_first != first_name:
                    results['wrong_first_name_detected'] = True
                    results['detected_wrong_name'] = name
                    results['wrong_first_name_details'] = f"Expected: {first_name}, Found: {found_first}"
    
    results['other_names_found'] = list(found_names)
    
    # Определяем контекст для промпта
    if results['wrong_first_name_detected'] and results['wrong_last_name_detected']:
        results['context'] = 'wrong_both_names'
    elif results['wrong_first_name_detected']:
        results['context'] = 'wrong_first_name'
    elif results['wrong_last_name_detected']:
        results['context'] = 'wrong_last_name'
    elif results['full_name_mentioned']:
        results['context'] = 'correct_name'
    elif results['first_name_mentioned'] and results['last_name_mentioned']:
        results['context'] = 'both_names_separate'
    elif results['first_name_mentioned'] and not results['last_name_mentioned']:
        results['context'] = 'partial_name_first_only'
    elif results['last_name_mentioned'] and not results['first_name_mentioned']:
        results['context'] = 'partial_name_last_only'
    elif results['other_names_found']:
        results['context'] = 'different_name'
    else:
        results['context'] = 'no_name'
    
    return results

def prepare_name_analysis_for_prompt(name_analysis, memorial):
    """
    Форматирует анализ имён для включения в промпт ИИ.
    """
    lines = []
    
    # Критические ошибки
    if name_analysis.get('wrong_both_names', False):
        lines.append(f"🚨 KRITISCH: Text erwähnt komplett anderen Namen '{name_analysis.get('detected_wrong_name', 'unbekannt')}' statt '{memorial.first_name} {memorial.last_name}'!")
    
    if name_analysis['wrong_first_name_detected']:
        lines.append(f"🚨 FALSCHER VORNAME: Text erwähnt '{name_analysis.get('detected_wrong_name', 'anderer Name')}' (erwartet: '{memorial.first_name}')")
    
    if name_analysis['wrong_last_name_detected']:
        lines.append(f"🚨 FALSCHER NACHNAME: Text erwähnt '{name_analysis.get('detected_wrong_name', 'anderer Name')}' (erwartet Nachname: '{memorial.last_name}')")
    
    # Затем предупреждения
    elif name_analysis['full_name_mentioned']:
        lines.append(f"✓ Korrekter Name '{memorial.first_name} {memorial.last_name}' wird erwähnt.")
    
    elif name_analysis['context'] == 'both_names_separate':
        lines.append(f"⚠️ Vorname '{memorial.first_name}' und Nachname '{memorial.last_name}' getrennt erwähnt.")
    
    elif name_analysis['context'] == 'partial_name_first_only':
        lines.append(f"⚠️ Nur Vorname '{memorial.first_name}' erwähnt (Nachname fehlt).")
    
    elif name_analysis['context'] == 'partial_name_last_only':
        lines.append(f"⚠️ Nur Nachname '{memorial.last_name}' erwähnt (Vorname fehlt).")
    
    if name_analysis['other_names_found'] and not (name_analysis['wrong_first_name_detected'] or name_analysis['wrong_last_name_detected']):
        lines.append(f"⚠️ Andere Namen gefunden: {', '.join(name_analysis['other_names_found'][:2])}")
    
    if name_analysis['context'] == 'no_name':
        lines.append("ℹ️ Kein spezifischer Name erwähnt.")
    
    return "\n".join(lines) if lines else "Keine Namensanalyse verfügbar."


def build_ai_prompt(text, memorial, name_analysis_text):
    prompt_template = """<|system|>
Du bist ein Moderator für Gedenkseiten in der Schweiz. Analysiere den folgenden Nachruf (Tribute).

MEMORIAL KONTEXT:
- Name der verstorbenen Person: {memorial_name}
- Memorial-ID: {memorial_code}

NAME-ANALYSE (für deine Berücksichtigung):
{name_analysis}

TEXT ZU ANALYSIEREN (kann auf Deutsch, Französisch, Italienisch oder Englisch sein):
"{text}"

KATEGORISCHE ABLEHNUNGSGRÜNDE (SOFORT REJECT wenn zutreffend):
1. EXPLIZITE BELEIDIGUNGEN in JEDER Sprache (auch Russisch/andere):
   - "жопа", "сука", "идиот", "дурак" (Russisch)
   - "scheisse", "arschloch", "hurensohn" (Deutsch)
   - "bitch", "asshole", "motherfucker" (Englisch)
   - "connard", "salope", "putain" (Französisch)
   - "stronzo", "cazzo", "vaffanculo" (Italienisch)

2. TIERBEZEICHNUNGEN als Beleidigung:
   - "Schwein", "Hund", "Kuh", "Affe" wenn auf Person bezogen
   - Ausnahme: Wenn offensichtlich Name (z.B. "Herr Schwein")

3. EXPLIZITE HASSREDE:
   - Rassistische, sexistische, homophobe Äußerungen
   - Drohungen, Gewaltaufrufe

ERWEITERTE PRÜFKRITERIEN:
1. Beleidigungen, Hassrede oder Vulgarität (in ALLEN Sprachen prüfen!)
2. Persönliche/private Daten (Telefon, Adresse, Email)  
3. Werbung/Spam (Links, Produktnennungen)
4. Unangemessener Ton für Trauerfeier
5. TEXT-INTEGRITÄT: Plötzliche Sprachwechsel, Testphrasen
6. NAMENS-KONTEXT: Bezieht sich Text auf richtiges Memorial?

ENTSCHEIDUNGSLOGIK (PRIORITÄTEN):
1. WENN kategorische Ablehnungsgründe (oben) → SOFORT REJECT (confidence 0.9+)
2. WENN offensichtliche Beleidigungen in Fremdsprachen → REJECT
3. WENN 'Schwein', 'Hund' etc. als Beleidigung erkennbar → REJECT
4. WENN unklarer Kontext (z.B. "Schwein" als möglicher Name) → FLAG
5. WENN respektvoll ohne Probleme → APPROVE

BEISPIELE für SOFORT-REJECT:
- "Er war жопа ein Mensch" → REJECT (жопа = russische Beleidigung)
- "Du Schwein!" → REJECT (Tier als Beleidigung)
- "Scheisse, er war..." → REJECT (explizite Vulgarität)

BEISPIELE für FLAG:
- "Herr Schwein war..." → FLAG (möglicher Name)
- "Er war stark wie ein Bär" → APPROVE (positiver Vergleich)

GIB DEINE ANTWORT NUR IM FOLGENDEN JSON-FORMAT AUS:
{{
  "verdict": "approved_ai" | "rejected_ai" | "flag_ai",
  "confidence": 0.0 bis 1.0,
  "reasoning": "Deutsche Begründung",
  "flags": ["liste", "der", "probleme"],
  "rejection_category": "explicit_insult" | "hate_speech" | "vulgarity" | "none"
}}

WICHTIG: Sei STRENG bei Beleidigungen! Gib NUR das JSON zurück, keinen zusätzlichen Text!<|end|>
<|user|>
Analysiere diesen Nachruf mit obigem Memorial-Kontext (Text kann Deutsch, Französisch, Italienisch oder Englisch sein):<|end|>
<|assistant|>"""
    
    return prompt_template.format(
        memorial_name=f"{memorial.first_name} {memorial.last_name}",
        memorial_code=memorial.short_code,
        name_analysis=name_analysis_text,
        text=text[:2000]
    )


def parse_ai_response(ai_response, tribute_id):
    """
    Парсит ответ от ИИ, извлекает JSON.
    """
    logger.info(f"Raw AI response for {tribute_id}: {ai_response[:200]}...")
    
    # Очистка ответа
    cleaned_response = ai_response.replace('```json', '').replace('```', '').strip()
    
    # Поиск JSON с помощью regex
    json_match = None
    json_pattern = r'\{[^{}]*\{[^{}]*\}[^{}]*\}|{[^{}]*\}'
    matches = re.findall(json_pattern, cleaned_response, re.DOTALL)
    
    if matches:
        json_match = max(matches, key=len)
        logger.info(f"Found JSON via regex: {json_match[:100]}...")
    
    if not json_match:
        start = cleaned_response.find('{')
        end = cleaned_response.rfind('}') + 1
        if start >= 0 and end > start:
            json_match = cleaned_response[start:end]
            logger.info(f"Found JSON via start/end: {json_match[:100]}...")
    
    # Парсинг JSON
    if json_match:
        try:
            return json.loads(json_match)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}, trying to fix...")
            
            # Попытка почистить JSON
            json_match_fixed = re.sub(r',\s*}', '}', json_match)
            json_match_fixed = re.sub(r',\s*]', ']', json_match_fixed)
            
            try:
                return json.loads(json_match_fixed)
            except json.JSONDecodeError as e2:
                logger.error(f"Still JSON parse error: {e2}")
    
    # Fallback если JSON не найден
    logger.warning(f"No valid JSON found in response for tribute {tribute_id}")
    return {
        "verdict": "flag_ai", 
        "confidence": 0.2,
        "reasoning": "AI did not return valid JSON format",
        "flags": ["invalid_format"],
        "name_context_note": "Parse error - manual review needed"
    }


def adjust_verdict_based_on_names(ai_result, name_analysis):
    """
    Корректирует вердикт ИИ на основе анализа имён.
    """
    from django.conf import settings
    
    name_settings = settings.AI_MODERATION_SETTINGS.get('name_check', {})
    strictness = settings.AI_MODERATION_SETTINGS.get('name_verification_strictness', 'moderate')
    
    # Используем настройки из AI_MODERATION_SETTINGS
    auto_reject_wrong_name = name_settings.get('auto_reject_on_wrong_last_name', False)
    
    # Критические ошибки 
    if name_analysis.get('wrong_both_names', False):
        # Комплектно неправильное имя
        if auto_reject_wrong_name:
            ai_result['verdict'] = 'rejected_ai'
        else:
            ai_result['verdict'] = 'flag_ai'
        ai_result['confidence'] = 0.2
        ai_result['flags'] = ai_result.get('flags', []) + ['wrong_both_names', 'name_mismatch']
    
    elif name_analysis['wrong_first_name_detected']:
        # Неправильное имя
        if auto_reject_wrong_name and strictness == 'strict':
            ai_result['verdict'] = 'rejected_ai'
        else:
            ai_result['verdict'] = 'flag_ai'
        ai_result['confidence'] = 0.3
        ai_result['flags'] = ai_result.get('flags', []) + ['wrong_first_name', 'name_mismatch']
    
    elif name_analysis['wrong_last_name_detected']:
        # Неправильная фамилия
        if auto_reject_wrong_name and strictness == 'strict':
            ai_result['verdict'] = 'rejected_ai'
        else:
            ai_result['verdict'] = 'flag_ai'
        ai_result['confidence'] = 0.3
        ai_result['flags'] = ai_result.get('flags', []) + ['wrong_last_name', 'name_mismatch']
        ai_result['reasoning'] = f"NAMENSFEHLER: {ai_result.get('reasoning', '')}"
    
    # Предупреждения
    elif name_analysis['context'] == 'partial_name_first_only':
        # Только имя без фамилии
        if strictness == 'strict':
            ai_result['verdict'] = 'flag_ai'
            ai_result['confidence'] = ai_result.get('confidence', 0.5) * 0.6
        elif strictness == 'moderate':
            ai_result['confidence'] = ai_result.get('confidence', 0.5) * 0.7
        ai_result['flags'] = ai_result.get('flags', []) + ['missing_last_name']
    
    elif name_analysis['context'] == 'partial_name_last_only':
        # Только фамилия без имени
        if strictness == 'strict':
            ai_result['verdict'] = 'flag_ai'
            ai_result['confidence'] = ai_result.get('confidence', 0.5) * 0.6
        elif strictness == 'moderate':
            ai_result['confidence'] = ai_result.get('confidence', 0.5) * 0.7
        ai_result['flags'] = ai_result.get('flags', []) + ['missing_first_name']
    
    elif name_analysis['context'] == 'different_name':
        # Другие имена
        if strictness == 'strict':
            ai_result['verdict'] = 'flag_ai'
            ai_result['confidence'] = 0.4
        elif strictness == 'moderate':
            ai_result['confidence'] = ai_result.get('confidence', 0.5) * 0.6
        ai_result['flags'] = ai_result.get('flags', []) + ['different_name_mentioned']
    
    return ai_result


def check_explicit_insults(text):
    """Проверка на явные оскорбления перед отправкой в AI"""
    text_lower = text.lower()
    
    # Явные оскорбления на разных языках
    explicit_insults = {
        'russian': ['жопа', 'сука', 'пизда', 'блядь', 'ебать', 'хуй', 'идиот', 'дурак'],
        'german': ['scheisse', 'arsch', 'hurensohn', 'wichser', 'fotze', 'miststück'],
        'english': ['shit', 'fuck', 'asshole', 'bitch', 'motherfucker', 'cunt'],
        'french': ['merde', 'putain', 'connard', 'salope', 'enculé'],
        'italian': ['merda', 'cazzo', 'stronzo', 'vaffanculo', 'puttana']
    }
    
    found_insults = []
    for language, words in explicit_insults.items():
        for word in words:
            if word in text_lower:
                found_insults.append(f"{word} ({language})")
    
    # Проверка животных как оскорблений
    animal_insults = ['schwein', 'hund', 'sau', 'kuh', 'affe', 'ratte']
    # Но исключаем, если это часть нормального предложения
    if 'schwein' in text_lower:
        # Проверяем контекст: "Du Schwein!" vs "Herr Schwein"
        if re.search(r'\b(du|sie|er|sie)\s+schwein\b', text_lower, re.IGNORECASE):
            found_insults.append("schwein (animal_insult)")
    
    return found_insults    

# Основная задача Celery для модерации трибьюта с помощью ИИ
@shared_task
def moderate_tribute_with_ai(tribute_id, retry_count=0):
    """
    Фоновая задача для модерации трибьюта с помощью ИИ
    """
    try:
        tribute = Tribute.objects.get(id=tribute_id)
        # Проверка на явные оскорбления
        explicit_insults = check_explicit_insults(tribute.text)

        if explicit_insults:
            logger.warning(f"Explicit insults detected for tribute {tribute_id}: {explicit_insults}")
            
            # Автоматически отклоняем если найдены явные оскорбления
            tribute.status = 'rejected'
            tribute.ai_verdict = 'rejected_ai'
            tribute.ai_confidence = 0.95
            tribute.ai_moderation_result = {
                "verdict": "rejected_ai",
                "confidence": 0.95,
                "reasoning": f"Explizite Beleidigungen gefunden: {', '.join(explicit_insults[:3])}",
                "flags": ["explicit_insult"] + explicit_insults[:3],
                "auto_action": True,
                "rejection_category": "explicit_insult"
            }
            tribute.save()
            
            return f"Auto-rejected for explicit insults: {explicit_insults[:2]}"
        # Если уже отмодерирован или не в pending - пропускаем
        if tribute.status != 'pending' or tribute.ai_moderated_at:
            return f"Tribute {tribute_id} already moderated or not pending"
        
        memorial = tribute.memorial
        
        # ===== 1. АНАЛИЗ ИМЁН =====
        name_analysis = analyze_name_mentions(tribute.text, memorial)
        name_analysis_text = prepare_name_analysis_for_prompt(name_analysis, memorial)
        
        logger.info(f"Name analysis for tribute {tribute_id}: {name_analysis['context']}")
        
        # ===== 2. ПОСТРОЕНИЕ ПРОМПТА С КОНТЕКСТОМ =====
        prompt = build_ai_prompt(tribute.text, memorial, name_analysis_text)
        
        # ===== 3. ОТПРАВКА В ИИ =====
        ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434/api/generate')
        model_name = getattr(settings, 'OLLAMA_MODEL', 'phi3:latest')
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 600,  # Немного больше для расширенного промпта
                "stop": ["<|end|>", "\n\n"]
            }
        }
        
        try:
            response = requests.post(ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            ai_response = result.get('response', '').strip()
            
            # ===== 4. ПАРСИНГ ОТВЕТА =====
            ai_result = parse_ai_response(ai_response, tribute_id)
            
            # ===== 5. КОРРЕКЦИЯ НА ОСНОВЕ ИМЁН =====
            ai_result = adjust_verdict_based_on_names(ai_result, name_analysis)
            
            # ===== 6. ДОБАВЛЕНИЕ КОНТЕКСТА ДЛЯ ЛОГОВ =====
            ai_result['name_context'] = name_analysis['context']
            if name_analysis['other_names_found']:
                ai_result['other_names'] = name_analysis['other_names_found'][:3]
            
            # ===== 7. ПРИМЕНЕНИЕ РЕЗУЛЬТАТА =====
            action = tribute.apply_ai_verdict(ai_result)
            
            # Логируем успех
            logger.info(f"ИИ отмодерировал трибьют {tribute_id}: {action}")
            logger.info(f"Name context: {name_analysis['context']}")
            
            return f"AI moderation completed for {tribute_id}: {action} (name context: {name_analysis['context']})"
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка подключения к Ollama: {e}")
            return handle_ollama_error(e, tribute, tribute_id, retry_count)
            
    except Tribute.DoesNotExist:
        logger.error(f"Трибьют {tribute_id} не найден")
        return f"Tribute {tribute_id} not found"
    except Exception as e:
        logger.exception(f"Неожиданная ошибка в moderate_tribute_with_ai: {e}")
        return f"Unexpected error: {str(e)}"


def handle_ollama_error(error, tribute, tribute_id, retry_count):
    """
    Обрабатывает ошибки подключения к Ollama.
    """
    # Fallback на флаг, если подключение не удалось
    if settings.DEBUG:
        logger.info(f"DEBUG: Using fallback for tribute {tribute_id}")
        
        # Упрощённая логика fallback с учётом имён
        text_lower = tribute.text.lower()
        memorial_name = f"{tribute.memorial.first_name} {tribute.memorial.last_name}".lower()
        
        # Проверяем наличие имени мемориала
        name_in_text = memorial_name in text_lower
        
        if any(word in text_lower for word in ['scheisse', 'hurensohn', 'arsch', 'idiot', 'hass', 'hassen']):
            ai_result = {
                "verdict": "rejected_ai",
                "confidence": 0.92,
                "reasoning": "Enthält unangemessene Sprache",
                "flags": ["inappropriate_language"],
                "name_context_note": f"Name {'erwähnt' if name_in_text else 'nicht erwähnt'}"
            }
        elif any(word in text_lower for word in ['@', 'http', 'www.', '.com', 'telefon', 'nummer']):
            ai_result = {
                "verdict": "flag_ai", 
                "confidence": 0.7,
                "reasoning": "Mögliche persönliche Daten oder Links",
                "flags": ["possible_personal_data"],
                "name_context_note": f"Name {'erwähnt' if name_in_text else 'nicht erwähnt'}"
            }
        elif len(text_lower) < 20:
            ai_result = {
                "verdict": "flag_ai",  
                "confidence": 0.6,
                "reasoning": "Text zu kurz für Analyse",
                "flags": ["short_text"],
                "name_context_note": f"Name {'erwähnt' if name_in_text else 'nicht erwähnt'}"
            }
        else:
            ai_result = {
                "verdict": "approved_ai",
                "confidence": 0.88 if name_in_text else 0.75,  # Ниже confidence если имя не упомянуто
                "reasoning": "Text respektvoll und angemessen",
                "flags": [],
                "name_context_note": f"Name {'erwähnt' if name_in_text else 'nicht erwähnt'}"
            }
        
        action = tribute.apply_ai_verdict(ai_result)
        return f"DEBUG fallback used for {tribute_id}: {action}"
    
    # Повторная попытка
    if retry_count < 3:
        moderate_tribute_with_ai.apply_async(
            args=[tribute_id, retry_count + 1],
            countdown=30 * (retry_count + 1)
        )
        return f"Retry scheduled for {tribute_id}"
    
    # Если все попытки исчерпаны
    logger.error(f"Failed after retries for tribute {tribute_id}: {error}")
    
    tribute.ai_verdict = 'error_ai'
    tribute.ai_moderation_result = {"error": str(error)}
    tribute.save()
    
    return f"Failed after retries for {tribute_id}"