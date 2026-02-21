from documents.tests.utils import TestMigrations

DASHBOARD_VIEWS_VISIBLE_IDS_KEY = (
    "general-settings:saved-views:dashboard-views-visible-ids"
)
SIDEBAR_VIEWS_VISIBLE_IDS_KEY = "general-settings:saved-views:sidebar-views-visible-ids"


class TestMigrateSavedViewVisibilityToUiSettings(TestMigrations):
    migrate_from = "0011_optimize_integer_field_sizes"
    migrate_to = "0012_savedview_visibility_to_ui_settings"

    def setUpBeforeMigration(self, apps) -> None:
        User = apps.get_model("auth", "User")
        SavedView = apps.get_model("documents", "SavedView")
        UiSettings = apps.get_model("documents", "UiSettings")

        self.user_with_empty_settings = User.objects.create(username="user1")
        self.user_with_existing_settings = User.objects.create(username="user2")
        self.user_with_owned_views = User.objects.create(username="user3")
        self.user_with_empty_settings_id = self.user_with_empty_settings.id
        self.user_with_existing_settings_id = self.user_with_existing_settings.id
        self.user_with_owned_views_id = self.user_with_owned_views.id

        self.dashboard_view = SavedView.objects.create(
            owner=self.user_with_empty_settings,
            name="dashboard",
            show_on_dashboard=True,
            show_in_sidebar=True,
            sort_field="created",
        )
        self.sidebar_only_view = SavedView.objects.create(
            owner=self.user_with_empty_settings,
            name="sidebar-only",
            show_on_dashboard=False,
            show_in_sidebar=True,
            sort_field="created",
        )
        self.hidden_view = SavedView.objects.create(
            owner=self.user_with_empty_settings,
            name="hidden",
            show_on_dashboard=False,
            show_in_sidebar=False,
            sort_field="created",
        )
        self.other_owner_visible_view = SavedView.objects.create(
            owner=self.user_with_owned_views,
            name="other-owner-visible",
            show_on_dashboard=True,
            show_in_sidebar=True,
            sort_field="created",
        )

        UiSettings.objects.create(user=self.user_with_empty_settings, settings={})
        UiSettings.objects.create(
            user=self.user_with_existing_settings,
            settings={
                DASHBOARD_VIEWS_VISIBLE_IDS_KEY: [self.sidebar_only_view.id],
                SIDEBAR_VIEWS_VISIBLE_IDS_KEY: [self.dashboard_view.id],
                "preserve": "value",
            },
        )

    def test_visibility_defaults_are_seeded_and_existing_values_preserved(self) -> None:
        UiSettings = self.apps.get_model("documents", "UiSettings")

        seeded_settings = UiSettings.objects.get(
            user_id=self.user_with_empty_settings_id,
        ).settings
        self.assertCountEqual(
            seeded_settings[DASHBOARD_VIEWS_VISIBLE_IDS_KEY],
            [self.dashboard_view.id],
        )
        self.assertCountEqual(
            seeded_settings[SIDEBAR_VIEWS_VISIBLE_IDS_KEY],
            [self.dashboard_view.id, self.sidebar_only_view.id],
        )

        existing_settings = UiSettings.objects.get(
            user_id=self.user_with_existing_settings_id,
        ).settings
        self.assertEqual(
            existing_settings[DASHBOARD_VIEWS_VISIBLE_IDS_KEY],
            [self.sidebar_only_view.id],
        )
        self.assertEqual(
            existing_settings[SIDEBAR_VIEWS_VISIBLE_IDS_KEY],
            [self.dashboard_view.id],
        )
        self.assertEqual(existing_settings["preserve"], "value")

        created_settings = UiSettings.objects.get(
            user_id=self.user_with_owned_views_id,
        ).settings
        self.assertCountEqual(
            created_settings[DASHBOARD_VIEWS_VISIBLE_IDS_KEY],
            [self.other_owner_visible_view.id],
        )
        self.assertCountEqual(
            created_settings[SIDEBAR_VIEWS_VISIBLE_IDS_KEY],
            [self.other_owner_visible_view.id],
        )


class TestReverseMigrateSavedViewVisibilityFromUiSettings(TestMigrations):
    migrate_from = "0012_savedview_visibility_to_ui_settings"
    migrate_to = "0011_optimize_integer_field_sizes"

    def setUpBeforeMigration(self, apps) -> None:
        User = apps.get_model("auth", "User")
        SavedView = apps.get_model("documents", "SavedView")
        UiSettings = apps.get_model("documents", "UiSettings")

        user1 = User.objects.create(username="user1")
        user2 = User.objects.create(username="user2")
        user3 = User.objects.create(username="user3")

        self.view1 = SavedView.objects.create(
            owner=user1,
            name="view-1",
            sort_field="created",
        )
        self.view2 = SavedView.objects.create(
            owner=user1,
            name="view-2",
            sort_field="created",
        )
        self.view3 = SavedView.objects.create(
            owner=user1,
            name="view-3",
            sort_field="created",
        )
        self.view4 = SavedView.objects.create(
            owner=user2,
            name="view-4",
            sort_field="created",
        )

        UiSettings.objects.create(
            user=user1,
            settings={
                DASHBOARD_VIEWS_VISIBLE_IDS_KEY: [self.view1.id],
                SIDEBAR_VIEWS_VISIBLE_IDS_KEY: [self.view2.id],
            },
        )
        UiSettings.objects.create(
            user=user2,
            settings={
                DASHBOARD_VIEWS_VISIBLE_IDS_KEY: [
                    self.view2.id,
                    self.view3.id,
                    self.view4.id,
                ],
                SIDEBAR_VIEWS_VISIBLE_IDS_KEY: [self.view4.id],
            },
        )
        UiSettings.objects.create(user=user3, settings={})

    def test_visibility_fields_restored_from_owner_visibility(self) -> None:
        SavedView = self.apps.get_model("documents", "SavedView")

        restored_view1 = SavedView.objects.get(pk=self.view1.id)
        restored_view2 = SavedView.objects.get(pk=self.view2.id)
        restored_view3 = SavedView.objects.get(pk=self.view3.id)
        restored_view4 = SavedView.objects.get(pk=self.view4.id)

        self.assertTrue(restored_view1.show_on_dashboard)
        self.assertFalse(restored_view2.show_on_dashboard)
        self.assertFalse(restored_view3.show_on_dashboard)
        self.assertTrue(restored_view4.show_on_dashboard)

        self.assertFalse(restored_view1.show_in_sidebar)
        self.assertTrue(restored_view2.show_in_sidebar)
        self.assertFalse(restored_view3.show_in_sidebar)
        self.assertTrue(restored_view4.show_in_sidebar)
