"""Helpers that grant permissions to users and groups in tests.

Two mechanisms, two names. A global permission is a Django model permission held
by a user. An object permission is a guardian permission held on one object by a
user or a group. They are not interchangeable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import Permission
from guardian.shortcuts import assign_perm

if TYPE_CHECKING:
    from django.contrib.auth.models import Group
    from django.contrib.auth.models import User
    from django.db.models import Model


def grant_global(user: User, *perms: str) -> None:
    """Grant model-level permissions.

    Each of perms is a codename or "app_label.codename". An unknown name raises
    Permission.DoesNotExist.
    """
    for perm in perms:
        app_label, _, codename = perm.rpartition(".")
        lookup = {"codename": codename}
        if app_label:
            lookup["content_type__app_label"] = app_label
        user.user_permissions.add(Permission.objects.get(**lookup))


def grant_all_global(user: User) -> None:
    """Grant every existing model-level permission without making a superuser."""
    user.user_permissions.add(*Permission.objects.all())


def grant_object(target: User | Group, obj: Model, *perms: str) -> None:
    """Grant object-level permissions on obj to a user or a group."""
    for perm in perms:
        assign_perm(perm, target, obj)
