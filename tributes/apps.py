from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class TributesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tributes'
    verbose_name = _('Tributes')

    def ready(self):
        
        import tributes.signals 
