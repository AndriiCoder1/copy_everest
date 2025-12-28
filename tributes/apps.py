from django.apps import AppConfig

class TributesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tributes'

    def ready(self):
        print("=== TributesConfig.ready() called ===")
        # Импортируем сигналы
        import tributes.signals