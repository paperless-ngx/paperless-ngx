from django.core.checks import Warning, register


@register()
def changed_password_check(app_configs, **kwargs):

    from documents.models import Document
    from paperless.db import GnuPG

    warning = (
        "At least one document:\n\n  {}\n\nin your data store was encrypted "
        "with a password other than the one currently\nin use.  This means "
        "that this file, and others encrypted with the other\npassword are no "
        "longer acessible, which is probably not what you want.  If\nyou "
        "intend to change your Paperless password, you must first export all "
        "of\nthe old documents, start fresh with the new password and then "
        "re-import them."
    )

    document = Document.objects.order_by("-pk").filter(
        storage_type=Document.STORAGE_TYPE_GPG
    ).first()

    if document and not GnuPG.decrypted(document.source_file):
        return [Warning(warning.format(document))]
    return []
