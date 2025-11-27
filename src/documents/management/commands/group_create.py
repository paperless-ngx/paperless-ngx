from django.contrib import auth
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.core.management import BaseCommand
from django.db import transaction

from documents.management.commands.mixins import ProgressBarMixin


class Command(ProgressBarMixin, BaseCommand):
    help = "Create a group"

    def add_arguments(self, parser):
        parser.add_argument(
            "name",
            help="Name of the group",
        )

        # Named (optional) arguments
        parser.add_argument(
            "-p",
            "--permission",
            action="append",
            help="Permissions to add to the created group",
        )
        # Named (optional) arguments
        parser.add_argument(
            "-a",
            "--all-permissions",
            action="store_true",
            help="Give this group all available permissions",
        )
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)
        with transaction.atomic():
            name = options["name"]
            permissions = options["permission"]
            setAllPermissions = options["all_permissions"]

            if setAllPermissions:
                permissions = set()
                # We create (but not persist) a temporary superuser and use it to game the
                # system and pull all permissions easily.
                tmp_superuser = get_user_model()(
                    is_active=True,
                    is_superuser=True,
                )
                for backend in auth.get_backends():
                    if hasattr(backend, "get_all_permissions"):
                        permissions.update(backend.get_all_permissions(tmp_superuser))

                # Output unique list of permissions sorted by permission name.
                permissions = sorted(list(permissions))

            new_group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(f"Created group: {new_group.name}\n")
            else:
                self.stdout.write(f"Group already exists: {new_group.name}\n")

            for permission in permissions:
                [module, codename] = permission.split(".")
                permission = Permission.objects.get(
                    content_type__app_label=module,
                    codename=codename,
                )
                new_group.permissions.add(permission)
                self.stdout.write(f"Added permission: {permission}\n")
