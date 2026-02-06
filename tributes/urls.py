from django.urls import path
from .api import TributePublicSubmit, TributeListModeration, TributeApprove, TributeReject, TributeAIModerate
from .views import family_full_view

urlpatterns = [
    path('api/memorials/<int:memorial_id>/tributes/', TributeListModeration.as_view()),
    path('api/memorials/<str:code>/tributes/', TributePublicSubmit.as_view()),
    path('api/tributes/<int:tribute_id>/approve/', TributeApprove.as_view()),
    path('api/tributes/<int:tribute_id>/reject/', TributeReject.as_view()),
    path('memorials/<str:short_code>/family/', 
         family_full_view, 
         name='family-full-view'),

    # ===== МАРШРУТЫ ДЛЯ ИИ-МОДЕРАЦИИ =====
    path('api/tributes/<int:tribute_id>/ai-moderate/', 
         TributeAIModerate.as_view(), 
         name='ai_moderate_tribute'),
    path('api/tributes/ai-moderate/batch/', 
         TributeAIModerate.as_view(), 
         name='ai_moderate_batch'),          
]
