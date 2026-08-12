import pytest_mock

from documents.utils import QuerySetStream


class TestQuerySetStream:
    def test_len_and_iter_delegate_to_streaming_queryset_methods(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A mock queryset
        WHEN:
            - A QuerySetStream wrapping it is measured and iterated
        THEN:
            - len() uses count() (not a materializing len()), and iteration
              uses .iterator(chunk_size=...) (not plain iteration, which
              would materialize the whole queryset, plus any prefetch
              caches, into Django's own result cache at once)
        """
        mock_queryset = mocker.MagicMock()
        mock_queryset.count.return_value = 42
        mock_queryset.iterator.return_value = iter(["row-1", "row-2"])
        streamed = QuerySetStream(mock_queryset, chunk_size=1000)

        assert len(streamed) == 42
        assert list(streamed) == ["row-1", "row-2"]
        # count.call_count isn't asserted exactly: list()'s own size-hint
        # optimization calls len(streamed) again internally, on top of the
        # explicit len() call above -- both legitimately delegate to
        # count(), so only the delegation itself (not the call count) is
        # the thing being verified here.
        mock_queryset.count.assert_called_with()
        mock_queryset.iterator.assert_called_once_with(chunk_size=1000)
