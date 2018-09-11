from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse

from documents.classifier import DocumentClassifier
from documents.models import Tag, Correspondent, DocumentType


def add_tag_to_selected(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    app_label = opts.app_label

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    if request.POST.get('post'):
        n = queryset.count()
        tag = Tag.objects.get(id=request.POST.get('tag_id'))
        if n:
            for obj in queryset:
                obj.tags.add(tag)
                obj_display = str(obj)
                modeladmin.log_change(request, obj, obj_display)
            modeladmin.message_user(request, "Successfully added tag %(tag)s to %(count)d %(items)s." % {
                "tag": tag.name, "count": n, "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)

        # Return None to display the change list page again.
        return None

    title = "Add tag to multiple documents"

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        queryset=queryset,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
        media=modeladmin.media,
        action="add_tag_to_selected",
        tags=Tag.objects.all()
    )

    request.current_app = modeladmin.admin_site.name

    return TemplateResponse(request,
        "admin/%s/%s/mass_modify_tag.html" % (app_label, opts.model_name)
    , context)


add_tag_to_selected.short_description = "Add tag to selected documents"


def remove_tag_from_selected(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    app_label = opts.app_label

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    if request.POST.get('post'):
        n = queryset.count()
        tag = Tag.objects.get(id=request.POST.get('tag_id'))
        if n:
            for obj in queryset:
                obj.tags.remove(tag)
                obj_display = str(obj)
                modeladmin.log_change(request, obj, obj_display)
            modeladmin.message_user(request, "Successfully removed tag %(tag)s from %(count)d %(items)s." % {
                "tag": tag.name, "count": n, "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)

        # Return None to display the change list page again.
        return None

    title = "Remove tag from multiple documents"

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        queryset=queryset,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
        media=modeladmin.media,
        action="remove_tag_from_selected",
        tags=Tag.objects.all()
    )

    request.current_app = modeladmin.admin_site.name

    return TemplateResponse(request,
        "admin/%s/%s/mass_modify_tag.html" % (app_label, opts.model_name)
    , context)


remove_tag_from_selected.short_description = "Remove tag from selected documents"


def set_correspondent_on_selected(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    app_label = opts.app_label

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    if request.POST.get('post'):
        n = queryset.count()
        correspondent = Correspondent.objects.get(id=request.POST.get('correspondent_id'))
        if n:
            for obj in queryset:
                obj_display = str(obj)
                modeladmin.log_change(request, obj, obj_display)
            queryset.update(correspondent=correspondent)
            modeladmin.message_user(request, "Successfully set correspondent %(correspondent)s on %(count)d %(items)s." % {
                "correspondent": correspondent.name, "count": n, "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)

        # Return None to display the change list page again.
        return None

    title = "Set correspondent on multiple documents"

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        queryset=queryset,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
        media=modeladmin.media,
        correspondents=Correspondent.objects.all()
    )

    request.current_app = modeladmin.admin_site.name

    return TemplateResponse(request,
        "admin/%s/%s/set_correspondent.html" % (app_label, opts.model_name)
    , context)


set_correspondent_on_selected.short_description = "Set correspondent on selected documents"


def remove_correspondent_from_selected(modeladmin, request, queryset):
    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    n = queryset.count()
    if n:
        for obj in queryset:
            obj_display = str(obj)
            modeladmin.log_change(request, obj, obj_display)
        queryset.update(correspondent=None)
        modeladmin.message_user(request, "Successfully removed correspondent from %(count)d %(items)s." % {
            "count": n, "items": model_ngettext(modeladmin.opts, n)
        }, messages.SUCCESS)

    return None


remove_correspondent_from_selected.short_description = "Remove correspondent from selected documents"


def set_document_type_on_selected(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    app_label = opts.app_label

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    if request.POST.get('post'):
        n = queryset.count()
        document_type = DocumentType.objects.get(id=request.POST.get('document_type_id'))
        if n:
            for obj in queryset:
                obj_display = str(obj)
                modeladmin.log_change(request, obj, obj_display)
            queryset.update(document_type=document_type)
            modeladmin.message_user(request, "Successfully set document type %(document_type)s on %(count)d %(items)s." % {
                "document_type": document_type.name, "count": n, "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)

        # Return None to display the change list page again.
        return None

    title = "Set document type on multiple documents"

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        queryset=queryset,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
        media=modeladmin.media,
        document_types=DocumentType.objects.all()
    )

    request.current_app = modeladmin.admin_site.name

    return TemplateResponse(request,
        "admin/%s/%s/set_document_type.html" % (app_label, opts.model_name)
    , context)


set_document_type_on_selected.short_description = "Set document type on selected documents"


def remove_document_type_from_selected(modeladmin, request, queryset):
    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    n = queryset.count()
    if n:
        for obj in queryset:
            obj_display = str(obj)
            modeladmin.log_change(request, obj, obj_display)
        queryset.update(document_type=None)
        modeladmin.message_user(request, "Successfully removed document type from %(count)d %(items)s." % {
            "count": n, "items": model_ngettext(modeladmin.opts, n)
        }, messages.SUCCESS)

    return None


remove_document_type_from_selected.short_description = "Remove document type from selected documents"


def run_document_classifier_on_selected(modeladmin, request, queryset):
    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    try:
        clf = DocumentClassifier.load_classifier()
    except FileNotFoundError:
        modeladmin.message_user(request, "Classifier model file not found.", messages.ERROR)
        return None

    n = queryset.count()
    if n:
        for obj in queryset:
            clf.classify_document(obj, classify_correspondent=True, classify_tags=True, classify_document_type=True, replace_tags=True)
            modeladmin.log_change(request, obj, str(obj))
        modeladmin.message_user(request, "Successfully applied tags, correspondent and document type to %(count)d %(items)s." % {
            "count": n, "items": model_ngettext(modeladmin.opts, n)
        }, messages.SUCCESS)

    return None


run_document_classifier_on_selected.short_description = "Run document classifier on selected"
