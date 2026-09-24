# Outbound Connect Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the URL-rewriting SSRF transport in `src/paperless/network.py` with an httpcore network-backend guard that validates the exact address dialled, falls back across resolved addresses, and leaves Host/SNI/pooling to httpx.

**Architecture:** A guard wraps httpcore's default network backend inside `httpx.HTTPTransport` / `AsyncHTTPTransport` subclasses. With `allow_internal=False` it resolves the origin hostname, rejects the name if any address is non-public, and dials validated IP literals in family-interleaved order under a shared connect budget. With `allow_internal=True` it passes the hostname through to the stock backend. New code is added alongside the old; consumers move one at a time; the old transport is deleted last.

**Tech Stack:** Python 3.11+, httpx 0.28.1, httpcore 1.0.9, anyio 4.14, Django, Celery, pytest, pytest-mock, pytest-django, pytest-httpx.

**Spec:** `docs/superpowers/specs/2026-09-10-outbound-connect-guard-design.md`. Read it before starting any task; this plan implements it and argues from it.

## Global Constraints

These apply to every task. A task's requirements implicitly include all of them.

- **No internal tracking or planning metadata anywhere in the change.** Not in code, comments, docstrings, test names, test ids, test docstrings, commit messages, branch names or PR text. Forbidden: task or step numbers, plan or spec file paths or names, section references ("see 4.4"), todo items, agent or model names or tiers, session identifiers, review-round labels. Code and history must read as ordinary engineering work that stands on its own.
- The only permitted attribution is the required commit trailer, verbatim, as the last line of every commit message: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- **Before every commit**, run both checks and fix anything they flag (a Celery "task" without a number is fine):
  ```bash
  git diff --cached -U0 | grep '^+' | grep -nEi '\b(task|step|phase) ?#?[0-9]+\b|docs/superpowers|superpowers|\bspec\b|implementation plan|sonnet|haiku|opus|subagent|review round|TODO|FIXME' || echo "clean"
  git diff --cached --name-only | grep -E '^docs/superpowers/' && echo "STOP: never commit docs/superpowers" || echo "clean"
  ```
  After committing, check the message body (the trailer line is expected to match "Opus"; nothing else may):
  ```bash
  git log -1 --format=%B | grep -v '^Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>$' | grep -nEi '\b(task|step) ?[0-9]+\b|spec|plan|sonnet|haiku|opus|subagent' || echo "clean"
  ```
- Never commit anything under `docs/superpowers/` (this plan and the spec stay uncommitted unless the user says otherwise).
- No em dashes in any written output: code, comments, docs, commit messages.
- `src/paperless/network.py` must not import Django.
- Full type annotations on every new or changed function, fixture, fixture return and test signature. No PEP 695 `type` statements (`requires-python = ">=3.11"`); use `TypeAlias`.
- New and changed code must have no `pyrefly` errors. The repo-wide run reports about a thousand pre-existing errors that the baseline does not absorb; ignore those and the baseline file. Check only that no error points at a file the task changed.
- Tests: pytest style, grouped in classes, `mocker` (pytest-mock), `@pytest.mark.parametrize` with `pytest.param(..., id="...")` on every case (the repo sets `strict_parametrization_ids`), GIVEN/WHEN/THEN docstrings, `@pytest.mark.django_db` on the class only when the DB is needed. Boolean test parameters go after a bare `*` in the signature (ruff FBT001). Async tests use `@pytest.mark.anyio` with a class-level autouse `anyio_backend` fixture returning `"asyncio"`. Existing unittest-style classes that are edited keep their style.
- Lint and format with the globally installed `ruff` (not `uv run ruff`): `ruff check <files>` and `ruff format <files>`.
- Tests cannot run on Windows. Run them on the VM with the helper, which syncs `src/`, `pyproject.toml` and `uv.lock` first:
  ```bash
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "<pytest targets and args>"
  ```
- `pyrefly` runs on the VM in the branch's clean test copy, the one `vmtest.sh` wipes and re-syncs (run a test through `vmtest.sh` first so it is current). pyrefly is in the `typing` dependency group. List errors in the files you changed (replace the pattern with your changed paths):
  ```bash
  ssh -o BatchMode=yes paperless-vm 'bash -lc "cd ~/projects/paperless-ngx-worktrees/fix-outbound-connect-guard- && uv run --group typing pyrefly check 2>&1 | grep -E \"^ *--> src/(paperless/network|paperless/tests/test_network)\""'
  ```
  No output means no errors in those files. (The directory name keeps the trailing hyphen the helper's slug adds.)

## Model Tiers and Review

Dispatch each task's implementer with the listed model (`model` parameter of the Agent tool). After each task: a spec-compliance review, then the listed security/quality review. The implementer only sees its own task, so pass the Global Constraints section and the task's full text verbatim.

| Task | Deliverable                                    | Implementer                         | Spec review | Security / quality review |
| ---- | ---------------------------------------------- | ----------------------------------- | ----------- | ------------------------- |
| 1    | Typed errors and `is_public_ip`                | sonnet                              | sonnet      | opus                      |
| 2    | Public-address resolution                      | opus                                | sonnet      | opus                      |
| 3    | Guard network backends                         | opus                                | sonnet      | opus                      |
| 4    | Guarded transports, factories, dependencies    | opus                                | sonnet      | opus                      |
| 5    | Real-socket test helpers and integration tests | sonnet                              | sonnet      | opus                      |
| 6    | AI clients on guarded transports               | sonnet                              | sonnet      | sonnet                    |
| 7    | AI block error surfaces                        | sonnet                              | sonnet      | sonnet                    |
| 8    | Webhooks on the guarded transport              | sonnet                              | sonnet      | opus                      |
| 9    | IMAP pinning on shared resolution              | sonnet                              | sonnet      | sonnet                    |
| 10   | Remove the old transport                       | sonnet                              | sonnet      | sonnet                    |
| 11   | Documentation                                  | haiku                               | sonnet      | n/a                       |
| 12   | Full test suite, ruff, pyrefly                 | haiku (escalate failures to sonnet) | n/a         | n/a                       |
| 13   | Manual reproduction on the VM                  | sonnet                              | n/a         | n/a                       |
| 14   | Whole-branch final review                      | n/a                                 | n/a         | opus                      |

Order: 1, 2, 3, 4, 5 sequential. 6, 8 and 9 after 5, independent of each other (do not run 6 and 7 concurrently: same file). 7 after 6. 10 after 6, 7, 8 and 9. 11 any time after 4. 12, 13, 14 last, in that order.

## File Structure

| File                                                                                                     | Responsibility                                                                                                                                                      |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/paperless/network.py` (modify)                                                                      | Address classification, typed errors, public-address resolution, guard backends, guarded transports and factories, `validate_outbound_http_url`. No Django imports. |
| `src/paperless/tests/test_network.py` (modify)                                                           | Unit tests for everything in `network.py`.                                                                                                                          |
| `src/paperless_testing/outbound.py` (create)                                                             | Shared real-socket test helpers: local HTTP server, resolver fake, dial spies, `guard_of`. Not a test module.                                                       |
| `src/paperless/tests/test_network_integration.py` (create)                                               | Real-socket tests of the guarded transports.                                                                                                                        |
| `src/conftest.py` (modify)                                                                               | Thin `local_http_server`, `fake_dns` and `dial_recorder` fixtures importing from `paperless_testing.outbound` in their bodies.                                      |
| `src/paperless_ai/client.py`, `src/paperless_ai/embedding.py`, `src/paperless_ai/exceptions.py` (modify) | Guarded transports; `LLMBlockedError`; block detection in `_normalize_errors`.                                                                                      |
| `src/documents/views.py` (modify)                                                                        | 502 for `LLMBlockedError` in `ai_suggestions`.                                                                                                                      |
| `src/documents/workflows/webhooks.py` (modify)                                                           | Guarded transport; `throws=` entry.                                                                                                                                 |
| `src/paperless_mail/mail.py` (modify)                                                                    | Shared resolution for IMAP pinning.                                                                                                                                 |
| `pyproject.toml`, `uv.lock` (modify)                                                                     | Declare `anyio`, `httpcore`, `httpx`.                                                                                                                               |
| `docs/configuration.md`, `docs/usage.md` (modify)                                                        | Policy wording.                                                                                                                                                     |

## Branch

Before Task 1, from an up-to-date `dev`:

```bash
git switch dev && git pull --ff-only && git switch -c fix-outbound-connect-guard
```

The hyphenated `fix-` prefix makes CI build a Docker image for the branch, so a co-maintainer can test it. Confirm with the user before pushing anything.

---

### Task 1: Typed errors and `is_public_ip`

**Model tier:** implementer sonnet; reviews sonnet (spec), opus (security).

**Files:**

- Modify: `src/paperless/network.py` (top of module; `is_public_ip`; the `is_public_ip` calls inside `validate_outbound_http_url` and `_rewrite_request_to_pinned_ip`)
- Modify: `src/paperless_mail/mail.py:48-49` imports and the loop in `get_mailbox` (around line 529)
- Test: `src/paperless/tests/test_network.py` (replace the two string-parametrized `is_public_ip` tests at lines 54-90; keep the two pinned-transport tests for now)

**Interfaces:**

- Produces:
  - `IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address`
  - `class BlockReason(StrEnum)`: `NON_PUBLIC_ADDRESS = "non_public_address"`, `UNIX_SOCKET = "unix_socket"`
  - `class OutboundRequestBlockedError(Exception)`: `__init__(self, *, host: str, port: int | None, reason: BlockReason, address: IPAddress | None = None)`; attributes `host`, `port`, `reason`, `address`
  - `class HostResolutionError(Exception)`: `__init__(self, *, host: str, detail: str)`; attributes `host`, `detail`
  - `def blocked_message(exc: OutboundRequestBlockedError | HostResolutionError) -> str`
  - `def is_public_ip(ip: IPAddress) -> bool`

- [ ] **Step 1: Write the failing tests**

Replace everything in `src/paperless/tests/test_network.py` from the first `@pytest.mark.parametrize` (line 54) to the end of the file with the classes below, and extend the imports at the top of the file so it starts like this (the two existing pinned-transport tests stay between the imports and the new classes):

```python
import ipaddress
import pickle
from unittest import mock

import httpx
import pytest
from celery.utils.serialization import get_pickleable_exception

from paperless.network import BlockReason
from paperless.network import HostResolutionError
from paperless.network import OutboundRequestBlockedError
from paperless.network import PinnedHostHTTPTransport
from paperless.network import blocked_message
from paperless.network import is_public_ip
```

```python
class TestIsPublicIp:
    @pytest.mark.parametrize(
        "address",
        [
            pytest.param("127.0.0.1", id="ipv4-loopback"),
            pytest.param("10.0.0.5", id="ipv4-private"),
            pytest.param("169.254.169.254", id="ipv4-link-local-metadata"),
            pytest.param("::1", id="ipv6-loopback"),
            pytest.param("fc00::1", id="ipv6-unique-local"),
            pytest.param("fe80::1", id="ipv6-link-local"),
            pytest.param("100.64.0.0", id="cgnat-first"),
            pytest.param("100.127.255.255", id="cgnat-last"),
            pytest.param("64:ff9b::", id="nat64-well-known-first"),
            pytest.param("64:ff9b::7f00:1", id="nat64-wrapping-loopback"),
            pytest.param("64:ff9b::ffff:ffff", id="nat64-well-known-last"),
            pytest.param("224.0.0.1", id="ipv4-multicast"),
            pytest.param("ff02::1", id="ipv6-multicast"),
            pytest.param("0.0.0.0", id="ipv4-unspecified"),
            pytest.param("::", id="ipv6-unspecified"),
            pytest.param("::ffff:127.0.0.1", id="ipv4-mapped-loopback"),
            pytest.param("::ffff:169.254.169.254", id="ipv4-mapped-metadata"),
            pytest.param("::ffff:10.0.0.1", id="ipv4-mapped-private"),
            pytest.param("::ffff:100.64.0.1", id="ipv4-mapped-cgnat"),
        ],
    )
    def test_rejects_non_public_addresses(self, address: str) -> None:
        """
        GIVEN:
            - An address that is internal, multicast, or reaches internal hosts
        WHEN:
            - It is classified
        THEN:
            - It is not public
        """
        assert not is_public_ip(ipaddress.ip_address(address))

    @pytest.mark.parametrize(
        "address",
        [
            pytest.param("8.8.8.8", id="ipv4-public"),
            pytest.param("2606:4700:4700::1111", id="ipv6-public"),
            pytest.param("100.63.255.255", id="below-cgnat"),
            pytest.param("100.128.0.0", id="above-cgnat"),
            pytest.param("64:ff9a:ffff:ffff:ffff:ffff:ffff:ffff", id="below-nat64"),
            pytest.param("64:ff9b::1:0:0", id="above-nat64-well-known"),
        ],
    )
    def test_accepts_public_addresses(self, address: str) -> None:
        """
        GIVEN:
            - A globally routable unicast address outside our extra ranges
        WHEN:
            - It is classified
        THEN:
            - It is public
        """
        assert is_public_ip(ipaddress.ip_address(address))


def _sample_errors() -> list[object]:
    return [
        pytest.param(
            OutboundRequestBlockedError(
                host="example.com",
                port=443,
                reason=BlockReason.NON_PUBLIC_ADDRESS,
                address=ipaddress.ip_address("10.0.0.1"),
            ),
            id="non-public-address",
        ),
        pytest.param(
            OutboundRequestBlockedError(
                host="/run/app.sock",
                port=None,
                reason=BlockReason.UNIX_SOCKET,
            ),
            id="unix-socket",
        ),
        pytest.param(
            HostResolutionError(
                host="missing.example", detail="Name or service not known"
            ),
            id="unresolvable",
        ),
    ]


class TestOutboundErrors:
    @pytest.mark.parametrize("error", _sample_errors())
    def test_round_trips_through_pickle(self, error: Exception) -> None:
        """
        GIVEN:
            - An outbound error with keyword-only fields
        WHEN:
            - It is pickled and unpickled
        THEN:
            - Type, fields and message are preserved
        """
        restored = pickle.loads(pickle.dumps(error))

        assert type(restored) is type(error)
        assert vars(restored) == vars(error)
        assert str(restored) == str(error)

    @pytest.mark.parametrize("error", _sample_errors())
    def test_celery_keeps_the_original_exception(self, error: Exception) -> None:
        """
        GIVEN:
            - An outbound error raised from a Celery task
        WHEN:
            - Celery prepares it for failure handling
        THEN:
            - The exception itself is kept, not an unpickleable wrapper
        """
        assert get_pickleable_exception(error) is error

    def test_message_names_the_destination_but_not_the_address(self) -> None:
        """
        GIVEN:
            - A block for a non-public address
        WHEN:
            - The error is rendered
        THEN:
            - Host, port and reason are in the message
            - The resolved internal address is not, so it never reaches logs or
              stored task results
        """
        error = OutboundRequestBlockedError(
            host="example.com",
            port=443,
            reason=BlockReason.NON_PUBLIC_ADDRESS,
            address=ipaddress.ip_address("10.0.0.1"),
        )

        message = str(error)

        assert "example.com:443" in message
        assert "non_public_address" in message
        assert "10.0.0.1" not in message

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            pytest.param(
                OutboundRequestBlockedError(
                    host="internal.example",
                    port=443,
                    reason=BlockReason.NON_PUBLIC_ADDRESS,
                    address=ipaddress.ip_address("10.0.0.1"),
                ),
                "Connection blocked: internal.example resolves to a non-public address",
                id="non-public-address",
            ),
            pytest.param(
                HostResolutionError(host="missing.example", detail="NXDOMAIN"),
                "Could not resolve hostname: missing.example",
                id="unresolvable",
            ),
            pytest.param(
                OutboundRequestBlockedError(
                    host="/run/app.sock",
                    port=None,
                    reason=BlockReason.UNIX_SOCKET,
                ),
                "Connection blocked: unix sockets are not permitted",
                id="unix-socket",
            ),
        ],
    )
    def test_blocked_message(
        self,
        error: OutboundRequestBlockedError | HostResolutionError,
        expected: str,
    ) -> None:
        """
        GIVEN:
            - An outbound error
        WHEN:
            - The user-facing message is requested
        THEN:
            - It matches the established wording
        """
        assert blocked_message(error) == expected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py -v"`
