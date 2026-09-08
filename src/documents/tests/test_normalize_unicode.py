from documents.utils import normalize_unicode


class TestNormalizeUnicode:
    def test_none_passes_through(self) -> None:
        assert normalize_unicode(None) is None
