from django.urls import path
from .api import MemorialCreate, MemorialList, MemorialActivate, FamilyInviteCreate, MemorialPublic

urlpatterns = [
    path('memorials/', MemorialCreate.as_view(), name='memorial-create'),
    path('memorials/list/', MemorialList.as_view(), name='memorial-list'), 
    path('memorials/<int:memorial_id>/activate/', MemorialActivate.as_view(), name='memorial-activate'),
    path('memorials/<int:memorial_id>/invites/', FamilyInviteCreate.as_view(), name='family-invite-create'),
    path('memorials/<str:code>/public/', MemorialPublic.as_view(), name='memorial-public'),
]