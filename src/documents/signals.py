from django.dispatch import Signal

document_consumption_started = Signal(providing_args=["filename"])
document_consumption_finished = Signal(providing_args=["document"])
