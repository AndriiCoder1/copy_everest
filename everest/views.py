from django.shortcuts import render

def debug_i18n(request):
    """Страница отладки загрузки переводов"""
    return render(request, 'debug_i18n.html')
