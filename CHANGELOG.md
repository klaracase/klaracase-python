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
