from django.apps import AppConfig

class TributesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tributes'
    verbose_name = 'Tributes'

    def ready(self):
        
        import tributes.signals 
