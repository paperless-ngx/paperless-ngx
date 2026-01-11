from typing import Any

import factory
from django.contrib.auth.models import User
from factory import Faker
from factory.django import DjangoModelFactory

from documents.models import Correspondent
from documents.models import Document
from documents.models import Tag


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances."""

    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = Faker("user_name")
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    is_active = True
    is_staff = False
    is_superuser = False

    @classmethod
    def _create(
        cls,
        model_class: type[User],
        *args: Any,
        **kwargs: Any,
    ) -> User:
        """Override create to use set_password for proper password handling."""
        password = kwargs.pop("password", None)
        user = super()._create(model_class, *args, **kwargs)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user

    class Params:
        staff = factory.Trait(is_staff=True)
        superuser = factory.Trait(is_staff=True, is_superuser=True)


class CorrespondentFactory(DjangoModelFactory):
    class Meta:
        model = Correspondent

    name = Faker("name")


class DocumentFactory(DjangoModelFactory):
    class Meta:
        model = Document


class TagFactory(DjangoModelFactory):
    """
    Factory for creating Tag instances.

    Examples:
        tag = TagFactory()
        tag = TagFactory(name="Invoice")
        tag = TagFactory(owner=user)
        tag = TagFactory(inbox=True)
        child = TagFactory(name="Child", parent=parent_tag)
    """

    class Meta:
        model = Tag
        skip_postgeneration_save = True

    name = Faker("catch_phrase")
    match = ""  # Intentionally empty - matching patterns are opt-in
    matching_algorithm = Tag.MATCH_ANY
    is_insensitive = True
    owner = None
    color = Faker("hex_color")
    is_inbox_tag = False
    tn_parent = None

    @factory.lazy_attribute
    def tn_priority(self) -> int:
        return 0

    @classmethod
    def _create(
        cls,
        model_class: type[Tag],
        *args: Any,
        **kwargs: Any,
    ) -> Tag:
        """Handle TreeNodeModel parent assignment via set_parent()."""
        parent = kwargs.pop("parent", None) or kwargs.pop("tn_parent", None)
        instance = super()._create(model_class, *args, **kwargs)
        if parent is not None:
            instance.set_parent(parent)
        return instance

    class Params:
        inbox = factory.Trait(is_inbox_tag=True)
        with_owner = factory.Trait(owner=factory.SubFactory(UserFactory))
