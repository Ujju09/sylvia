from django.apps import AppConfig


class GodownConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'godown'
    
    def ready(self):
        import godown.signals
