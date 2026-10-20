from __future__ import annotations

import time
import warnings
from typing import TYPE_CHECKING
from typing import Any

import httpx
import pytest

from documents.parsers import ParseError

if TYPE_CHECKING:
    from collections.abc import Callable


def util_call_with_backoff(
    method_or_callable: Callable,
    args: list | tuple,
    *,
    skip_on_50x_err: bool = True,
) -> tuple[bool, Any]:
    """
    For whatever reason, the images started during the test pipeline like to
    segfault sometimes, crash and otherwise fail randomly, when run with the
    exact files that usually pass.

    So, this function will retry the given method/function up to 3 times, with larger backoff
    periods between each attempt, in hopes the issue resolves itself during
    one attempt to parse.

    This will wait the following:
        - Attempt 1 - 20s following failure
        - Attempt 2 - 40s following failure
        - Attempt 3 - 80s following failure

    """
    result = None
    succeeded = False
    retry_time = 20.0
    retry_count = 0
    status_codes = []
    max_retry_count = 3

    while retry_count < max_retry_count and not succeeded:
        try:
            result = method_or_callable(*args)

            succeeded = True
        except ParseError as e:  # pragma: no cover
            cause_exec = e.__cause__
            if cause_exec is not None and isinstance(cause_exec, httpx.HTTPStatusError):
                status_codes.append(cause_exec.response.status_code)
                warnings.warn(
                    f"HTTP Exception for {cause_exec.request.url} - {cause_exec}",
                )
            else:
                warnings.warn(f"Unexpected error: {e}")
        except Exception as e:  # pragma: no cover
            warnings.warn(f"Unexpected error: {e}")

        retry_count = retry_count + 1

        if not succeeded and retry_count < max_retry_count:
            time.sleep(retry_time)
            retry_time = retry_time * 2.0

    if (
        not succeeded
        and status_codes
        and skip_on_50x_err
        and all(httpx.codes.is_server_error(code) for code in status_codes)
    ):
        pytest.skip("Repeated HTTP 50x for service")  # pragma: no cover

    return succeeded, result
