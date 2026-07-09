from __future__ import annotations

import tempfile
from pathlib import Path

from django.test import TestCase
from django.test import override_settings

from documents.tests.utils import DirectoriesMixin
from paperless.storage import PaperlessStorage
from paperless.storage import get_storage
from paperless.storage import reset_storage


class TestPaperlessStorageSingleton(TestCase):
    def setUp(self) -> None:
        reset_storage()

    def tearDown(self) -> None:
        reset_storage()

    def test_get_storage_returns_instance(self) -> None:
        storage = get_storage()
        self.assertIsInstance(storage, PaperlessStorage)

    def test_get_storage_returns_same_instance(self) -> None:
        storage1 = get_storage()
        storage2 = get_storage()
        self.assertIs(storage1, storage2)

    def test_reset_storage_clears_singleton(self) -> None:
        storage1 = get_storage()
        reset_storage()
        storage2 = get_storage()
        self.assertIsNot(storage1, storage2)

    @override_settings(PAPERLESS_STORAGE_BACKEND="file")
    def test_custom_backend_setting(self) -> None:
        reset_storage()
        storage = get_storage()
        self.assertEqual(storage._protocol, "file")
        reset_storage()


class TestPaperlessStorageLocalFS(DirectoriesMixin, TestCase):
    """Tests for PaperlessStorage using the local filesystem backend."""

    def setUp(self) -> None:
        super().setUp()
        self.storage = get_storage()
        self.tmp_dir = Path(tempfile.mkdtemp(dir=self.dirs.scratch_dir))

    def test_write_from_path(self) -> None:
        src = self.tmp_dir / "source.txt"
        src.write_bytes(b"hello")
        dst = self.tmp_dir / "dest.txt"

        self.storage.write(dst, src)

        self.assertTrue(dst.is_file())
        self.assertEqual(dst.read_bytes(), b"hello")

    def test_write_from_bytes(self) -> None:
        dst = self.tmp_dir / "dest.txt"

        self.storage.write(dst, b"hello bytes")

        self.assertTrue(dst.is_file())
        self.assertEqual(dst.read_bytes(), b"hello bytes")

    def test_write_from_file_object(self) -> None:
        src = self.tmp_dir / "source.txt"
        src.write_bytes(b"from fileobj")
        dst = self.tmp_dir / "dest.txt"

        with src.open("rb") as f:
            self.storage.write(dst, f)

        self.assertEqual(dst.read_bytes(), b"from fileobj")

    def test_open_reads_file(self) -> None:
        path = self.tmp_dir / "file.txt"
        path.write_bytes(b"read me")

        with self.storage.open(path) as f:
            data = f.read()

        self.assertEqual(data, b"read me")

    def test_delete_existing_file(self) -> None:
        path = self.tmp_dir / "to_delete.txt"
        path.write_bytes(b"bye")

        self.storage.delete(path)

        self.assertFalse(path.exists())

    def test_delete_nonexistent_file_no_error(self) -> None:
        path = self.tmp_dir / "nonexistent.txt"
        # Should not raise
        self.storage.delete(path)

    def test_delete_none_no_error(self) -> None:
        # Should not raise
        self.storage.delete(None)

    def test_move(self) -> None:
        src = self.tmp_dir / "original.txt"
        src.write_bytes(b"move me")
        dst = self.tmp_dir / "moved.txt"

        self.storage.move(src, dst)

        self.assertFalse(src.exists())
        self.assertTrue(dst.is_file())
        self.assertEqual(dst.read_bytes(), b"move me")

    def test_copy(self) -> None:
        src = self.tmp_dir / "original.txt"
        src.write_bytes(b"copy me")
        dst = self.tmp_dir / "copied.txt"

        self.storage.copy(src, dst)

        self.assertTrue(src.is_file())
        self.assertTrue(dst.is_file())
        self.assertEqual(dst.read_bytes(), b"copy me")

    def test_exists_true(self) -> None:
        path = self.tmp_dir / "exists.txt"
        path.write_bytes(b"here")

        self.assertTrue(self.storage.exists(path))

    def test_exists_false(self) -> None:
        path = self.tmp_dir / "nope.txt"

        self.assertFalse(self.storage.exists(path))

    def test_size_returns_file_size(self) -> None:
        path = self.tmp_dir / "sized.txt"
        path.write_bytes(b"12345")

        result = self.storage.size(path)

        self.assertEqual(result, 5)

    def test_size_returns_none_for_missing_file(self) -> None:
        path = self.tmp_dir / "missing.txt"

        result = self.storage.size(path)

        self.assertIsNone(result)

    def test_makedirs_creates_parent_directory(self) -> None:
        file_path = self.tmp_dir / "subdir" / "nested" / "file.txt"

        self.storage.makedirs(file_path)

        self.assertTrue(file_path.parent.is_dir())

    def test_makedirs_existing_directory_no_error(self) -> None:
        file_path = self.tmp_dir / "file.txt"
        # Should not raise even though parent already exists
        self.storage.makedirs(file_path)

    def test_delete_empty_dirs_prunes_empty_parents(self) -> None:
        subdir = self.tmp_dir / "a" / "b"
        subdir.mkdir(parents=True)
        file_path = subdir / "doc.txt"
        file_path.write_bytes(b"x")
        file_path.unlink()

        self.storage.delete_empty_dirs(file_path, self.tmp_dir)

        # Both 'a/b' and 'a' should be removed since they're empty
        self.assertFalse(subdir.exists())
        self.assertFalse((self.tmp_dir / "a").exists())

    def test_delete_empty_dirs_keeps_nonempty_parent(self) -> None:
        subdir = self.tmp_dir / "nonempty"
        subdir.mkdir()
        sibling = subdir / "sibling.txt"
        sibling.write_bytes(b"keep")
        file_path = subdir / "doc.txt"

        self.storage.delete_empty_dirs(file_path, self.tmp_dir)

        # subdir should remain because it contains sibling.txt
        self.assertTrue(subdir.is_dir())

    def test_glob_returns_matching_paths(self) -> None:
        (self.tmp_dir / "a.txt").write_bytes(b"1")
        (self.tmp_dir / "b.txt").write_bytes(b"2")
        (self.tmp_dir / "c.pdf").write_bytes(b"3")

        results = self.storage.glob(self.tmp_dir / "*.txt")

        result_names = {Path(p).name for p in results}
        self.assertIn("a.txt", result_names)
        self.assertIn("b.txt", result_names)
        self.assertNotIn("c.pdf", result_names)

    def test_acquire_lock_local(self) -> None:
        with self.storage.acquire_lock():
            # Should enter and exit cleanly
            pass
