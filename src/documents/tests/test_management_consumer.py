import filecmp
import os
import shutil
from threading import Thread
from time import sleep
from unittest import mock

from django.conf import settings
from django.core.management import call_command, CommandError
from django.test import override_settings, TransactionTestCase

from documents.models import Tag
from documents.consumer import ConsumerError
from documents.management.commands import document_consumer
from documents.tests.utils import DirectoriesMixin


class ConsumerThread(Thread):

    def __init__(self):
        super().__init__()
        self.cmd = document_consumer.Command()

    def run(self) -> None:
        self.cmd.handle(directory=settings.CONSUMPTION_DIR, oneshot=False)

    def stop(self):
        # Consumer checks this every second.
        self.cmd.stop_flag = True


def chunked(size, source):
    for i in range(0, len(source), size):
        yield source[i:i+size]


class ConsumerMixin:

    sample_file = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")

    def setUp(self) -> None:
        super(ConsumerMixin, self).setUp()
        self.t = None
        patcher = mock.patch("documents.management.commands.document_consumer.async_task")
        self.task_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def t_start(self):
        self.t = ConsumerThread()
        self.t.start()
        # give the consumer some time to do initial work
        sleep(1)

    def tearDown(self) -> None:
        if self.t:
            # set the stop flag
            self.t.stop()
            # wait for the consumer to exit.
            self.t.join()

        super(ConsumerMixin, self).tearDown()

    def wait_for_task_mock_call(self, excpeted_call_count=1):
        n = 0
        while n < 100:
            if self.task_mock.call_count >= excpeted_call_count:
                # give task_mock some time to finish and raise errors
                sleep(1)
                return
            n += 1
            sleep(0.1)

    # A bogus async_task that will simply check the file for
    # completeness and raise an exception otherwise.
    def bogus_task(self, func, filename, **kwargs):
        eq = filecmp.cmp(filename, self.sample_file, shallow=False)
        if not eq:
            print("Consumed an INVALID file.")
            raise ConsumerError("Incomplete File READ FAILED")
        else:
            print("Consumed a perfectly valid file.")

    def slow_write_file(self, target, incomplete=False):
        with open(self.sample_file, 'rb') as f:
            pdf_bytes = f.read()

        if incomplete:
            pdf_bytes = pdf_bytes[:len(pdf_bytes) - 100]

        with open(target, 'wb') as f:
            # this will take 2 seconds, since the file is about 20k.
            print("Start writing file.")
            for b in chunked(1000, pdf_bytes):
                f.write(b)
                sleep(0.1)
            print("file completed.")


