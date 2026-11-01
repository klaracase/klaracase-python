# klaracase

The official Python client for the [Klaracase](https://klaracase.de) REST API. Klaracase holds
German court decisions and statutes, linked by a citation graph. It also checks the citations in a
German legal text.

Klaracase covers German law only. It is a research tool. It gives no legal advice and does not
replace a lawyer's review. A `not_found` verdict means the citation was not found in the corpus; it
is not a claim that the citation is fabricated.

- Sync client `Klaracase` and async client `AsyncKlaracase`.
- One runtime dependency: `httpx`. Python 3.11 or newer.
- Typed requests and responses. Unknown response keys are kept.
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
    print(hit["aktenzeichen"], hit["court"], hit["date"], hit["title"])

print(result.credits.cost, result.credits.credits_remaining)
print(result.meta.status, result.meta.api_release, result.meta.request_duration)
```

Other calls:

```python
client.search("§ 266 StGB Untreue")  # statutes and decisions together
decision = client.decisions.get("1 StR 185/01", section="Leitsatz")
graph = client.decisions.citations(decision.id, direction="incoming")
norm = client.norms.get("§ 535 BGB")
package = client.datapackages.create([decision.id], full_text=False)
coverage = client.corpus.coverage(top=5)  # free
facets = client.corpus.facets("court_name", prefix="BGH")  # free
```

`decisions.get` takes a UUID, an Aktenzeichen or an ECLI. The client encodes a slash or a space in
a path value for you.

## Check the citations in a text

```python
text = open("schriftsatz.txt", encoding="utf-8").read()
run = client.citation_checks.create(text=text, reference_date="2026-10-01")

for finding in run.findings:
    where = text[finding["start_offset"] : finding["end_offset"]]
    print(f"{finding['verdict']:<18} {finding['canonical']}  <- {where!r}")
    if finding["verdict"] == "not_found":
        print("  Not found in the corpus. Check it by hand before you rely on it or call it wrong.")

print(run.verdict_counts)
```

The seven verdicts are `verified_corpus`, `verified_external`, `not_found`, `out_of_coverage`,
`ambiguous`, `unverifiable` and `discrepancy`. A verdict that the API adds later stays a plain
string. `verified_corpus` means the citation exists in the corpus. It does not show that a quote or
a legal claim is correct.

The text must be 50 to 20,000 characters. The check runs in one request and the answer is the
finished run. It costs `max(2, ceil(characters / 5000))` credits. Checking the same text again in
the same month costs 0. Offsets are Unicode code point offsets into the exact string you sent.

To check a file, upload it first:

```python
with open("schriftsatz.pdf", "rb") as handle:
    receipt = client.citation_check_documents.upload(
        handle, filename="schriftsatz.pdf", content_type="application/pdf"
    )
receipt = client.citation_check_documents.wait_until_ready(receipt.id, timeout=120.0)
print(receipt.quoted_credits)
run = client.citation_checks.create(document_id=receipt.id)
```

An upload accepts PDF, DOCX, Markdown and text files up to 25 MB. Uploading is free. Pass exactly
one of `text` and `document_id`. If the upload ends in status `failed`, `wait_until_ready` raises
`DocumentFailedError` and `error.code` holds the reason, for example `encrypted_pdf`. If it is not
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


asyncio.run(main())
```

Both clients have the same methods and arguments. Use `with` or `async with`, or call `close()` or
`aclose()`, to release the connection pool.

## Errors

Every error from the API or the network is a `KlaracaseError`. It has the fields of the RFC 9457
problem: `type`, `title`, `status`, `detail` and `code`. Every other member of the problem body is
in `error.extra`. `error.api_release` holds the `X-Klaracase-Api-Release` header.

```python
from klaracase import (
    InsufficientCreditsError,
    RateLimitError,
    ForbiddenError,
    KlaracaseError,
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
    print(error.status, error.code, error.detail)
```

| Class | When |
|---|---|
| `AuthenticationError` | 401 |
| `InsufficientCreditsError` | 402, with `cost` and `balance` |
| `ForbiddenError` | 403, with `required_ability` |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `ValidationError` | 422, with `errors`; also a request the client refuses to send (`code == "client_validation"`, `status is None`) |
| `RateLimitError` | 429, with `retry_after_seconds` |
| `ServiceUnavailableError` | 503 |
| `ApiError` | any other status, and any body that is not a problem |
| `TransportError` | no answer arrived; `KlaracaseTimeoutError` is the timeout subclass |
| `DocumentFailedError`, `DocumentTimeoutError` | raised by `wait_until_ready` |
| `ConfigurationError` | a bad client setting; not a `KlaracaseError` |

Two names differ from the usual ones because Python already uses them: the 403 class is
`ForbiddenError` (Python has a builtin `PermissionError`) and the timeout class is
`KlaracaseTimeoutError` (Python has a builtin `TimeoutError`).

A body that is not a problem (for example an HTML 502 page from a proxy) becomes the class for its
status with `code == "unknown"`. `detail` holds the first 1,000 characters of the body.

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
client = Klaracase(max_retries=0, timeout=10.0)  # fail fast
```

## Credits

Search, `decisions.get` and `norms.get` cost 1 credit each. `decisions.citations` costs 2. A data
package costs 5. A citation check costs from 2 credits, by length. Corpus calls, uploads and reads
of a stored run are free. Every answer has `credits` with `metered`, `cost` and
`credits_remaining`.

## Response objects

Every method returns a frozen dataclass.

- One attribute for each documented top-level key, with the value exactly as the API sent it.
  Nested items are plain `dict` and `list` values. A documented key that the server did not send reads as `None`.
- `extra`: every top-level key this version does not model. The API only adds keys, so a new API
  release does not break your code.
- `meta`: `status`, `api_release` and `request_duration` (seconds).
- `credits`: `metered`, `cost`, `credits_remaining`.
- `to_dict()`: the parsed JSON body, unchanged. Nothing is renamed, reordered, cleaned or
  translated, including the German advisory strings.

## Deprecations

When an endpoint is deprecated, the API announces it with `Deprecation` and `Sunset` headers. The
client calls `on_deprecation` once per process with the raw header values. The default hook emits
a `DeprecationWarning`.

```python
Klaracase(on_deprecation=lambda notice: log.warning("deprecated: %s", notice.sunset))
```

Call `klaracase.reset_deprecation_warnings()` in tests to reset the once-per-process guard.

## Settings and tests

```python
Klaracase(
    token=None,  # else KLARACASE_API_TOKEN
    base_url="https://klaracase.de/api/v1",
    timeout=30.0,  # seconds, per attempt
    max_retries=2,
    user_agent_suffix=None,  # appended to "klaracase-python/0.1.0 python/3.x.y"
    http_client=None,  # your own httpx.Client / httpx.AsyncClient (proxy, mTLS, transport)
    on_deprecation=None,
    sleep=None,  # replace time.sleep / asyncio.sleep, for tests
    monotonic=None,  # replace time.monotonic, for tests
)
```

To test your code without the network, pass an `httpx.Client` built on `httpx.MockTransport`.
This repository tests itself that way.

## Agents

This client is a REST client. It does not speak MCP. To give an AI agent Klaracase tools, connect
the agent to the Klaracase MCP server at `https://klaracase.de/mcp` (streamable HTTP). It accepts
the same API token as a Bearer token. This is the way for the OpenAI Agents SDK, for LangChain
with `langchain-mcp-adapters`, and for CrewAI.

The transport is streamable HTTP. Put the same API token in the header
`Authorization: Bearer <token>`. See the documentation of `langchain-mcp-adapters`, the OpenAI
Agents SDK or CrewAI for how to register a remote MCP server.

If you prefer a plain function tool, wrap the client. Register the function with the function-tool
decorator of your framework. The docstring becomes the tool description.

```python
from klaracase import Klaracase

client = Klaracase()


def check_citations(text: str) -> dict:
    """Check the court-decision and statute citations in a German legal text against the
    Klaracase corpus. Returns one verdict per citation. `not_found` means the citation was not
    found in the corpus. It does not mean the citation is fabricated."""
    run = client.citation_checks.create(text=text)
    return {
        "verdict_counts": run.verdict_counts,
        "findings": [
            {
                "citation": f["canonical"],
                "verdict": f["verdict"],
                "start_offset": f["start_offset"],
                "end_offset": f["end_offset"],
            }
            for f in run.findings
        ],
    }
```

An agent should cite only what a tool returned.

## Development

```sh
uv sync
make test       # pytest, no network
make lint       # ruff
make typecheck  # mypy --strict
make smoke      # real API, free endpoints only, needs KLARACASE_API_TOKEN
```

## License

MIT. Copyright (c) 2026 SPARQ VENTURES UG.
