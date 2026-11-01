# Changelog

All notable changes to this project go in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `Klaracase` and `AsyncKlaracase` clients for the Klaracase REST API v1 (API release 0.95.0).
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