class TestConsumer(DirectoriesMixin, ConsumerMixin, TransactionTestCase):

    def test_consume_file(self):
        self.t_start()

        f = os.path.join(self.dirs.consumption_dir, "my_file.pdf")
        shutil.copy(self.sample_file, f)

        self.wait_for_task_mock_call()

        self.task_mock.assert_called_once()

        args, kwargs = self.task_mock.call_args
        self.assertEqual(args[1], f)

    def test_consume_file_invalid_ext(self):
        self.t_start()

        f = os.path.join(self.dirs.consumption_dir, "my_file.wow")
        shutil.copy(self.sample_file, f)

        self.wait_for_task_mock_call()

        self.task_mock.assert_not_called()

    def test_consume_existing_file(self):
        f = os.path.join(self.dirs.consumption_dir, "my_file.pdf")
        shutil.copy(self.sample_file, f)

        self.t_start()
        self.task_mock.assert_called_once()

        args, kwargs = self.task_mock.call_args
        self.assertEqual(args[1], f)

    @mock.patch("documents.management.commands.document_consumer.logger.error")
    def test_slow_write_pdf(self, error_logger):

        self.task_mock.side_effect = self.bogus_task

        self.t_start()

        fname = os.path.join(self.dirs.consumption_dir, "my_file.pdf")

        self.slow_write_file(fname)

        self.wait_for_task_mock_call()

        error_logger.assert_not_called()

        self.task_mock.assert_called_once()

        args, kwargs = self.task_mock.call_args
        self.assertEqual(args[1], fname)

    @mock.patch("documents.management.commands.document_consumer.logger.error")
    def test_slow_write_and_move(self, error_logger):

        self.task_mock.side_effect = self.bogus_task

        self.t_start()

        fname = os.path.join(self.dirs.consumption_dir, "my_file.~df")
        fname2 = os.path.join(self.dirs.consumption_dir, "my_file.pdf")

        self.slow_write_file(fname)
        shutil.move(fname, fname2)

        self.wait_for_task_mock_call()

        self.task_mock.assert_called_once()

        args, kwargs = self.task_mock.call_args
        self.assertEqual(args[1], fname2)

        error_logger.assert_not_called()

    @mock.patch("documents.management.commands.document_consumer.logger.error")
    def test_slow_write_incomplete(self, error_logger):

        self.task_mock.side_effect = self.bogus_task

        self.t_start()

        fname = os.path.join(self.dirs.consumption_dir, "my_file.pdf")
        self.slow_write_file(fname, incomplete=True)

        self.wait_for_task_mock_call()

        self.task_mock.assert_called_once()
        args, kwargs = self.task_mock.call_args
        self.assertEqual(args[1], fname)

        # assert that we have an error logged with this invalid file.
        error_logger.assert_called_once()

    @override_settings(CONSUMPTION_DIR="does_not_exist")
    def test_consumption_directory_invalid(self):

        self.assertRaises(CommandError, call_command, 'document_consumer', '--oneshot')

    @override_settings(CONSUMPTION_DIR="")
    def test_consumption_directory_unset(self):

        self.assertRaises(CommandError, call_command, 'document_consumer', '--oneshot')

    def test_mac_write(self):
        self.task_mock.side_effect = self.bogus_task

        self.t_start()

        shutil.copy(self.sample_file, os.path.join(self.dirs.consumption_dir, ".DS_STORE"))
        shutil.copy(self.sample_file, os.path.join(self.dirs.consumption_dir, "my_file.pdf"))
        shutil.copy(self.sample_file, os.path.join(self.dirs.consumption_dir, "._my_file.pdf"))
        shutil.copy(self.sample_file, os.path.join(self.dirs.consumption_dir, "my_second_file.pdf"))
        shutil.copy(self.sample_file, os.path.join(self.dirs.consumption_dir, "._my_second_file.pdf"))

        sleep(5)

        self.wait_for_task_mock_call(excpeted_call_count=2)

        self.assertEqual(2, self.task_mock.call_count)

        fnames = [os.path.basename(args[1]) for args, _ in self.task_mock.call_args_list]
        self.assertCountEqual(fnames, ["my_file.pdf", "my_second_file.pdf"])

    def test_is_ignored(self):
        test_paths = [
            (os.path.join(self.dirs.consumption_dir, "foo.pdf"), False),
            (os.path.join(self.dirs.consumption_dir, "foo","bar.pdf"), False),
            (os.path.join(self.dirs.consumption_dir, ".DS_STORE", "foo.pdf"), True),
            (os.path.join(self.dirs.consumption_dir, "foo", ".DS_STORE", "bar.pdf"), True),
            (os.path.join(self.dirs.consumption_dir, ".stfolder", "foo.pdf"), True),
            (os.path.join(self.dirs.consumption_dir, "._foo.pdf"), True),
            (os.path.join(self.dirs.consumption_dir, "._foo", "bar.pdf"), False),
        ]
        for file_path, expected_ignored in test_paths:
            self.assertEqual(
                expected_ignored,
                document_consumer._is_ignored(file_path),
                f'_is_ignored("{file_path}") != {expected_ignored}')


@override_settings(CONSUMER_POLLING=1, CONSUMER_POLLING_DELAY=1, CONSUMER_POLLING_RETRY_COUNT=20)
class TestConsumerPolling(TestConsumer):
    # just do all the tests with polling
    pass


@override_settings(CONSUMER_RECURSIVE=True)
class TestConsumerRecursive(TestConsumer):
    # just do all the tests with recursive
    pass


@override_settings(CONSUMER_RECURSIVE=True, CONSUMER_POLLING=1, CONSUMER_POLLING_DELAY=1, CONSUMER_POLLING_RETRY_COUNT=20)
class TestConsumerRecursivePolling(TestConsumer):
    # just do all the tests with polling and recursive
    pass


class TestConsumerTags(DirectoriesMixin, ConsumerMixin, TransactionTestCase):

    @override_settings(CONSUMER_RECURSIVE=True)
    @override_settings(CONSUMER_SUBDIRS_AS_TAGS=True)
    def test_consume_file_with_path_tags(self):

        tag_names = ("existingTag", "Space Tag")
        # Create a Tag prior to consuming a file using it in path
        tag_ids = [Tag.objects.create(name="existingtag").pk,]

        self.t_start()

        path = os.path.join(self.dirs.consumption_dir, *tag_names)
        os.makedirs(path, exist_ok=True)
        f = os.path.join(path, "my_file.pdf")
        # Wait at least inotify read_delay for recursive watchers
        # to be created for the new directories
        sleep(1)
        shutil.copy(self.sample_file, f)

        self.wait_for_task_mock_call()

        self.task_mock.assert_called_once()

        # Add the pk of the Tag created by _consume()
        tag_ids.append(Tag.objects.get(name=tag_names[1]).pk)

        args, kwargs = self.task_mock.call_args
        self.assertEqual(args[1], f)

        # assertCountEqual has a bad name, but test that the first
        # sequence contains the same elements as second, regardless of
        # their order.
        self.assertCountEqual(kwargs["override_tag_ids"], tag_ids)

    @override_settings(CONSUMER_POLLING=1, CONSUMER_POLLING_DELAY=1, CONSUMER_POLLING_RETRY_COUNT=20)
    def test_consume_file_with_path_tags_polling(self):
        self.test_consume_file_with_path_tags()
