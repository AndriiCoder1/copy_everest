from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class MemorialsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'memorials'
    verbose_name = _('Memorials')
    
    def ready(self):
        
        import memorials.signals 