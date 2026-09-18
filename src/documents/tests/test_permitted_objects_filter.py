import pytest
from rest_framework.test import APIRequestFactory

from documents.filters import PermittedObjectsFilter
from documents.models import Tag
from paperless_testing.factories import TagFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_object


class _DummyView:
    queryset = Tag.objects.all()


@pytest.mark.django_db
class TestPermittedObjectsFilter:
    def test_superuser_bypasses_filtering_entirely(self):
        superuser = UserFactory(username="root", superuser=True)
        owner = UserFactory(username="owner")
        TagFactory(owner=owner)
        request = APIRequestFactory().get("/")
        request.user = superuser

        result = PermittedObjectsFilter().filter_queryset(
            request,
            Tag.objects.all(),
            _DummyView(),
        )
        assert result.count() == Tag.objects.count()

    def test_non_superuser_sees_only_owned_unowned_and_granted(self):
        owner = UserFactory(username="owner")
        grantee = UserFactory(username="grantee")
        owned = TagFactory(owner=grantee)
        unowned = TagFactory(owner=None)
        granted = TagFactory(owner=owner)
        hidden = TagFactory(owner=owner)
        grant_object(grantee, granted, "view_tag")
        request = APIRequestFactory().get("/")
        request.user = grantee

        result = PermittedObjectsFilter().filter_queryset(
            request,
            Tag.objects.all(),
            _DummyView(),
        )
        visible_ids = set(result.values_list("id", flat=True))
        assert visible_ids == {owned.pk, unowned.pk, granted.pk}
        assert hidden.pk not in visible_ids

    def test_include_granted_false_excludes_explicitly_shared_objects(self):
        owner = UserFactory(username="owner2")
        grantee = UserFactory(username="grantee2")
        owned = TagFactory(owner=grantee)
        granted = TagFactory(owner=owner)
        grant_object(grantee, granted, "view_tag")
        request = APIRequestFactory().get("/")
        request.user = grantee

        class _OwnerOnlyFilter(PermittedObjectsFilter):
            include_granted = False

        result = _OwnerOnlyFilter().filter_queryset(
            request,
            Tag.objects.all(),
            _DummyView(),
        )
        visible_ids = set(result.values_list("id", flat=True))
        assert visible_ids == {owned.pk}
        assert granted.pk not in visible_ids

    @pytest.mark.parametrize(
        ("username", "is_superuser"),
        [("inactive", False), ("inactive_super", True)],
    )
    def test_inactive_user_sees_nothing(self, username: str, *, is_superuser: bool):
        user = UserFactory(
            username=username,
            is_active=False,
            is_superuser=is_superuser,
        )
        TagFactory(owner=None)
        TagFactory(owner=user)
        granted = TagFactory(owner=UserFactory(username=f"o_{username}"))
        grant_object(user, granted, "view_tag")
        request = APIRequestFactory().get("/")
        request.user = user

        result = PermittedObjectsFilter().filter_queryset(
            request,
            Tag.objects.all(),
            _DummyView(),
        )
        assert result.count() == 0

    def test_inactive_user_sees_nothing_with_include_granted_false(self):
        user = UserFactory(username="inactive_owner", is_active=False)
        TagFactory(owner=user)
        TagFactory(owner=None)
        request = APIRequestFactory().get("/")
        request.user = user

        class _OwnerOnlyFilter(PermittedObjectsFilter):
            include_granted = False

        result = _OwnerOnlyFilter().filter_queryset(
            request,
            Tag.objects.all(),
            _DummyView(),
        )
        assert result.count() == 0
