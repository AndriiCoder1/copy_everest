import json
import requests
from django.conf import settings
from celery import shared_task
from django.utils import timezone
from .models import Tribute
import logging
import re

logger = logging.getLogger(__name__)

@shared_task
def moderate_tribute_with_ai(tribute_id, retry_count=0):
    """
    Фоновая задача для модерации трибьюта с помощью ИИ
    """
    try:
        tribute = Tribute.objects.get(id=tribute_id)
        
        # Если уже отмодерирован или не в pending - пропускаем
        if tribute.status != 'pending' or tribute.ai_moderated_at:
            return f"Tribute {tribute_id} already moderated or not pending"
        
        # Получаем конфигурацию из настроек
        ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434/api/generate')
        model_name = getattr(settings, 'OLLAMA_MODEL', 'phi3:latest')
        
        # Промпт для модерации (адаптируйте под многоязычность)
        prompt_template = """<|system|>
        Du bist ein Moderator für Gedenkseiten in der Schweiz. Analysiere den folgenden Nachruf (Tribute).
        
        TEXT ZU ANALYSIEREN:
        "{text}"
        
        PRÜFKRITERIEN:
        1. Beleidigungen, Hassrede oder Vulgarität (Ja/Nein)
        2. Persönliche/private Daten (Ja/Nein)  
        3. Werbung/Spam (Ja/Nein)
        4. Unangemessener Ton für Trauerfeier (Ja/Nein)
        5. Respektvoller und angemessener Inhalt (Ja/Nein)
        
        GIB DEINE ANTWORT NUR IM FOLGENDEN JSON-FORMAT AUS:
        {{
          "verdict": "approved_ai" | "rejected_ai" | "flag_ai",
          "confidence": 0.0 bis 1.0,
          "reasoning": "Zusammenfassung der Analyse auf Deutsch",
          "flags": ["liste", "der", "erkannten", "probleme"]
        }}
        
        WICHTIG: Gib NUR das JSON zurück, keinen zusätzlichen Text!<|end|>
        <|user|>
        Analyze this tribute text (may be in German, French, Italian, or English):
        <|end|>
        <|assistant|>
        """

        # Ограничиваем длину
        prompt = prompt_template.format(text=tribute.text[:2000])  
        
        # Отправляем запрос к Ollama API
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                # Низкая температура для детерминированности
                "temperature": 0.1,  
                "top_p": 0.9,
                # Максимальная длина ответа
                "num_predict": 500, 
                # Стоп-токены
                "stop": ["<|end|>", "\n\n"]
            }
        }
        
        try:
            response = requests.post(
                ollama_url, 
                json=payload, 
                # Время ожидания ответа 60 секунд
                timeout=60  
            )
            response.raise_for_status()
            
            result = response.json()
            ai_response = result.get('response', '').strip()
            
            # ===== ПАРСИНГ JSON =====
            logger.info(f"Raw AI response for {tribute_id}: {ai_response[:200]}...")
            
            # 1. Убираем markdown код если есть
            cleaned_response = ai_response.replace('```json', '').replace('```', '').strip()
            
            # 2. Ищем JSON с помощью regex
            json_match = None
            
            # Сначала пробуем найти чистый JSON
            json_pattern = r'\{[^{}]*\{[^{}]*\}[^{}]*\}|{[^{}]*\}'
            matches = re.findall(json_pattern, cleaned_response, re.DOTALL)
            
            if matches:
                # Берём самый длинный match 
                json_match = max(matches, key=len)
                logger.info(f"Found JSON via regex: {json_match[:100]}...")
            
            # Если не нашли regex, пробуем старый метод
            if not json_match:
                start = cleaned_response.find('{')
                end = cleaned_response.rfind('}') + 1
                if start >= 0 and end > start:
                    json_match = cleaned_response[start:end]
                    logger.info(f"Found JSON via start/end: {json_match[:100]}...")
            
            # Парсим JSON
            if json_match:
                try:
                    ai_result = json.loads(json_match)
                    logger.info(f"Successfully parsed JSON for tribute {tribute_id}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}, trying to fix...")
                    
                    # Пробуем почистить JSON
                    json_match_fixed = re.sub(r',\s*}', '}', json_match) # Убираем лишние запятые после объектов
                    json_match_fixed = re.sub(r',\s*]', ']', json_match_fixed)
                    
                    try:
                        ai_result = json.loads(json_match_fixed)
                        logger.info(f"JSON fixed and parsed successfully")
                    except json.JSONDecodeError as e2:
                        logger.error(f"Still JSON parse error: {e2}")
                        # Fallback на флаг
                        ai_result = {
                            "verdict": "flag_ai", 
                            "confidence": 0.3,
                            "reasoning": f"JSON parse error: {str(e2)[:50]}",
                            "flags": ["parse_error"]
                        }
            else:
                logger.warning(f"No JSON found in response for tribute {tribute_id}")
                # Fallback на флаг
                ai_result = {
                    "verdict": "flag_ai", 
                    "confidence": 0.2,
                    "reasoning": "AI did not return valid JSON format",
                    "flags": ["invalid_format"]
                }
            
            
            # Применяем результат
            action = tribute.apply_ai_verdict(ai_result)
            
            # Логируем успех
            logger.info(f"ИИ отмодерировал трибьют {tribute_id}: {action}")
            
            return f"AI moderation completed for {tribute_id}: {action}"
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка подключения к Ollama: {e}")

            # Fallback на флаг, если подключение не удалось
            if settings.DEBUG:
                # В режиме разработки используем тестовые данные
                logger.info(f"DEBUG: Using fallback for tribute {tribute_id}")
                
                # Анализируем текст для тестового вердикта
                text_lower = tribute.text.lower()
                
                if any(word in text_lower for word in ['scheisse', 'hurensohn', 'arsch', 'idiot', 'hass', 'hassen']):
                    ai_result = {
                        "verdict": "rejected_ai",
                        "confidence": 0.92,
                        "reasoning": "Enthält unangemessene Sprache",
                        "flags": ["inappropriate_language"]
                    }
                elif any(word in text_lower for word in ['@', 'http', 'www.', '.com', 'telefon', 'nummer']):
                    ai_result = {
                        "verdict": "flag_ai", 
                        "confidence": 0.7,
                        "reasoning": "Mögliche persönliche Daten oder Links",
                        "flags": ["possible_personal_data"]
                    }
                elif len(text_lower) < 20:
                    ai_result = {
                        "verdict": "flag_ai",  
                        "confidence": 0.6,
                        "reasoning": "Text zu kurz für Analyse",
                        "flags": ["short_text"]
                    }
                else:
                    ai_result = {
                        "verdict": "approved_ai",
                        "confidence": 0.88,
                        "reasoning": "Text respektvoll und angemessen",
                        "flags": []
                    }
                
                action = tribute.apply_ai_verdict(ai_result)
                return f"DEBUG fallback used for {tribute_id}: {action}"
            
            
            # Повторная попытка (макс 3 раза)
            if retry_count < 3:
                moderate_tribute_with_ai.apply_async(
                    args=[tribute_id, retry_count + 1],
                    # Экспоненциальная задержка 
                    countdown=30 * (retry_count + 1)  
                )
                return f"Retry scheduled for {tribute_id}"
            
            # Если все попытки исчерпаны
            logger.error(f"Failed after retries for tribute {tribute_id}: {e}")
            
            # Присваиваем флаг, если все попытки исчерпаны
            tribute.ai_verdict = 'error_ai'
            tribute.ai_moderation_result = {"error": str(e)}
            tribute.save()
            
            return f"Failed after retries for {tribute_id}"
            
    except Tribute.DoesNotExist:
        logger.error(f"Трибьют {tribute_id} не найден")
        return f"Tribute {tribute_id} not found"
    except Exception as e:
        logger.exception(f"Неожиданная ошибка в moderate_tribute_with_ai: {e}")
        return f"Unexpected error: {str(e)}"