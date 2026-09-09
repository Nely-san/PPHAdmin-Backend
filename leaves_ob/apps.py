from django.apps import AppConfig

class LeavesOBConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'leaves_ob'

    def ready(self):
        import leaves_ob.signals
