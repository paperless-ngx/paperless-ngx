from __future__ import annotations

import logging
import re

from django.conf import settings
from rest_framework import serializers

from documents.models import CustomField
from documents.models import SavedView
from documents.models import SavedViewFilterRule
from documents.models import UiSettings

from .base import OwnedObjectSerializer

logger = logging.getLogger("paperless.serializers")


class SavedViewFilterRuleSerializer(serializers.ModelSerializer[SavedViewFilterRule]):
    class Meta:
        model = SavedViewFilterRule
        fields = ["rule_type", "value"]


class SavedViewSerializer(OwnedObjectSerializer):
    filter_rules = SavedViewFilterRuleSerializer(many=True)

    class Meta:
        model = SavedView
        fields = [
            "id",
            "name",
            "icon",
            "sort_field",
            "sort_reverse",
            "filter_rules",
            "page_size",
            "display_mode",
            "display_fields",
            "owner",
            "permissions",
            "user_can_change",
            "set_permissions",
        ]

    def _get_api_version(self) -> int:
        request = self.context.get("request")
        return int(
            request.version if request else settings.REST_FRAMEWORK["DEFAULT_VERSION"],
        )

    def _update_legacy_visibility_preferences(
        self,
        saved_view_id: int,
        *,
        show_on_dashboard: bool | None,
        show_in_sidebar: bool | None,
    ) -> UiSettings | None:
        if show_on_dashboard is None and show_in_sidebar is None:
            return None

        request = self.context.get("request")
        user = request.user if request else self.user
        if user is None:
            return None

        ui_settings, _ = UiSettings.objects.get_or_create(
            user=user,
            defaults={"settings": {}},
        )
        current_settings = (
            ui_settings.settings if isinstance(ui_settings.settings, dict) else {}
        )
        current_settings = dict(current_settings)

        saved_views_settings = current_settings.get("saved_views")
        if isinstance(saved_views_settings, dict):
            saved_views_settings = dict(saved_views_settings)
        else:
            saved_views_settings = {}

        dashboard_ids = {
            int(raw_id)
            for raw_id in saved_views_settings.get("dashboard_views_visible_ids", [])
            if str(raw_id).isdigit()
        }
        sidebar_ids = {
            int(raw_id)
            for raw_id in saved_views_settings.get("sidebar_views_visible_ids", [])
            if str(raw_id).isdigit()
        }

        if show_on_dashboard is not None:
            if show_on_dashboard:
                dashboard_ids.add(saved_view_id)
            else:
                dashboard_ids.discard(saved_view_id)
        if show_in_sidebar is not None:
            if show_in_sidebar:
                sidebar_ids.add(saved_view_id)
            else:
                sidebar_ids.discard(saved_view_id)

        saved_views_settings["dashboard_views_visible_ids"] = sorted(dashboard_ids)
        saved_views_settings["sidebar_views_visible_ids"] = sorted(sidebar_ids)
        current_settings["saved_views"] = saved_views_settings
        ui_settings.settings = current_settings
        ui_settings.save(update_fields=["settings"])
        return ui_settings

    def to_representation(self, instance):
        # TODO: remove this and related backwards compatibility code when API v9 is dropped
        ret = super().to_representation(instance)
        request = self.context.get("request")
        api_version = self._get_api_version()

        if api_version < 10:
            dashboard_ids = set()
            sidebar_ids = set()
            user = request.user if request else None
            if user is not None and hasattr(user, "ui_settings"):
                ui_settings = user.ui_settings.settings or None
                saved_views = None
                if isinstance(ui_settings, dict):
                    saved_views = ui_settings.get("saved_views", {})
                if isinstance(saved_views, dict):
                    dashboard_ids = set(
                        saved_views.get("dashboard_views_visible_ids", []),
                    )
                    sidebar_ids = set(
                        saved_views.get("sidebar_views_visible_ids", []),
                    )
            ret["show_on_dashboard"] = instance.id in dashboard_ids
            ret["show_in_sidebar"] = instance.id in sidebar_ids

        return ret

    def to_internal_value(self, data):
        # TODO: remove this and related backwards compatibility code when API v9 is dropped
        api_version = self._get_api_version()
        if api_version >= 10:
            return super().to_internal_value(data)

        normalized_data = data.copy()
        legacy_visibility_fields = {}
        boolean_field = serializers.BooleanField()

        for field_name in ("show_on_dashboard", "show_in_sidebar"):
            if field_name in normalized_data:
                try:
                    legacy_visibility_fields[field_name] = (
                        boolean_field.to_internal_value(
                            normalized_data.get(field_name),
                        )
                    )
                except serializers.ValidationError as exc:
                    raise serializers.ValidationError({field_name: exc.detail})
                del normalized_data[field_name]

        ret = super().to_internal_value(normalized_data)
        ret.update(legacy_visibility_fields)
        return ret

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "display_fields" in attrs and attrs["display_fields"] is not None:
            for field in attrs["display_fields"]:
                if (
                    SavedView.DisplayFields.CUSTOM_FIELD[:-2] in field
                ):  # i.e. check for 'custom_field_' prefix
                    field_id = int(re.search(r"\d+", field)[0])
                    if not CustomField.objects.filter(id=field_id).exists():
                        raise serializers.ValidationError(
                            f"Invalid field: {field}",
                        )
                elif field not in SavedView.DisplayFields.values:
                    raise serializers.ValidationError(
                        f"Invalid field: {field}",
                    )
        return attrs

    def update(self, instance, validated_data):
        request = self.context.get("request")
        show_on_dashboard = validated_data.pop("show_on_dashboard", None)
        show_in_sidebar = validated_data.pop("show_in_sidebar", None)
        if "filter_rules" in validated_data:
            rules_data = validated_data.pop("filter_rules")
        else:
            rules_data = None
        if "user" in validated_data:
            # backwards compatibility
            validated_data["owner"] = validated_data.pop("user")
        if (
            "display_fields" in validated_data
            and isinstance(
                validated_data["display_fields"],
                list,
            )
            and len(validated_data["display_fields"]) == 0
        ):
            validated_data["display_fields"] = None
        instance = super().update(instance, validated_data)
        if rules_data is not None:
            SavedViewFilterRule.objects.filter(saved_view=instance).delete()
            for rule_data in rules_data:
                SavedViewFilterRule.objects.create(saved_view=instance, **rule_data)
        ui_settings = self._update_legacy_visibility_preferences(
            instance.id,
            show_on_dashboard=show_on_dashboard,
            show_in_sidebar=show_in_sidebar,
        )
        if request is not None and ui_settings is not None:
            request.user.ui_settings = ui_settings
        return instance

    def create(self, validated_data):
        request = self.context.get("request")
        show_on_dashboard = validated_data.pop("show_on_dashboard", None)
        show_in_sidebar = validated_data.pop("show_in_sidebar", None)
        rules_data = validated_data.pop("filter_rules")
        if "user" in validated_data:
            # backwards compatibility
            validated_data["owner"] = validated_data.pop("user")
        saved_view = super().create(validated_data)
        for rule_data in rules_data:
            SavedViewFilterRule.objects.create(saved_view=saved_view, **rule_data)
        ui_settings = self._update_legacy_visibility_preferences(
            saved_view.id,
            show_on_dashboard=show_on_dashboard,
            show_in_sidebar=show_in_sidebar,
        )
        if request is not None and ui_settings is not None:
            request.user.ui_settings = ui_settings
        return saved_view
