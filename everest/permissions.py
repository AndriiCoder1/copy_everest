from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.utils import timezone
from partners.models import PartnerUser
from memorials.models import FamilyInvite

def get_partner_user(request):
    if not request.user or not request.user.is_authenticated:
        return None
    try:
        return PartnerUser.objects.get(email=request.user.email)
    except PartnerUser.DoesNotExist:
        return None

class IsPartnerUser(BasePermission):
    def has_permission(self, request, view):
        return get_partner_user(request) is not None

class HasFamilyToken(BasePermission):
    def has_permission(self, request, view):
        token = request.headers.get('X-Family-Token') or request.query_params.get('token')
        if not token:
            return False
        try:
            invite = FamilyInvite.objects.get(token=token)
        except FamilyInvite.DoesNotExist:
            return False
        if invite.expires_at and invite.expires_at < timezone.now():
            return False
        request.family_invite = invite
        return True

class IsPartnerOrFamily(BasePermission):
    def has_permission(self, request, view):
        return IsPartnerUser().has_permission(request, view) or HasFamilyToken().has_permission(request, view)
