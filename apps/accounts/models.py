from django.contrib.auth.models import AbstractUser
from django.db import models

from config.models import TimeStampedModel


class Role(TimeStampedModel):
    class Codes(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "超级管理员"
        SECURITY_ADMIN = "SECURITY_ADMIN", "安全管理员"
        ORCHARD_ADMIN = "ORCHARD_ADMIN", "果园管理员"
        NORMAL_USER = "NORMAL_USER", "普通用户"

    name = models.CharField("角色名称", max_length=40)
    code = models.CharField("角色编码", max_length=32, choices=Codes.choices, unique=True)
    description = models.TextField("说明", blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "角色"
        verbose_name_plural = "角色"

    def __str__(self):
        return self.name


class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users", verbose_name="业务角色")
    assigned_orchards = models.ManyToManyField("orchards.Orchard", blank=True, related_name="authorized_users", verbose_name="授权果园")
    display_name = models.CharField("姓名", max_length=50, blank=True)
    phone = models.CharField("手机号", max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_active", "role"])]

    @property
    def role_code(self):
        return self.role.code if self.role_id else ""

    def has_role(self, *codes):
        return self.is_superuser or self.role_code in codes

    @property
    def can_view_raw_sensitive(self):
        return self.has_role(Role.Codes.SUPER_ADMIN, Role.Codes.SECURITY_ADMIN)


class LoginAttempt(TimeStampedModel):
    username = models.CharField(max_length=150, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="login_attempts")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    success = models.BooleanField(default=False, db_index=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["username", "success", "created_at"])]

