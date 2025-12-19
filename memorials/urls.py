from django.urls import path, include
urlpatterns = [
    path('', include('memorials.urls_api')),
]
