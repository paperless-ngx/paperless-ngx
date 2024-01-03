from django.dispatch import Signal

document_consumption_started = Signal()
document_consumption_finished = Signal()
document_consumer_declaration = Signal()
document_updated = Signal()
