# Outbound connect guard: design

**Status:** Draft for review (revised after two independent reviews)
**Date:** 2026-09-10
**Target:** `dev`, next minor release
**Related:** discussion #13782 (localhost AI endpoint failures), issue #14226 (dual-stack OpenAI-like endpoint failures, closed as not planned pending a security-preserving fallback), GHSA-6653-vcx4-69mc (original webhook DNS rebinding advisory)

## 1. Problem

`src/paperless/network.py` protects outbound HTTP (webhooks, AI LLM and embedding endpoints) against SSRF by rewriting each request: it resolves the hostname, checks every resolved address, then replaces the URL host with `ips[0]` and patches the `Host` header and TLS SNI back to the original name. This design has several defects:

1. **Only the first resolved address is ever tried.** There is no fallback when that address refuses or times out. This applies even with the default `allow_internal=True` settings, because the rewrite happens regardless of the policy.
   - Suspected, **not yet confirmed**, cause of the `localhost` failures in #13782: on hosts whose `/etc/hosts` maps `localhost` to `::1` as well, glibc typically returns `::1` first, while Ollama listens on `127.0.0.1` only. We have asked the reporters for `getent ahosts localhost` and `ss -ltnp` output. This spec does not depend on that confirmation; items 2 to 5 justify the change on their own.
   - **Confirmed in the field** by #14226: an OpenAI-compatible proxy on a dual-stack Podman network, whose hostname resolves to IPv6 and IPv4, fails on every chat and embedding request with `APIConnectionError` while the proxy logs no request; disabling IPv6 on the network fixes it. `PAPERLESS_AI_LLM_ALLOW_INTERNAL_ENDPOINTS=true` was set, so this is the rewrite to `ips[0]` running under the permissive policy, not the SSRF check. The PR should reference it.
2. **TLS certificate verification can be skipped across hosts.** After the rewrite, httpcore keys pooled connections by the IP origin. A kept-alive TLS connection opened for host A can be reused for host B that shares the IP (common behind CDNs), and B's certificate is never checked.
3. **Blocking DNS inside async code.** `PinnedHostAsyncHTTPTransport` calls the synchronous `socket.getaddrinfo` on the event loop.
4. **Duplicate resolution results.** `getaddrinfo(host, None)` without `type=SOCK_STREAM` returns each address once per socket type.
5. **Fragile request reconstruction.** The rewrite rebuilds `httpx.Request` objects and has already caused two bugs (a1026f03d streamed bodies, 5d6ea1182 async stream adoption). The Host header and SNI patching is security-relevant code we would rather not own.

## 2. Goals and non-goals

**Goals**

- Validate the destination at TCP connect time, on exactly the address that is dialled, so DNS rebinding and redirect-to-internal remain closed.
- Try validated addresses in turn (up to a cap, 4.4) within the caller's connect timeout.
- Leave `Host`, SNI, certificate verification and connection pooling to httpx/httpcore defaults.
- Strong typing throughout, using `ipaddress` types for addresses.
- Keep `paperless/network.py` free of Django imports so the guard can be extracted into a standalone library later without changes.

**Non-goals**

- Outbound proxy support (see 4.7).
- Unix socket support (see 4.6).
- Remote OCR (Azure Document Intelligence) pinning. It uses azure-core's requests transport and remains validate-per-request without pinning. Listed as a known gap, follow-up work.
- The OpenAI-like client when no endpoint is configured. The destination is api.openai.com or the admin-set `OPENAI_BASE_URL`, not user-controllable, and it stays on the SDK's default client.
- Handling ordinary LLM connection failures (unreachable backend currently returns a 500). That is a separate, smaller PR.
- Full RFC 8305 happy eyeballs (parallel staggered attempts). See 4.4 for the sequential alternative and why.
- Extracting a library now (see 9).

## 3. Background findings

These were verified against the locked versions (httpx 0.28.1, httpcore 1.0.9, anyio 4.14.2, ollama 0.6.1, openai 2.48.0) on the dev VM, partly by running prototypes against the installed packages. The llama-index integrations have since been bumped (llms-ollama 0.11.0, embeddings-ollama 0.10.0, llms-openai-like 0.8.0, embeddings-openai-like 0.4.0); the client-construction code relied on here is unchanged in those releases.

- **Injection point.** httpx has no public `network_backend` parameter. `HTTPTransport.__init__` builds `self._pool` (`httpcore.ConnectionPool`; `httpcore.AsyncConnectionPool` for `AsyncHTTPTransport`), which stores `_network_backend` and reads it only in `create_connection()`, once per new connection. Nothing reads it before a subclass's `__init__` returns. Replacing it after `super().__init__()` is what Prefect (PrefectHQ/prefect#21591), Hermes-agent and romm do. Upstream PR encode/httpx#3749 (public `network_backend=`) has been open without review since 2026-01-26; httpx has not released since 0.28.1 (Dec 2024).
- **`connect_tcp` receives the origin hostname** (IDNA-encoded, IPv6 brackets stripped), passed as keyword arguments matching the base-class parameter names. `start_tls` uses `server_hostname = sni_hostname or origin.host`, so SNI and certificate checks use the real hostname even when we connect to an IP literal. httpx sets `Host` from the request URL.
- **Sync default backend** uses `socket.create_connection`, which walks all resolved addresses, giving each the full timeout; DNS time is not counted. **Async default** is `AutoBackend` to `AnyIOBackend`, which wraps `anyio.connect_tcp` in `fail_after(timeout)` (DNS included); with a hostname it does happy eyeballs, with an IP literal a single attempt.
- **Exceptions.** A non-httpcore exception raised from `connect_tcp` passes through httpx's `map_httpcore_exceptions` unmapped. httpcore's connect retry loop only retries `ConnectError`/`ConnectTimeout`. The pool re-raises with `raise exc from None`, so any `__cause__` attached inside `connect_tcp` is lost; detail must go in the message. Raising a plain `Exception` from `connect_tcp` leaves the pool consistent (prototype: `max_connections=1`, three consecutive blocked requests, no hang, pool empty afterwards; sync and async).
- **Consumers' error handling.**
  - ollama converts `httpx.ConnectError` into the builtin `ConnectionError` with `from None`, losing the reason. Any other exception passes through untouched (verified for chat, streaming chat and embed).
  - openai retries any non-`OpenAIError` exception, then raises `APIConnectionError(...) from err`; `__cause__` is the original exception. llama-index's tenacity layer uses `reraise=True`.
  - openai via our httpx client does not follow redirects; only the SDK's own default client sets `follow_redirects=True`. ollama follows redirects.
  - `paperless_ai/ai_classifier.py` `get_taxonomy_context` swallows every exception from the embedding path.
