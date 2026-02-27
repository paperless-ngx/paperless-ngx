"""Tests for PaperlessCommand base class."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from django.core.management import CommandError
from django.db.models import QuerySet
from rich.console import Console

from documents.management.commands.base import PaperlessCommand
from documents.management.commands.base import ProcessResult

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


# --- Test Commands ---
# These simulate real command implementations for testing


class SimpleCommand(PaperlessCommand):
    """Command with default settings (progress bar, no multiprocessing)."""

    help = "Simple test command"

    def handle(self, *args, **options):
        items = list(range(5))
        results = []
        for item in self.track(items, description="Processing..."):
            results.append(item * 2)
        self.stdout.write(f"Results: {results}")


class NoProgressBarCommand(PaperlessCommand):
    """Command with progress bar disabled."""

    help = "No progress bar command"
    supports_progress_bar = False

    def handle(self, *args, **options):
        items = list(range(3))
        for _ in self.track(items):
            # We don't need to actually work
            pass
        self.stdout.write("Done")


class MultiprocessCommand(PaperlessCommand):
    """Command with multiprocessing support."""

    help = "Multiprocess test command"
    supports_multiprocessing = True

    def handle(self, *args, **options):
        items = list(range(5))
        results = []
        for result in self.process_parallel(
            _double_value,
            items,
            description="Processing...",
        ):
            results.append(result)
        successes = sum(1 for r in results if r.success)
        self.stdout.write(f"Successes: {successes}")


# --- Helper Functions for Multiprocessing ---
# Must be at module level to be picklable


def _double_value(x: int) -> int:
    """Double the input value."""
    return x * 2


def _divide_ten_by(x: int) -> float:
    """Divide 10 by x. Raises ZeroDivisionError if x is 0."""
    return 10 / x


# --- Fixtures ---


@pytest.fixture
def console() -> Console:
    """Create a non-interactive console for testing."""
    return Console(force_terminal=False, force_interactive=False)


@pytest.fixture
def simple_command(console: Console) -> SimpleCommand:
    """Create a SimpleCommand instance configured for testing."""
    command = SimpleCommand()
    command.stdout = io.StringIO()
    command.stderr = io.StringIO()
    command.console = console
    command.no_progress_bar = True
    command.process_count = 1
    return command


@pytest.fixture
def multiprocess_command(console: Console) -> MultiprocessCommand:
    """Create a MultiprocessCommand instance configured for testing."""
    command = MultiprocessCommand()
    command.stdout = io.StringIO()
    command.stderr = io.StringIO()
    command.console = console
    command.no_progress_bar = True
    command.process_count = 1
    return command


@pytest.fixture
def mock_queryset():
    """
    Create a mock Django QuerySet that tracks method calls.

    This verifies we use .count() instead of len() for querysets.
    """

    class MockQuerySet(QuerySet):
        def __init__(self, items: list):
            self._items = items
            self.count_called = False

        def count(self) -> int:
            self.count_called = True
            return len(self._items)

        def __iter__(self):
            return iter(self._items)

        def __len__(self):
            raise AssertionError("len() should not be called on querysets")

    return MockQuerySet


# --- Test Classes ---


@pytest.mark.management
class TestProcessResult:
    """Tests for the ProcessResult dataclass."""

    def test_success_result(self):
        result = ProcessResult(item=1, result=2, error=None)

        assert result.item == 1
        assert result.result == 2
        assert result.error is None
        assert result.success is True

    def test_error_result(self):
        error = ValueError("test error")
        result = ProcessResult(item=1, result=None, error=error)

        assert result.item == 1
        assert result.result is None
        assert result.error is error
        assert result.success is False


@pytest.mark.management
class TestPaperlessCommandArguments:
    """Tests for argument parsing behavior."""

    def test_progress_bar_argument_added_by_default(self):
        command = SimpleCommand()
        parser = command.create_parser("manage.py", "simple")

        options = parser.parse_args(["--no-progress-bar"])
        assert options.no_progress_bar is True

        options = parser.parse_args([])
        assert options.no_progress_bar is False

    def test_progress_bar_argument_not_added_when_disabled(self):
        command = NoProgressBarCommand()
        parser = command.create_parser("manage.py", "noprogress")

        options = parser.parse_args([])
        assert not hasattr(options, "no_progress_bar")

    def test_processes_argument_added_when_multiprocessing_enabled(self):
        command = MultiprocessCommand()
        parser = command.create_parser("manage.py", "multiprocess")

        options = parser.parse_args(["--processes", "4"])
        assert options.processes == 4

        options = parser.parse_args([])
        assert options.processes >= 1

    def test_processes_argument_not_added_when_multiprocessing_disabled(self):
        command = SimpleCommand()
        parser = command.create_parser("manage.py", "simple")

        options = parser.parse_args([])
        assert not hasattr(options, "processes")


@pytest.mark.management
class TestPaperlessCommandExecute:
    """Tests for the execute() setup behavior."""

    @pytest.fixture
    def base_options(self) -> dict:
        """Base options required for execute()."""
        return {
            "verbosity": 1,
            "no_color": True,
            "force_color": False,
            "skip_checks": True,
        }

    @pytest.mark.parametrize(
        ("no_progress_bar_flag", "expected"),
        [
            pytest.param(False, False, id="progress-bar-enabled"),
            pytest.param(True, True, id="progress-bar-disabled"),
        ],
    )
    def test_no_progress_bar_state_set(
        self,
        base_options: dict,
        *,
        no_progress_bar_flag: bool,
        expected: bool,
    ):
        command = SimpleCommand()
        command.stdout = io.StringIO()
        command.stderr = io.StringIO()

        options = {**base_options, "no_progress_bar": no_progress_bar_flag}
        command.execute(**options)

        assert command.no_progress_bar is expected

    def test_no_progress_bar_always_true_when_not_supported(self, base_options: dict):
        command = NoProgressBarCommand()
        command.stdout = io.StringIO()
        command.stderr = io.StringIO()

        command.execute(**base_options)

        assert command.no_progress_bar is True

    @pytest.mark.parametrize(
        ("processes", "expected"),
        [
            pytest.param(1, 1, id="single-process"),
            pytest.param(4, 4, id="four-processes"),
        ],
    )
    def test_process_count_set(
        self,
        base_options: dict,
        processes: int,
        expected: int,
    ):
        command = MultiprocessCommand()
        command.stdout = io.StringIO()
        command.stderr = io.StringIO()

        options = {**base_options, "processes": processes, "no_progress_bar": True}
        command.execute(**options)

        assert command.process_count == expected

    @pytest.mark.parametrize(
        "invalid_count",
        [
            pytest.param(0, id="zero"),
            pytest.param(-1, id="negative"),
        ],
    )
    def test_process_count_validation_rejects_invalid(
        self,
        base_options: dict,
        invalid_count: int,
    ):
        command = MultiprocessCommand()
        command.stdout = io.StringIO()
        command.stderr = io.StringIO()

        options = {**base_options, "processes": invalid_count, "no_progress_bar": True}

        with pytest.raises(CommandError, match="--processes must be at least 1"):
            command.execute(**options)

    def test_process_count_defaults_to_one_when_not_supported(self, base_options: dict):
        command = SimpleCommand()
        command.stdout = io.StringIO()
        command.stderr = io.StringIO()

        options = {**base_options, "no_progress_bar": True}
        command.execute(**options)

        assert command.process_count == 1


@pytest.mark.management
class TestGetIterableLength:
    """Tests for the _get_iterable_length() method."""

    def test_uses_count_for_querysets(
        self,
        simple_command: SimpleCommand,
        mock_queryset,
    ):
        """Should call .count() on Django querysets rather than len()."""
        queryset = mock_queryset([1, 2, 3, 4, 5])

        result = simple_command._get_iterable_length(queryset)

        assert result == 5
        assert queryset.count_called is True

    def test_uses_len_for_sized(self, simple_command: SimpleCommand):
        """Should use len() for sequences and other Sized types."""
        result = simple_command._get_iterable_length([1, 2, 3, 4])

        assert result == 4

    def test_returns_none_for_unsized_iterables(self, simple_command: SimpleCommand):
        """Should return None for generators and other iterables without len()."""
        result = simple_command._get_iterable_length(x for x in [1, 2, 3])

        assert result is None


@pytest.mark.management
class TestTrack:
    """Tests for the track() method."""

    def test_with_progress_bar_disabled(self, simple_command: SimpleCommand):
        simple_command.no_progress_bar = True
        items = ["a", "b", "c"]

        result = list(simple_command.track(items, description="Test..."))

        assert result == items

    def test_with_progress_bar_enabled(self, simple_command: SimpleCommand):
        simple_command.no_progress_bar = False
        items = [1, 2, 3]

        result = list(simple_command.track(items, description="Processing..."))

        assert result == items

    def test_with_explicit_total(self, simple_command: SimpleCommand):
        simple_command.no_progress_bar = False

        def gen():
            yield from [1, 2, 3]

        result = list(simple_command.track(gen(), total=3))

        assert result == [1, 2, 3]

    def test_with_generator_no_total(self, simple_command: SimpleCommand):
        def gen():
            yield from [1, 2, 3]

        result = list(simple_command.track(gen()))

        assert result == [1, 2, 3]

    def test_empty_iterable(self, simple_command: SimpleCommand):
        result = list(simple_command.track([]))

        assert result == []

    def test_uses_queryset_count(
        self,
        simple_command: SimpleCommand,
        mock_queryset,
        mocker: MockerFixture,
    ):
        """Verify track() uses .count() for querysets."""
        simple_command.no_progress_bar = False
        queryset = mock_queryset([1, 2, 3])

        spy = mocker.spy(simple_command, "_get_iterable_length")

        result = list(simple_command.track(queryset))

        assert result == [1, 2, 3]
        spy.assert_called_once_with(queryset)
        assert queryset.count_called is True


@pytest.mark.management
class TestProcessParallel:
    """Tests for the process_parallel() method."""

    def test_sequential_processing_single_process(
        self,
        multiprocess_command: MultiprocessCommand,
    ):
        multiprocess_command.process_count = 1
        items = [1, 2, 3, 4, 5]

        results = list(multiprocess_command.process_parallel(_double_value, items))

        assert len(results) == 5
        assert all(r.success for r in results)

        result_map = {r.item: r.result for r in results}
        assert result_map == {1: 2, 2: 4, 3: 6, 4: 8, 5: 10}

    def test_sequential_processing_handles_errors(
        self,
        multiprocess_command: MultiprocessCommand,
    ):
        multiprocess_command.process_count = 1
        items = [1, 2, 0, 4]  # 0 causes ZeroDivisionError

        results = list(multiprocess_command.process_parallel(_divide_ten_by, items))

        assert len(results) == 4

        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]

        assert len(successes) == 3
        assert len(failures) == 1
        assert failures[0].item == 0
        assert isinstance(failures[0].error, ZeroDivisionError)

    def test_parallel_closes_db_connections(
        self,
        multiprocess_command: MultiprocessCommand,
        mocker: MockerFixture,
    ):
        multiprocess_command.process_count = 2
        items = [1, 2, 3]

        mock_connections = mocker.patch(
            "documents.management.commands.base.db.connections",
        )

        results = list(multiprocess_command.process_parallel(_double_value, items))

        mock_connections.close_all.assert_called_once()
        assert len(results) == 3

    def test_parallel_processing_handles_errors(
        self,
        multiprocess_command: MultiprocessCommand,
        mocker: MockerFixture,
    ):
        multiprocess_command.process_count = 2
        items = [1, 2, 0, 4]

        mocker.patch("documents.management.commands.base.db.connections")

        results = list(multiprocess_command.process_parallel(_divide_ten_by, items))

        failures = [r for r in results if not r.success]
        assert len(failures) == 1
        assert failures[0].item == 0

    def test_empty_items(self, multiprocess_command: MultiprocessCommand):
        results = list(multiprocess_command.process_parallel(_double_value, []))

        assert results == []

    def test_result_contains_original_item(
        self,
        multiprocess_command: MultiprocessCommand,
    ):
        items = [10, 20, 30]

        results = list(multiprocess_command.process_parallel(_double_value, items))

        for result in results:
            assert result.item in items
            assert result.result == result.item * 2

    def test_sequential_path_used_for_single_process(
        self,
        multiprocess_command: MultiprocessCommand,
        mocker: MockerFixture,
    ):
        """Verify single process uses sequential path (important for testing)."""
        multiprocess_command.process_count = 1

        spy_sequential = mocker.spy(multiprocess_command, "_process_sequential")
        spy_parallel = mocker.spy(multiprocess_command, "_process_parallel")

        list(multiprocess_command.process_parallel(_double_value, [1, 2, 3]))

        spy_sequential.assert_called_once()
        spy_parallel.assert_not_called()

    def test_parallel_path_used_for_multiple_processes(
        self,
        multiprocess_command: MultiprocessCommand,
        mocker: MockerFixture,
    ):
        """Verify multiple processes uses parallel path."""
        multiprocess_command.process_count = 2

        mocker.patch("documents.management.commands.base.db.connections")
        spy_sequential = mocker.spy(multiprocess_command, "_process_sequential")
        spy_parallel = mocker.spy(multiprocess_command, "_process_parallel")

        list(multiprocess_command.process_parallel(_double_value, [1, 2, 3]))

        spy_parallel.assert_called_once()
        spy_sequential.assert_not_called()
