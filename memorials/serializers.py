from rest_framework import serializers
from .models import Memorial, FamilyInvite
from assets.models import MediaAsset
from tributes.models import Tribute

class MemorialCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Memorial
        fields = ['first_name','last_name','birth_date','death_date','quote','biography_language','family_contact_email','theme_key']

class FamilyInviteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyInvite
        fields = ['email','expires_at']

class MediaAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaAsset
        fields = ['id','kind','original_filename','mime_type','size_bytes']

class TributePublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tribute
        fields = ['author_name','author_email','text']

class TributeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tribute
        fields = ['id','author_name','author_email','text','status','created_at']

class MemorialPublicSerializer(serializers.ModelSerializer):
     assets = MediaAssetSerializer(many=True)
     tributes = serializers.SerializerMethodField()

     class Meta:
        model = Memorial
        fields = ['first_name','last_name','birth_date','death_date','quote','biography_language','theme_key','assets','tributes']

     def get_tributes(self, obj):
        try:
            qs = obj.tributes.filter(status='approved').order_by('-created_at')
            return TributeListSerializer(qs, many=True).data
        except Exception as e:
            # Логируем ошибку для отладки
            print(f"⚠️ Error while receiving tributes: {type(e).__name__}: {e}") 
            return []  # Возвращаем пустой список вместо ошибки
     def get_assets(self, obj):
        try:
            # Возвращаем только публичные активы
            qs = obj.assets.filter(is_public=True)
            return MediaAssetSerializer(qs, many=True).data
        except Exception as e:
            print(f"⚠️ Error while receiving assets: {type(e).__name__}: {e}") 
            return []