import abc
from pathlib import Path
from typing import Final

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.plugins.helpers import ProgressManager


class StopConsumeTaskError(Exception):
    """
    A plugin setup or run may raise this to exit the asynchronous consume task.

    Most likely, this means it has created one or more new tasks to execute instead,
    such as when a barcode has been used to create new documents
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ConsumeTaskPlugin(abc.ABC):
    """
    Defines the interface for a plugin for the document consume task
    Meanings as per RFC2119 (https://datatracker.ietf.org/doc/html/rfc2119)

    Plugin Implementation

    The plugin SHALL implement property able_to_run and methods setup, run and cleanup.
    The plugin property able_to_run SHALL return True if the plugin is able to run, given the conditions, settings and document information.
    The plugin property able_to_run MAY be hardcoded to return True.
    The plugin setup SHOULD perform any resource creation or additional initialization needed to run the document.
    The plugin setup MAY be a non-operation.
    The plugin cleanup SHOULD perform resource cleanup, including in the event of an error.
    The plugin cleanup MAY be a non-operation.
    The plugin run SHALL perform any operations against the document or system state required for the plugin.
    The plugin run MAY update the document metadata.
    The plugin run MAY return an informational message.
    The plugin run MAY raise StopConsumeTaskError to cease any further operations against the document.

    Plugin Manager Implementation

    The plugin manager SHALL provide the plugin with the input document, document metadata, progress manager and a created temporary directory.
    The plugin manager SHALL execute the plugin setup, run and cleanup, in that order IF the plugin property able_to_run is True.
    The plugin manager SHOULD log the return message of executing a plugin's run.
    The plugin manager SHALL always execute the plugin cleanup, IF the plugin property able_to_run is True.
    The plugin manager SHALL cease calling plugins and exit the task IF a plugin raises StopConsumeTaskError.
    The plugin manager SHOULD return the StopConsumeTaskError message IF a plugin raises StopConsumeTaskError.
    """

    NAME: str = "ConsumeTaskPlugin"

    def __init__(
        self,
        input_doc: ConsumableDocument,
        metadata: DocumentMetadataOverrides,
        status_mgr: ProgressManager,
        base_tmp_dir: Path,
        task_id: str,
    ) -> None:
        super().__init__()
        self.input_doc = input_doc
        self.metadata = metadata
        self.base_tmp_dir: Final = base_tmp_dir
        self.status_mgr = status_mgr
        self.task_id: Final = task_id

    @property
    @abc.abstractmethod
    def able_to_run(self) -> bool:
        """
        Return True if the conditions are met for the plugin to run, False otherwise

        If False, setup(), run() and cleanup() will not be called
        """

    @abc.abstractmethod
    def setup(self) -> None:
        """
        Allows the plugin to perform any additional setup it may need, such as creating
        a temporary directory, copying a file somewhere, etc.

        Executed before run()

        In general, this should be the "light" work, not the bulk of processing
        """

    @abc.abstractmethod
    def run(self) -> str | None:
        """
        The bulk of plugin processing, this does whatever action the plugin is for.

        Executed after setup() and before cleanup()
        """

    @abc.abstractmethod
    def cleanup(self) -> None:
        """
        Allows the plugin to execute any cleanup it may require

        Executed after run(), even in the case of error
        """


class AlwaysRunPluginMixin(ConsumeTaskPlugin):
    """
    A plugin which is always able to run
    """

    @property
    def able_to_run(self) -> bool:
        return True


class NoSetupPluginMixin(ConsumeTaskPlugin):
    """
    A plugin which requires no setup
    """

    def setup(self) -> None:
        pass


class NoCleanupPluginMixin(ConsumeTaskPlugin):
    """
    A plugin which needs to clean up no files
    """

    def cleanup(self) -> None:
        pass
