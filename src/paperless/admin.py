from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User


class PaperlessUserForm(forms.ModelForm):
    """
    Custom form for the User model that adds validation to prevent non-superusers
    from changing the superuser status of a user.
    """

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "is_staff",
            "is_active",
            "is_superuser",
            "groups",
            "user_permissions",
        ]

    def clean(self):
        cleaned_data = super().clean()
        user_being_edited = self.instance
        is_superuser = cleaned_data.get("is_superuser")

        if (
            not self.request.user.is_superuser
            and is_superuser != user_being_edited.is_superuser
        ):
            raise forms.ValidationError(
                "Superuser status can only be changed by a superuser",
            )

        return cleaned_data


class PaperlessUserAdmin(UserAdmin):
    form = PaperlessUserForm

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.request = request
        return form


admin.site.unregister(User)
admin.site.register(User, PaperlessUserAdmin)
