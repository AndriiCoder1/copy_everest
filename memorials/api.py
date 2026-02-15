from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.core.files.base import ContentFile
from io import BytesIO
import segno
from .models import Memorial, FamilyInvite
from .serializers import MemorialCreateSerializer, FamilyInviteCreateSerializer, MemorialPublicSerializer
from .utils import generate_short_code
from everest.permissions import IsPartnerUser, HasFamilyToken, get_partner_user
from django.utils import translation

class MemorialCreate(APIView):
    permission_classes = [IsPartnerUser]
    
    def post(self, request):
        partner_user = get_partner_user(request)
        if not partner_user:
            return Response({'error': 'Not authorized'}, status=401)
        
        serializer = MemorialCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        short_code = generate_short_code()
        slug = slugify(f"{data.get('first_name','')}-{data.get('last_name','')}-{short_code}")[:64]
        
        memorial = Memorial.objects.create(
            partner=partner_user.partner,  
            first_name=data['first_name'],
            last_name=data['last_name'],
            birth_date=data.get('birth_date'),
            death_date=data.get('death_date'),
            quote=data.get('quote',''),
            biography_language=data.get('biography_language','en'),
            family_contact_email=data['family_contact_email'],
            theme_key=data.get('theme_key','calm'),
            short_code=short_code,
            slug=slug,
        )
        return Response({
            'id': memorial.id, 
            'short_code': memorial.short_code, 
            'slug': memorial.slug, 
            'status': memorial.status
        }, status=status.HTTP_201_CREATED)

class MemorialList(APIView):
    permission_classes = [IsPartnerUser]
    
    def get(self, request):
        partner_user = get_partner_user(request)
        if not partner_user:
            return Response({'error': 'Not authorized'}, status=401)
        
        # Только мемориалы этого партнера
        memorials = Memorial.objects.filter(partner=partner_user.partner)
        
        data = [{
            'id': m.id,
            'first_name': m.first_name,
            'last_name': m.last_name,
            'short_code': m.short_code,
            'status': m.status,
            'created_at': m.created_at
        } for m in memorials]
        
        return Response(data)

class MemorialActivate(APIView):
    permission_classes = [IsPartnerUser]
    
    def post(self, request, memorial_id):
        partner_user = get_partner_user(request)
        if not partner_user:
            return Response({'error': 'Not authorized'}, status=401)
        
        # Находим мемориал И проверяем, что он принадлежит партнеру
        memorial = get_object_or_404(
            Memorial, 
            pk=memorial_id,
            partner=partner_user.partner  
        )
        
        url = f"http://127.0.0.1:8000/memorials/{memorial.short_code}/public/"
        qr = segno.make(url, error='h')
        
        png_buf = BytesIO()
        pdf_buf = BytesIO()
        qr.save(png_buf, kind='png', scale=12, border=2)
        qr.save(pdf_buf, kind='pdf', border=2)
        
        memorial.qr_png.save(f"{memorial.short_code}.png", ContentFile(png_buf.getvalue()), save=False)
        memorial.qr_pdf.save(f"{memorial.short_code}.pdf", ContentFile(pdf_buf.getvalue()), save=False)
        memorial.status = 'active'
        memorial.save()
        
        return Response({
            'status': memorial.status, 
            'qr_png': memorial.qr_png.url if memorial.qr_png else None, 
            'qr_pdf': memorial.qr_pdf.url if memorial.qr_pdf else None
        })

class FamilyInviteCreate(APIView):
    permission_classes = [IsPartnerUser]
    
    def post(self, request, memorial_id):
        partner_user = get_partner_user(request)
        if not partner_user:
            return Response({'error': 'Not authorized'}, status=401)
        
        # Находим мемориал И проверяем, что он принадлежит партнеру
        memorial = get_object_or_404(
            Memorial, 
            pk=memorial_id,
            partner=partner_user.partner 
        )
        
        serializer = FamilyInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = generate_short_code(32)
        invite = FamilyInvite.objects.create(
            memorial=memorial,
            email=serializer.validated_data['email'],
            token=token,
            expires_at=serializer.validated_data['expires_at'],
        )
        
        return Response({
            'token': invite.token, 
            'expires_at': invite.expires_at.isoformat()
        }, status=status.HTTP_201_CREATED)

class MemorialPublic(APIView):
    authentication_classes = []
    permission_classes = []
    
    def get(self, request, code):
        memorial = get_object_or_404(Memorial, short_code=code, status='active')
        
        # Контент‑негация: JSON для API‑клиентов, HTML для браузеров
        accept = (request.headers.get('Accept') or '').lower()
        if 'application/json' in accept:
             # Для API-клиентов отдаем JSON
            serializer = MemorialPublicSerializer(memorial)
            return Response(serializer.data)
        
            
        else:
            # Для браузеров отдаем красивую HTML страницу
            from tributes.models import Tribute
            from assets.models import MediaAsset
            # Для браузеров - активируем язык мемориала!
            lang = memorial.language  # 'it', 'de', 'fr', 'en'
            translation.activate(lang)
            
            
            assets = MediaAsset.objects.filter(memorial=memorial, is_public=True)
            tributes = Tribute.objects.filter(
                memorial=memorial, status='approved'
            ).order_by('-created_at')[:10]
            
            return render(request, 'tributes/public_view.html', {
                'memorial': memorial,
                'assets': assets,
                'approved_tributes': tributes,
                'lang': lang,
            })