- **Proxies.** `httpx.Client(transport=...)` disables env proxies (`allow_env_proxies = trust_env and transport is None`), so guarded clients already ignore `HTTP_PROXY`/`HTTPS_PROXY` today. Passing `proxy=` or `mounts=` alongside `transport=` still installs an unguarded transport. With a proxy, `connect_tcp` receives the proxy host, never the target.
- **Unix sockets.** With `uds=`, `connect_tcp` is never called; `connect_unix_socket` is.
- **Resolver quirks.** Sync `socket.getaddrinfo` raises `UnicodeError` (a `ValueError`) for over-long or empty IDNA labels (`"a"*64 + ".com"`, `"x..com"`); `anyio.getaddrinfo` raises `gaierror` for the same input. Numeric forms such as `2130706433` and `0x7f.1` pass through httpx as hostnames and glibc resolves them to `127.0.0.1`.
- **stdlib `ipaddress` classification** was checked on 3.11.9, 3.11.16, 3.12.3, 3.12.13, 3.13.4 and 3.14.4.
  - On current patch releases `is_global` is `False` for Teredo, 6to4 (`2002::/16`), local-use NAT64 (`64:ff9b:1::/48`) and CGNAT (`100.64.0.0/10`).
  - For IPv4-mapped addresses (`::ffff:a.b.c.d`) `is_global` and `is_multicast` follow the embedded IPv4 address (`::ffff:127.0.0.1` is not global, `::ffff:8.8.8.8` is).
  - `is_global` is `True` for multicast (`224.0.0.0/4`), the well-known NAT64 prefix (`64:ff9b::/96`), IPv4-compatible `::a.b.c.d`, IPv4-translated `::ffff:0:a.b.c.d`, site-local `fec0::/10`, the 6to4 relay anycast `192.88.99.0/24` and SRv6 `5f00::/16`.
  - Unpatched 3.11.9 and 3.12.3 (before the CVE-2024-4032 fix) additionally report 6to4 and `64:ff9b:1::/48` as global.
- **Dependencies.** `httpx`, `httpcore` and `anyio` are not declared in `pyproject.toml`; they arrive transitively (`gotenberg-client[httpx]`, `tika-client[httpx]`, `openai`, `httpx-oauth`).
- **Existing IMAP pinning** (`paperless_mail/mail.py`, `PinnedIMAP4._connect_pinned`) already tries each validated address in turn. That is the same model this spec adopts for HTTP.

## 4. Design

All new code lives in `src/paperless/network.py`. The module must not import Django.

### 4.1 Types and errors

```python
# requires-python is >=3.11, so no PEP 695 `type` statement.
IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address


class BlockReason(StrEnum):
    NON_PUBLIC_ADDRESS = "non_public_address"
    UNIX_SOCKET = "unix_socket"


class OutboundRequestBlockedError(Exception):
    def __init__(
        self,
        *,
        host: str,
        port: int | None,
        reason: BlockReason,
        address: IPAddress | None = None,
    ) -> None: ...

    def __reduce__(self) -> tuple[Callable[..., Self], tuple[object, ...]]: ...


class HostResolutionError(Exception):
    def __init__(self, *, host: str, detail: str) -> None: ...

    def __reduce__(self) -> tuple[Callable[..., Self], tuple[object, ...]]: ...
```

- `OutboundRequestBlockedError` means **a policy decision**: a non-public address, or a Unix socket. It subclasses `Exception` directly: not `httpcore.ConnectError` (so httpcore does not retry it and ollama does not swallow it) and not `ValueError` (so the AI view's existing `except ValueError` does not misreport it as invalid configuration).
  - For `NON_PUBLIC_ADDRESS`: `host` is the hostname or IP literal being connected to, `port` the destination port, `address` the first offending address.
  - For `UNIX_SOCKET`: `host` is the socket path, `port` and `address` are `None`.
- `HostResolutionError` means **the resolver failed** (NXDOMAIN, temporary failure, invalid IDNA, empty result). It is not a policy block. Inside the guard it is converted to `httpcore.ConnectError` (4.4), so a DNS outage looks the same whether or not `allow_internal` is set.
- **Message.** Each `__init__` builds its message and calls `super().__init__(message)`, so `str(exc)` and `exc.args` are populated. Without this `str(exc)` is empty, and `task_failure_handler` stores `str(exception)` as the tracked task's error message. The message names host, port and reason. It never includes a URL path or query string, and never the offending address: the message is logged and stored on tracked tasks (readable through the tasks API), and a resolved internal address is internal DNS information the requester should not learn. The offending address is available only as the `address` attribute, in memory.
- **Pickling.** Both implement `__reduce__` as `(functools.partial(type(self), <all keyword fields>), ())`. This is required because Celery's `handle_failure` runs `get_pickleable_exception()` on every task failure; an exception whose keyword-only `__init__` cannot be rebuilt from `args` is replaced by `UnpickleableExceptionWrapper`, and then `isinstance(exc, task.throws)` no longer matches, so the webhook `throws=` entry (5) would have no effect. (The result backend is not the reason: the signed-pickle serializer is not in Celery's exception-capable codecs, so results store the type name and `args` either way.) The `partial` form round-trips, satisfies `get_pickleable_exception(exc) is exc`, and passes pyrefly with the annotation above.
- Every function in this module has full annotations. Addresses stay `IPAddress` objects internally; conversion to `str` happens only at the httpcore boundary (`connect_tcp(host: str, ...)`) and the socket boundary in IMAP.
- Backends override httpcore's methods with httpcore's exact signatures and parameter names, using the public `httpcore.SOCKET_OPTION`, `httpcore.NetworkStream` and `httpcore.AsyncNetworkStream`.
- New and changed code must pass `pyrefly check` without adding entries to `.pyrefly-baseline.json`.

### 4.2 IP classification

```python
def is_public_ip(ip: IPAddress) -> bool:
    return (
        ip.is_global
        and not ip.is_multicast
        and not any(ip in net for net in _NON_PUBLIC_NETWORKS)
    )
```