Expected: collection error, `ImportError: cannot import name 'BlockReason' from 'paperless.network'`.

- [ ] **Step 3: Implement the types, errors and new `is_public_ip`**

In `src/paperless/network.py`, replace the imports, `_NON_PUBLIC_NETWORKS` and `is_public_ip` (current lines 1-33) with:

```python
import functools
import ipaddress
import socket
from collections.abc import Callable
from collections.abc import Collection
from enum import StrEnum
from typing import Self
from typing import TypeAlias
from urllib.parse import ParseResult
from urllib.parse import urlparse

import httpx

# requires-python is >=3.11, so no PEP 695 `type` statement.
IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address

# Ranges that ipaddress reports as global but which still reach internal hosts.
_NON_PUBLIC_NETWORKS = (
    # RFC 6052 NAT64 well-known prefix: 64:ff9b::7f00:1 is 127.0.0.1 wherever
    # a NAT64 gateway exists, yet ipaddress classifies the prefix as global.
    ipaddress.ip_network("64:ff9b::/96"),
)


class BlockReason(StrEnum):
    NON_PUBLIC_ADDRESS = "non_public_address"
    UNIX_SOCKET = "unix_socket"


class OutboundRequestBlockedError(Exception):
    """
    An outbound connection was refused by policy before any socket was opened.

    For NON_PUBLIC_ADDRESS, ``host`` is the name or literal being connected to
    and ``address`` the first offending address. For UNIX_SOCKET, ``host`` is
    the socket path and ``port`` and ``address`` are None.

    ``address`` is deliberately left out of the message: the message is logged
    and stored on failed tasks, and must not disclose internal addresses.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int | None,
        reason: BlockReason,
        address: IPAddress | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.reason = reason
        self.address = address
        target = host if port is None else f"{host}:{port}"
        super().__init__(f"Outbound connection to {target} blocked ({reason})")

    def __reduce__(self) -> tuple[Callable[..., Self], tuple[object, ...]]:
        # Celery rebuilds failed-task exceptions by pickling; keyword-only
        # fields cannot be recovered from ``args`` alone.
        return (
            functools.partial(
                type(self),
                host=self.host,
                port=self.port,
                reason=self.reason,
                address=self.address,
            ),
            (),
        )


class HostResolutionError(Exception):
    """The resolver returned no usable addresses for a host."""

    def __init__(self, *, host: str, detail: str) -> None:
        self.host = host
        self.detail = detail
        super().__init__(f"Could not resolve {host}: {detail}")

    def __reduce__(self) -> tuple[Callable[..., Self], tuple[object, ...]]:
        return (
            functools.partial(type(self), host=self.host, detail=self.detail),
            (),
        )


def blocked_message(exc: OutboundRequestBlockedError | HostResolutionError) -> str:
    """User-facing text for validation errors, kept stable for existing callers."""
    if isinstance(exc, HostResolutionError):
        return f"Could not resolve hostname: {exc.host}"
    if exc.reason is BlockReason.UNIX_SOCKET:
        return "Connection blocked: unix sockets are not permitted"
    return f"Connection blocked: {exc.host} resolves to a non-public address"


def is_public_ip(ip: IPAddress) -> bool:
    """
    True when ``ip`` is globally routable unicast and not in a range that
    ipaddress reports as global but which still reaches internal hosts.
    """
    return (
        ip.is_global
        and not ip.is_multicast
        and not any(ip in network for network in _NON_PUBLIC_NETWORKS)
    )
```

Then update the two remaining callers in `network.py` that pass strings. In `validate_outbound_http_url`:

```python
    if not allow_internal:
        for ip_str in resolve_hostname_ips(parsed.hostname):
            if not is_public_ip(ipaddress.ip_address(ip_str)):
```

In `_rewrite_request_to_pinned_ip`:

```python
    if not allow_internal:
        for ip_str in ips:
            if not is_public_ip(ipaddress.ip_address(ip_str)):
```

- [ ] **Step 4: Update the mail caller**

In `src/paperless_mail/mail.py`, add `import ipaddress` to the stdlib imports (alphabetical, after `import imaplib`), and in `get_mailbox` change:

```python
        for ip_str in pinned_ips:
            if not is_public_ip(ipaddress.ip_address(ip_str)):
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py src/paperless_mail/tests/test_mail.py src/documents/tests/test_workflows.py::TestWebhookSecurity src/paperless_ai/tests/test_client.py src/paperless_ai/tests/test_embedding.py src/documents/tests/test_api_app_config.py -v"`
Expected: all PASS.

- [ ] **Step 6: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless/network.py src/paperless/tests/test_network.py src/paperless_mail/mail.py
ruff format src/paperless/network.py src/paperless/tests/test_network.py src/paperless_mail/mail.py
git add src/paperless/network.py src/paperless/tests/test_network.py src/paperless_mail/mail.py
# run the two pre-commit checks from Global Constraints
git commit -m "Type outbound block errors and classify addresses with is_global

is_public_ip now takes an ipaddress object and relies on is_global, keeping
multicast and the NAT64 well-known prefix as explicit extra exclusions.
Adds OutboundRequestBlockedError and HostResolutionError, both picklable so
Celery keeps them intact on task failure.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
# run the post-commit message check from Global Constraints
```

---

### Task 2: Public-address resolution

**Model tier:** implementer opus; reviews sonnet (spec), opus (security).

**Files:**

- Modify: `src/paperless/network.py` (add hooks, resolution helpers and the two resolvers after `is_public_ip`; rework the DNS part of `validate_outbound_http_url` so it resolves the same IDNA 2008 name the HTTP clients dial; keep `resolve_hostname_ips` untouched, it is still used)
- Test: `src/paperless/tests/test_network.py` (append classes)

**Interfaces:**

- Consumes: `IPAddress`, `BlockReason`, `OutboundRequestBlockedError`, `HostResolutionError`, `blocked_message`, `is_public_ip` from Task 1.
- Produces:
  - `def resolve_public_addresses(host: str, port: int | None) -> tuple[IPAddress, ...]`
  - `async def aresolve_public_addresses(host: str, port: int | None) -> tuple[IPAddress, ...]`
  - Module hooks that tests patch: `paperless.network._getaddrinfo`, `paperless.network._agetaddrinfo`

- [ ] **Step 1: Write the failing tests**

Append to `src/paperless/tests/test_network.py` (add `import socket`, `from typing import Any`, `from unittest.mock import MagicMock`, `from pytest_mock import MockerFixture` and `from paperless.network import aresolve_public_addresses`, `resolve_public_addresses`, `validate_outbound_http_url` to the imports):

```python
def _addrinfo(
    *addresses: str,
) -> list[tuple[socket.AddressFamily, socket.SocketKind, int, str, tuple[Any, ...]]]:
    return [
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, 443, 0, 0))
        if ":" in address
        else (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
        for address in addresses
    ]


def _answer(mocker: MockerFixture, *addresses: str) -> MagicMock:
    """Make both resolver hooks answer with ``addresses``; returns the sync mock."""
    infos = _addrinfo(*addresses)
    mocker.patch(
        "paperless.network._agetaddrinfo",
        new=mocker.AsyncMock(return_value=infos),
    )
    return mocker.patch("paperless.network._getaddrinfo", return_value=infos)


