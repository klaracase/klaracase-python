# Changelog

All notable changes to this project go in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `Klaracase` and `AsyncKlaracase` clients for the Klaracase REST API v1 (API release 0.96.0).
- Resource groups for decisions, cross-type search, norms, data packages, citation checks,
  citation check documents and corpus.
- Typed responses that keep unknown keys, and a `ResponseMeta` with the HTTP status, the API
  release and the request duration.
- Typed errors for every problem status, with `code` and the extra problem members.
- Retries for 429 and 503, and for transport errors on GET.
- An `on_deprecation` hook for `Deprecation` and `Sunset` headers.
- The HTTP library is now `httpx2` (the maintained continuation of `httpx`; the same API under a
  new import name; the OpenAI and Anthropic SDKs depend on it). All HTTP imports sit in one
  internal module, `_transport.py`.
- `timeout` accepts a float or a `Timeout`. The default is `Timeout(30, connect=5)`.
- `DefaultHttpClient` and `DefaultAsyncHttpClient` for proxy, CA bundle or certificate changes.
- Typed response model: frozen, slotted dataclasses nested at every level (`hit.court`,
  `finding.verdict`, `finding.matched_decision.ecli`) instead of dicts. Unknown keys land in
  `extra` at every depth. A wrong-typed value never raises. `Model.from_dict` is the decoder.
- `ResponseShapeError` for a body that lacks an identity key (`id`, `reference`, `field`).
- `credits` is always a `Credits`. `Decision.ecli` and `Decision.document_type` read from
  `metadata`. `Finding.excerpt(text)` and `CitationCheck.by_verdict()`.
- Open enums are `Literal[...] | str`: `Verdict`, `RunStatus`, `DocumentStatus`,
  `DocumentErrorCode`, `DocumentType`, `Confidence`, `Lifecycle`, `Jurisdiction`, `SearchMode`,
  `Branch`.
- Drift guards in the tests: a walker fails when any `extra` is non-empty at any depth for every
  example, conformance body and contract example, and a seen-to-fail test proves the walker works.
- Keyword-only `timeout`, `extra_headers` and `extra_query` on all 12 methods, sync and async.
- `client.with_options(timeout=, max_retries=, extra_headers=)` returns a new client that shares
  the connection pool.
- `client.get(path, params)` and `client.post(path, json)` escape hatches, with retries, that
  return a `Response`.
- `citation_checks.create` has two overloads, so a type checker rejects `text` and `document_id`
  together.
- Date arguments accept `str | datetime.date`. `cited_statutes` accepts `CitedStatute | str`.
- Uploads accept `Path | str | bytes | BinaryIO`. The file name and the content type are inferred.
- Google-style `Args:` docstrings on all 12 methods.
- `ResponseMeta.headers` (lower-case names). Errors carry `response_headers`, `body` (the raw
  problem dict), `status_code` (an alias of `status`) and a `retryable` property, and have a
  readable `repr`.
- `UnprocessableEntityError` is another name for `ValidationError`.
- `ErrorCode` and `KnownErrorCode`: `error.code` is typed from the closed vocabulary, plus `str`.
- `repr` of the clients never shows the token. Public classes present as `klaracase.Name`.
- Logging on `logging.getLogger("klaracase")` with a `NullHandler`. `KLARACASE_LOG=info|debug`
  adds a stderr handler when the first client is built. INFO logs method, path, status, attempt
  and the wait on a retry. A deprecation is a WARNING. The token, bodies and query values are
  never logged.
- `decisions.iter_pages` and `decisions.iter_citation_pages` (generators; async generators on the
  async client). `max_pages` is required and is capped at 10 and 20. They stop on an empty page.
- `citation_checks.create_from_file` uploads, waits for the extraction and creates the check.
- `klaracase.agents`: `tool_definitions()` for Anthropic, OpenAI or plain JSON Schema, and
  `dispatch` / `adispatch` that run a tool call and return compact JSON or an error object. No
  new dependency. A test keeps every schema equal to the method signature it calls.
- `pyright` (strict) joins `mypy --strict` in the dev group and in CI. `tests/typing/consumer.py`
  is a realistic user program that both checkers must accept. Its refusal lines carry
  `type: ignore`, so a checker that stops refusing them fails the build.
- The README code blocks are type-checked with mypy and pyright strict.
- `__all__` lists the whole public surface. `AsyncKlaracase` is imported on first use.
- The package version has a single source, `src/klaracase/_version.py`. Hatch reads it.
- Tests: sync and async parity (methods, signatures, coroutines, `Args:` docs), a lowest-direct
  dependency job in CI, and a wheel check (`scripts/check_wheel.py`) for `py.typed`.
- `examples/`: `quickstart.py`, `citation_check.py` and `agent_loop.py`. They run against a local
  mock and need no token. A test runs them.
- README: token, async, uploads, pagination, errors, retries, request options, logging, agents,
  credits, response objects, a pydantic `TypeAdapter` note, versioning and privacy.
- Correction: paging the same query within a credit period costs no extra credits (the API leaves
  `page` and `limit` out of the charge). A changed query, filter or mode is a new charge. The
  iterator docstrings and the README now say so. `max_pages` stays required as a runaway guard.
- API release 0.96.0 (additive): `Credits.api_budget`, an `ApiBudget` with `cents`,
  `rate_cents_per_credit` and `credits_at_rate`. It is `None` when the body has no `api_budget`
  key, and unknown keys stay in `extra`.
- `InsufficientCreditsError.reason` (`api_budget_empty`, `api_budget_not_available`, or a value the
  API adds later) and `InsufficientCreditsError.top_up_url`. The client never opens the URL. A
  program or an AI agent must not either.
- `InsufficientCreditsError.api_budget`, an `ApiBudget` read from the optional `api_budget` member
  of the 402 problem, or `None` when the problem has none.
- `TokenLimitReachedError` for a 402 `token_limit_reached`, a subclass of
  `InsufficientCreditsError`, with `unit`, `cap`, `spent`, `resets_at` (a `datetime`),
  `resets_at_raw` and `settings_url`. `cost` and `balance` read `None`. It is never retried.
- `klaracase.agents`: the error object of a 402 adds `reason`, or `unit`, `cap`, `spent` and
  `resets_at`. It never carries `top_up_url` or `settings_url`.
- The conformance pack is 106 cases (four new), and the drift guards cover the new body.

### Docs

- README section "Credits, API budget and limits": plan credits, the optional prepaid API budget
  for Professional and Enterprise, limits per API token, and what a program does on each refusal.

- Docs: credit period wording. Credits renew per credit period: the UTC calendar month for free organizations, the paid billing period for subscribers. Unused credits do not roll over. The docs said "calendar month" for every organization.
