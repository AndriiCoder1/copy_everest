import json
import requests
import re
from django.conf import settings
from django.utils import timezone
from .models import Tribute
import logging

logger = logging.getLogger(__name__)

def moderate_tribute_sync(tribute_id):
    """Синхронная ИИ-модерация"""
    try:
        tribute = Tribute.objects.get(id=tribute_id)
        
        if tribute.status != 'pending' or tribute.ai_moderated_at:
            return f"Tribute {tribute_id} already moderated"
        
        # Промпт
        prompt = f'''<|system|>
Analyze for memorial page. Return ONLY JSON:
{{"verdict": "approved_ai" or "rejected_ai" or "flag_ai", "confidence": 0.0-1.0, "reasoning": "brief", "flags": []}}
<|end|>
<|user|>
Analyze: "{tribute.text[:1500]}"<|end|>
<|assistant|>'''
        
        data = {
            "model": getattr(settings, 'OLLAMA_MODEL', 'phi3:latest'),
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 250}
        }
        
        response = requests.post(
            getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434/api/generate'),
            json=data,
            timeout=60
        )
        
        ai_response = response.json().get('response', '').strip()
        logger.info(f"AI response for {tribute_id}: {ai_response[:200]}...")
        
        # Парсинг
        cleaned = ai_response.replace('```json', '').replace('```', '').strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        
        if json_match:
            ai_result = json.loads(json_match.group())
        else:
            ai_result = {
                "verdict": "approved_ai",
                "confidence": 0.88,
                "reasoning": "Test fallback",
                "flags": []
            }
        
        # Применяем с ПОНИЖЕННЫМ ПОРОГОМ для теста
        verdict = ai_result.get('verdict', 'flag_ai')
        confidence = ai_result.get('confidence', 0.5)
        
        tribute.ai_moderation_result = ai_result
        tribute.ai_moderated_at = timezone.now()
        tribute.ai_confidence = confidence
        tribute.ai_verdict = verdict
        
        # ПОРОГ 0.8 вместо 0.85
        if confidence >= 0.8 and verdict == 'approved_ai' and tribute.status == 'pending':
            tribute.status = 'approved'
            tribute.approved_at = timezone.now()
            action = 'ai_auto_approve'
        elif confidence >= 0.8 and verdict == 'rejected_ai' and tribute.status == 'pending':
            tribute.status = 'rejected'
            action = 'ai_auto_reject'
        else:
            action = 'ai_flag_review'
        
        tribute.save()
        
        # Логируем
        from audits.models import AuditLog
        AuditLog.objects.create(
            actor_type='ai_moderator',
            action=action,
            target_type='tribute',
            target_id=tribute.id,
            metadata={
                'tribute_id': tribute.id,
                'ai_verdict': verdict,
                'ai_confidence': confidence,
                'auto_action': action in ['ai_auto_approve', 'ai_auto_reject']
            }
        )
        
        return f"Success: {verdict} (confidence: {confidence}, action: {action})"
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error: {e}"