class TestResolvePublicAddresses:
    def test_ip_literal_skips_dns(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A public IP literal
        WHEN:
            - It is resolved
        THEN:
            - It is returned without a resolver call
        """
        resolver = _answer(mocker)

        assert resolve_public_addresses("93.184.216.34", 443) == (
            ipaddress.ip_address("93.184.216.34"),
        )
        resolver.assert_not_called()

    def test_private_ip_literal_is_blocked(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A private IP literal
        WHEN:
            - It is resolved
        THEN:
            - It is blocked as a non-public address
        """
        _answer(mocker)

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            resolve_public_addresses("10.0.0.1", 443)

        assert exc_info.value.reason is BlockReason.NON_PUBLIC_ADDRESS
        assert exc_info.value.address == ipaddress.ip_address("10.0.0.1")

    def test_asks_for_stream_sockets_on_the_port(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A hostname
        WHEN:
            - It is resolved
        THEN:
            - The resolver is asked for TCP stream results for that port
        """
        resolver = _answer(mocker, "93.184.216.34")

        resolve_public_addresses("example.com", 443)

        resolver.assert_called_once_with("example.com", 443, type=socket.SOCK_STREAM)

    def test_deduplicates_preserving_order(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Resolver results containing a duplicate
        WHEN:
            - They are resolved
        THEN:
            - Each address appears once, in resolver order
        """
        _answer(mocker, "2606:4700::1", "93.184.216.34", "2606:4700::1")

        assert resolve_public_addresses("example.com", 443) == (
            ipaddress.ip_address("2606:4700::1"),
            ipaddress.ip_address("93.184.216.34"),
        )

    def test_strips_zone_ids(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A scoped link-local result
        WHEN:
            - It is resolved
        THEN:
            - The zone id is stripped and the address is blocked
        """
        _answer(mocker, "fe80::1%eth0")

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            resolve_public_addresses("example.com", 443)

        assert exc_info.value.address == ipaddress.ip_address("fe80::1")

    def test_any_non_public_answer_blocks_the_name(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Resolver results mixing public and private addresses
        WHEN:
            - They are resolved
        THEN:
            - The whole name is blocked, naming the first offending address
        """
        _answer(mocker, "93.184.216.34", "127.0.0.1", "10.0.0.1")

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            resolve_public_addresses("example.com", 443)

        assert exc_info.value.reason is BlockReason.NON_PUBLIC_ADDRESS
        assert exc_info.value.host == "example.com"
        assert exc_info.value.port == 443
        assert exc_info.value.address == ipaddress.ip_address("127.0.0.1")

    @pytest.mark.parametrize(
        "failure",
        [
            pytest.param(
                socket.gaierror(-2, "Name or service not known"), id="gaierror"
            ),
            pytest.param(UnicodeError("label too long"), id="invalid-idna"),
        ],
    )
    def test_resolver_failure(self, mocker: MockerFixture, failure: Exception) -> None:
        """
        GIVEN:
            - A resolver that fails
        WHEN:
            - A hostname is resolved
        THEN:
            - HostResolutionError is raised
        """
        mocker.patch("paperless.network._getaddrinfo", side_effect=failure)

        with pytest.raises(HostResolutionError):
            resolve_public_addresses("example.com", 443)

    def test_empty_answer(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A resolver returning no results
        WHEN:
            - A hostname is resolved
        THEN:
            - HostResolutionError is raised
        """
        _answer(mocker)

        with pytest.raises(HostResolutionError):
            resolve_public_addresses("example.com", 443)


class TestAsyncResolvePublicAddresses:
    @pytest.fixture(autouse=True)
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_returns_public_addresses(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Public resolver results
        WHEN:
            - They are resolved asynchronously
        THEN:
            - The addresses are returned
        """
        _answer(mocker, "93.184.216.34")

        assert await aresolve_public_addresses("example.com", 443) == (
            ipaddress.ip_address("93.184.216.34"),
        )

    @pytest.mark.anyio
    async def test_blocks_non_public(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A private resolver result
        WHEN:
            - It is resolved asynchronously
        THEN:
            - It is blocked
        """
        _answer(mocker, "10.0.0.1")

        with pytest.raises(OutboundRequestBlockedError):
            await aresolve_public_addresses("example.com", 443)

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "failure",
        [
            pytest.param(
                socket.gaierror(-2, "Name or service not known"), id="gaierror"
            ),
            pytest.param(UnicodeError("label too long"), id="invalid-idna"),
        ],
    )
    async def test_resolver_failure(
        self,
        mocker: MockerFixture,
        failure: Exception,
    ) -> None:
        """
        GIVEN:
            - An async resolver that fails
        WHEN:
            - A hostname is resolved
        THEN:
            - HostResolutionError is raised
        """
        mocker.patch(
            "paperless.network._agetaddrinfo",
            new=mocker.AsyncMock(side_effect=failure),
        )

        with pytest.raises(HostResolutionError):
            await aresolve_public_addresses("example.com", 443)


class TestValidateOutboundHttpUrl:
    @pytest.mark.parametrize(
        ("answers", "expected"),
        [
            pytest.param(
                ["10.0.0.1"],
                "Connection blocked: internal.example resolves to a non-public address",
                id="non-public",
            ),
            pytest.param(
                [],
                "Could not resolve hostname: internal.example",
                id="unresolvable",
            ),
        ],
    )
    def test_messages(
        self,
        mocker: MockerFixture,
        answers: list[str],
        expected: str,
    ) -> None:
        """
        GIVEN:
            - A hostname that resolves to a private address, or to nothing
        WHEN:
            - The URL is validated with internal addresses disallowed
        THEN:
            - ValueError carries the established message
        """
        _answer(mocker, *answers)

        with pytest.raises(ValueError, match=expected):
            validate_outbound_http_url(
                "https://internal.example/v1",
                allow_internal=False,
            )

    def test_allow_internal_skips_dns(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - A URL is validated
        THEN:
            - No resolver call is made
        """
        resolver = _answer(mocker, "10.0.0.1")

        validate_outbound_http_url("https://internal.example/v1", allow_internal=True)

        resolver.assert_not_called()

    def test_resolves_the_name_http_clients_connect_to(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A hostname containing a character that IDNA 2003 and IDNA 2008
              encode differently ("fass" versus "xn--fa-hia")
            - The IDNA 2003 name resolves to a public address and the IDNA 2008
              name, which httpx and urllib3 connect to, to a private one
        WHEN:
            - The URL is validated with internal addresses disallowed
        THEN:
            - The IDNA 2008 name is the one checked, so the URL is blocked
        """
        answers = {
            "fass.example": _addrinfo("93.184.216.34"),
            "xn--fa-hia.example": _addrinfo("10.0.0.1"),
        }
        resolver = mocker.patch(
            "paperless.network._getaddrinfo",
            side_effect=lambda host, *args, **kwargs: answers[host],
        )

        with pytest.raises(ValueError, match="resolves to a non-public address"):
            validate_outbound_http_url(
                "https://fa\u00df.example/v1",
                allow_internal=False,
            )

        resolver.assert_called_once_with(
            "xn--fa-hia.example",
            443,
            type=socket.SOCK_STREAM,
        )

    def test_hostname_invalid_for_http_clients_is_rejected(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A hostname that has no valid IDNA 2008 encoding
        WHEN:
            - The URL is validated with internal addresses disallowed
        THEN:
            - It is rejected as invalid without a resolver call
        """
        resolver = _answer(mocker, "93.184.216.34")

        with pytest.raises(ValueError, match="Invalid URL scheme or hostname"):
            validate_outbound_http_url(
                "https://bad\u2764host.example/v1",
                allow_internal=False,
            )

        resolver.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py -v"`
Expected: collection error, `ImportError: cannot import name 'aresolve_public_addresses'`.

- [ ] **Step 3: Implement resolution**

In `src/paperless/network.py` add `import anyio` to the third-party imports (above `import httpx`) and `from collections.abc import Iterable` plus `from typing import Any` to the stdlib imports. After `is_public_ip`, add:

```python
# Resolver indirection so tests can fake DNS for this module without changing
# how the stock httpcore backends resolve the literals the guard dials.
_getaddrinfo = socket.getaddrinfo
_agetaddrinfo = anyio.getaddrinfo


def _parse_ip_literal(host: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return None


def _collect_addresses(
    host: str,
    infos: Iterable[tuple[Any, ...]],
) -> tuple[IPAddress, ...]:
    # dict keys keep the first occurrence and resolver order
    addresses: dict[IPAddress, None] = {}
    for info in infos:
        address = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        addresses.setdefault(address, None)
    if not addresses:
        raise HostResolutionError(host=host, detail="no addresses returned")
    return tuple(addresses)


def _require_public(
    host: str,
    port: int | None,
    addresses: tuple[IPAddress, ...],
) -> tuple[IPAddress, ...]:
    for address in addresses:
        if not is_public_ip(address):
            raise OutboundRequestBlockedError(
                host=host,
                port=port,
                reason=BlockReason.NON_PUBLIC_ADDRESS,
                address=address,
            )
    return addresses


def resolve_public_addresses(host: str, port: int | None) -> tuple[IPAddress, ...]:
    """
    Resolve ``host`` and return its addresses in resolver order, or raise if
    any of them is non-public. A name is rejected as a whole; offending
    addresses are never filtered out.
    """
    literal = _parse_ip_literal(host)
    if literal is not None:
        return _require_public(host, port, (literal,))
    try:
        infos = _getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as e:
        raise HostResolutionError(host=host, detail=str(e)) from e
    return _require_public(host, port, _collect_addresses(host, infos))


async def aresolve_public_addresses(
    host: str,
    port: int | None,
) -> tuple[IPAddress, ...]:
    """Async variant of resolve_public_addresses."""
    literal = _parse_ip_literal(host)
    if literal is not None:
        return _require_public(host, port, (literal,))
    try:
        infos = await _agetaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as e:
        raise HostResolutionError(host=host, detail=str(e)) from e
    return _require_public(host, port, _collect_addresses(host, infos))
```

Add this helper above `validate_outbound_http_url`:

```python
def _dns_name(url: str) -> str:
    """
    The ASCII hostname that httpx and urllib3 look up for ``url``.

    urlparse keeps a non-ASCII hostname as typed, and getaddrinfo would then
    encode it with the stdlib IDNA 2003 codec. That maps some characters
    differently from the IDNA 2008 encoding the HTTP clients use ("faß"
    becomes "fass" instead of "xn--fa-hia"), so the check would resolve a
    different name from the one that is connected to.
    """
    try:
        return httpx.URL(url).raw_host.decode("ascii")
    except (httpx.InvalidURL, UnicodeError) as e:
        raise ValueError("Invalid URL scheme or hostname.") from e
```

In `validate_outbound_http_url`, replace the whole `if not allow_internal:` block with:

```python
    if not allow_internal:
        try:
            resolve_public_addresses(_dns_name(url), port)
        except (OutboundRequestBlockedError, HostResolutionError) as e:
            raise ValueError(blocked_message(e)) from e
```

Scheme and port checks keep using `urlparse`; only the name handed to the resolver changes. For ASCII hostnames the two are identical, so existing messages are unchanged. For a non-ASCII hostname a block message names the IDNA 2008 form. Remote OCR re-checks every Azure request through this function, so it gets the same fix.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py src/paperless_ai/tests/test_client.py src/paperless_ai/tests/test_embedding.py src/documents/tests/test_api_app_config.py src/documents/tests/test_workflows.py::TestWebhookSecurity -v"`
Expected: all PASS.

- [ ] **Step 5: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless/network.py src/paperless/tests/test_network.py
ruff format src/paperless/network.py src/paperless/tests/test_network.py
git add src/paperless/network.py src/paperless/tests/test_network.py
git commit -m "Resolve outbound hosts to validated public addresses

resolve_public_addresses and its async twin return every resolved address
in resolver order, de-duplicated and zone-stripped, and reject the whole
name if any address is non-public. validate_outbound_http_url uses them and
keeps its existing messages.

validate_outbound_http_url now resolves the hostname as httpx and urllib3
encode it (IDNA 2008). It previously let getaddrinfo apply the stdlib IDNA
2003 codec, which encodes characters such as "ß" differently, so a URL
could pass the check under one DNS name and be connected to under another.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Guard network backends

**Model tier:** implementer opus; reviews sonnet (spec), opus (security).

**Files:**

- Modify: `src/paperless/network.py` (add logger, constants, clock hook, helpers and the two backend classes after `aresolve_public_addresses`)
- Test: `src/paperless/tests/test_network.py` (append classes)

**Interfaces:**

- Consumes: `resolve_public_addresses`, `aresolve_public_addresses`, errors from Tasks 1 and 2.
- Produces:
  - `MAX_ADDRESSES_TRIED: Final = 8`, `MIN_ATTEMPT_TIMEOUT: Final = 2.0`, `MAX_ATTEMPT_TIMEOUT: Final = 10.0`
  - `class _GuardedSyncBackend(httpcore.NetworkBackend)`: `__init__(self, inner: httpcore.NetworkBackend, *, allow_internal: bool)`; attributes `_inner`, `_allow_internal`
  - `class _GuardedAsyncBackend(httpcore.AsyncNetworkBackend)`: same shape with `httpcore.AsyncNetworkBackend`
  - Clock hook `paperless.network._monotonic`
  - Logger `paperless.network`

- [ ] **Step 1: Write the failing tests**

Append to `src/paperless/tests/test_network.py` (add `import anyio`, `import httpcore`, `import logging` and `from paperless.network import MAX_ADDRESSES_TRIED, _GuardedAsyncBackend, _GuardedSyncBackend` to the imports):

```python
class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(mocker: MockerFixture) -> FakeClock:
    fake = FakeClock()
    mocker.patch("paperless.network._monotonic", new=fake)
    return fake


class ScriptedBackend(httpcore.NetworkBackend):
    """
    Inner backend double. Each host either connects (default), refuses
    immediately, or black-holes (uses its whole timeout, then times out).
    """

    def __init__(self, clock: FakeClock, outcomes: dict[str, str]) -> None:
        self.clock = clock
        self.outcomes = outcomes
        self.calls: list[tuple[str, float | None]] = []
        self.slept: list[float] = []

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        self.calls.append((host, timeout))
        outcome = self.outcomes.get(host, "connect")
        if outcome == "refuse":
            raise httpcore.ConnectError(f"refused {host}")
        if outcome == "blackhole":
            self.clock.advance(timeout or 0.0)
            raise httpcore.ConnectTimeout(f"timed out {host}")
        return httpcore.MockStream([])

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


class AsyncScriptedBackend(httpcore.AsyncNetworkBackend):
    """Async twin of ScriptedBackend."""

    def __init__(self, clock: FakeClock, outcomes: dict[str, str]) -> None:
        self.clock = clock
        self.outcomes = outcomes
        self.calls: list[tuple[str, float | None]] = []
        self.slept: list[float] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        self.calls.append((host, timeout))
        outcome = self.outcomes.get(host, "connect")
        if outcome == "refuse":
            raise httpcore.ConnectError(f"refused {host}")
        if outcome == "blackhole":
            self.clock.advance(timeout or 0.0)
            raise httpcore.ConnectTimeout(f"timed out {host}")
        return httpcore.AsyncMockStream([])

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


def _public_ipv4(count: int) -> list[str]:
    return [f"93.184.216.{index + 1}" for index in range(count)]


_ATTEMPT_BUDGETS = [
    pytest.param(5.0, 2, [2.5, 2.5], id="5s-2-addresses"),
    pytest.param(5.0, 3, [2.0, 3.0], id="5s-3-addresses"),
    pytest.param(5.0, 8, [2.0, 3.0], id="5s-8-addresses"),
    pytest.param(1.0, 2, [1.0], id="1s-2-addresses"),
    pytest.param(120.0, 8, [10.0] * 7 + [50.0], id="120s-8-addresses"),
    pytest.param(None, 3, [10.0, 10.0, None], id="no-timeout-3-addresses"),
]


class TestGuardedSyncBackend:
    def test_dials_validated_literals_in_order(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A hostname whose first address refuses and second accepts
        WHEN:
            - The guard connects
        THEN:
            - It dials the IP literals in turn, never the hostname
        """
        _answer(mocker, "93.184.216.1", "93.184.216.2")
        inner = ScriptedBackend(clock, {"93.184.216.1": "refuse"})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [host for host, _ in inner.calls] == ["93.184.216.1", "93.184.216.2"]

    @pytest.mark.parametrize(
        ("answers", "expected"),
        [
            pytest.param(
                ["2606:4700::1", "2606:4700::2", "93.184.216.1", "93.184.216.2"],
                ["2606:4700::1", "93.184.216.1", "2606:4700::2", "93.184.216.2"],
                id="balanced",
            ),
            pytest.param(
                ["2606:4700::1", "2606:4700::2", "2606:4700::3", "93.184.216.1"],
                ["2606:4700::1", "93.184.216.1", "2606:4700::2", "2606:4700::3"],
                id="one-family-runs-out",
            ),
            pytest.param(
                ["93.184.216.1", "93.184.216.2"],
                ["93.184.216.1", "93.184.216.2"],
                id="single-family",
            ),
        ],
    )
    def test_interleaves_address_families(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        answers: list[str],
        expected: list[str],
    ) -> None:
        """
        GIVEN:
            - Resolver results grouped by address family
        WHEN:
            - Every address refuses
        THEN:
            - Families are alternated, starting with the first result's family
        """
        _answer(mocker, *answers)
        inner = ScriptedBackend(clock, dict.fromkeys(answers, "refuse"))
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectError):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [host for host, _ in inner.calls] == expected

    @pytest.mark.parametrize(("timeout", "count", "expected"), _ATTEMPT_BUDGETS)
    def test_attempt_budgets(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        timeout: float | None,
        count: int,
        expected: list[float | None],
    ) -> None:
        """
        GIVEN:
            - Every resolved address black-holed
        WHEN:
            - The guard connects with a given timeout
        THEN:
            - Each attempt gets the budget the connect-time policy prescribes
        """
        addresses = _public_ipv4(count)
        _answer(mocker, *addresses)
        inner = ScriptedBackend(clock, dict.fromkeys(addresses, "blackhole"))
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectTimeout):
            guard.connect_tcp("example.com", 443, timeout=timeout)

        assert [budget for _, budget in inner.calls] == expected

    def test_quick_refusal_leaves_budget_for_next_address(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A 1 second budget, a refusing first address and a working second
        WHEN:
            - The guard connects
        THEN:
            - Both addresses are tried and the connection succeeds
        """
        _answer(mocker, "93.184.216.1", "93.184.216.2")
        inner = ScriptedBackend(clock, {"93.184.216.1": "refuse"})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        guard.connect_tcp("example.com", 443, timeout=1.0)

        assert inner.calls == [("93.184.216.1", 1.0), ("93.184.216.2", 1.0)]

    def test_resolution_time_is_not_charged(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A resolver that takes 4 seconds against a 5 second timeout
        WHEN:
            - The guard connects to two black-holed addresses
        THEN:
            - The attempts share the full 5 seconds
        """
        infos = _addrinfo("93.184.216.1", "93.184.216.2")

        def slow_resolver(*_args: object, **_kwargs: object) -> list[tuple[Any, ...]]:
            clock.advance(4.0)
            return infos

        mocker.patch("paperless.network._getaddrinfo", side_effect=slow_resolver)
        inner = ScriptedBackend(
            clock,
            {"93.184.216.1": "blackhole", "93.184.216.2": "blackhole"},
        )
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectTimeout):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [budget for _, budget in inner.calls] == [2.5, 2.5]

    @pytest.mark.parametrize(
        "timeout",
        [pytest.param(0.0, id="zero"), pytest.param(-1.0, id="negative")],
    )
    def test_non_positive_timeout(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        timeout: float,
    ) -> None:
        """
        GIVEN:
            - A zero or negative connect timeout
        WHEN:
            - The guard connects
        THEN:
            - It times out without resolving or dialling
        """
        resolver = _answer(mocker, "93.184.216.1")
        inner = ScriptedBackend(clock, {})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectTimeout):
            guard.connect_tcp("example.com", 443, timeout=timeout)

        resolver.assert_not_called()
        assert inner.calls == []

    def test_caps_attempts(self, mocker: MockerFixture, clock: FakeClock) -> None:
        """
        GIVEN:
            - More public addresses than the attempt cap, all refusing
        WHEN:
            - The guard connects
        THEN:
            - Only the capped number of addresses is dialled
        """
        addresses = _public_ipv4(MAX_ADDRESSES_TRIED + 2)
        _answer(mocker, *addresses)
        inner = ScriptedBackend(clock, dict.fromkeys(addresses, "refuse"))
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectError):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert len(inner.calls) == MAX_ADDRESSES_TRIED

    def test_private_address_beyond_cap_still_blocks(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A private address after more public addresses than the cap
        WHEN:
            - The guard connects
        THEN:
            - The name is blocked and nothing is dialled
        """
        _answer(mocker, *_public_ipv4(MAX_ADDRESSES_TRIED), "10.0.0.1")
        inner = ScriptedBackend(clock, {})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(OutboundRequestBlockedError):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert inner.calls == []

    def test_block_is_logged(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A hostname resolving to a private address
        WHEN:
            - The guard connects
        THEN:
            - A warning names the destination and the reason
            - The resolved internal address is not logged
        """
        _answer(mocker, "10.0.0.1")
        guard = _GuardedSyncBackend(ScriptedBackend(clock, {}), allow_internal=False)

        with (
            caplog.at_level(logging.DEBUG, logger="paperless.network"),
            pytest.raises(OutboundRequestBlockedError),
        ):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert "example.com:443" in caplog.text
        assert "non_public_address" in caplog.text
        assert "10.0.0.1" not in caplog.text

    def test_resolves_again_for_every_connection(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A hostname that resolves to a public address, then to a private
              one (DNS rebinding)
        WHEN:
            - The guard opens two connections to it
        THEN:
            - The first connects to the public address
            - The second is blocked and nothing more is dialled
        """
        mocker.patch(
            "paperless.network._getaddrinfo",
            side_effect=[_addrinfo("93.184.216.34"), _addrinfo("10.0.0.1")],
        )
        inner = ScriptedBackend(clock, {})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        guard.connect_tcp("example.com", 443, timeout=5.0)
        with pytest.raises(OutboundRequestBlockedError):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [host for host, _ in inner.calls] == ["93.184.216.34"]

    def test_resolution_failure_is_a_connect_error(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A resolver that fails
        WHEN:
            - The guard connects
        THEN:
            - A connect error is raised, not a policy block
        """
        mocker.patch(
            "paperless.network._getaddrinfo",
            side_effect=socket.gaierror(-2, "Name or service not known"),
        )
        guard = _GuardedSyncBackend(ScriptedBackend(clock, {}), allow_internal=False)

        with pytest.raises(
            httpcore.ConnectError, match=r"Could not resolve example\.com"
        ):
            guard.connect_tcp("example.com", 443, timeout=5.0)

    def test_allow_internal_passes_hostname_through(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - The guard connects
        THEN:
            - The inner backend gets the hostname and no resolution happens
        """
        resolver = _answer(mocker, "10.0.0.1")
        inner = ScriptedBackend(clock, {})
        guard = _GuardedSyncBackend(inner, allow_internal=True)

        guard.connect_tcp("localhost", 8080, timeout=5.0)

        assert inner.calls == [("localhost", 5.0)]
        resolver.assert_not_called()

    def test_unix_sockets_are_refused(self, clock: FakeClock) -> None:
        """
        GIVEN:
            - A guard
        WHEN:
            - A unix socket connection is requested
        THEN:
            - It is blocked with the unix socket reason
        """
        guard = _GuardedSyncBackend(ScriptedBackend(clock, {}), allow_internal=True)

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            guard.connect_unix_socket("/run/app.sock")

        assert exc_info.value.reason is BlockReason.UNIX_SOCKET
        assert exc_info.value.host == "/run/app.sock"

    def test_sleep_delegates(self, clock: FakeClock) -> None:
        """
        GIVEN:
            - A guard
        WHEN:
            - httpcore asks it to sleep between retries
        THEN:
            - The inner backend sleeps
        """
        inner = ScriptedBackend(clock, {})

        _GuardedSyncBackend(inner, allow_internal=False).sleep(0.5)

        assert inner.slept == [0.5]


class TestGuardedAsyncBackend:
    @pytest.fixture(autouse=True)
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_falls_back_to_next_address(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A refusing first address and a working second
        WHEN:
            - The async guard connects
        THEN:
            - Both literals are dialled in order
        """
        _answer(mocker, "2606:4700::1", "93.184.216.1")
        inner = AsyncScriptedBackend(clock, {"2606:4700::1": "refuse"})
        guard = _GuardedAsyncBackend(inner, allow_internal=False)

        await guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [host for host, _ in inner.calls] == ["2606:4700::1", "93.184.216.1"]

    @pytest.mark.anyio
    @pytest.mark.parametrize(("timeout", "count", "expected"), _ATTEMPT_BUDGETS)
    async def test_attempt_budgets(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        timeout: float | None,
        count: int,
        expected: list[float | None],
    ) -> None:
        """
        GIVEN:
            - Every resolved address black-holed
        WHEN:
            - The async guard connects with a given timeout
        THEN:
            - Each attempt gets the prescribed budget
        """
        addresses = _public_ipv4(count)
        _answer(mocker, *addresses)
        inner = AsyncScriptedBackend(clock, dict.fromkeys(addresses, "blackhole"))
        guard = _GuardedAsyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectTimeout):
            await guard.connect_tcp("example.com", 443, timeout=timeout)

        assert [budget for _, budget in inner.calls] == expected

    @pytest.mark.anyio
    async def test_blocks_non_public(
        self, mocker: MockerFixture, clock: FakeClock
    ) -> None:
        """
        GIVEN:
            - A hostname resolving to a private address
        WHEN:
            - The async guard connects
        THEN:
            - It is blocked and nothing is dialled
        """
        _answer(mocker, "10.0.0.1")
        inner = AsyncScriptedBackend(clock, {})
        guard = _GuardedAsyncBackend(inner, allow_internal=False)

        with pytest.raises(OutboundRequestBlockedError):
            await guard.connect_tcp("example.com", 443, timeout=5.0)

        assert inner.calls == []

    @pytest.mark.anyio
    async def test_slow_resolution_times_out(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A resolver slower than the connect timeout
        WHEN:
            - The async guard connects
        THEN:
            - It raises a connect timeout (real time: fail_after follows the
              event loop clock)
        """

        async def slow_resolver(
            *_args: object, **_kwargs: object
        ) -> list[tuple[Any, ...]]:
            await anyio.sleep(0.2)
            return _addrinfo("93.184.216.1")

        mocker.patch("paperless.network._agetaddrinfo", new=slow_resolver)
        guard = _GuardedAsyncBackend(
            AsyncScriptedBackend(FakeClock(), {}),
            allow_internal=False,
        )

        with pytest.raises(httpcore.ConnectTimeout, match="Timed out resolving"):
            await guard.connect_tcp("example.com", 443, timeout=0.05)

    @pytest.mark.anyio
    async def test_resolution_failure_is_a_connect_error(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - An async resolver that fails
        WHEN:
            - The async guard connects
        THEN:
            - A connect error is raised, not a policy block
        """
        mocker.patch(
            "paperless.network._agetaddrinfo",
            new=mocker.AsyncMock(
                side_effect=socket.gaierror(-2, "Name or service not known")
            ),
        )
        guard = _GuardedAsyncBackend(
            AsyncScriptedBackend(clock, {}), allow_internal=False
        )

        with pytest.raises(
            httpcore.ConnectError, match=r"Could not resolve example\.com"
        ):
            await guard.connect_tcp("example.com", 443, timeout=5.0)

    @pytest.mark.anyio
    async def test_allow_internal_passes_hostname_through(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - The async guard connects
        THEN:
            - The inner backend gets the hostname and no resolution happens
        """
        _answer(mocker, "10.0.0.1")
        inner = AsyncScriptedBackend(clock, {})
        guard = _GuardedAsyncBackend(inner, allow_internal=True)

        await guard.connect_tcp("localhost", 8080, timeout=5.0)

        assert inner.calls == [("localhost", 5.0)]

    @pytest.mark.anyio
    async def test_unix_sockets_are_refused(self, clock: FakeClock) -> None:
        """
        GIVEN:
            - An async guard
        WHEN:
            - A unix socket connection is requested
        THEN:
            - It is blocked with the unix socket reason
        """
        guard = _GuardedAsyncBackend(
            AsyncScriptedBackend(clock, {}), allow_internal=True
        )

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            await guard.connect_unix_socket("/run/app.sock")

        assert exc_info.value.reason is BlockReason.UNIX_SOCKET

    @pytest.mark.anyio
    async def test_sleep_delegates(self, clock: FakeClock) -> None:
        """
        GIVEN:
            - An async guard
        WHEN:
            - httpcore asks it to sleep between retries
        THEN:
            - The inner backend sleeps
        """
        inner = AsyncScriptedBackend(clock, {})

        await _GuardedAsyncBackend(inner, allow_internal=False).sleep(0.5)

        assert inner.slept == [0.5]
```

Add `from collections.abc import Iterable` to the test imports as well.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py -v"`
Expected: collection error, `ImportError: cannot import name 'MAX_ADDRESSES_TRIED'`.

- [ ] **Step 3: Implement the backends**

In `src/paperless/network.py`: add `import logging`, `import math`, `import time` and `from typing import Final` to the stdlib imports and `import httpcore` to the third-party imports. Below the imports add `logger = logging.getLogger("paperless.network")`. Next to `_getaddrinfo` / `_agetaddrinfo` add `_monotonic = time.monotonic` and update that comment to mention the clock too. After `aresolve_public_addresses`, add:

```python
MAX_ADDRESSES_TRIED: Final = 8
MIN_ATTEMPT_TIMEOUT: Final = 2.0
MAX_ATTEMPT_TIMEOUT: Final = 10.0


def _require_positive_timeout(host: str, timeout: float | None) -> None:
    # A zero timeout makes the socket non-blocking and a negative one is
    # rejected by settimeout; neither can produce a useful connection attempt.
    if timeout is not None and timeout <= 0:
        raise httpcore.ConnectTimeout(
            f"Connect timeout for {host} must be positive, got {timeout}",
        )


def _deadline(timeout: float | None) -> float:
    return math.inf if timeout is None else _monotonic() + timeout


def _attempt_order(addresses: tuple[IPAddress, ...]) -> list[IPAddress]:
    # Alternate address families, starting with the resolver's first family
    # (RFC 8305 section 4), so one unreachable family cannot delay the other.
    first_version = addresses[0].version
    primary = [a for a in addresses if a.version == first_version]
    secondary = [a for a in addresses if a.version != first_version]
    ordered: list[IPAddress] = []
    for index in range(max(len(primary), len(secondary))):
        ordered.extend(primary[index : index + 1])
        ordered.extend(secondary[index : index + 1])
    return ordered[:MAX_ADDRESSES_TRIED]


def _attempt_timeout(remaining: float, attempts_left: int) -> float:
    """
    Budget for the next attempt. Once the budget is too small to split, or on
    the last address, the attempt gets everything left. Otherwise it gets an
    equal share clamped to [MIN, MAX], always leaving MIN for a later attempt.
    The floor survives one lost SYN; the ceiling bounds how long a black-holed
    address delays the next one.
    """
    if attempts_left == 1 or remaining < 2 * MIN_ATTEMPT_TIMEOUT:
        return remaining
    share = remaining / attempts_left
    return min(
        MAX_ATTEMPT_TIMEOUT,
        max(MIN_ATTEMPT_TIMEOUT, share),
        remaining - MIN_ATTEMPT_TIMEOUT,
    )


def _as_httpcore_timeout(seconds: float) -> float | None:
    return None if math.isinf(seconds) else seconds


def _log_block(error: OutboundRequestBlockedError) -> None:
    logger.warning("Blocked outbound connection: %s", error)


def _budget_exhausted(host: str, tried: int, total: int) -> httpcore.ConnectTimeout:
    return httpcore.ConnectTimeout(
        f"Timed out connecting to {host} after trying {tried} of {total} addresses",
    )


def _resolve_for_connect(host: str, port: int) -> tuple[IPAddress, ...]:
    try:
        return resolve_public_addresses(host, port)
    except OutboundRequestBlockedError as e:
        _log_block(e)
        raise
    except HostResolutionError as e:
        raise httpcore.ConnectError(str(e)) from e


class _GuardedSyncBackend(httpcore.NetworkBackend):
    """
    Wraps httpcore's sync backend. With internal addresses disallowed, it
    resolves the origin host itself, rejects the name if any address is
    non-public, and dials the validated literals so the checked address is
    the connected one. TLS still verifies against the origin hostname.
    """

    def __init__(self, inner: httpcore.NetworkBackend, *, allow_internal: bool) -> None:
        self._inner = inner
        self._allow_internal = allow_internal

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        if self._allow_internal:
            return self._inner.connect_tcp(
                host,
                port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,
            )
        _require_positive_timeout(host, timeout)
        # Resolution is not charged to the budget, matching the stock backend.
        candidates = _attempt_order(_resolve_for_connect(host, port))
        deadline = _deadline(timeout)
        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for index, address in enumerate(candidates):
            remaining = deadline - _monotonic()
            if remaining <= 0:
                raise _budget_exhausted(host, index, len(candidates))
            budget = _attempt_timeout(remaining, len(candidates) - index)
            try:
                return self._inner.connect_tcp(
                    str(address),
                    port,
                    timeout=_as_httpcore_timeout(budget),
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as e:
                logger.debug("Connecting to %s via %s failed: %s", host, address, e)
                last_error = e
        # candidates is never empty, so every address was tried and failed
        raise last_error or _budget_exhausted(host, len(candidates), len(candidates))

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        error = OutboundRequestBlockedError(
            host=path,
            port=None,
            reason=BlockReason.UNIX_SOCKET,
        )
        _log_block(error)
        raise error

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


class _GuardedAsyncBackend(httpcore.AsyncNetworkBackend):
    """Async twin of _GuardedSyncBackend."""

    def __init__(
        self,
        inner: httpcore.AsyncNetworkBackend,
        *,
        allow_internal: bool,
    ) -> None:
        self._inner = inner
        self._allow_internal = allow_internal

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if self._allow_internal:
            return await self._inner.connect_tcp(
                host,
                port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,
            )
        _require_positive_timeout(host, timeout)
        # Resolution counts against the budget, matching the stock backend.
        # This scope closes before dialling; attempts are not nested inside it.
        deadline = _deadline(timeout)
        try:
            with anyio.fail_after(timeout):
                addresses = await aresolve_public_addresses(host, port)
        except TimeoutError as e:
            raise httpcore.ConnectTimeout(f"Timed out resolving {host}") from e
        except OutboundRequestBlockedError as e:
            _log_block(e)
            raise
        except HostResolutionError as e:
            raise httpcore.ConnectError(str(e)) from e
        candidates = _attempt_order(addresses)
        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for index, address in enumerate(candidates):
            remaining = deadline - _monotonic()
            if remaining <= 0:
                raise _budget_exhausted(host, index, len(candidates))
            budget = _attempt_timeout(remaining, len(candidates) - index)
            try:
                return await self._inner.connect_tcp(
                    str(address),
                    port,
                    timeout=_as_httpcore_timeout(budget),
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as e:
                logger.debug("Connecting to %s via %s failed: %s", host, address, e)
                last_error = e
        raise last_error or _budget_exhausted(host, len(candidates), len(candidates))

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        error = OutboundRequestBlockedError(
            host=path,
            port=None,
            reason=BlockReason.UNIX_SOCKET,
        )
        _log_block(error)
        raise error

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py -v"`
Expected: all PASS. If a budget row fails, re-derive it by hand from `_attempt_timeout` before touching the expectation; the table values were worked out against exactly this formula.

- [ ] **Step 5: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless/network.py src/paperless/tests/test_network.py
ruff format src/paperless/network.py src/paperless/tests/test_network.py
git add src/paperless/network.py src/paperless/tests/test_network.py
git commit -m "Guard outbound connections in the httpcore network backend

With internal addresses disallowed, the backend resolves the origin host,
rejects it if any address is non-public, and dials the validated literals
in family-interleaved order under the caller's connect timeout. Resolver
failures surface as connect errors; unix sockets are always refused.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Guarded transports, factories and declared dependencies

**Model tier:** implementer opus; reviews sonnet (spec), opus (security).

**Files:**

- Modify: `src/paperless/network.py` (add `AutoBackend` import, the two transports and two factories after the backends)
- Modify: `pyproject.toml` (dependencies list), `uv.lock` (regenerated)
- Test: `src/paperless/tests/test_network.py` (append a class)

**Interfaces:**

- Consumes: `_GuardedSyncBackend`, `_GuardedAsyncBackend` (Task 3), `validate_outbound_http_url`.
- Produces:
  - `class GuardedHTTPTransport(httpx.HTTPTransport)`: `__init__(self, *, allow_internal: bool) -> None`
  - `class GuardedAsyncHTTPTransport(httpx.AsyncHTTPTransport)`: `__init__(self, *, allow_internal: bool) -> None`
  - `def create_guarded_httpx_client(url: str, *, allow_internal: bool, timeout: float) -> httpx.Client`
  - `def create_guarded_async_httpx_client(url: str, *, allow_internal: bool, timeout: float) -> httpx.AsyncClient`

- [ ] **Step 1: Write the failing tests**

Append to `src/paperless/tests/test_network.py` (add `import ollama` and `from httpcore._backends.auto import AutoBackend`, and import `GuardedAsyncHTTPTransport`, `GuardedHTTPTransport`, `create_guarded_async_httpx_client`, `create_guarded_httpx_client` from `paperless.network`):

```python
class TestGuardedTransports:
    def test_sync_transport_installs_guard(self) -> None:
        """
        GIVEN:
            - A guarded sync transport
        WHEN:
            - It is constructed
        THEN:
            - The httpcore pool dials through the guard wrapping the stock backend
        """
        transport = GuardedHTTPTransport(allow_internal=False)

        assert type(transport._pool) is httpcore.ConnectionPool
        backend = transport._pool._network_backend
        assert isinstance(backend, _GuardedSyncBackend)
        assert type(backend._inner) is httpcore.SyncBackend
        assert backend._allow_internal is False

    def test_async_transport_installs_guard(self) -> None:
        """
        GIVEN:
            - A guarded async transport
        WHEN:
            - It is constructed
        THEN:
            - The httpcore pool dials through the guard wrapping the stock backend
        """
        transport = GuardedAsyncHTTPTransport(allow_internal=True)

        assert type(transport._pool) is httpcore.AsyncConnectionPool
        backend = transport._pool._network_backend
        assert isinstance(backend, _GuardedAsyncBackend)
        assert type(backend._inner) is AutoBackend
        assert backend._allow_internal is True

    def test_sync_transport_refuses_unexpected_layout(
        self, mocker: MockerFixture
    ) -> None:
        """
        GIVEN:
            - An httpcore whose default sync backend is not the expected type
        WHEN:
            - A guarded transport is constructed
        THEN:
            - Construction fails instead of producing an unguarded transport
        """
        mocker.patch.object(httpcore, "SyncBackend", type("OtherBackend", (), {}))

        with pytest.raises(RuntimeError, match="transport layout"):
            GuardedHTTPTransport(allow_internal=False)

    def test_async_transport_refuses_unexpected_layout(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An httpcore whose default async backend is not the expected type
        WHEN:
            - A guarded async transport is constructed
        THEN:
            - Construction fails instead of producing an unguarded transport
        """
        mocker.patch("paperless.network.AutoBackend", type("OtherBackend", (), {}))

        with pytest.raises(RuntimeError, match="transport layout"):
            GuardedAsyncHTTPTransport(allow_internal=False)

    def test_factory_validates_url_first(self) -> None:
        """
        GIVEN:
            - An internal endpoint with internal addresses disallowed
        WHEN:
            - A guarded client is requested
        THEN:
            - The up-front check raises ValueError
        """
        with pytest.raises(ValueError, match="non-public address"):
            create_guarded_httpx_client(
                "http://127.0.0.1:8080",
                allow_internal=False,
                timeout=5.0,
            )

    def test_factory_builds_guarded_clients(self) -> None:
        """
        GIVEN:
            - A public endpoint
        WHEN:
            - Sync and async guarded clients are requested
        THEN:
            - Both use guarded transports and the requested timeout
        """
        with create_guarded_httpx_client(
            "http://93.184.216.34",
            allow_internal=False,
            timeout=5.0,
        ) as client:
            assert isinstance(client._transport, GuardedHTTPTransport)
            assert client.timeout == httpx.Timeout(5.0)

        async_client = create_guarded_async_httpx_client(
            "http://93.184.216.34",
            allow_internal=False,
            timeout=5.0,
        )
        assert isinstance(async_client._transport, GuardedAsyncHTTPTransport)
        assert async_client.timeout == httpx.Timeout(5.0)

    def test_environment_proxies_are_ignored(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        GIVEN:
            - HTTP_PROXY and HTTPS_PROXY set in the environment
        WHEN:
            - A guarded client is built, directly or inside ollama.Client
        THEN:
            - No proxy transport is mounted, so requests go through the guard
        """
        monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")

        with create_guarded_httpx_client(
            "http://93.184.216.34",
            allow_internal=False,
            timeout=5.0,
        ) as client:
            assert client._mounts == {}

        ollama_client = ollama.Client(
            host="http://93.184.216.34:11434",
            transport=GuardedHTTPTransport(allow_internal=False),
        )
        assert ollama_client._client._mounts == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py::TestGuardedTransports -v"`
Expected: collection error, `ImportError: cannot import name 'GuardedAsyncHTTPTransport'`.

- [ ] **Step 3: Implement transports and factories**

In `src/paperless/network.py` add, after `import httpx`:

```python
# Not exported by httpcore; the guard asserts it is still the async default.
from httpcore._backends.auto import AutoBackend
```

After `_GuardedAsyncBackend`, add:

```python
_LAYOUT_ERROR = (
    "Unexpected httpx transport layout; refusing to create a transport "
    "without the outbound connection guard"
)


class GuardedHTTPTransport(httpx.HTTPTransport):
    """
    httpx transport whose connections pass through the outbound guard.

    Deliberately accepts no proxy, uds or retries options: a proxy would be
    dialled instead of the destination, and a unix socket bypasses TCP
    entirely. Adding an option here is a reviewed change, not a pass-through.
    """

    def __init__(self, *, allow_internal: bool) -> None:
        super().__init__()
        # httpx has no public hook for the network backend. Check the exact
        # layout before swapping so an httpx or httpcore change fails loudly.
        pool = self._pool
        if (
            type(pool) is not httpcore.ConnectionPool
            or type(pool._network_backend) is not httpcore.SyncBackend
        ):
            raise RuntimeError(_LAYOUT_ERROR)
        pool._network_backend = _GuardedSyncBackend(
            pool._network_backend,
            allow_internal=allow_internal,
        )


class GuardedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """Async twin of GuardedHTTPTransport."""

    def __init__(self, *, allow_internal: bool) -> None:
        super().__init__()
        pool = self._pool
        if (
            type(pool) is not httpcore.AsyncConnectionPool
            or type(pool._network_backend) is not AutoBackend
        ):
            raise RuntimeError(_LAYOUT_ERROR)
        pool._network_backend = _GuardedAsyncBackend(
            pool._network_backend,
            allow_internal=allow_internal,
        )


def create_guarded_httpx_client(
    url: str,
    *,
    allow_internal: bool,
    timeout: float,
) -> httpx.Client:
    """
    Validate ``url`` up front, then build a client that re-checks at connect
    time. The up-front check turns static misconfiguration into a ValueError
    before any retry layer sees it.
    """
    validate_outbound_http_url(url, allow_internal=allow_internal)
    return httpx.Client(
        transport=GuardedHTTPTransport(allow_internal=allow_internal),
        timeout=timeout,
    )


def create_guarded_async_httpx_client(
    url: str,
    *,
    allow_internal: bool,
    timeout: float,
) -> httpx.AsyncClient:
    """Async twin of create_guarded_httpx_client."""
    validate_outbound_http_url(url, allow_internal=allow_internal)
    return httpx.AsyncClient(
        transport=GuardedAsyncHTTPTransport(allow_internal=allow_internal),
        timeout=timeout,
    )
```

The layout checks must reference `httpcore.SyncBackend` and `AutoBackend` through their module-level names at call time (as written), because the drift tests patch those names. Do not use `assert` for the layout check in production code; it is stripped under `python -O`.

- [ ] **Step 4: Declare the dependencies**

In `pyproject.toml` `[project] dependencies`, insert in alphabetical position:

- `"anyio>=4.12",` before `"azure-ai-documentintelligence>=1.0.2",`
- `"httpcore~=1.0.9",` and `"httpx~=0.28.1",` before `"httpx-oauth~=0.17",`

Then regenerate the lock (works on Windows):

```bash
uv lock
git diff --stat uv.lock
```

Expected: no package version changes; the only `uv.lock` diff is the three new `requires-dist` entries for `paperless-ngx`. Any other change: stop and report it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py -v"`
Expected: all PASS.

- [ ] **Step 6: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless/network.py src/paperless/tests/test_network.py
ruff format src/paperless/network.py src/paperless/tests/test_network.py
git add src/paperless/network.py src/paperless/tests/test_network.py pyproject.toml uv.lock
git commit -m "Add guarded httpx transports and client factories

The transports install the outbound guard on httpcore's connection pool
after checking its exact layout, and accept no proxy, uds or retries
options. httpx, httpcore and anyio become declared dependencies, pinned
narrowly where private attributes are relied on.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Real-socket test helpers and integration tests

**Model tier:** implementer sonnet; reviews sonnet (spec), opus (security).

**Files:**

- Create: `src/paperless_testing/outbound.py` (the shared test-support package, which is already excluded from the Docker image and from coverage)
- Modify: `src/conftest.py` (thin fixtures that import from `paperless_testing.outbound` inside their bodies)
- Create: `src/paperless/tests/test_network_integration.py`

The shared helpers live in `paperless_testing`, not under any app's `tests/` package, so the `documents` and `paperless_ai` tests can use them without importing test helpers across app boundaries. The fixtures are registered once in the root `src/conftest.py`, following its rule that module-scope imports stay minimal: each fixture imports what it needs in its body.

**Interfaces:**

- Consumes: `GuardedHTTPTransport`, `GuardedAsyncHTTPTransport`, `OutboundRequestBlockedError`, `_GuardedSyncBackend`, `_GuardedAsyncBackend`.
- Produces (in `paperless_testing.outbound`):
  - `class ReceivedRequest` (dataclass: `method: str`, `path: str`, `headers: dict[str, str]` with lower-cased keys, `body: bytes`)
  - `class LocalHTTPServer` (dataclass: `port: int`, `requests: list[ReceivedRequest]`, `connections: int`, `redirect_to: str | None`)
  - `class FakeDNS` with `add(hostname: str, *addresses: str) -> None` and `lookups: list[str]`
  - `class DialRecorder` with `hosts() -> list[str]`
  - `def running_http_server() -> Iterator[LocalHTTPServer]` (context manager), `def install_fake_dns(mocker) -> FakeDNS`, `def install_dial_recorder(mocker) -> DialRecorder`
  - `def guard_of(client: httpx.Client | httpx.AsyncClient) -> _GuardedSyncBackend | _GuardedAsyncBackend`
- Produces (in `src/conftest.py`): fixtures `local_http_server`, `fake_dns`, `dial_recorder`, available to every app's tests.

- [ ] **Step 1: Create the helper module**

Create `src/paperless_testing/outbound.py`:

```python
"""
Real-socket helpers for tests of the outbound connection guard in
paperless.network: a local HTTP server, a per-hostname resolver fake and
spies recording which addresses were actually dialled.

The fixtures wrapping these live in the root conftest.
"""

from __future__ import annotations

import http.server
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

import anyio
import httpcore

from paperless.network import GuardedAsyncHTTPTransport
from paperless.network import GuardedHTTPTransport
from paperless.network import _GuardedAsyncBackend
from paperless.network import _GuardedSyncBackend

if TYPE_CHECKING:
    from collections.abc import Iterator

    import httpx
    from unittest.mock import MagicMock
    from unittest.mock import _Call

    from pytest_mock import MockerFixture

_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_AGETADDRINFO = anyio.getaddrinfo


@dataclass
class ReceivedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class LocalHTTPServer:
    """State of a threaded HTTP server bound to 127.0.0.1 on an ephemeral port."""

    port: int
    requests: list[ReceivedRequest] = field(default_factory=list)
    connections: int = 0
    redirect_to: str | None = None


class _Handler(http.server.BaseHTTPRequestHandler):
    # HTTP/1.1 keeps connections open, so tests can observe connection reuse.
    # Every response sets Content-Length, which keep-alive requires.
    protocol_version = "HTTP/1.1"
    server: _RecordingHTTPServer

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        state = self.server.state
        state.requests.append(
            ReceivedRequest(
                method=self.command,
                path=self.path,
                headers={key.lower(): value for key, value in self.headers.items()},
                body=body,
            ),
        )
        if state.redirect_to is not None:
            self.send_response(302)
            self.send_header("Location", state.redirect_to)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    do_GET = _handle
    do_POST = _handle

    def log_message(self, format: str, *args: Any) -> None:
        return None


class _RecordingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.state = LocalHTTPServer(port=self.socket.getsockname()[1])

    def verify_request(self, request: Any, client_address: Any) -> bool:
        self.state.connections += 1
        return True


@contextmanager
def running_http_server() -> Iterator[LocalHTTPServer]:
    """Serve on 127.0.0.1 in a background thread until the block exits."""
    server = _RecordingHTTPServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _addrinfo(address: str, port: int | None) -> tuple[Any, ...]:
    if ":" in address:
        return (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port or 0, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 0))


class FakeDNS:
    """
    Answers the guard's resolver hooks for registered names and delegates
    every other name to the real resolver. The stock httpcore backends keep
    using the unpatched socket.getaddrinfo.
    """

    def __init__(self) -> None:
        self._answers: dict[str, list[str]] = {}
        self.lookups: list[str] = []

    def add(self, hostname: str, *addresses: str) -> None:
        self._answers[hostname] = list(addresses)

    def getaddrinfo(
        self,
        host: str,
        port: int | None,
        *args: Any,
        **kwargs: Any,
    ) -> list[tuple[Any, ...]]:
        self.lookups.append(host)
        if host in self._answers:
            return [_addrinfo(address, port) for address in self._answers[host]]
        return list(_REAL_GETADDRINFO(host, port, *args, **kwargs))

    async def agetaddrinfo(
        self,
        host: str,
        port: int | None,
        **kwargs: Any,
    ) -> list[tuple[Any, ...]]:
        self.lookups.append(host)
        if host in self._answers:
            return [_addrinfo(address, port) for address in self._answers[host]]
        return list(await _REAL_AGETADDRINFO(host, port, **kwargs))


def install_fake_dns(mocker: MockerFixture) -> FakeDNS:
    """Patch the guard's resolver hooks with a FakeDNS for the current test."""
    dns = FakeDNS()
    mocker.patch("paperless.network._getaddrinfo", new=dns.getaddrinfo)
    mocker.patch("paperless.network._agetaddrinfo", new=dns.agetaddrinfo)
    return dns


def _dialled_host(call: _Call) -> str:
    # The spy sits on the class, so args[0] is the backend instance.
    if "host" in call.kwargs:
        return str(call.kwargs["host"])
    return str(call.args[1])


@dataclass
class DialRecorder:
    sync_spy: MagicMock
    async_spy: MagicMock

    def hosts(self) -> list[str]:
        calls = [*self.sync_spy.call_args_list, *self.async_spy.call_args_list]
        return [_dialled_host(call) for call in calls]


def install_dial_recorder(mocker: MockerFixture) -> DialRecorder:
    """Spy on the stock backends' connect_tcp for the current test."""
    return DialRecorder(
        sync_spy=mocker.spy(httpcore.SyncBackend, "connect_tcp"),
        async_spy=mocker.spy(httpcore.AnyIOBackend, "connect_tcp"),
    )


def guard_of(
    client: httpx.Client | httpx.AsyncClient,
) -> _GuardedSyncBackend | _GuardedAsyncBackend:
    """Return the guard installed on a client's transport."""
    transport = client._transport
    assert isinstance(transport, GuardedHTTPTransport | GuardedAsyncHTTPTransport)
    backend = transport._pool._network_backend
    assert isinstance(backend, _GuardedSyncBackend | _GuardedAsyncBackend)
    return backend
```

- [ ] **Step 2: Register the fixtures in the root conftest**

In `src/conftest.py`, add to the `if TYPE_CHECKING:` block (keeping its import ordering):

```python
    from pytest_mock import MockerFixture

    from paperless_testing.outbound import DialRecorder
    from paperless_testing.outbound import FakeDNS
    from paperless_testing.outbound import LocalHTTPServer
```

and append these fixtures at the end of the file. They import inside the body, like the existing `paperless_dirs` fixture, so sessions that never use them do not import httpx or `paperless.network`:

```python
@pytest.fixture
def local_http_server() -> Generator[LocalHTTPServer, None, None]:
    """A recording HTTP server on 127.0.0.1, for outbound connection tests."""
    from paperless_testing.outbound import running_http_server

    with running_http_server() as server:
        yield server


@pytest.fixture
def fake_dns(mocker: MockerFixture) -> FakeDNS:
    """Per-hostname answers for the outbound guard's resolver hooks."""
    from paperless_testing.outbound import install_fake_dns

    return install_fake_dns(mocker)


@pytest.fixture
def dial_recorder(mocker: MockerFixture) -> DialRecorder:
    """Records which addresses the outbound guard actually dialled."""
    from paperless_testing.outbound import install_dial_recorder

    return install_dial_recorder(mocker)
```

- [ ] **Step 3: Write the integration tests**

Create `src/paperless/tests/test_network_integration.py`:

```python
import ipaddress
import os

import httpcore
import httpx
import pytest
from pytest_mock import MockerFixture

from paperless.network import GuardedAsyncHTTPTransport
from paperless.network import GuardedHTTPTransport
from paperless.network import OutboundRequestBlockedError
from paperless_testing.outbound import DialRecorder
from paperless_testing.outbound import FakeDNS
from paperless_testing.outbound import LocalHTTPServer


class TestGuardedTransportSync:
    def test_pinned_connection_falls_back_to_next_address(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - A hostname resolving to ::1 then 127.0.0.1
            - A server listening on 127.0.0.1 only
            - Internal addresses disallowed, with loopback treated as public
        WHEN:
            - A request is made
        THEN:
            - ::1 fails, 127.0.0.1 is dialled next and the request succeeds
        """
        fake_dns.add("dual-stack.test", "::1", "127.0.0.1")
        mocker.patch("paperless.network.is_public_ip", return_value=True)

        with httpx.Client(
            transport=GuardedHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            response = client.get(f"http://dual-stack.test:{local_http_server.port}/")

        assert response.status_code == 200
        assert dial_recorder.hosts() == ["::1", "127.0.0.1"]

    def test_allow_internal_uses_stock_resolution(
        self,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
    ) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - A request is made to localhost
        THEN:
            - It succeeds without the guard resolving anything
        """
        with httpx.Client(
            transport=GuardedHTTPTransport(allow_internal=True),
            timeout=5.0,
        ) as client:
            response = client.get(f"http://localhost:{local_http_server.port}/")

        assert response.status_code == 200
        assert fake_dns.lookups == []

    def test_blocks_internal_host_without_connecting(
        self,
        local_http_server: LocalHTTPServer,
    ) -> None:
        """
        GIVEN:
            - Internal addresses disallowed
        WHEN:
            - A request is made to localhost through the transport
        THEN:
            - It is blocked and the server never sees a connection
        """
        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
            ) as client,
            pytest.raises(OutboundRequestBlockedError),
        ):
            client.get(f"http://localhost:{local_http_server.port}/")

        assert local_http_server.connections == 0

    def test_host_header_is_the_hostname(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
    ) -> None:
        """
        GIVEN:
            - A pinned connection to a named host
        WHEN:
            - A request is made
        THEN:
            - The server receives the hostname in Host, not the dialled IP
        """
        fake_dns.add("pinned.test", "127.0.0.1")
        mocker.patch("paperless.network.is_public_ip", return_value=True)

        with httpx.Client(
            transport=GuardedHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            client.get(f"http://pinned.test:{local_http_server.port}/")

        assert local_http_server.requests[0].headers["host"] == (
            f"pinned.test:{local_http_server.port}"
        )

    def test_redirect_to_internal_host_is_blocked(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - An allowed origin that redirects to a host resolving to a blocked
              address, and a client that follows redirects
        WHEN:
            - The origin is requested
        THEN:
            - The redirect hop is blocked without dialling the blocked address
        """
        allowed = ipaddress.ip_address("127.0.0.1")
        mocker.patch(
            "paperless.network.is_public_ip",
            side_effect=lambda address: address == allowed,
        )
        fake_dns.add("origin.test", "127.0.0.1")
        fake_dns.add("internal.test", "127.0.0.2")
        local_http_server.redirect_to = (
            f"http://internal.test:{local_http_server.port}/"
        )

        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
                follow_redirects=True,
            ) as client,
            pytest.raises(OutboundRequestBlockedError) as exc_info,
        ):
            client.get(f"http://origin.test:{local_http_server.port}/")

        assert exc_info.value.address == ipaddress.ip_address("127.0.0.2")
        assert dial_recorder.hosts() == ["127.0.0.1"]
        assert len(local_http_server.requests) == 1

    def test_connections_are_not_shared_between_hosts_on_one_address(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - Two hostnames resolving to the same address
            - Internal addresses disallowed, with loopback treated as public
        WHEN:
            - One client requests the first host twice, then the second host
        THEN:
            - The first host's connection is reused for its second request
            - The second host gets its own connection, so its certificate would
              be checked rather than inheriting the first host's session
        """
        fake_dns.add("first.test", "127.0.0.1")
        fake_dns.add("second.test", "127.0.0.1")
        mocker.patch("paperless.network.is_public_ip", return_value=True)

        with httpx.Client(
            transport=GuardedHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            client.get(f"http://first.test:{local_http_server.port}/")
            client.get(f"http://first.test:{local_http_server.port}/")
            client.get(f"http://second.test:{local_http_server.port}/")

        assert dial_recorder.hosts() == ["127.0.0.1", "127.0.0.1"]
        assert local_http_server.connections == 2
        assert [request.headers["host"] for request in local_http_server.requests] == [
            f"first.test:{local_http_server.port}",
            f"first.test:{local_http_server.port}",
            f"second.test:{local_http_server.port}",
        ]

    def test_tls_uses_the_hostname_not_the_dialled_address(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - A pinned HTTPS connection to a named host
            - A plain HTTP server, so the handshake itself fails
        WHEN:
            - A request is made
        THEN:
            - The validated address is dialled
            - TLS is started with the hostname for SNI and certificate checks
        """
        fake_dns.add("pinned.test", "127.0.0.1")
        mocker.patch("paperless.network.is_public_ip", return_value=True)
        start_tls = mocker.spy(httpcore._backends.sync.SyncStream, "start_tls")

        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
            ) as client,
            pytest.raises(httpx.ConnectError),
        ):
            client.get(f"https://pinned.test:{local_http_server.port}/")

        assert dial_recorder.hosts() == ["127.0.0.1"]
        start_tls.assert_called_once()
        assert start_tls.call_args.kwargs["server_hostname"] == "pinned.test"

    @pytest.mark.parametrize(
        "host",
        [
            pytest.param("2130706433", id="decimal"),
            pytest.param("0x7f.1", id="hex-short"),
            pytest.param("127.1", id="short-dotted"),
        ],
    )
    def test_numeric_host_forms_are_blocked(
        self,
        local_http_server: LocalHTTPServer,
        host: str,
    ) -> None:
        """
        GIVEN:
            - Internal addresses disallowed
            - A URL whose host is a non-canonical spelling of 127.0.0.1
        WHEN:
            - A request is made through the transport
        THEN:
            - The resolved address is checked, the request is blocked and the
              server never sees a connection
        """
        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
            ) as client,
            pytest.raises(OutboundRequestBlockedError),
        ):
            client.get(f"http://{host}:{local_http_server.port}/")

        assert local_http_server.connections == 0

    def test_environment_proxy_is_not_used(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
    ) -> None:
        """
        GIVEN:
            - Proxy variables in the environment pointing at an unreachable proxy
            - Internal addresses disallowed
        WHEN:
            - A request is made to localhost
        THEN:
            - The guard blocks it, rather than the request going to the proxy
        """
        unreachable = "http://127.0.0.1:9"
        mocker.patch.dict(
            os.environ,
            {
                "HTTP_PROXY": unreachable,
                "HTTPS_PROXY": unreachable,
                "ALL_PROXY": unreachable,
            },
        )

        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
            ) as client,
            pytest.raises(OutboundRequestBlockedError),
        ):
            client.get(f"http://localhost:{local_http_server.port}/")

        assert local_http_server.connections == 0


class TestGuardedTransportAsync:
    @pytest.fixture(autouse=True)
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_pinned_connection_falls_back_to_next_address(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - A hostname resolving to ::1 then 127.0.0.1
            - A server listening on 127.0.0.1 only
            - Internal addresses disallowed, with loopback treated as public
        WHEN:
            - An async request is made
        THEN:
            - ::1 fails, 127.0.0.1 is dialled next and the request succeeds
        """
        fake_dns.add("dual-stack.test", "::1", "127.0.0.1")
        mocker.patch("paperless.network.is_public_ip", return_value=True)

        async with httpx.AsyncClient(
            transport=GuardedAsyncHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            response = await client.get(
                f"http://dual-stack.test:{local_http_server.port}/",
            )

        assert response.status_code == 200
        assert dial_recorder.hosts() == ["::1", "127.0.0.1"]

    @pytest.mark.anyio
    async def test_allow_internal_uses_stock_resolution(
        self,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
    ) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - An async request is made to localhost
        THEN:
            - It succeeds without the guard resolving anything
        """
        async with httpx.AsyncClient(
            transport=GuardedAsyncHTTPTransport(allow_internal=True),
            timeout=5.0,
        ) as client:
            response = await client.get(f"http://localhost:{local_http_server.port}/")

        assert response.status_code == 200
        assert fake_dns.lookups == []

    @pytest.mark.anyio
    async def test_blocks_internal_host_without_connecting(
        self,
        local_http_server: LocalHTTPServer,
    ) -> None:
        """
        GIVEN:
            - Internal addresses disallowed
        WHEN:
            - An async request is made to localhost through the transport
        THEN:
            - It is blocked and the server never sees a connection
        """
        async with httpx.AsyncClient(
            transport=GuardedAsyncHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            with pytest.raises(OutboundRequestBlockedError):
                await client.get(f"http://localhost:{local_http_server.port}/")

        assert local_http_server.connections == 0
```

- [ ] **Step 4: Run the tests**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network_integration.py src/paperless/tests/test_network.py -v"`
Expected: all PASS. These exercise code that already exists, so they pass on first run. To prove they test something, make each temporary change below, confirm the named tests fail, then revert it:

- `_attempt_order` returning `list(addresses[:1])`: both fallback tests fail.
- The sync guard dialling `host` instead of `str(address)`: `test_connections_are_not_shared_between_hosts_on_one_address` and `test_tls_uses_the_hostname_not_the_dialled_address` fail.

- [ ] **Step 5: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless_testing/outbound.py src/paperless/tests/test_network_integration.py src/conftest.py
ruff format src/paperless_testing/outbound.py src/paperless/tests/test_network_integration.py src/conftest.py
git add src/paperless_testing/outbound.py src/paperless/tests/test_network_integration.py src/conftest.py
git commit -m "Add real-socket tests for the outbound connection guard

A local HTTP server, a per-hostname resolver fake and dial spies exercise
the guarded transports end to end: address fallback, blocking before any
connection, the Host header, TLS server name, per-host connection pooling,
numeric host spellings, environment proxies and redirects to blocked hosts.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: AI clients on guarded transports

**Model tier:** implementer sonnet; reviews sonnet (spec), sonnet (quality).

**Files:**

- Modify: `src/paperless_ai/client.py:17-20` imports, `get_llm` (lines 56-119)
- Modify: `src/paperless_ai/embedding.py:12-15` imports, `get_embedding_model` (lines 23-95)
- Test: `src/paperless_ai/tests/test_client.py`, `src/paperless_ai/tests/test_embedding.py` (append classes)

**Interfaces:**

- Consumes: `GuardedHTTPTransport`, `GuardedAsyncHTTPTransport`, `create_guarded_httpx_client`, `create_guarded_async_httpx_client` (Task 4); `guard_of` (Task 5).

- [ ] **Step 1: Write the failing tests**

Append to `src/paperless_ai/tests/test_client.py` (add `from paperless_testing.outbound import guard_of`):

```python
class TestGuardedLLMClients:
    @pytest.mark.parametrize(
        ("endpoint", "allow_internal"),
        [
            pytest.param("http://test-url", True, id="internal-allowed"),
            pytest.param("http://93.184.216.34:11434", False, id="internal-blocked"),
        ],
    )
    def test_ollama_clients_are_guarded(
        self,
        mock_ai_config: MagicMock,
        mock_ollama_llm: MagicMock,
        endpoint: str,
        *,
        allow_internal: bool,
    ) -> None:
        """
        GIVEN:
            - The Ollama backend
        WHEN:
            - The LLM is built
        THEN:
            - Its sync and async clients use guarded transports with the setting
        """
        mock_ai_config.llm_backend = "ollama"
        mock_ai_config.llm_model = "test_model"
        mock_ai_config.llm_endpoint = endpoint
        mock_ai_config.llm_allow_internal_endpoints = allow_internal

        AIClient()

        kwargs = mock_ollama_llm.call_args.kwargs
        assert guard_of(kwargs["client"]._client)._allow_internal is allow_internal
        assert (
            guard_of(kwargs["async_client"]._client)._allow_internal is allow_internal
        )

    @pytest.mark.parametrize(
        ("endpoint", "allow_internal"),
        [
            pytest.param("http://test-url", True, id="internal-allowed"),
            pytest.param("http://93.184.216.34:8080", False, id="internal-blocked"),
        ],
    )
    def test_openai_like_clients_are_guarded(
        self,
        mock_ai_config: MagicMock,
        mock_openai_llm: MagicMock,
        endpoint: str,
        *,
        allow_internal: bool,
    ) -> None:
        """
        GIVEN:
            - The OpenAI-like backend with an endpoint
        WHEN:
            - The LLM is built
        THEN:
            - Its sync and async http clients use guarded transports
        """
        mock_ai_config.llm_backend = "openai-like"
        mock_ai_config.llm_model = "test_model"
        mock_ai_config.llm_api_key = "key"
        mock_ai_config.llm_endpoint = endpoint
        mock_ai_config.llm_allow_internal_endpoints = allow_internal

        AIClient()

        kwargs = mock_openai_llm.call_args.kwargs
        assert guard_of(kwargs["http_client"])._allow_internal is allow_internal
        assert guard_of(kwargs["async_http_client"])._allow_internal is allow_internal
```

Append to `src/paperless_ai/tests/test_embedding.py` (add `from pytest_mock import MockerFixture` and `from paperless_testing.outbound import guard_of`):

```python
class TestGuardedEmbeddingClients:
    def test_ollama_embedding_clients_are_guarded(
        self,
        mocker: MockerFixture,
        mock_ai_config: MagicMock,
    ) -> None:
        """
        GIVEN:
            - The Ollama embedding backend
        WHEN:
            - The embedding model is built
        THEN:
            - The clients swapped onto it use guarded transports
        """
        config = mock_ai_config.return_value
        config.llm_embedding_backend = LLMEmbeddingBackend.OLLAMA
        config.llm_embedding_model = "embeddinggemma"
        config.llm_endpoint = "http://93.184.216.34:11434"
        config.llm_allow_internal_endpoints = False

        mocker.patch("llama_index.embeddings.ollama.OllamaEmbedding")

        model = get_embedding_model(config)

        assert guard_of(model._client._client)._allow_internal is False
        assert guard_of(model._async_client._client)._allow_internal is False

    def test_openai_like_embedding_clients_are_guarded(
        self,
        mocker: MockerFixture,
        mock_ai_config: MagicMock,
    ) -> None:
        """
        GIVEN:
            - The OpenAI-like embedding backend with an endpoint
        WHEN:
            - The embedding model is built
        THEN:
            - Its http clients use guarded transports
        """
        config = mock_ai_config.return_value
        config.llm_embedding_backend = LLMEmbeddingBackend.OPENAI_LIKE
        config.llm_embedding_model = "text-embedding-3-small"
        config.llm_api_key = "key"
        config.llm_endpoint = "http://93.184.216.34:8080"
        config.llm_allow_internal_endpoints = False

        embedding_class = mocker.patch(
            "llama_index.embeddings.openai_like.OpenAILikeEmbedding",
        )

        get_embedding_model(config)

        kwargs = embedding_class.call_args.kwargs
        assert guard_of(kwargs["http_client"])._allow_internal is False
        assert guard_of(kwargs["async_http_client"])._allow_internal is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_client.py::TestGuardedLLMClients src/paperless_ai/tests/test_embedding.py::TestGuardedEmbeddingClients -v"`
Expected: FAIL with `AssertionError` inside `guard_of` (the transports are still the old pinned ones).

- [ ] **Step 3: Switch the consumers**

In `src/paperless_ai/client.py` replace the four `PinnedHost*` / `create_pinned_*` imports with:

```python
from paperless.network import GuardedAsyncHTTPTransport
from paperless.network import GuardedHTTPTransport
from paperless.network import create_guarded_async_httpx_client
from paperless.network import create_guarded_httpx_client
```

and in `get_llm`: `PinnedHostHTTPTransport(` becomes `GuardedHTTPTransport(`, `PinnedHostAsyncHTTPTransport(` becomes `GuardedAsyncHTTPTransport(`, `create_pinned_httpx_client(` becomes `create_guarded_httpx_client(`, `create_pinned_async_httpx_client(` becomes `create_guarded_async_httpx_client(`. Arguments are unchanged (`allow_internal=...` and, for the factories, `timeout=self.settings.llm_request_timeout`).

Make the same four import and call replacements in `src/paperless_ai/embedding.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests -v"`
Expected: all PASS.

- [ ] **Step 5: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless_ai/client.py src/paperless_ai/embedding.py src/paperless_ai/tests/test_client.py src/paperless_ai/tests/test_embedding.py
ruff format src/paperless_ai/client.py src/paperless_ai/embedding.py src/paperless_ai/tests/test_client.py src/paperless_ai/tests/test_embedding.py
git add src/paperless_ai/client.py src/paperless_ai/embedding.py src/paperless_ai/tests/test_client.py src/paperless_ai/tests/test_embedding.py
git commit -m "Use guarded transports for AI LLM and embedding clients

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: AI block error surfaces

**Model tier:** implementer sonnet; reviews sonnet (spec), sonnet (quality).

**Files:**

- Modify: `src/paperless_ai/exceptions.py`, `src/paperless_ai/client.py` (`_normalize_errors`, imports), `src/documents/views.py` (imports around lines 259-260; `ai_suggestions` except chain around lines 1661-1698)
- Test: `src/paperless_ai/tests/test_client.py`, `src/documents/tests/test_views.py` (`TestAISuggestions`), `src/documents/tests/test_tasks.py` (`TestApplyAISuggestionsTask`)

**Interfaces:**

- Consumes: `OutboundRequestBlockedError`, `BlockReason` (Task 1).
- Produces: `class LLMBlockedError(Exception)` in `paperless_ai.exceptions`.

- [ ] **Step 1: Write the failing tests**

Append to `src/paperless_ai/tests/test_client.py` (add `import ipaddress`, `from paperless.network import BlockReason`, `from paperless.network import OutboundRequestBlockedError`, `from paperless_ai.exceptions import LLMBlockedError`):

```python
def _block() -> OutboundRequestBlockedError:
    return OutboundRequestBlockedError(
        host="llm.example",
        port=443,
        reason=BlockReason.NON_PUBLIC_ADDRESS,
        address=ipaddress.ip_address("10.0.0.1"),
    )


class TestBlockedLLMRequests:
    def test_ollama_block_becomes_llm_blocked_error(
        self,
        mock_ai_config: MagicMock,
        mock_ollama_llm: MagicMock,
    ) -> None:
        """
        GIVEN:
            - The Ollama backend and a connection blocked by policy
        WHEN:
            - An LLM query runs
        THEN:
            - LLMBlockedError is raised with a message, chained to the block
            - The message, which tracked tasks store, names the destination but
              not the resolved internal address
        """
        mock_ai_config.llm_backend = "ollama"
        mock_ai_config.llm_model = "test_model"
        mock_ai_config.llm_endpoint = "http://test-url"
        block = _block()
        mock_ollama_llm.return_value.chat.side_effect = block

        with pytest.raises(LLMBlockedError) as exc_info:
            AIClient().run_llm_query("test_prompt")

        assert exc_info.value.__cause__ is block
        assert "llm.example:443" in str(exc_info.value)
        assert "10.0.0.1" not in str(exc_info.value)

    def test_openai_wrapped_block_becomes_llm_blocked_error(
        self,
        mock_ai_config: MagicMock,
        mock_openai_llm: MagicMock,
    ) -> None:
        """
        GIVEN:
            - The OpenAI-like backend, whose SDK wraps the block in
              APIConnectionError
        WHEN:
            - An LLM query runs
        THEN:
            - LLMBlockedError is raised
        """
        mock_ai_config.llm_backend = "openai-like"
        mock_ai_config.llm_model = "test_model"
        mock_ai_config.llm_api_key = "key"
        mock_ai_config.llm_endpoint = "http://test-url"
        wrapped = openai.APIConnectionError(
            request=httpx.Request("POST", "http://test-url/v1/chat/completions"),
        )
        wrapped.__cause__ = _block()
        mock_openai_llm.return_value.chat_with_tools.side_effect = wrapped

        with pytest.raises(LLMBlockedError):
            AIClient().run_llm_query("test_prompt")
```

Add to `TestAISuggestions` in `src/documents/tests/test_views.py` (next to `test_ai_suggestions_with_llm_provider_error`; import `LLMBlockedError` beside the other `paperless_ai.exceptions` imports):

```python
    @patch("documents.views.get_ai_document_classification")
    @override_settings(
        AI_ENABLED=True,
        LLM_BACKEND="openai-like",
    )
    def test_ai_suggestions_with_blocked_llm_request(
        self,
        mock_get_ai_classification,
    ) -> None:
        """
        GIVEN:
            - An AI backend request blocked by the outbound request policy
        WHEN:
            - AI suggestions are requested
        THEN:
            - 502 is returned with a generic message and nothing is cached
        """
        mock_get_ai_classification.side_effect = LLMBlockedError(
            "AI backend request was blocked by the outbound request policy: detail",
        )

        self.client.force_login(user=self.user)
        response = self.client.get(
            f"/api/documents/{self.document.pk}/ai_suggestions/",
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(
            response.json(),
            {
                "ai": [
                    "AI backend request was blocked by the outbound request policy. "
                    "Check logs for details.",
                ],
            },
        )
        self.assertIsNone(
            get_llm_suggestion_cache(self.document.pk, backend="openai-like"),
        )
```

Add to `TestApplyAISuggestionsTask` in `src/documents/tests/test_tasks.py` (import `from paperless_ai.exceptions import LLMBlockedError`):

```python
def test_blocked_request_fails_without_retry(self) -> None:
    """
    GIVEN:
        - AI enabled and a document with content
        - The AI classification call blocked by the outbound request policy
    WHEN:
        - The task runs through Celery
    THEN:
        - The workflow code does not swallow the block
        - The task fails with LLMBlockedError and is never retried
    """
    with (
        mock.patch(
            "documents.workflows.ai.get_ai_document_classification",
            side_effect=LLMBlockedError(
                "AI backend request was blocked by the outbound request policy: detail",
            ),
        ),
        mock.patch.object(
            tasks.apply_ai_suggestions,
            "retry",
            wraps=tasks.apply_ai_suggestions.retry,
        ) as retry,
    ):
        result = tasks.apply_ai_suggestions.apply(
            args=(self.action.pk, self.doc.pk),
        )

    self.assertTrue(result.failed())
    self.assertIsInstance(result.result, LLMBlockedError)
    retry.assert_not_called()
```

The patch targets the name `documents/workflows/ai.py` imported, so its `except ValueError` runs for real. `apply_ai_suggestions_to_document` returns early unless AI is enabled in `AIConfig` and the document has non-blank content: make sure the test's setup satisfies both (the existing `setUp` document has content; enable AI the way neighbouring AI tests in this file or in `documents/tests/test_workflows.py` do). If the early-return guards are not satisfied, the test would pass vacuously on `retry.assert_not_called()` but fail `result.failed()`; that assertion is what proves the block reached the task.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_client.py::TestBlockedLLMRequests src/documents/tests/test_views.py::TestAISuggestions::test_ai_suggestions_with_blocked_llm_request src/documents/tests/test_tasks.py::TestApplyAISuggestionsTask::test_blocked_request_fails_without_retry -v"`
Expected: collection error, `ImportError: cannot import name 'LLMBlockedError'`.

- [ ] **Step 3: Implement**

Append to `src/paperless_ai/exceptions.py`:

```python
class LLMBlockedError(Exception):
    """The outbound request policy refused the connection to the LLM backend."""
```

In `src/paperless_ai/client.py` add imports `from paperless.network import OutboundRequestBlockedError` and `from paperless_ai.exceptions import LLMBlockedError`, add this module-level helper above `class AIClient`:

```python
def _find_blocked_cause(exc: BaseException) -> OutboundRequestBlockedError | None:
    # The openai SDK wraps transport errors in APIConnectionError, so the
    # block can sit anywhere in the __cause__ chain.
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, OutboundRequestBlockedError):
            return current
        seen.add(id(current))
        current = current.__cause__
    return None
```

and change the generic branch of `_normalize_errors` to check for a block first:

```python
        except Exception as exc:
            blocked = _find_blocked_cause(exc)
            if blocked is not None:
                raise LLMBlockedError(
                    "AI backend request was blocked by the outbound request "
                    f"policy: {blocked}",
                ) from exc
            if self._is_openai_timeout(exc):
                raise LLMTimeoutError from exc
            if self._is_provider_error(exc):
                raise LLMProviderError from exc
            raise
```

In `src/documents/views.py` add `from paperless_ai.exceptions import LLMBlockedError` beside the other `paperless_ai.exceptions` imports, and add this branch to the `ai_suggestions` except chain, directly after the `except LLMProviderError:` block:

```python
            except LLMBlockedError as exc:
                logger.warning(
                    "AI backend request for document %s was blocked: %s",
                    doc.pk,
                    exc,
                )
                return Response(
                    {
                        "ai": [
                            _(
                                "AI backend request was blocked by the outbound "
                                "request policy. Check logs for details.",
                            ),
                        ],
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests src/documents/tests/test_views.py::TestAISuggestions src/documents/tests/test_tasks.py::TestApplyAISuggestionsTask -v"`
Expected: all PASS.

- [ ] **Step 5: Leave locale files alone**

The new `_()` string is picked up by the repository's automated "Auto translate strings" commits, as with the neighbouring error messages. Do not run `makemessages` or edit anything under `src/locale/`. Confirm: `git status --short src/locale` prints nothing.

- [ ] **Step 6: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless_ai/exceptions.py src/paperless_ai/client.py src/documents/views.py src/paperless_ai/tests/test_client.py src/documents/tests/test_views.py src/documents/tests/test_tasks.py
ruff format src/paperless_ai/exceptions.py src/paperless_ai/client.py src/documents/views.py src/paperless_ai/tests/test_client.py src/documents/tests/test_views.py src/documents/tests/test_tasks.py
git add src/paperless_ai/exceptions.py src/paperless_ai/client.py src/documents/views.py src/paperless_ai/tests/test_client.py src/documents/tests/test_views.py src/documents/tests/test_tasks.py
git commit -m "Report outbound policy blocks from AI requests as 502

AIClient raises LLMBlockedError when a request was refused by the outbound
connection policy, including when the openai SDK wraps the block in
APIConnectionError. ai_suggestions answers 502 instead of a 500.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Webhooks on the guarded transport

**Model tier:** implementer sonnet; reviews sonnet (spec), opus (security).

**Files:**

- Modify: `src/documents/workflows/webhooks.py`
- Test: `src/documents/tests/test_workflows.py` (delete the `resolve_to` fixture defined just above `TestWebhookSecurity`, around line 5073; update `TestWebhookSecurity`; fix imports)

**Interfaces:**

- Consumes: `GuardedHTTPTransport`, `OutboundRequestBlockedError` (Tasks 1, 4); fixtures `local_http_server`, `fake_dns` and classes `LocalHTTPServer`, `FakeDNS` (Task 5).

- [ ] **Step 1: Rewrite the webhook security tests**

In `src/documents/tests/test_workflows.py`:

- Delete the `resolve_to` fixture (the whole `@pytest.fixture def resolve_to(...)` block).
- Remove the now-unused imports `import socket`, `from collections.abc import Callable` and `from httpx import ConnectError`. Keep `from typing import Any`; it is used elsewhere in the file.
- Add `from paperless.network import OutboundRequestBlockedError`, `from paperless_testing.outbound import FakeDNS` and `from paperless_testing.outbound import LocalHTTPServer`.
- Replace `test_blocks_private_loopback_linklocal` and `test_allows_public_ip_and_sends` with:

```python
@pytest.mark.parametrize(
    "address",
    [
        pytest.param("127.0.0.1", id="loopback"),
        pytest.param("10.0.0.1", id="private"),
        pytest.param("169.254.169.254", id="link-local-metadata"),
        pytest.param("::ffff:127.0.0.1", id="ipv4-mapped-loopback"),
        pytest.param("64:ff9b::7f00:1", id="nat64-wrapping-loopback"),
    ],
)
@override_settings(WEBHOOKS_ALLOW_INTERNAL_REQUESTS=False)
def test_blocks_private_loopback_linklocal(
    self,
    local_http_server: LocalHTTPServer,
    fake_dns: FakeDNS,
    address: str,
) -> None:
    """
    GIVEN:
        - A webhook host resolving to a non-public address
        - WEBHOOKS_ALLOW_INTERNAL_REQUESTS is False
    WHEN:
        - send_webhook is called
    THEN:
        - The request is blocked before any connection is opened
    """
    fake_dns.add("webhook.test", address)

    with pytest.raises(OutboundRequestBlockedError):
        send_webhook(
            f"http://webhook.test:{local_http_server.port}",
            data="",
            headers={},
            files=None,
            as_json=False,
        )

    assert local_http_server.connections == 0


@override_settings(WEBHOOKS_ALLOW_INTERNAL_REQUESTS=False)
def test_sends_to_validated_address(
    self,
    mocker: MockerFixture,
    local_http_server: LocalHTTPServer,
    fake_dns: FakeDNS,
) -> None:
    """
    GIVEN:
        - A webhook host resolving to an address the policy accepts
        - WEBHOOKS_ALLOW_INTERNAL_REQUESTS is False
    WHEN:
        - send_webhook is called
    THEN:
        - The payload arrives with the webhook hostname in the Host header
    """
    fake_dns.add("webhook.test", "127.0.0.1")
    mocker.patch("paperless.network.is_public_ip", return_value=True)

    send_webhook(
        url=f"http://webhook.test:{local_http_server.port}",
        data="hi",
        headers={},
        files=None,
        as_json=False,
    )

    received = local_http_server.requests[0]
    assert received.body == b"hi"
    assert received.headers["host"] == f"webhook.test:{local_http_server.port}"


@override_settings(WEBHOOKS_ALLOW_INTERNAL_REQUESTS=False)
def test_block_is_an_expected_task_failure(
    self,
    mocker: MockerFixture,
    local_http_server: LocalHTTPServer,
    fake_dns: FakeDNS,
) -> None:
    """
    GIVEN:
        - A webhook host resolving to a loopback address
        - WEBHOOKS_ALLOW_INTERNAL_REQUESTS is False
    WHEN:
        - The webhook task runs through Celery
    THEN:
        - The task fails with the original block error, not a wrapper,
          so it matches the task's expected errors, and is not retried
    """
    fake_dns.add("webhook.test", "127.0.0.1")
    retry = mocker.spy(send_webhook, "retry")

    result = send_webhook.apply(
        kwargs={
            "url": f"http://webhook.test:{local_http_server.port}",
            "data": "",
            "headers": {},
            "files": None,
            "as_json": False,
        },
    )

    assert result.failed()
    assert isinstance(result.result, OutboundRequestBlockedError)
    assert isinstance(result.result, send_webhook.throws)
    retry.assert_not_called()
    assert local_http_server.connections == 0
```

(Add `from pytest_mock import MockerFixture` to the imports if the file does not already have it.)

- In `test_follow_redirects_disabled` and `test_strips_user_supplied_host_header`, delete the `resolve_to` parameter and the `resolve_to("52.207.186.75")` line. Keep everything else; both still run against `httpx_mock`, and httpx now sets `Host` from the URL, so the header assertion still holds.

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_workflows.py::TestWebhookSecurity -v"`
Expected: `test_blocks_private_loopback_linklocal` and `test_block_is_an_expected_task_failure` FAIL (the old transport raises `httpx.ConnectError`); `test_sends_to_validated_address` may pass or fail; the rest PASS.

- [ ] **Step 3: Switch the webhook task**

In `src/documents/workflows/webhooks.py` replace `from paperless.network import PinnedHostHTTPTransport` with:

```python
from paperless.network import GuardedHTTPTransport
from paperless.network import OutboundRequestBlockedError
```

Change the decorator's `throws` to include the block:

```python
throws = ((httpx.HTTPError, OutboundRequestBlockedError),)
```

Replace the comment on `allow_internal=True` in the `validate_outbound_http_url` call with:

```python
# Scheme and port only; the transport enforces the internal-address
# policy at connect time, on the address actually dialled.
allow_internal = (True,)
```

and replace the transport construction with:

```python
    transport = GuardedHTTPTransport(
        allow_internal=settings.WEBHOOKS_ALLOW_INTERNAL_REQUESTS,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_workflows.py -k Webhook -v"`
Expected: all PASS.

- [ ] **Step 5: Lint, run the metadata checks, commit**

```bash
ruff check src/documents/workflows/webhooks.py src/documents/tests/test_workflows.py
ruff format src/documents/workflows/webhooks.py src/documents/tests/test_workflows.py
git add src/documents/workflows/webhooks.py src/documents/tests/test_workflows.py
git commit -m "Use the guarded transport for workflow webhooks

A blocked webhook now raises OutboundRequestBlockedError, which the task
treats as an expected failure and does not retry. The webhook security
tests run against a real local server instead of a patched resolver.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: IMAP pinning on shared resolution

**Model tier:** implementer sonnet; reviews sonnet (spec), sonnet (quality).

**Files:**

- Modify: `src/paperless_mail/mail.py` (imports lines 48-49 plus `import ipaddress` added earlier; `PinnedIMAP4`; `PinnedClientMixin`; `get_mailbox`)
- Test: `src/paperless_mail/tests/test_mail.py` (`TestGetMailboxHostPinning`; `test_mail_account_test_view_blocks_internal_host_when_disabled` near line 2306)

**Interfaces:**

- Consumes: `IPAddress`, `resolve_public_addresses`, `blocked_message`, `OutboundRequestBlockedError`, `HostResolutionError`.

- [ ] **Step 1: Update the tests**

These classes are unittest-style; keep that style. In `TestGetMailboxHostPinning`, replace the `resolve_hostname_ips` patches:

```python
    @override_settings(EMAIL_ALLOW_INTERNAL_HOSTS=False)
    @mock.patch(
        "paperless_mail.mail.resolve_public_addresses",
        return_value=(ipaddress.ip_address("93.184.216.34"),),
    )
    def test_connects_to_validated_ip(self, _mock_resolve) -> None:
```

(same change for `test_ssl_pins_ip_but_keeps_hostname_for_sni`; the `create_connection` and `wrap_socket` assertions stay exactly as they are), and replace the last test with one that goes through real resolution with a faked resolver:

```python
@override_settings(EMAIL_ALLOW_INTERNAL_HOSTS=False)
@mock.patch(
    "paperless.network._getaddrinfo",
    return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 993)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 993)),
    ],
)
def test_blocks_when_any_resolved_address_is_internal(self, _mock_resolve) -> None:
    """
    GIVEN:
        - A mail host resolving to one public and one loopback address
        - EMAIL_ALLOW_INTERNAL_HOSTS is False
    WHEN:
        - A mailbox is requested
    THEN:
        - The whole host is blocked with the existing message
    """
    with self.assertRaisesMessage(
        MailError,
        "Connection blocked: mail.example.com resolves to a non-public address",
    ):
        get_mailbox("mail.example.com", 993, MailAccount.ImapSecurity.SSL)


def test_empty_pin_list_never_falls_back_to_hostname_lookup(self) -> None:
    """
    GIVEN:
        - A pinned IMAP client given an empty tuple of addresses
    WHEN:
        - It connects
    THEN:
        - It fails without opening any socket, rather than resolving the
          hostname itself
    """
    with (
        mock.patch("paperless_mail.mail.socket.create_connection") as pinned,
        mock.patch("imaplib.IMAP4._create_socket") as unpinned,
        self.assertRaises(OSError),
    ):
        PinnedIMAP4("mail.example.com", 143, ())

    pinned.assert_not_called()
    unpinned.assert_not_called()
```

For the account test view (near line 2306), replace its decorator with:

```python
    @mock.patch(
        "paperless.network._getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 993))],
    )
```

and rename its mock parameter from `_mock_resolve_hostname_ips` to `_mock_getaddrinfo: MagicMock`, so no reference to `resolve_hostname_ips` remains for the cleanup task's grep. Annotate the `_mock_resolve` parameters of the pinning tests you touch as `MagicMock` too (import `from unittest.mock import MagicMock` if missing).

Add `import ipaddress`, `import socket` and `from paperless_mail.mail import PinnedIMAP4` to the test module imports if missing.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_mail/tests/test_mail.py -k 'HostPinning or blocks_internal_host' -v"`
Expected: FAIL, `AttributeError: <module 'paperless_mail.mail'> does not have the attribute 'resolve_public_addresses'`, and the block tests fail because the old path still calls `resolve_hostname_ips`.

- [ ] **Step 3: Switch mail to shared resolution**

In `src/paperless_mail/mail.py` replace the two `paperless.network` imports with:

```python
from paperless.network import HostResolutionError
from paperless.network import IPAddress
from paperless.network import OutboundRequestBlockedError
from paperless.network import blocked_message
from paperless.network import resolve_public_addresses
```

and remove the `import ipaddress` added earlier (no longer used). In `PinnedIMAP4`, annotate the constructor parameter `pinned_ips: tuple[IPAddress, ...] | None` and change `_connect_pinned` to dial the string form:

```python
    def _connect_pinned(self, timeout):
        last_error: OSError | None = None
        for ip in self._pinned_ips:
            try:
                address = (str(ip), self.port)
                if timeout is not None:
                    return socket.create_connection(address, timeout)
                return socket.create_connection(address)
            except OSError as e:
                last_error = e
        raise last_error or OSError(f"Could not connect to {self.host}")
```

In `_create_socket`, test for `None` rather than truthiness, so an empty tuple fails in `_connect_pinned` instead of silently falling back to imaplib's own hostname lookup:

```python
        if self._pinned_ips is not None:
            sock = self._connect_pinned(timeout)
        else:
            sock = super()._create_socket(timeout)
```

In `PinnedClientMixin.__init__`, change the annotation to `pinned_ips: tuple[IPAddress, ...] | None`.

Every function this task changes gets full annotations: `PinnedIMAP4.__init__` (`host: str`, `port: int | None`, `pinned_ips: tuple[IPAddress, ...] | None`, `ssl_context: ssl.SSLContext | None = None`, `timeout: float | None = None`, `-> None`), `_connect_pinned(self, timeout: float | None) -> socket.socket`, `_create_socket(self, timeout: float | None) -> socket.socket`, and `get_mailbox`'s parameters and return type. Match the types to what the callers actually pass; check them rather than guessing. In `get_mailbox`, replace the resolution block with:

```python
    pinned_ips: tuple[IPAddress, ...] | None = None
    if not settings.EMAIL_ALLOW_INTERNAL_HOSTS:
        try:
            pinned_ips = resolve_public_addresses(server, port)
        except (OutboundRequestBlockedError, HostResolutionError) as e:
            raise MailError(blocked_message(e)) from e
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_mail/tests -v"`
Expected: all PASS.

- [ ] **Step 5: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless_mail/mail.py src/paperless_mail/tests/test_mail.py
ruff format src/paperless_mail/mail.py src/paperless_mail/tests/test_mail.py
git add src/paperless_mail/mail.py src/paperless_mail/tests/test_mail.py
git commit -m "Use shared outbound resolution for IMAP host pinning

get_mailbox validates the IMAP host with resolve_public_addresses and keeps
its existing error messages; the pinned client dials typed addresses.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: Remove the old transport

**Model tier:** implementer sonnet; reviews sonnet (spec), sonnet (quality).

**Files:**

- Modify: `src/paperless/network.py` (delete `resolve_hostname_ips`, `format_host_for_url`, `_rewrite_request_to_pinned_ip`, `PinnedHostHTTPTransport`, `PinnedHostAsyncHTTPTransport`, `create_pinned_httpx_client`, `create_pinned_async_httpx_client`)
- Modify: `src/paperless/tests/test_network.py` (delete `test_pinned_host_transport_blocks_internal_rebinding`, `test_pinned_host_transport_rewrites_to_vetted_ip`, and the `PinnedHostHTTPTransport` and `from unittest import mock` imports if now unused)

- [ ] **Step 1: Confirm nothing outside `network.py` and its tests still uses the old names**

```bash
git grep -nE "resolve_hostname_ips|format_host_for_url|_rewrite_request_to_pinned_ip|PinnedHost(Async)?HTTPTransport|create_pinned_(async_)?httpx_client" -- src
```

Expected: matches only in `src/paperless/network.py` and `src/paperless/tests/test_network.py`. Anything else means an earlier consumer task is incomplete: stop and report.

- [ ] **Step 2: Delete the old code and its tests**

Delete the listed functions and classes from `network.py` and the two listed tests. Remove imports that become unused (ruff will report them).

- [ ] **Step 3: Confirm the names are gone**

Run the `git grep` from Step 1 again. Expected: no output.

- [ ] **Step 4: Run the affected suites**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless/tests/test_network.py src/paperless/tests/test_network_integration.py src/paperless_ai/tests src/paperless_mail/tests src/documents/tests/test_workflows.py src/documents/tests/test_api_app_config.py -v"`
Expected: all PASS.

- [ ] **Step 5: Lint, run the metadata checks, commit**

```bash
ruff check src/paperless/network.py src/paperless/tests/test_network.py
ruff format src/paperless/network.py src/paperless/tests/test_network.py
git add src/paperless/network.py src/paperless/tests/test_network.py
git commit -m "Remove the URL-rewriting pinned transport

Every consumer now uses the guarded transports, so the request-rewriting
transport and its helpers are no longer needed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 11: Documentation

**Model tier:** implementer haiku; review sonnet (spec).

**Files:**

- Modify: `docs/configuration.md` (the `PAPERLESS_WEBHOOKS_ALLOW_INTERNAL_REQUESTS`, `PAPERLESS_EMAIL_ALLOW_INTERNAL_HOSTS` and `PAPERLESS_AI_LLM_ALLOW_INTERNAL_ENDPOINTS` entries)
- Modify: `docs/usage.md` (webhook security paragraph, around line 615)

- [ ] **Step 1: Update `PAPERLESS_WEBHOOKS_ALLOW_INTERNAL_REQUESTS`**

Replace its description paragraph with:

```markdown
: If set to false, webhooks cannot be sent to internal URLs (e.g., localhost).
A hostname is blocked if any of the addresses it resolves to is non-public.
Webhook requests connect directly, without using the `HTTP_PROXY` or
`HTTPS_PROXY` environment variables, and never follow redirects.

    Defaults to true, which allows internal requests.
```

- [ ] **Step 2: Update `PAPERLESS_EMAIL_ALLOW_INTERNAL_HOSTS`**

Replace its description paragraph with:

```markdown
: If set to false, incoming mail account connections are blocked when the
configured IMAP hostname resolves to any non-public address (for example,
localhost, link-local, or RFC1918 private ranges).

    Defaults to true, which allows internal hosts.
```

- [ ] **Step 3: Update `PAPERLESS_AI_LLM_ALLOW_INTERNAL_ENDPOINTS`**

Replace its description paragraph with:

```markdown
: If set to false, Paperless blocks AI endpoint URLs that resolve to non-public addresses (e.g., localhost, etc).
A hostname is blocked if any of the addresses it resolves to is non-public, and redirects are checked the same way.
Requests to a configured AI endpoint connect directly, without using the `HTTP_PROXY` or `HTTPS_PROXY` environment variables.

    Defaults to true, which allows internal endpoints.
```

- [ ] **Step 4: Update `docs/usage.md`**

After the sentence ending "...to change this behavior." in the webhook section, add:

```markdown
Webhook requests connect directly (proxy environment variables are not used) and do not follow redirects.
```

- [ ] **Step 5: Run the metadata checks, commit**

```bash
git add docs/configuration.md docs/usage.md
git commit -m "Document outbound connection policy for internal-address settings

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 12: Full test suite, ruff, pyrefly

**Model tier:** implementer haiku; escalate any failure to a sonnet subagent with the failing output. No commit unless a fix was needed (then commit the fix with a plain description of what it fixes, following the Global Constraints).

- [ ] **Step 1: Lint everything that changed on the branch**

```bash
ruff check $(git diff --name-only dev...HEAD -- '*.py')
ruff format --check $(git diff --name-only dev...HEAD -- '*.py')
```

Expected: no findings.

- [ ] **Step 2: Every suite the branch touches, on the VM (parallel)**

Do not run all of `src/documents/tests`: it pulls in OCR and other slow suites unrelated to this change. Run the suites covering every changed module:

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "-n auto --dist=loadscope src/paperless/tests src/paperless_ai/tests src/paperless_mail/tests src/documents/tests/test_workflows.py src/documents/tests/test_views.py src/documents/tests/test_tasks.py src/documents/tests/test_api_app_config.py"`
Expected: all PASS. If tests marked `live`, `gotenberg`, `tika`, `greenmail` or `nginx` fail only because those services are not running on the VM, re-run with `-m "not live and not gotenberg and not tika and not greenmail and not nginx"` added and report which were deselected; any other failure is real. If `git diff --name-only dev...HEAD` shows a changed module not covered by these paths, add its test file.

- [ ] **Step 3: pyrefly**

```bash
tar czf - src pyproject.toml uv.lock .pyrefly-baseline.json | ssh -o BatchMode=yes paperless-vm 'tar xzf - -C ~/projects/paperless-ngx'
ssh -o BatchMode=yes paperless-vm 'bash -lc "cd ~/projects/paperless-ngx && uv run pyrefly check"'
```

Expected: no errors beyond the baseline. `git diff dev...HEAD -- .pyrefly-baseline.json` must be empty.

- [ ] **Step 4: Branch-wide metadata sweep**

```bash
git diff dev...HEAD -U0 | grep '^+' | grep -nEi '\b(task|step|phase) ?#?[0-9]+\b|docs/superpowers|superpowers|\bspec\b|implementation plan|sonnet|haiku|opus|subagent|review round|TODO|FIXME' || echo "clean"
git log dev..HEAD --format=%B | grep -v '^Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>$' | grep -nEi '\b(task|step) ?[0-9]+\b|spec|plan|sonnet|haiku|opus|subagent' || echo "clean"
git diff --name-only dev...HEAD | grep '^docs/superpowers/' || echo "clean"
```

Expected: `clean` three times. Any hit is a blocker: fix it (reword, or amend/rebase the offending commit with the user's approval) before continuing.

---

### Task 13: Manual reproduction on the VM

**Model tier:** implementer sonnet. Editing `/etc/hosts` on the VM needs `sudo`; ask the user before doing it, and let them run it via `! <command>` if sudo prompts.

- [ ] **Step 1: Make `localhost` resolve to `::1` first**

On the VM, back up and prepend: `sudo cp /etc/hosts /etc/hosts.bak && sudo sed -i '1i ::1 localhost' /etc/hosts`, then confirm `getent ahosts localhost` lists `::1` before `127.0.0.1`.

- [ ] **Step 2: Run a server bound only to 127.0.0.1**

`ssh -o BatchMode=yes paperless-vm 'python3 -m http.server 18080 --bind 127.0.0.1 >/tmp/srv.log 2>&1 & echo $!'` (note the PID).

- [ ] **Step 3: Reproduce on `dev` and confirm the fix on the branch**

Export both trees to separate VM directories without touching the Windows working tree:

```bash
for ref in dev HEAD; do
  dir="~/projects/connect-guard-check-$( [ "$ref" = dev ] && echo dev || echo branch )"
  ssh -o BatchMode=yes paperless-vm "rm -rf $dir && mkdir -p $dir"
  git archive "$ref" src pyproject.toml uv.lock | ssh -o BatchMode=yes paperless-vm "tar xf - -C $dir"
done
```

Do not create new virtual environments for these two directories: the VM disk is tight, and a fresh `uv run` in each would download the whole AI stack twice. Both trees lock the same package versions (the branch only adds `requires-dist` entries), so reuse the environment the test helper built for the branch in Task 12. The helper's directory slug keeps a trailing hyphen, so the interpreter is `~/projects/paperless-ngx-worktrees/fix-outbound-connect-guard-/.venv/bin/python`; confirm it exists (`ls`) and check `df -h /` first. Running `python -c` from each tree's `src` puts that tree first on `sys.path`.

In each directory's `src` (`~/projects/connect-guard-check-dev/src`, then `~/projects/connect-guard-check-branch/src`), run over `ssh -o BatchMode=yes paperless-vm 'bash -lc "cd <dir>/src && ..."'`, with `PY` set to that interpreter:

```bash
"$PY" -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','paperless.settings'); django.setup(); from documents.workflows.webhooks import send_webhook; send_webhook('http://localhost:18080/', data='x', headers={}, files=None, as_json=False); print('sent')"
```

Expected on `dev`: a connect error (if it succeeds, the suspected cause in discussion #13782 is wrong; report that). Expected on the branch: `sent` (the server returns 501 for POST, so `raise_for_status` may raise `HTTPStatusError`: that also proves the connection succeeded; either outcome is a pass, a connect error is not).

- [ ] **Step 4: Confirm the policy path**

On the branch with `PAPERLESS_WEBHOOKS_ALLOW_INTERNAL_REQUESTS=false` exported, the same command raises `OutboundRequestBlockedError` and the log shows a `Blocked outbound connection` warning.

- [ ] **Step 5: Clean up**

Kill the server PID, restore hosts (`sudo mv /etc/hosts.bak /etc/hosts`) and remove both `~/projects/connect-guard-check-*` directories. Report results to the user; nothing to commit.

---

### Task 14: Whole-branch final review

**Model tier:** opus reviewer (no implementation).

- [ ] **Step 1: Review the full diff against the spec**

Dispatch an opus reviewer with the spec path and `git diff dev...HEAD`. It checks: every spec requirement implemented; no SSRF path bypasses the guard (proxies, mounts, uds, redirects, both sync and async, the OllamaEmbedding private clients, the openai path); typing and pyrefly cleanliness; test conventions; the no-metadata rule across code and commit messages; no em dashes; no Django import in `network.py`.

- [ ] **Step 2: Resolve findings**

Fix confirmed findings in new commits that follow the Global Constraints, re-run Task 12, and report to the user. Do not push or open a PR without the user's go-ahead. When the user asks for the PR, its description must list the behaviour changes from the spec's compatibility section, note the AI assistance as the contribution policy requires, and end with the required attribution line.
