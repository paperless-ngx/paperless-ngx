from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse

from documents.models import Correspondent, Tag


def select_action(
        modeladmin, request, queryset, title, action, modelclass,
        success_message="", document_action=None, queryset_action=None):

    opts = modeladmin.model._meta
    app_label = opts.app_label

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    if request.POST.get('post'):
        n = queryset.count()
        selected_object = modelclass.objects.get(id=request.POST.get('obj_id'))
        if n:
            for document in queryset:
                if document_action:
                    document_action(document, selected_object)
                document_display = str(document)
                modeladmin.log_change(request, document, document_display)
            if queryset_action:
                queryset_action(queryset, selected_object)

            modeladmin.message_user(request, success_message % {
                "selected_object": selected_object.name,
                "count": n,
                "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)

        # Return None to display the change list page again.
        return None

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        queryset=queryset,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
        media=modeladmin.media,
        action=action,
        objects=modelclass.objects.all(),
        itemname=model_ngettext(modelclass, 1)
    )

    request.current_app = modeladmin.admin_site.name

    return TemplateResponse(
        request,
        "admin/{}/{}/select_object.html".format(app_label, opts.model_name),
        context
    )


def simple_action(
        modeladmin, request, queryset, success_message="",
        document_action=None, queryset_action=None):

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    n = queryset.count()
    if n:
        for document in queryset:
            if document_action:
                document_action(document)
            document_display = str(document)
            modeladmin.log_change(request, document, document_display)
        if queryset_action:
            queryset_action(queryset)
        modeladmin.message_user(request, success_message % {
            "count": n, "items": model_ngettext(modeladmin.opts, n)
        }, messages.SUCCESS)

    # Return None to display the change list page again.
    return None


def add_tag_to_selected(modeladmin, request, queryset):
    return select_action(
        modeladmin=modeladmin,
        request=request,
        queryset=queryset,
        title="Add tag to multiple documents",
        action="add_tag_to_selected",
        modelclass=Tag,
        success_message="Successfully added tag %(selected_object)s to "
                        "%(count)d %(items)s.",
        document_action=lambda doc, tag: doc.tags.add(tag)
    )


def remove_tag_from_selected(modeladmin, request, queryset):
    return select_action(
        modeladmin=modeladmin,
        request=request,
        queryset=queryset,
        title="Remove tag from multiple documents",
        action="remove_tag_from_selected",
        modelclass=Tag,
        success_message="Successfully removed tag %(selected_object)s from "
                        "%(count)d %(items)s.",
        document_action=lambda doc, tag: doc.tags.remove(tag)
    )


def set_correspondent_on_selected(modeladmin, request, queryset):

    return select_action(
        modeladmin=modeladmin,
        request=request,
        queryset=queryset,
        title="Set correspondent on multiple documents",
        action="set_correspondent_on_selected",
        modelclass=Correspondent,
        success_message="Successfully set correspondent %(selected_object)s "
                        "on %(count)d %(items)s.",
        queryset_action=lambda qs, corr: qs.update(correspondent=corr)
    )


def remove_correspondent_from_selected(modeladmin, request, queryset):
    return simple_action(
        modeladmin=modeladmin,
        request=request,
        queryset=queryset,
        success_message="Successfully removed correspondent from %(count)d "
                        "%(items)s.",
        queryset_action=lambda qs: qs.update(correspondent=None)
    )


add_tag_to_selected.short_description = "Add tag to selected documents"
remove_tag_from_selected.short_description = \
    "Remove tag from selected documents"
set_correspondent_on_selected.short_description = \
    "Set correspondent on selected documents"
remove_correspondent_from_selected.short_description = \
    "Remove correspondent from selected documents"
