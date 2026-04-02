import pytest

from documents.tests.utils import TestMigrations

pytestmark = pytest.mark.search


class TestMigrateFulltextQueryFieldPrefixes(TestMigrations):
    migrate_from = "0016_sha256_checksums"
    migrate_to = "0017_migrate_fulltext_query_field_prefixes"

    def setUpBeforeMigration(self, apps) -> None:
        User = apps.get_model("auth", "User")
        SavedView = apps.get_model("documents", "SavedView")
        SavedViewFilterRule = apps.get_model("documents", "SavedViewFilterRule")

        user = User.objects.create(username="testuser")

        def make_rule(value: str):
            view = SavedView.objects.create(
                owner=user,
                name=f"view-{value}",
                sort_field="created",
            )
            return SavedViewFilterRule.objects.create(
                saved_view=view,
                rule_type=20,  # fulltext query
                value=value,
            )

        # Simple field prefixes
        self.rule_note = make_rule("note:invoice")
        self.rule_cf = make_rule("custom_field:amount")

        # Combined query
        self.rule_combined = make_rule("note:invoice AND custom_field:total")

        # Parenthesized groups (Whoosh syntax)
        self.rule_parens = make_rule("(note:invoice OR note:receipt)")

        # Prefix operators
        self.rule_plus = make_rule("+note:foo")
        self.rule_minus = make_rule("-note:bar")

        # Boosted
        self.rule_boost = make_rule("note:test^2")

        # Should NOT be rewritten — no field prefix match
        self.rule_no_match = make_rule("title:hello content:world")

        # Should NOT false-positive on word boundaries
        self.rule_denote = make_rule("denote:foo")

        # Already using new syntax — should be idempotent
        self.rule_already_migrated = make_rule("notes.note:foo")
        self.rule_already_migrated_cf = make_rule("custom_fields.value:bar")

        # Null value — should not crash
        view_null = SavedView.objects.create(
            owner=user,
            name="view-null",
            sort_field="created",
        )
        self.rule_null = SavedViewFilterRule.objects.create(
            saved_view=view_null,
            rule_type=20,
            value=None,
        )

        # Non-fulltext rule type — should be untouched
        view_other = SavedView.objects.create(
            owner=user,
            name="view-other-type",
            sort_field="created",
        )
        self.rule_other_type = SavedViewFilterRule.objects.create(
            saved_view=view_other,
            rule_type=0,  # title contains
            value="note:something",
        )

    def test_note_prefix_rewritten(self):
        self.rule_note.refresh_from_db()
        self.assertEqual(self.rule_note.value, "notes.note:invoice")

    def test_custom_field_prefix_rewritten(self):
        self.rule_cf.refresh_from_db()
        self.assertEqual(self.rule_cf.value, "custom_fields.value:amount")

    def test_combined_query_rewritten(self):
        self.rule_combined.refresh_from_db()
        self.assertEqual(
            self.rule_combined.value,
            "notes.note:invoice AND custom_fields.value:total",
        )

    def test_parenthesized_groups(self):
        self.rule_parens.refresh_from_db()
        self.assertEqual(
            self.rule_parens.value,
            "(notes.note:invoice OR notes.note:receipt)",
        )

    def test_plus_prefix(self):
        self.rule_plus.refresh_from_db()
        self.assertEqual(self.rule_plus.value, "+notes.note:foo")

    def test_minus_prefix(self):
        self.rule_minus.refresh_from_db()
        self.assertEqual(self.rule_minus.value, "-notes.note:bar")

    def test_boosted(self):
        self.rule_boost.refresh_from_db()
        self.assertEqual(self.rule_boost.value, "notes.note:test^2")

    def test_no_match_unchanged(self):
        self.rule_no_match.refresh_from_db()
        self.assertEqual(self.rule_no_match.value, "title:hello content:world")

    def test_word_boundary_no_false_positive(self):
        self.rule_denote.refresh_from_db()
        self.assertEqual(self.rule_denote.value, "denote:foo")

    def test_already_migrated_idempotent(self):
        self.rule_already_migrated.refresh_from_db()
        self.assertEqual(self.rule_already_migrated.value, "notes.note:foo")

    def test_already_migrated_cf_idempotent(self):
        self.rule_already_migrated_cf.refresh_from_db()
        self.assertEqual(self.rule_already_migrated_cf.value, "custom_fields.value:bar")

    def test_null_value_no_crash(self):
        self.rule_null.refresh_from_db()
        self.assertIsNone(self.rule_null.value)

    def test_non_fulltext_rule_untouched(self):
        self.rule_other_type.refresh_from_db()
        self.assertEqual(self.rule_other_type.value, "note:something")
