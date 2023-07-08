from django.contrib.auth.models import Group
from django.db import models
from django.utils.translation import gettext_lazy as _


class SSOGroup(models.Model):
    group = models.ForeignKey(
        Group,
        related_name="sso_groups",
        on_delete=models.CASCADE,
        null=False,
    )
    name = models.CharField(max_length=256, blank=False, null=False, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("SSO group")
        verbose_name_plural = _("SSO groups")

    def __str__(self):
        return self.name
