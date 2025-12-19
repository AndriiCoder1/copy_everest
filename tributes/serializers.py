from rest_framework import serializers
from .models import Tribute

class TributeSubmitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tribute
        fields = ['author_name','author_email','text']

class TributeModerationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tribute
        fields = ['id','author_name','author_email','text','status','created_at']
