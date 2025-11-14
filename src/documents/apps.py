from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocumentsConfig(AppConfig):
    name = "documents"

    verbose_name = _("Documents")

    def ready(self):
        from documents.signals import document_consumption_finished
        from documents.signals import document_updated
        from documents.signals.handlers import add_inbox_tags
        from documents.signals.handlers import add_to_index
        from documents.signals.handlers import run_workflows_added
        from documents.signals.handlers import run_workflows_updated
        from documents.signals.handlers import set_correspondent
        from documents.signals.handlers import set_document_type
        from documents.signals.handlers import set_storage_path
        from documents.signals.handlers import set_tags

        document_consumption_finished.connect(add_inbox_tags)
        document_consumption_finished.connect(set_correspondent)
        document_consumption_finished.connect(set_document_type)
        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_storage_path)
        document_consumption_finished.connect(add_to_index)
        document_consumption_finished.connect(run_workflows_added)
        document_updated.connect(run_workflows_updated)

        import documents.schema  # noqa: F401

        # Initialize ML model cache with warm-up if configured
        self._initialize_ml_cache()

        AppConfig.ready(self)

    def _initialize_ml_cache(self):
        """Initialize ML model cache and optionally warm up models."""
        from django.conf import settings
        
        # Only initialize if ML features are enabled
        if not getattr(settings, "PAPERLESS_ENABLE_ML_FEATURES", False):
            return
        
        # Initialize cache manager with settings
        from documents.ml.model_cache import ModelCacheManager
        
        max_models = getattr(settings, "PAPERLESS_ML_CACHE_MAX_MODELS", 3)
        cache_dir = getattr(settings, "PAPERLESS_ML_MODEL_CACHE", None)
        
        cache_manager = ModelCacheManager.get_instance(
            max_models=max_models,
            disk_cache_dir=str(cache_dir) if cache_dir else None,
        )
        
        # Warm up models if configured
        warmup_enabled = getattr(settings, "PAPERLESS_ML_CACHE_WARMUP", False)
        if warmup_enabled:
            try:
                from documents.ai_scanner import get_ai_scanner
                scanner = get_ai_scanner()
                scanner.warm_up_models()
            except Exception as e:
                import logging
                logger = logging.getLogger("paperless.documents")
                logger.warning(f"Failed to warm up ML models: {e}")
