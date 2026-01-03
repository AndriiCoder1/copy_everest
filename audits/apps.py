from django.apps import AppConfig

class AuditsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audits'
    verbose_name = 'Audits'

    def ready(self):
    
        import audits.signals  