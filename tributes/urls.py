from django.urls import path
from .api import TributePublicSubmit, TributeListModeration, TributeApprove, TributeReject

urlpatterns = [
    path('api/memorials/<str:code>/tributes', TributePublicSubmit.as_view()),
    path('api/memorials/<int:memorial_id>/tributes', TributeListModeration.as_view()),
    path('api/tributes/<int:tribute_id>/approve', TributeApprove.as_view()),
    path('api/tributes/<int:tribute_id>/reject', TributeReject.as_view()),
]
