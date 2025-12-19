from django.contrib import admin
from .models import Tribute

@admin.register(Tribute)
class TributeAdmin(admin.ModelAdmin):
    list_display = ('id','memorial','author_name','status','created_at','approved_at')
