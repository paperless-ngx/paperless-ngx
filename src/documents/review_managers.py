from django_softdelete import managers  # type: ignore[import-untyped]

from documents.review import ReviewAwareQuerySetMixin


class DocumentQuerySet(ReviewAwareQuerySetMixin, managers.SoftDeleteQuerySet):
    pass


class GlobalDocumentQuerySet(ReviewAwareQuerySetMixin, managers.GlobalQuerySet):
    pass


class DeletedDocumentQuerySet(ReviewAwareQuerySetMixin, managers.DeletedQuerySet):
    pass


class DocumentManager(managers.SoftDeleteManager):
    def get_queryset(self) -> DocumentQuerySet:
        return DocumentQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=True,
        )


class GlobalDocumentManager(managers.GlobalManager):
    def get_queryset(self) -> GlobalDocumentQuerySet:
        return GlobalDocumentQuerySet(self.model, using=self._db)


class DeletedDocumentManager(managers.DeletedManager):
    def get_queryset(self) -> DeletedDocumentQuerySet:
        return DeletedDocumentQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=False,
        )
