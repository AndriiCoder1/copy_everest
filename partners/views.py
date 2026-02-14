from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.db.models import Count, Q
from everest.permissions import get_partner_user
from memorials.models import Memorial
from tributes.models import Tribute


@login_required
def partner_dashboard(request):
    """
    Dashboard for partner staff: stats and quick actions.
    Access limited to PartnerUser (is_staff user with PartnerUser profile).
    """
    partner_user = get_partner_user(request)
    if not partner_user:
        return redirect('/admin/login/?next=' + request.path)

    memorials = list(Memorial.objects.filter(partner=partner_user.partner).order_by('-created_at'))

    # Compute statistics
    total_memorials = len(memorials)
    tribute_counts = Tribute.objects.filter(memorial__in=memorials).values('status').annotate(c=Count('id'))
    total_pending = sum(x['c'] for x in tribute_counts if x['status'] == 'pending')
    total_approved = sum(x['c'] for x in tribute_counts if x['status'] == 'approved')

    # Per-memorial counts
    per_memorial = {}
    for row in Tribute.objects.filter(memorial__in=memorials)\
            .values('memorial_id', 'status').annotate(c=Count('id')):
        mid = row['memorial_id']
        per = per_memorial.setdefault(mid, {'pending': 0, 'approved': 0})
        per[row['status']] = row['c']

    items = []
    for m in memorials:
        counts = per_memorial.get(m.id, {'pending': 0, 'approved': 0})
        items.append({
            'id': m.id,
            'name': f'{m.first_name} {m.last_name}',
            'created_at': m.created_at,
            'short_code': m.short_code,
            'pending': counts.get('pending', 0),
            'approved': counts.get('approved', 0),
            'family_url': f"/memorials/{m.short_code}/family/",  # token added via admin flow
            'admin_edit_url': f"/admin/memorials/memorial/{m.id}/change/",
            'admin_invite_url': f"/admin/memorials/familyinvite/add/?memorial={m.id}",
            'qr_download_url': f"/admin/memorials/qrcode/?memorial={m.id}"  # placeholder if admin has action
        })

    context = {
        'partner': partner_user.partner,
        'stats': {
            'memorials': total_memorials,
            'pending': total_pending,
            'approved': total_approved,
        },
        'items': items,
    }
    return render(request, 'partners/dashboard.html', context)

