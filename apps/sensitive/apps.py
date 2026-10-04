from django.apps import AppConfig


class SensitiveConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sensitive'
    verbose_name = '敏感识别'
