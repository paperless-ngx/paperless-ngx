from django.dispatch import Signal

document_consumption_started = Signal()
document_consumption_finished = Signal()
document_updated = Signal()
document_version_added = Signal()
