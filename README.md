# klaracase

The official Python client for the [Klaracase](https://klaracase.de) REST API. Klaracase holds
German court decisions and statutes, linked by a citation graph. It also checks the citations in a
German legal text.

Klaracase covers German law only. It is a research tool. It gives no legal advice and does not
replace a lawyer's review. A `not_found` verdict means the citation was not found in the corpus; it
is not a claim that the citation is fabricated.

- Sync client `Klaracase` and async client `AsyncKlaracase`.
- One runtime dependency: `httpx2`. Python 3.11 or newer.
- Typed requests and typed responses (frozen dataclasses). Unknown response keys are kept.
- API reference: https://klaracase.de/docs/api. This client targets API release 0.95.0.

## Install

```sh
pip install klaracase
# or
uv add klaracase
```

## Get a token

Create an API token at https://klaracase.de/settings/api-tokens. You need a login and a verified
email.

- A token has abilities: `search`, `read`, `graph`, `datapackage` and `citation-check`. A call
  that needs an ability the token lacks fails with a 403.
- A token is bound to the organization that is open when you create it. Every call is billed to
  that organization.
- A token expires after 30, 90, 180 or 365 days. The default is 365.
- The same token works on the REST API and on the MCP server.

Never put a token in source code. Set it in the environment:

```sh
export KLARACASE_API_TOKEN=klc_your_token_here
```

The client reads `KLARACASE_API_TOKEN` when you pass no `token`. With no token at all, the
constructor raises `ConfigurationError`.

## Quick start

```python
from klaracase import Klaracase

client = Klaracase()  # reads KLARACASE_API_TOKEN

result = client.decisions.search("Vermögensbetreuungspflicht Geschäftsführer", court="BGH")
for hit in result.results:
    print(hit.aktenzeichen, hit.court, hit.date, hit.title)

print(result.credits.cost, result.credits.credits_remaining)
print(result.meta.status, result.meta.api_release, result.meta.request_duration)
```

Other calls:

```python
import datetime

client.search("§ 266 StGB Untreue")  # statutes and decisions together
decision = client.decisions.get("1 StR 185/01", section="Leitsatz")
print(decision.ecli, decision.document_type)
graph = client.decisions.citations(decision.id, direction="incoming")
norm = client.norms.get("§ 535 BGB")
package = client.datapackages.create([decision.id], full_text=False)
coverage = client.corpus.coverage(top=5)  # free
facets = client.corpus.facets("court_name", prefix="BGH")  # free
recent = client.decisions.search("Untreue", date_from=datetime.date(2020, 1, 1))
```

`decisions.get` takes a UUID, an Aktenzeichen or an ECLI. The client encodes a slash or a space in
a path value for you. A date argument is a `YYYY-MM-DD` string or a `datetime.date`.

Every answer is a typed object, nested at every level: `hit.court`, `finding.verdict`,
`finding.matched_decision.ecli`. See "Response objects" below.

## Check the citations in a text

```python
text = open("schriftsatz.txt", encoding="utf-8").read()
run = client.citation_checks.create(text=text, reference_date="2026-10-01")

if run.status != "complete":
    raise RuntimeError(f"The check ended {run.status}: {run.findings_unavailable_reason}")

for finding in run.findings:
    print(f"{finding.verdict:<18} {finding.canonical}  <- {finding.excerpt(text)!r}")
    if finding.verdict == "not_found":
        print("  Not found in the corpus. Check it by hand before you rely on it or call it wrong.")

print(run.verdict_counts)
print({verdict: len(found) for verdict, found in run.by_verdict().items()})
```

Check `status` before you use `findings`. The call answers with the finished run, but a run can
end `rejected` or `failed`.

The seven verdicts are `verified_corpus`, `verified_external`, `not_found`, `out_of_coverage`,
`ambiguous`, `unverifiable` and `discrepancy`. A verdict that the API adds later stays a plain
string. `verified_corpus` means the citation exists in the corpus. It does not show that a quote or
a legal claim is correct.

The text must be 50 to 20,000 characters. The check runs in one request and the answer is the
finished run. It costs `max(2, ceil(characters / 5000))` credits. Checking the same text again in
the same month costs 0. Offsets are Unicode code point offsets into the exact string you sent.
`finding.excerpt(text)` slices them for you.

## Uploads and polling

To check a file, use `create_from_file`. It uploads the file, waits until the text is extracted,
and then checks it:

```python
from pathlib import Path

from klaracase import DocumentFailedError, DocumentTimeoutError

try:
    run = client.citation_checks.create_from_file(Path("schriftsatz.pdf"), wait_timeout=120.0)
except DocumentFailedError as error:
    print("The file could not be read:", error.error_code)  # for example encrypted_pdf
except DocumentTimeoutError:
    print("The text extraction took too long. Try again later.")
else:
    print(run.status, run.verdict_counts)
```

The same in steps, if you want the receipt (it shows the price before you pay it):

```python
from pathlib import Path

receipt = client.citation_check_documents.upload(Path("schriftsatz.pdf"))
receipt = client.citation_check_documents.wait_until_ready(receipt.id, timeout=120.0)
print(receipt.quoted_credits)
run = client.citation_checks.create(document_id=receipt.id)
```

`upload` takes a `Path`, a `str` path, `bytes` or a binary file object. The file name and the
content type are taken from the path. For bytes, pass `filename=`. An upload accepts PDF, DOCX,
Markdown and text files up to 25 MB. Uploading is free. Pass exactly one of `text` and
`document_id`; a type checker refuses both. If the upload ends in status `failed`,
`wait_until_ready` raises `DocumentFailedError` and `error.code` holds the reason. If it is not
ready in time, it raises `DocumentTimeoutError`.

## Async

```python
import asyncio

from klaracase import AsyncKlaracase


async def main() -> None:
    async with AsyncKlaracase() as client:
        found, coverage = await asyncio.gather(
            client.decisions.search("Widerrufsrecht Fernabsatzvertrag"),
            client.corpus.coverage(),
        )
        print(len(found.results), coverage.total_decisions)

        async for page in client.decisions.iter_pages("Widerrufsrecht", max_pages=2):
            print(page.page, len(page.results))


asyncio.run(main())
```

Both clients have the same methods and arguments. Use `with` or `async with`, or call `close()` or
`aclose()`, to release the connection pool. The async client is imported on first use, so a sync
program does not pay for `asyncio`.

## Pagination

```python
for page in client.decisions.iter_pages("Untreue", max_pages=3, court="BGH"):
    for hit in page.results:
        print(page.page, hit.aktenzeichen)

for graph in client.decisions.iter_citation_pages("1 StR 185/01", max_pages=2):
    print(len(graph.references), len(graph.referenced_by))
```

`max_pages` is required. There is no default, so a loop cannot run away. The iterators stop at an
empty page, and at 10 pages (search) or 20 pages (citation graph), which is all the API serves.

Credits: paging the same query within a credit period costs no extra credits. A changed query,
filter or mode is a new charge. Check `credits` on each response. Each page is still one request,
so it counts against your rate limit and your daily row cap. The citation graph costs 2 credits
for each decision, direction and depth, and its pages cost nothing more.

## Errors

Every error from the API or the network is a `KlaracaseError`. It has the fields of the RFC 9457
problem: `type`, `title`, `status` (also `status_code`), `detail` and `code`. Every other member of
the problem body is in `error.extra`. `error.body` is the whole problem body, `error.response_headers`
holds the response headers with lower-case names, and `error.api_release` holds the
`X-Klaracase-Api-Release` header. `error.retryable` says if a later retry can succeed.

```python
from klaracase import (
    ForbiddenError,
    InsufficientCreditsError,
    KlaracaseError,
    RateLimitError,
)

try:
    run = client.citation_checks.create(text=text)
except InsufficientCreditsError as error:
    print(f"Needs {error.cost} credits, balance {error.balance}.")
except ForbiddenError as error:
    print(f"The token lacks the {error.required_ability!r} ability.")
except RateLimitError as error:
    print(f"Try again in {error.retry_after_seconds} s.")
except KlaracaseError as error:
    print(error.status_code, error.code, error.detail, error.retryable)
```

| Class | When |
|---|---|
| `AuthenticationError` | 401 |
| `InsufficientCreditsError` | 402, with `cost` and `balance` |
| `ForbiddenError` | 403, with `required_ability` |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `ValidationError` (also `UnprocessableEntityError`) | 422, with `errors`; also a request the client refuses to send (`code == "client_validation"`, `status is None`) |
| `RateLimitError` | 429, with `retry_after_seconds` |
| `ServiceUnavailableError` | 503 |
| `ApiError` | any other status, and any body that is not a problem |
| `TransportError` | no answer arrived; `KlaracaseTimeoutError` is the timeout subclass |
| `ResponseShapeError` | the answer lacks an identity key (`id`, `reference` or `field`) |
| `DocumentFailedError`, `DocumentTimeoutError` | raised by `wait_until_ready` |
| `ConfigurationError` | a bad client setting; not a `KlaracaseError` |

Two names differ from the usual ones because Python already uses them: the 403 class is
`ForbiddenError` (Python has a builtin `PermissionError`) and the timeout class is
`KlaracaseTimeoutError` (Python has a builtin `TimeoutError`).

`error.code` is typed `ErrorCode`: the known codes as a `Literal`, plus `str` for a code the API
adds later. A body that is not a problem (for example an HTML 502 page from a proxy) becomes the
class for its status with `code == "unknown"`. `detail` holds the first 1,000 characters of the
body.

## Retries

The client retries at most `max_retries` times (default 2).

- It retries a 429 and a 503. Both mean that nothing ran and nothing was charged, so the retry is
  safe on every call, including POST.
- It waits `retry_after_seconds` from the body, or else the `Retry-After` header, or else an
  exponential backoff with jitter (up to 0.5 s, 1 s, 2 s, capped at 8 s).
- If the server asks for more than 30 seconds, the client does not sleep. It raises
  `RateLimitError` and you decide. A `volume_cap` error (the daily cap) is always raised at once.
- It never retries a 402 or another 4xx, and it does not retry a 500 or a 502.
- A transport error (connection refused, DNS, TLS, timeout) is retried on GET only. A POST whose
  connection dropped after the request was sent is not retried, because the request may have run.
  A repeat of the same check text in the same month costs 0.

```python
fast = Klaracase(max_retries=0, timeout=10.0)  # fail fast
```

## Request options

Every call takes three keyword-only options. They apply to that call only.

```python
from klaracase import Timeout

result = client.decisions.search(
    "Untreue",
    timeout=Timeout(60.0, connect=5.0),  # or a number of seconds
    extra_headers={"X-Team": "billing"},
    extra_query={"flag": True},
)
```

`extra_headers` are added to the request, and win over a header of the same name. `extra_query`
parameters are added to the query and replace a parameter of the same name. The default timeout is
30 seconds, with 5 seconds to connect.

`with_options` returns a new client with other settings. It shares the connection pool of the
first client, so it is cheap:

```python
patient = client.with_options(timeout=120.0, max_retries=5, extra_headers={"X-Team": "billing"})
patient.citation_checks.create(text=text)
```

Closing the new client does nothing. Close the first client when you are done with both.

For an endpoint that this version does not wrap, use `client.get(path, params)` or
`client.post(path, json)`. They keep the retries and return a `Response` with `raw`, `extra`,
`credits` and `meta`:

```python
answer = client.get("/corpus/coverage", {"top": 3})
print(answer.raw["courts_total"], answer.meta.status)
```

## Logging

The package logs to `logging.getLogger("klaracase")` and is silent until you configure logging.
To see what it does, set `KLARACASE_LOG` before you build the first client:

```sh
KLARACASE_LOG=info python my_script.py    # one line per request and per retry
KLARACASE_LOG=debug python my_script.py   # adds the names of the query parameters
```

INFO lines hold the method, the path, the status, the attempt and, on a retry, the wait. A
deprecation is a WARNING. The token, request bodies and query values are never logged. In your own
logging setup, use the logger name `klaracase`.

## Credits

Search, `decisions.get` and `norms.get` cost 1 credit each. `decisions.citations` costs 2. A data
package costs 5. A citation check costs from 2 credits, by length. Corpus calls, uploads and reads
of a stored run are free. Every answer has `credits` with `metered`, `cost` and
`credits_remaining`. `credits` is always an object, so `result.credits.cost` is safe to read; its
fields are `None` when the account is not metered.

## Response objects

Every method returns a frozen dataclass, nested at every level.

- One attribute for each documented key, named like the wire key. The wire key `from` is `from_`
  because `from` is a Python keyword.
- `extra`: every key this version does not model, at every depth. The API only adds keys, so a new
  API release does not break your code.
- A value of the wrong type never raises. A scalar or an object reads as `None`, a list as `[]`
  and a mapping as `{}`. `raw` keeps the body as it came.
- An identity key (`id`, `reference`, `field`) is required. A body without it raises
  `ResponseShapeError`.
- Open vocabularies are `Literal[...] | str` (`Verdict`, `RunStatus`, `DocumentType`,
  `Confidence`, and more), so a value added later stays a string.
- `meta`: `status`, `api_release`, `request_duration` (seconds) and `headers` (lower-case names).
- `raw` and `to_dict()`: the parsed JSON body, unchanged (`to_dict()` is a deep copy). Nothing is
  renamed, reordered, cleaned or translated, including the German advisory strings.
- `Decision.ecli` and `Decision.document_type` read from `metadata`.

### Use the models with pydantic

The models are plain dataclasses, so pydantic takes them as they are. This package does not depend
on pydantic. Checked with pydantic 2.14:

```python
from pydantic import TypeAdapter

from klaracase import Decision

adapter = TypeAdapter(Decision)
decision = client.decisions.get("1 StR 185/01")
payload = adapter.dump_json(decision)  # serialise
again = adapter.validate_python(decision.to_dict())  # validate a wire body
```

Pydantic is stricter than the SDK decoder. It raises on a value of the wrong type, and it does not
fill `extra` or `raw`. The wire key `from` of `CoverageRange` needs the SDK decoder
(`CorpusCoverage.from_dict`).

## Deprecations

When an endpoint is deprecated, the API announces it with `Deprecation` and `Sunset` headers. The
client calls `on_deprecation` once per process with the raw header values. The default hook emits
a `DeprecationWarning`. The same notice is logged as a WARNING.

```python
import logging

log = logging.getLogger(__name__)
watched = Klaracase(on_deprecation=lambda notice: log.warning("deprecated: %s", notice.sunset))
```

Call `klaracase.reset_deprecation_warnings()` in tests to reset the once-per-process guard.

## Agents

This client is a REST client. It does not speak MCP. To give an AI agent Klaracase tools, you have
two ways.

1. Connect the agent to the Klaracase MCP server at `https://klaracase.de/mcp` (streamable HTTP).
   It accepts the same API token as a Bearer token (`Authorization: Bearer <token>`). This is the
   way for the OpenAI Agents SDK, for LangChain with `langchain-mcp-adapters`, and for CrewAI.
2. Use `klaracase.agents`. It needs no extra package. It gives you tool definitions and a
   dispatcher for five tools: `search_decisions`, `get_decision`, `get_norm`, `check_citations`
   and `cross_type_search`.

```python
from klaracase.agents import dispatch, tool_definitions

tools = tool_definitions(format="anthropic")  # or "openai", or "json_schema" (the default)
only_two = tool_definitions(["search_decisions", "get_norm"], format="openai")

# When the model asks for a tool, run it and give the text back to the model:
result_text = dispatch(client, "get_norm", {"reference": "§ 535 BGB"})
```

`dispatch` returns compact JSON text. `get_decision` cuts the text to 4,000 characters unless the
call sets `max_chars`. `check_citations` returns the run `id`, the `status`, the `verdict_counts`,
the `unique_citations` and, for each finding, only `id`, `canonical`, `verdict`, `raw_text` and the
offsets. A `KlaracaseError` does not raise. It comes back as text the model can read:

```json
{"error":{"code":"insufficient_credits","detail":"...","retry_after_seconds":null}}
```

`adispatch(async_client, name, args)` does the same for the async client. The schemas are built
from the same types as the methods, and a test keeps every schema equal to the keyword arguments
of the method it calls. An agent should cite only what a tool returned.

See `examples/agent_loop.py` for a runnable loop with a scripted model.

## Advanced

### Your own HTTP client

Pass an `httpx2.Client` (or `httpx2.AsyncClient`) as `http_client`. The SDK does not close it. The
SDK sets the timeout on every request, so the timeout of your client is not used. Set the timeout
with the `timeout` argument of the SDK client, or of one call.

To change only a proxy, a CA bundle or a client certificate, use `DefaultHttpClient`. It is an
`httpx2.Client` with the SDK defaults, and it takes every argument of `httpx2.Client`:

```python
from klaracase import DefaultHttpClient, Klaracase

proxied = Klaracase(http_client=DefaultHttpClient(proxy="http://proxy.example:3128"))
private_ca = Klaracase(http_client=DefaultHttpClient(verify="/etc/ssl/company-ca.pem"))
```

`DefaultAsyncHttpClient` is the async twin. To test your code without the network, pass an
`httpx2.Client` built on `httpx2.MockTransport`. This repository tests itself that way.

### Settings

```python
Klaracase(
    token=None,  # else KLARACASE_API_TOKEN
    base_url="https://klaracase.de/api/v1",
    timeout=30.0,  # seconds or a Timeout, per attempt; the default is Timeout(30, connect=5)
    max_retries=2,
    user_agent_suffix=None,  # appended to "klaracase-python/0.1.0 python/3.x.y"
    http_client=None,  # your own httpx2.Client / httpx2.AsyncClient
    on_deprecation=None,
    sleep=None,  # replace time.sleep / asyncio.sleep, for tests
    monotonic=None,  # replace time.monotonic, for tests
)
```

The `repr` of a client never shows the token.

## Requirements

- Python 3.11 or newer.
- `httpx2` 2.12 or newer, below 3. It is the maintained continuation of `httpx`, with the same API
  under a new import name. The OpenAI and Anthropic SDKs use it too.
- The package is typed (`py.typed`). It passes `mypy --strict` and `pyright` in strict mode, and a
  type checker refuses a call with both `text` and `document_id`.

## Versioning

This SDK follows semantic versioning, with the 0.x rule: until 1.0, a minor version (0.2.0) may
change the public surface, and a patch version (0.1.1) only fixes bugs. Every change is listed in
[CHANGELOG.md](CHANGELOG.md). All Klaracase SDKs bump together when the API contract changes. This
version targets API release 0.95.0. The API itself only adds keys in v1, so a key that is new on
the wire shows up in `extra` first and becomes a field in a later minor version.

## Stability and privacy

The SDK sends no telemetry. The only thing it adds to a request is the User-Agent header
`klaracase-python/<version> python/<version>`, for example `klaracase-python/0.1.0 python/3.12.4`.
Logging is off unless you turn it on, and it never holds the token, a request body or a query
value.

Klaracase is not affiliated with any court or with the federal government.

## Development

```sh
uv sync
make test        # pytest, no network
make lint        # ruff
make typecheck   # mypy --strict and pyright strict
make wheel-check # build the wheel and check that py.typed ships
make smoke       # real API, free endpoints only, needs KLARACASE_API_TOKEN
```

The programs in `examples/` run against a local mock and need no token:

```sh
uv run python examples/quickstart.py
uv run python examples/citation_check.py
uv run python examples/agent_loop.py
```

## License

MIT. Copyright (c) 2026 SPARQ VENTURES UG.
