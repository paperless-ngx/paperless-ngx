from collections.abc import Generator
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from documents.consumer import AsnCheckPlugin
from documents.consumer import ConsumerPlugin
from documents.consumer import ConsumerPreflightPlugin
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from paperless_testing.fakes.progress import FakeProgressManager


class ConsumeTaskMixin:
    """
    Provides mocking of the consume_file asynchronous task and useful utilities
    for decoding its arguments
    """

    def setUp(self) -> None:
        self.consume_file_patcher = mock.patch(
            "documents.tasks.consume_file.apply_async",
        )
        self.consume_file_mock = self.consume_file_patcher.start()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.consume_file_patcher.stop()

    def assert_queue_consumption_task_call_args(
        self,
    ) -> tuple[ConsumableDocument, DocumentMetadataOverrides]:
        """Assert the task was queued exactly once and return its call args."""
        self.consume_file_mock.assert_called_once()
        task_kwargs = self.consume_file_mock.call_args.kwargs["kwargs"]
        return (task_kwargs["input_doc"], task_kwargs["overrides"])

    def get_all_consume_task_call_args(
        self,
    ) -> Iterator[tuple[ConsumableDocument, DocumentMetadataOverrides]]:
        """Iterate over all queued consume task calls and yield their call args."""
        self.consume_file_mock.assert_called()
        for call in self.consume_file_mock.call_args_list:
            task_kwargs = call.kwargs["kwargs"]
            yield (task_kwargs["input_doc"], task_kwargs["overrides"])


class SampleDirMixin:
    SAMPLE_DIR = Path(__file__).parent / "samples"

    BARCODE_SAMPLE_DIR = SAMPLE_DIR / "barcodes"


class GetConsumerMixin:
    @contextmanager
    def get_consumer(
        self,
        filepath: Path,
        overrides: DocumentMetadataOverrides | None = None,
        source: DocumentSource = DocumentSource.ConsumeFolder,
        mailrule_id: int | None = None,
    ) -> Generator[ConsumerPlugin, None, None]:
        # Store this for verification
        self.status = FakeProgressManager(filepath.name, None)
        doc = ConsumableDocument(
            source,
            original_file=filepath,
            mailrule_id=mailrule_id or None,
        )
        preflight_plugin = ConsumerPreflightPlugin(
            doc,
            overrides or DocumentMetadataOverrides(),
            self.status,  # type: ignore
            self.dirs.scratch_dir,
            "task-id",
        )
        preflight_plugin.setup()
        asncheck_plugin = AsnCheckPlugin(
            doc,
            overrides or DocumentMetadataOverrides(),
            self.status,  # type: ignore
            self.dirs.scratch_dir,
            "task-id",
        )
        asncheck_plugin.setup()
        reader = ConsumerPlugin(
            doc,
            overrides or DocumentMetadataOverrides(),
            self.status,  # type: ignore
            self.dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        try:
            preflight_plugin.run()
            asncheck_plugin.run()
            yield reader
        finally:
            reader.cleanup()
