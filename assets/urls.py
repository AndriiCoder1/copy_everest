from django.urls import path
from .api import MediaUpload, MediaList, MediaDelete

urlpatterns = [
    path('api/memorials/<int:memorial_id>/assets', MediaUpload.as_view()),
    path('api/memorials/<int:memorial_id>/assets/list', MediaList.as_view()),
    path('api/assets/<int:asset_id>', MediaDelete.as_view()),
]
