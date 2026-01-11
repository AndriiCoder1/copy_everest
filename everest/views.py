from django.shortcuts import render

def debug_i18n(request):
    """Translation download debug page"""
    return render(request, 'debug_i18n.html')
