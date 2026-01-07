from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class ShortlinksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shortlinks'
    verbose_name = _('Shortlinks')

    