- Built on the stdlib's `is_global`, which replaces the current five-way check (private, loopback, link-local, multicast, unspecified) and is stricter than `is_private`.
- `is_multicast` is kept because the stdlib classifies `224.0.0.0/4` as global.
- `_NON_PUBLIC_NETWORKS` is reduced to ranges the latest stdlib reports as global but which reach internal hosts: `64:ff9b::/96` (the NAT64 well-known prefix; `64:ff9b::7f00:1` reaches `127.0.0.1` through a NAT64 gateway). `100.64.0.0/10` is removed because `is_global` covers it. Each entry carries a comment explaining why the stdlib is insufficient.
- The signature changes from `str | int` to `IPAddress`. The current silent `ValueError` swallow goes away; callers parse, so malformed input fails loudly.
- No hand-rolled unwrapping of embedded IPv4 (6to4, Teredo, mapped). The stdlib is the source of truth.
- **Accepted as public**, each deprecated or not routed to internal IPv4 by modern OSes: `::a.b.c.d` (IPv4-compatible, RFC 4291), `::ffff:0:a.b.c.d` (IPv4-translated, SIIT), `fec0::/10` (site-local, RFC 3879), `192.88.99.0/24` (6to4 relay anycast, RFC 7526), `5f00::/16` (SRv6 SIDs).
- **Known limitation:** on unpatched Pythons (3.11 before 3.11.10, 3.12 before 3.12.4) 6to4 and `64:ff9b:1::/48` are classified as global. Those interpreters lack the CVE-2024-4032 fix regardless; we do not work around it.
- Blocking all of `64:ff9b::/96` is retained from a29856896. On IPv6-only DNS64 networks this also blocks public IPv4 destinations, but only when an `*_ALLOW_INTERNAL_*` setting is `false`. Recorded as an accepted trade-off.

### 4.3 Resolution and validation

```python
def resolve_public_addresses(host: str, port: int | None) -> tuple[IPAddress, ...]: ...


async def aresolve_public_addresses(
    host: str, port: int | None
) -> tuple[IPAddress, ...]: ...
```

`port` is optional because `MailAccount.imap_port` is nullable; `getaddrinfo(host, None, type=SOCK_STREAM)` is valid.

These always enforce the public-address policy; callers only call them when `allow_internal` is `False`. Behaviour (both variants):

1. If `host` parses as an IP literal, validate and return it without DNS.
2. Otherwise resolve with `_getaddrinfo(host, port, type=socket.SOCK_STREAM)`; the async variant uses `_agetaddrinfo` (see test hooks below).
3. A resolver failure raises `HostResolutionError`. Both variants catch `(OSError, UnicodeError)`: sync `getaddrinfo` raises `UnicodeError` for invalid IDNA labels, and `anyio.getaddrinfo` raises `idna.IDNAError` (a `UnicodeError`) for invalid non-ASCII hosts. An empty result also raises `HostResolutionError`.
4. Strip IPv6 zone IDs (`%eth0`), parse into `IPAddress`, de-duplicate preserving resolver order.
5. If **any** address is not public, raise `OutboundRequestBlockedError(reason=NON_PUBLIC_ADDRESS, address=<first offending>)`. A name is rejected as a whole; offending addresses are never filtered out.

Validating resolver output (not the URL text) covers numeric host forms such as `2130706433` and `0x7f.1`.

**Test hooks.** The module binds `_getaddrinfo = socket.getaddrinfo`, `_agetaddrinfo = anyio.getaddrinfo` and `_monotonic = time.monotonic` at module level and calls only those names. Tests patch these module attributes instead of the global `socket`/`time` functions: patching `socket.getaddrinfo` globally would also change how `socket.create_connection` resolves the IP literals the guard dials, and patching `time.monotonic` globally breaks the asyncio event loop.

**Legacy messages.** A single helper `blocked_message(exc: OutboundRequestBlockedError | HostResolutionError) -> str` produces the existing user-facing texts: "Connection blocked: <host> resolves to a non-public address" (`NON_PUBLIC_ADDRESS`) and "Could not resolve hostname: <host>" (`HostResolutionError`). For `UNIX_SOCKET`, which no legacy caller can produce, it returns "Connection blocked: unix sockets are not permitted". `validate_outbound_http_url` and the mail code both use it.

`resolve_hostname_ips` is removed. `validate_outbound_http_url` keeps its signature, its `ValueError` contract (the config serializers and AI client construction rely on the messages) and its current rule of resolving DNS only when `allow_internal` is `False`. Internally it calls `resolve_public_addresses` and converts both exceptions into `ValueError(blocked_message(exc))`.

**Resolve the name that is dialled.** The hostname passed to `resolve_public_addresses` is taken from `httpx.URL(url).raw_host`, not `urlparse(url).hostname`. `urlparse` keeps a non-ASCII hostname as typed, and `getaddrinfo` then encodes it with the stdlib `idna` codec (IDNA 2003). httpx and urllib3 use IDNA 2008 (UTS 46), and the two encode a few characters differently: `faß.example` is checked as `fass.example` but connected to as `xn--fa-hia.example` (verified on the VM). An attacker who controls both names could pass the check with a public answer and connect to an internal one. The guarded httpx paths are not affected, because httpcore hands the guard the already-encoded name, but Remote OCR re-checks each Azure request through `validate_outbound_http_url` and then dials through urllib3, so the gap is real on `dev` today. A hostname httpx cannot encode (`httpx.InvalidURL` or `UnicodeError`) raises the existing "Invalid URL scheme or hostname." `ValueError`. With `allow_internal=False` a URL containing a raw backslash, an ASCII control character or whitespace is also rejected as invalid before resolving: urlparse and httpx read `http://127.0.0.1\@evil.example/` as host `evil.example`, while urllib3 reads `127.0.0.1` and dials it (verified on the VM), and azure-core copies redirect `Location` values into the request URL unchanged. Such URLs are not valid RFC 3986 anyway. Scheme and port checks keep using `urlparse`. For ASCII hostnames the two names are identical, so messages are unchanged; for a non-ASCII hostname a block message names the IDNA 2008 form.

### 4.4 Guard backends

