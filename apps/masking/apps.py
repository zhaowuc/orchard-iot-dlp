from django.apps import AppConfig


class MaskingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.masking'
    verbose_name = '动态脱敏'
