from django.apps import AppConfig

class BaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'base'
    

    def ready(self):
        import base.signals  # or 'base.signals' if your signals.py is in the same app