```python
class _GuardedSyncBackend(httpcore.NetworkBackend):
    def __init__(
        self, inner: httpcore.NetworkBackend, *, allow_internal: bool
    ) -> None: ...


class _GuardedAsyncBackend(httpcore.AsyncNetworkBackend):
    def __init__(
        self, inner: httpcore.AsyncNetworkBackend, *, allow_internal: bool
    ) -> None: ...
```

Constants: `MAX_ADDRESSES_TRIED = 8`, `MIN_ATTEMPT_TIMEOUT = 2.0`, `MAX_ATTEMPT_TIMEOUT = 10.0` (seconds).

`connect_tcp(host, port, timeout=None, local_address=None, socket_options=None)`:

- **`allow_internal=True`:** delegate to `inner.connect_tcp` with the hostname unchanged. No resolution, no pinning. Users get stock httpx behaviour: `socket.create_connection` fallback in sync code, anyio happy eyeballs in async code. This is the default configuration for every consumer.
- **`allow_internal=False`:**
  1. **Timeout sanity.** If `timeout` is not `None` and `<= 0`, raise `httpcore.ConnectTimeout` immediately (a zero timeout would make the socket non-blocking and a negative one raises `ValueError` from `settimeout`).
  2. **Resolve and validate.**
     - Sync: call `resolve_public_addresses`. DNS time is not charged to the connect budget, matching the stock sync backend (a single glibc resolver retry takes 5 s, which would otherwise consume a whole 5 s webhook budget).
     - Async: the deadline starts before resolution, matching the stock async backend. Wrap `aresolve_public_addresses` in `anyio.fail_after(timeout)`; a timeout becomes `httpcore.ConnectTimeout`. That scope closes before any dialling: resolution and the per-attempt `inner.connect_tcp` calls (which apply their own `fail_after`) are sequential, not nested. Note that `fail_after` uses the event loop clock while the attempt budget uses `_monotonic`; both measure elapsed wall time, but tests can only drive the latter by patching.
     - `HostResolutionError` becomes `httpcore.ConnectError(str(exc))`. `OutboundRequestBlockedError` propagates.
  3. **Order and cap.** Starting from the de-duplicated, fully validated list: interleave address families beginning with the family of the first resolver result (RFC 8305 section 4). When one family runs out, append the rest of the other family in resolver order. A single-family list is unchanged, and an IP literal is a one-element list. Then take the first `MAX_ADDRESSES_TRIED`. Only the attempt list is capped; every resolved address was validated in step 2.
  4. **Attempts.** Loop over the capped list. Before each attempt, compute `remaining = deadline - _monotonic()` (infinite when `timeout` is `None`). If `remaining <= 0`, stop and raise (step 5). The attempt's timeout is:
     - `remaining` (`None` when `timeout` is `None`) if this is the last address, **or** if `remaining < 2 * MIN_ATTEMPT_TIMEOUT`;
     - otherwise `min(MAX_ATTEMPT_TIMEOUT, max(MIN_ATTEMPT_TIMEOUT, remaining / (n - i)), remaining - MIN_ATTEMPT_TIMEOUT)` for attempt `i` of `n` (zero-based).

     The third term always leaves at least `MIN_ATTEMPT_TIMEOUT` for a later attempt, and once the budget is too small to split, the current attempt gets all of it. An attempt that fails quickly (connection refused) does not end the loop: the next address gets whatever remains. Worked examples with every address black-holed (seconds per attempt):

     | Timeout | Addresses | Attempts                 |
     | ------- | --------- | ------------------------ |
     | 5       | 2         | 2.5, 2.5                 |
     | 5       | 3         | 2, 3 (third not reached) |
     | 5       | 8         | 2, 3                     |
     | 1       | 2         | 1 (second not reached)   |
     | 120     | 8         | 10 x7, 50                |
     | None    | 3         | 10, 10, None             |

     With the refused-then-working case from #13782 (`::1` refused instantly, `127.0.0.1` listening), both addresses are always tried whatever the timeout. The floor keeps a single lost SYN (1 s initial retransmit) from failing a healthy address. The ceiling bounds how long a black-holed address delays the next one.

  5. **Errors.** On `httpcore.ConnectError` or `httpcore.ConnectTimeout` from `inner`, log it at DEBUG and continue. If every attempt fails, re-raise the last error. If the budget runs out before an address is tried, raise `httpcore.ConnectTimeout` naming the host and the number of addresses tried.
- All per-call state (deadline, address list) is local. The backend instance is shared across threads/tasks by the pool and holds no mutable state.

**Why sequential instead of happy eyeballs.** Parallel staggered attempts would reproduce anyio's task-group logic in our code for both sync and async. The floor and ceiling keep the worst case for a black-holed first address at 10 s. This only affects installs with `allow_internal=False`; the default path keeps anyio's happy eyeballs.

`connect_unix_socket(...)`: always raises `OutboundRequestBlockedError(reason=UNIX_SOCKET)`.

`sleep(seconds)`: delegates to `inner`. (The async base class has no default implementation.)

**Logging.** The guard backend, and only the guard backend, logs each block at `WARNING` on the `paperless.network` logger with host, port and reason (the exception's message). The offending address is not logged. Per-attempt `DEBUG` lines name the dialled address, which is always a validated public one. `resolve_public_addresses` does not log, so serializer validation and IMAP do not emit it. Because retry layers call `connect_tcp` again, one logical request can produce several WARNING lines (see 5.2). Accepted: blocks are rare and each line is accurate.

**Why the async guard matters.** No paperless code calls the async LLM or embedding APIs today. The async transport is still guarded because llama-index's Ollama LLM creates an unguarded `AsyncClient` on first use if none is supplied, so we always supply a guarded one.

### 4.5 Transports and client factories

```python
class GuardedHTTPTransport(httpx.HTTPTransport):
    def __init__(self, *, allow_internal: bool) -> None: ...


class GuardedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    def __init__(self, *, allow_internal: bool) -> None: ...


def create_guarded_httpx_client(
    url: str,
    *,
    allow_internal: bool,
    timeout: float,
) -> httpx.Client: ...


def create_guarded_async_httpx_client(
    url: str,
    *,
    allow_internal: bool,
    timeout: float,
) -> httpx.AsyncClient: ...
```

- The transports accept only `allow_internal`, which is required (no default) so every call site states its policy. `proxy`, `uds`, `retries` and the rest of httpx's transport arguments are deliberately not accepted. Adding one later is a reviewed change, not a pass-through.
- **Layout assertion.** After `super().__init__()`, before swapping, each transport checks the exact expected layout and raises `RuntimeError` if it differs:
  - sync: `type(self._pool) is httpcore.ConnectionPool` and `type(self._pool._network_backend) is httpcore.SyncBackend`;
  - async: `type(self._pool) is httpcore.AsyncConnectionPool` and `type(self._pool._network_backend) is AutoBackend`, imported from the private `httpcore._backends.auto` (httpcore does not export it).

  Exact type checks also exclude the `HTTPProxy`/`SOCKSProxy` pool subclasses. It then wraps the existing backend in the matching guard. If a future httpx or httpcore moves or renames these attributes, construction fails loudly instead of silently running unguarded.

- The factories call `validate_outbound_http_url(url, allow_internal=allow_internal)` first. A static misconfiguration fails immediately with `ValueError` (the AI view maps this to 400) and never reaches the openai/llama-index retry layers. They then return a client built with the guarded transport and `timeout`. `timeout` is a required `float`, not optional. There is no `**kwargs`, so `proxy`, `mounts` and `transport` cannot be passed.
- **Dependencies.** Declare the packages whose internals or API we now use directly in `pyproject.toml`, in alphabetical position: `anyio>=4.12` (public API only), `httpcore~=1.0.9` and `httpx~=0.28.1` (both narrow, because we depend on private attributes). Regenerate `uv.lock` with `uv lock`. Verified: resolution succeeds with no package version changes, and `uv lock --check` is clean on current `dev`, so the only lock diff is the new `requires-dist` entries.
- **Removed** (in the final cleanup, 8): `PinnedHostHTTPTransport`, `PinnedHostAsyncHTTPTransport`, `_rewrite_request_to_pinned_ip`, `create_pinned_httpx_client`, `create_pinned_async_httpx_client`, `format_host_for_url` (its only caller is the rewrite), `resolve_hostname_ips`. The classes are renamed rather than kept because their behaviour changes.

### 4.6 Unix sockets

No consumer can configure a Unix socket today and there is no feature request for it. The guard refuses `connect_unix_socket` unconditionally and the transports do not accept `uds`. Supporting it later (allowed only when `allow_internal` is true) would be a contained change.

### 4.7 Proxies

Guarded requests always connect directly. This is today's behaviour made explicit: env proxies are already ignored because a `transport=` is passed. The factories and transports cannot be given proxy configuration (4.5). Tests pin that `HTTPS_PROXY` in the environment has no effect on a guarded client, including the client ollama builds internally (7). Documented in 6.

### 4.8 Request flow

With `allow_internal=False`:

1. Factory validates the URL up front (`ValueError` on failure).
2. httpx builds the request with its normal `Host` header.
3. httpcore asks the guard backend for a connection to the origin hostname.
4. The guard resolves, validates and dials each address in turn, returning the first stream that connects.
5. httpcore performs TLS with `server_hostname=<origin host>`; certificate verification uses the real hostname.
6. The pooled connection is keyed by the real origin, so it is only reused for the same host.
7. For clients that follow redirects (ollama), a redirect to a different origin opens a new connection, which goes through the guard again. Webhooks and the openai path do not follow redirects.

With `allow_internal=True`, step 4 passes the hostname straight to the stock backend.

## 5. Consumers

| File                                       | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/paperless_ai/client.py` (Ollama)      | `ollama.Client(..., transport=GuardedHTTPTransport(allow_internal=...))` and the async twin. The up-front `validate_outbound_http_url` stays.                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `src/paperless_ai/client.py` (OpenAI-like) | `create_guarded_*_client` when an endpoint is set. No endpoint: unchanged, SDK default client.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `src/paperless_ai/embedding.py`            | Same two paths. The `OllamaEmbedding` override of private `_client` / `_async_client` stays (llama-index accepts one `client_kwargs` dict for both clients, so it cannot carry separate sync and async transports).                                                                                                                                                                                                                                                                                                                                                                   |
| `src/documents/workflows/webhooks.py`      | `GuardedHTTPTransport(allow_internal=settings.WEBHOOKS_ALLOW_INTERNAL_REQUESTS)`. The up-front scheme/port check (`allow_internal=True`) stays; its comment about preserving `ConnectError` is updated. `Host` header stripping stays (a user-supplied header would still override httpx's). `OutboundRequestBlockedError` is added to the task's `throws=` so Celery logs it without a traceback; it is not added to `autoretry_for`.                                                                                                                                                |
| `src/paperless_mail/mail.py`               | When `EMAIL_ALLOW_INTERNAL_HOSTS` is false (the only case that pins today), `get_mailbox` calls `resolve_public_addresses(server, port)` in place of `resolve_hostname_ips` plus the manual `is_public_ip` loop, converting both exceptions to `MailError(blocked_message(exc))`. `PinnedIMAP4` takes `tuple[IPAddress, ...]` and calls `str(ip)` at `socket.create_connection`. `_create_socket` tests `pinned_ips is not None` rather than truthiness, so an empty tuple fails closed instead of falling back to imaplib's own hostname lookup. User-facing messages are unchanged. |
| `src/paperless/serialisers.py`             | Unchanged; still calls `validate_outbound_http_url` on save.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |

### 5.1 Error surfaces for AI

- New `LLMBlockedError` in `src/paperless_ai/exceptions.py`. It is raised with a message ("AI backend request was blocked by the outbound request policy: <str of the underlying block>") so that tracked Celery tasks record a useful `error_message`.
- `AIClient._normalize_errors` raises `LLMBlockedError(...) from exc` when the exception, or any exception in its `__cause__` chain, is an `OutboundRequestBlockedError`. This covers the Ollama path (our exception passes through ollama untouched) and the OpenAI-like path (`APIConnectionError` whose `__cause__` is ours). This check runs before the existing timeout and provider checks.
- `DocumentViewSet.ai_suggestions` maps `LLMBlockedError` to **502** with body `{"ai": [_("AI backend request was blocked by the outbound request policy. Check logs for details.")]}`, matching the shape and gettext use of the neighbouring timeout and provider handlers.
- **`apply_ai_suggestions` Celery task** (`documents/tasks.py`) also calls `get_ai_document_classification`. It auto-retries only `LLMTimeoutError`, and `workflows/ai.py` swallows only `ValueError`, so a block fails the task without retry and is recorded on the tracked task with the message above. Intended; no change needed beyond the message.
- If the separate connection-error PR lands first, `LLMBlockedError` is added alongside its handling; if this lands first, that PR builds on it.
- **Embedding blocks do not produce a 502.** `get_taxonomy_context` swallows every exception from the embedding path, so `ai_suggestions` continues without similar-document context after the retries finish (5.2). This is existing behaviour for any embedding failure and is not changed here.
- Chat streaming and the `llmindex_index` Celery task get no new handling; a block fails them the same way an unreachable backend does today.

### 5.2 Retry amplification (accepted)

On the OpenAI-like path a request-time block is retried by the openai SDK and llama-index:

- LLM: 4 SDK attempts (1 + `max_retries=3`) times 3 tenacity attempts, **12 attempts**.
- Embeddings: 11 SDK attempts times 10 tenacity attempts, **110 attempts**. Tenacity's `stop_after_delay(60)` is checked only after an attempt completes, and one SDK attempt with backoff takes roughly 40 to 55 s, so the total can exceed **100 s**.
- ollama has no retry layer. Only ollama follows redirects, so the redirect trigger does not apply to the openai path.
- `ai_suggestions` runs the embedding lookup and then the LLM call in series, so when both use the same blocked OpenAI-like endpoint the two retry costs add up (roughly 100 s of embedding retries, then the LLM retries).

Accepted because:

- No connection is opened to a blocked destination; each retry re-resolves and re-validates.
- It only occurs when an `*_ALLOW_INTERNAL_*` setting is `false` and DNS changes between the up-front check and connect. Static misconfiguration fails at client construction before any retry layer.
- The latency matches what an unreachable backend already costs.
- Avoiding it would require subclassing `openai.OpenAIError` or setting `max_retries=0`, which would also remove retries for genuine transient failures.

## 6. Documentation and compatibility

**Behaviour changes (changelog):**

- A blocked destination raises `OutboundRequestBlockedError` instead of `httpx.ConnectError`; webhook logs say "blocked" instead of a connect failure.
- With `allow_internal=False`, a DNS failure at connect time is reported as a connection error, not a block.
- Pinned connections fall back to the next resolved address.
- With default settings, AI and webhook connections use stock httpx connection behaviour (no pinning).
- `ai_suggestions` can return 502 for a policy block.
- `httpx`, `httpcore` and `anyio` become declared dependencies (versions unchanged from the current lock).

No settings, migrations or other API changes.

**Docs:**

- `docs/configuration.md`:
  - `PAPERLESS_AI_LLM_ALLOW_INTERNAL_ENDPOINTS`: when false, a hostname is blocked if any of its addresses is non-public, and redirects are re-checked. Requests connect directly and do not use `HTTP_PROXY`/`HTTPS_PROXY`.
  - `PAPERLESS_WEBHOOKS_ALLOW_INTERNAL_REQUESTS`: when false, a hostname is blocked if any of its addresses is non-public. Webhooks never follow redirects. Requests connect directly and do not use `HTTP_PROXY`/`HTTPS_PROXY`.
  - `PAPERLESS_EMAIL_ALLOW_INTERNAL_HOSTS`: when false, a hostname is blocked if any of its addresses is non-public (the existing text already mostly says this; align the wording).
- `docs/usage.md` webhook security paragraph: the webhook points above, briefly.

## 7. Testing

Conventions: pytest classes with the `django_db` mark only where needed, `mocker`, `@pytest.mark.parametrize` with `pytest.param(..., id=...)` on every case, class-level `usefixtures` for setup-only fixtures, GIVEN/WHEN/THEN docstrings, full annotations on tests and fixtures. Async tests use `@pytest.mark.anyio` with an `anyio_backend` fixture returning `"asyncio"`, following `src/paperless/tests/test_websockets.py`. No tests of stdlib behaviour. Resolver and clock are patched only through the module hooks (4.3).

**Errors**

- `OutboundRequestBlockedError` and `HostResolutionError` survive a pickle round trip with all fields intact, and `celery.utils.serialization.get_pickleable_exception(exc) is exc`.
- `str(exc)` is non-empty and names host, port and reason, and does not contain the offending address.
- `blocked_message` produces the two legacy texts and the unix-socket text.

**`is_public_ip`**

- Multicast blocked; `64:ff9b::/96` blocked at both boundaries and allowed just outside them.
- One CGNAT address blocked (pins that `is_global` still covers it after `100.64.0.0/10` is removed from our list).
- One ordinary public and one private address as sanity checks.
- Policy cases that must stay blocked: `0.0.0.0` and `::` (Linux routes the unspecified address to localhost), and IPv4-mapped loopback, metadata, private and CGNAT addresses (`::ffff:127.0.0.1`, `::ffff:169.254.169.254`, `::ffff:10.0.0.1`, `::ffff:100.64.0.1`).

**`resolve_public_addresses` / `aresolve_public_addresses`** (`_getaddrinfo` / `_agetaddrinfo` patched)

- IP literal: resolver not called.
- De-duplication with order preserved; zone ID stripped.
- Mixed public and private answers: blocked, `reason` and `address` correct.
- Resolver `gaierror`, `UnicodeError` (sync) and empty result: `HostResolutionError`.

**`validate_outbound_http_url`**

- Existing messages for a non-public answer and for an unresolvable name; `allow_internal=True` makes no resolver call.
- IDNA: for `https://faß.example/`, with `fass.example` answering public and `xn--fa-hia.example` answering private, the URL is blocked and the resolver is asked only for `xn--fa-hia.example`.
- A hostname with no valid IDNA 2008 encoding is rejected as invalid without a resolver call.

**Guard backends** (fake inner backend recording calls, configurable to fail per address; `_monotonic` patched)

- Dials IP literals, never the hostname.
- Family interleaving: resolver order `[v6a, v6b, v4a, v4b]` is dialled as `[v6a, v4a, v6b, v4b]`; `[v6a, v6b, v6c, v4a]` as `[v6a, v4a, v6b, v6c]`; a single-family list is unchanged.
- Falls back on `ConnectError` and on `ConnectTimeout`; re-raises the last error when all fail.
- Per-attempt timeouts: one parametrized case per row of the worked-examples table in 4.4, plus a fast refusal followed by a success within a 1 s budget (both addresses tried).
- Budget exhausted before an attempt raises `ConnectTimeout`; `timeout <= 0` raises `ConnectTimeout` without dialling.
- Attempt list capped at `MAX_ADDRESSES_TRIED`; a private address beyond the cap still blocks the name.
- `HostResolutionError` surfaces as `httpcore.ConnectError`, not a block.
- Async: a `_agetaddrinfo` fake that sleeps longer than a small real timeout (for example 0.05 s sleep against 0.01 s) yields `httpcore.ConnectTimeout`. This uses real time because `fail_after` follows the event loop clock, not `_monotonic`.
- Sync: resolver time does not reduce the attempt budget.
- `allow_internal=True`: hostname passed through unchanged, resolver not called.
- Every connection resolves again: a resolver answering public then private lets the first `connect_tcp` through and blocks the second with nothing dialled (DNS rebinding between pooled connections).
- The block WARNING names host, port and reason, and no captured log line contains the offending address.
- `connect_unix_socket` raises `UNIX_SOCKET`; `sleep` delegates.
- Every applicable case for both sync and async.

**Transports and factories**

- Layout canary: for each transport, the pool and backend types match 4.5 and the installed backend is the guard wrapping the original.
- Layout drift: when the pool or backend type is unexpected (patched), construction raises `RuntimeError`.
- Env `HTTPS_PROXY` set: a guarded client has `_mounts == {}` and connects through the guard; the same holds for the `httpx.Client` built inside `ollama.Client(transport=...)`.

**Real-socket integration.** Helpers live in `src/paperless_testing/outbound.py`, the shared test-support package (excluded from the Docker image and from coverage), so no app imports another app's test helpers. Thin `local_http_server`, `fake_dns` and `dial_recorder` fixtures in the root `src/conftest.py` import from it inside their bodies, keeping that file's module-scope imports minimal. No new dependency. It provides:

- a stdlib TCP/HTTP server on `127.0.0.1:0` in a thread, recording accepted connections and received request headers, and able to answer with a redirect;
- a resolver fake patched onto `paperless.network._getaddrinfo` (and `_agetaddrinfo`) that answers from a `{hostname: [addresses]}` map and delegates every other name to the real resolver (the guard never passes IP literals to it, and the stock backends use the unpatched `socket.getaddrinfo`);
- spies via `mocker.spy(httpcore.SyncBackend, "connect_tcp")` and `mocker.spy(AnyIOBackend, "connect_tcp")` to record the guard's dial sequence, since the transports accept no injected backend.

Scenarios (sync and async where the path differs), using the transports directly unless stated:

- Regression for the suspected #13782 cause: the test hostname maps to `::1` then `127.0.0.1`; the server listens on `127.0.0.1` only. Connecting to `::1` fails (refused, or unavailable where IPv6 is disabled; both surface as `ConnectError`).
  - Pinning path: `allow_internal=False` with `paperless.network.is_public_ip` patched to return `True`. The request succeeds and the spied dial sequence is `["::1", "127.0.0.1"]`.
  - `allow_internal=True` against `localhost`: the request succeeds, and the resolver fake was not consulted.
- `allow_internal=False` against `localhost` via the transport: `OutboundRequestBlockedError`, and the server records no connection. (Via a factory the up-front check raises `ValueError` first; that is covered by the factory tests.)
- The server receives `Host: <test hostname>:<port>`, not an IP.
- Connection pooling per host: two hostnames mapped to `127.0.0.1` on one client. Repeating a request to the first reuses its connection; the second hostname opens a new one (two dials, two server connections). This pins the fix for cross-host TLS session reuse.
- TLS server name: an HTTPS request to a named host (against the plain server, so the handshake fails) dials the validated address and calls `start_tls` with `server_hostname` equal to the hostname.
- Numeric host spellings (`2130706433`, `0x7f.1`, `127.1`) are blocked by the transport with no server connection.
- Proxy variables in the environment pointing at an unreachable proxy: a request to `localhost` raises `OutboundRequestBlockedError`, not a proxy error.
- Redirect: `is_public_ip` patched to allow `127.0.0.1` only. A client with `follow_redirects=True` requests the server on `127.0.0.1`, which redirects to a second test hostname mapped to `127.0.0.2`. The first hop succeeds and the second raises `OutboundRequestBlockedError` without dialling `127.0.0.2`.

**Consumers**

- AI client and embedding tests assert guarded transports with the right `allow_internal`, including the `OllamaEmbedding` private-client override (currently untested).
- Webhook SSRF tests move off pytest-httpx (it patches `HTTPTransport.handle_request` and so intercepts before any connection is opened) onto the integration fixture. The `resolve_to` fixture in `test_workflows.py` is **deleted**: it patches `socket.getaddrinfo` globally and returns port 0, which no longer reaches the guard and would misroute the stock backend's dialling of IP literals. `test_allows_public_ip_and_sends` loses its `req.url.host == <IP>` assertion because the rewrite is gone. Content-type and header tests stay on pytest-httpx.
- Webhook block test parametrized over loopback, private, link-local metadata, IPv4-mapped loopback and NAT64-wrapped loopback answers.
- Webhook task: a block is raised, matches `throws=` (the exception reaching `task_failure` is ours, not an `UnpickleableExceptionWrapper`), and `retry` is never called.
- `ai_suggestions` returns 502 with the specified body for `LLMBlockedError` from both the direct (Ollama) and `__cause__` (OpenAI-like) paths.
- `apply_ai_suggestions`: a block fails the task without retry, with a non-empty message. `task_failure_handler` stores `str(exception)` unchanged, so the message tests (which also assert the address is absent) stand in for the stored value.
- Mail: the pinning tests (`TestGetMailboxHostPinning`) and the mail-account API test that patches `paperless_mail.mail.resolve_hostname_ips` are updated to `resolve_public_addresses` and typed addresses; messages unchanged. A `PinnedIMAP4` with an empty tuple opens no socket, pinned or unpinned.

**Manual verification on the VM**

1. Add `::1 localhost` to `/etc/hosts` (first, so `getent ahosts localhost` lists `::1` before `127.0.0.1`); run a server bound only to `127.0.0.1`.
2. On current `dev`, with the default `WEBHOOKS_ALLOW_INTERNAL_REQUESTS=true`, a webhook to `http://localhost:<port>` fails with a connect error. If it does not, the suspected cause is wrong and section 1 is updated.
3. On the branch, the same webhook succeeds.
4. On the branch with `WEBHOOKS_ALLOW_INTERNAL_REQUESTS=false`, the webhook fails with `OutboundRequestBlockedError` logged as a block, not a connect error.
5. Revert the `/etc/hosts` change.
6. `ruff check`, `ruff format`, `pyrefly check` clean.

## 8. Implementation delegation

Implementation runs as subagent-driven development from a plan produced by the writing-plans skill. Each task is assigned a model tier by risk. Every task is followed by a spec-compliance review; security-relevant tasks additionally get an independent security review.

New code is added **alongside** the old until every consumer has moved, so the tree imports and tests pass after each task. Old code is removed in one cleanup task at the end.

| #   | Task                                                                                                                                                                                                                                                                                                                                                                   | Implementer | Review        |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------------- |
| 1   | Types and errors (`IPAddress`, `BlockReason`, both exceptions with message and `__reduce__`, `blocked_message`), `is_public_ip` rewrite, and **every** existing string caller updated to parse addresses: `validate_outbound_http_url`, `_rewrite_request_to_pinned_ip`, `mail.py`; the string-parametrized `is_public_ip` tests in `test_network.py` rewritten; tests | Sonnet      | Opus security |
| 2   | `resolve_public_addresses` / `aresolve_public_addresses`, module test hooks, `validate_outbound_http_url` switched to them (`resolve_hostname_ips` kept for now); tests                                                                                                                                                                                                | Opus        | Opus security |
| 3   | Guard backends (sync and async): timeout sanity, resolution, interleaving, cap, attempt timeouts, error mapping, unix socket refusal, logging; tests                                                                                                                                                                                                                   | Opus        | Opus security |
| 4   | Guarded transports and factories with layout assertions; declared dependencies and `uv lock`; transport tests including proxy and drift                                                                                                                                                                                                                                | Opus        | Opus security |
| 5   | Real-socket integration helpers in `src/paperless_testing/outbound.py`, fixtures in the root `src/conftest.py`; scenarios                                                                                                                                                                                                                                              | Sonnet      | Opus security |
| 6   | AI consumers (`client.py`, `embedding.py`) switched; tests                                                                                                                                                                                                                                                                                                             | Sonnet      | Sonnet spec   |
| 7   | `LLMBlockedError` with message, `_normalize_errors` cause-chain check, 502 mapping in the view, `apply_ai_suggestions` behaviour; tests (after 6, same file)                                                                                                                                                                                                           | Sonnet      | Sonnet spec   |
| 8   | Webhooks switched, `throws=` updated, SSRF tests moved onto the shared integration helpers, `resolve_to` fixture deleted                                                                                                                                                                                                                                               | Sonnet      | Opus security |
| 9   | Mail switched to `resolve_public_addresses` and `blocked_message`; typed addresses; pinning tests and the mail-account API test updated                                                                                                                                                                                                                                | Sonnet      | Sonnet spec   |
| 10  | Cleanup: remove the old transports, factories, rewrite, `format_host_for_url`, `resolve_hostname_ips` and their tests; grep confirms no references remain                                                                                                                                                                                                              | Sonnet      | Sonnet spec   |
| 11  | Docs (`configuration.md`, `usage.md`)                                                                                                                                                                                                                                                                                                                                  | Haiku       | Sonnet spec   |
| 12  | Full backend test run on the VM, `ruff`, `pyrefly`; failures escalate to Sonnet                                                                                                                                                                                                                                                                                        | Haiku       | n/a           |
| 13  | Whole-branch final review (security, typing, conventions, this spec)                                                                                                                                                                                                                                                                                                   | n/a         | Opus          |

Order: 1, 2, 3, 4, 5 are sequential. 6, 8 and 9 depend on 5 and are independent of each other; 7 follows 6. 10 follows 6 to 9. 11 can run any time after 4. 12 and 13 run last.

## 9. Library extraction

Not now. A published library would still be security code we own, would widen the support and CVE surface, and would have to support a range of httpx versions while depending on private attributes. The in-tree module is kept extractable (no Django imports, small public surface: the two transports, the two factories, `validate_outbound_http_url`, `OutboundRequestBlockedError`, `HostResolutionError`, `BlockReason`, `blocked_message`, `IPAddress`, `is_public_ip`, `resolve_public_addresses`, `aresolve_public_addresses`). Revisit after a release or two in production, or if httpx gains a public `network_backend` parameter.

## 10. Rules for implementation, commits and PRs

- **No internal tracking or planning metadata** in code, comments, docstrings, test names, test docstrings, commit messages, branch names or PR descriptions. That includes task or step numbers, plan or spec file paths, section references from this document, todo items, agent or model tier names, session identifiers and review-round labels. Code and history must read as ordinary engineering work that stands on its own.
- The project's required AI-assistance attribution (the commit `Co-Authored-By` trailer and the PR description note required by the contribution policy) is not tracking metadata and is still included.
- This spec and the implementation plan are not committed without explicit approval.
- No em dashes in any written output.
- Branch from `dev`; PR targets `dev`.

## 11. Known limitations

- Remote OCR (Azure) validates per request but does not pin, so DNS rebinding between the check and urllib3's own lookup remains possible there. The check does resolve the same IDNA 2008 name urllib3 dials (4.3). Follow-up.
- OpenAI-like with no endpoint configured uses the SDK's unguarded default client (admin-controlled destination).
- No outbound proxy support for guarded clients.
- Request-time blocks on the OpenAI-like path are retried by the SDK and llama-index (latency only; up to about 100 s for embeddings).
- Depends on httpx's private `HTTPTransport._pool`, httpcore's `_network_backend`, and httpcore's unexported `httpcore._backends.auto.AutoBackend`; guarded by exact-type assertions at construction, a canary test, and narrow version pins.
- Per-attempt budgets can be very small near the end of a nearly exhausted timeout (the loop stops only at `remaining <= 0`); harmless, the attempt fails fast.
- With `allow_internal=False`, attempts are sequential rather than happy eyeballs; a black-holed first address delays the next by up to 10 s.
- Unpatched Python 3.11/3.12 builds classify 6to4 and `64:ff9b:1::/48` as global.
- The deprecated or special ranges listed in 4.2 are treated as public.
- Sync DNS resolution cannot be interrupted by the connect timeout (same as the stock backend).
- The suspected #13782 root cause is unconfirmed pending reporter output.
