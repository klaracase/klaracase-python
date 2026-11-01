# Klaracase SDK conformance pack

Language-neutral test cases for the five SDKs (TypeScript, Python, PHP, Go, Rust), 106 cases in
all (102 for API 0.95.0, four added for 0.96.0: `meta.credits_api_budget`,
`errors.insufficient_credits_api_budget_empty`, `errors.insufficient_credits_api_budget_not_available`
and `errors.token_limit_reached`). Each SDK test
suite loads these files, runs a local mock HTTP server, and checks that the SDK sends the right
request and returns or raises the right thing. The design is `../../DESIGN.md` (sections 2 and 3);
the API is `../CONTRACT.md`.

```
conformance/
  README.md        this file
  validate.py      checks the pack itself:  python3 -I validate.py
  cases/*.json     one case per file; the file name is the case name plus .json
  problems/*.json  problem+json bodies, one per file (also usable on their own)
  bodies/*.json    other response bodies derived from ../examples (document states, unknown keys, ...)
  files/           input files for upload cases (schriftsatz.pdf)
../examples/*.json the twelve success bodies; cases reference them as ../../examples/<file>
```

Copy what you use into your repo's `tests/fixtures/`. Keep the relative layout (`cases/`,
`problems/`, `bodies/`, `files/`, `examples/`), because `body_file` paths are relative to the case
file.

## 1. Case file format

```json
{
  "name": "decisions.search.basic",
  "description": "free text",
  "sdk": {"group": "decisions", "method": "search", "args": {"query": "..."}, "options": {}, "env": {}, "repeat": 1},
  "expect": {"request": {...} , "request_count": 1, "sleeps": [{"exact": 1}]},
  "responses": [{"status": 200, "headers": {...}, "body_file": "../../examples/decisions.search.json"}],
  "expect_result": {"kind": "success", "assert": {"results[0].aktenzeichen": "1 StR 185/01"}},
  "runner": {"real_clock": true, "repeat_last_response": true}
}
```

### `sdk`

| Key | Meaning |
|---|---|
| `group`, `method` | The SDK method to call, from the method table in DESIGN.md 3.2, written in snake_case. `group` is `null` for the top-level `search` method. Adapt casing to your language (`citationChecks.create`, `CitationChecks.Create`). |
| `args` | Arguments by their API parameter name (snake_case). A value of `null` means "pass nothing" (see section 3). A value `{"$file": "files/schriftsatz.pdf"}` means "the bytes of that file, relative to this folder"; pass them in your SDK's file type. |
| `options` | Client options. `token` (omitted: the runner's default `test_token_123`; `null`: pass no token; `""`: pass an empty string), `max_retries`, `timeout` (seconds), `user_agent_suffix`, `base_url_trailing_slash` (append `/` to the base URL). |
| `env` | Environment for this case. The runner first removes `KLARACASE_API_TOKEN`, then sets exactly these variables. |
| `repeat` | Call the method this many times in a row on the SAME client (default 1). `expect_result` applies to every call. |

The runner builds the client with `base_url = http://127.0.0.1:<port>/api/v1` (plus `/` when
`base_url_trailing_slash` is set), `max_retries` and `timeout` from `options` (SDK defaults when
absent), and the token `test_token_123`.

### `expect`

- `request`: the one request the mock must see (section 3), or `null` when the SDK must fail before
  any request.
- `request_count`: how many requests the mock must see in total. An integer, or `{"min": n,
  "max": m}`. Present in every case.
- `sleeps` (optional): the waits the SDK took between attempts, in order (section 6). Absent
  means: no assertion on sleeps, and the retry policy produces none for this case.

Every request the mock receives must match `expect.request`. A retry sends the same request again.

### `responses`

The mock answers the 1st request with `responses[0]`, the 2nd with `responses[1]`, and so on. A
request with no response left fails the test (HTTP 599 from the mock and a test failure), unless
`runner.repeat_last_response` is true, in which case the last entry repeats.

| Key | Meaning |
|---|---|
| `status` | HTTP status. |
| `headers` | Lower-case header names. The mock sends them as given. If `content-type` is absent and the body is JSON, the mock sends `application/json`. |
| `body` | Inline JSON, sent serialised. |
| `body_file` | Path relative to the case file. A `.json` file is sent as is; any other file is sent as text. |
| `body_text` | A string sent as is (non-JSON bodies). |
| `delay_seconds` | The mock waits this long before it answers. Used with a short `timeout` to test timeouts. The SDK has given up by then; the mock must not fail when it cannot write the late answer. |
| `drop_connection` | `true`: the mock reads the whole request, then closes the socket without sending anything. Replaces `status`. |

At most one of `body`, `body_file`, `body_text` per response.

### `expect_result`

- `kind: "success"` with `assert`: a map from a path to an expected value (section 5).
  Optional extras: `deprecation_warning` (bool), `deprecation` (raw header values the hook must
  receive), `deprecation_warning_count` (how many times the hook ran in total), `body_roundtrip`.
- `kind: "error"` with `class`, `code`, `status` and optional `fields` (section 7).

### `runner`

Optional flags for a case that needs special handling. `real_clock`: do not stub sleep or the
clock for this case (a timeout test). `repeat_last_response`: see `responses`.

## 2. How a runner uses a case

One test per case file:

1. Reset state: unset `KLARACASE_API_TOKEN`, then apply `sdk.env`; reset the process-wide
   deprecation guard (section 8); clear the mock's recorded requests and recorded sleeps.
2. Load the case. Start (or reuse) the mock with `responses`.
3. Build the client from `sdk.options`. If construction raises, go to step 6.
4. Call the SDK method named by `sdk.group` and `sdk.method` with `sdk.args`, `repeat` times.
5. Record what it returned or raised.
6. Assert: every recorded request matches `expect.request` (section 3); the number of requests
   fits `request_count`; the recorded sleeps fit `sleeps`; the result fits `expect_result`.

If `expect.request` is `null`, the failure must come before any request: the mock sees 0 requests.
A case with an `error` result and `class: "ConfigurationError"` fails in step 3, all other cases in
step 4.

## 3. Request matching rules

**Method.** Exact.

**Path.** Relative to the path of the base URL (`/api/v1`). Compared as the RAW request path, not
decoded. This is the percent-encoding rule, and it is binding for every SDK:

> Each path parameter is encoded on its own as ONE segment. Every byte of its UTF-8 form outside
> the unreserved set of RFC 3986 (`A-Z a-z 0-9 - . _ ~`) becomes `%XX` with UPPER-case hex.
> A space is `%20` (never `+`), a slash is `%2F`, a colon is `%3A`, `§` is `%C2%A7`. The
> characters `! * ' ( ) : @ & = + $ , ;` are encoded too, although some standard library helpers
> (JavaScript `encodeURIComponent`, Go `url.PathEscape`) leave some of them alone. The fixed
> parts of the path (`/decisions/`, `/citations`) are written as is.

Examples: `VIII ZR 271/17` is `VIII%20ZR%20271%2F17`; `§ 535 BGB` is `%C2%A7%20535%20BGB`;
`Art. 6 DSGVO` is `Art.%206%20DSGVO`; an ECLI is `ECLI%3ADE%3ABGH%3A2001%3A151101U1STR185.01.0`.
The server also accepts a raw slash; the SDK never sends one.

**Query.** The mock decodes the query string into name/value pairs (it decodes both `%20` and `+`
as a space, and `%5B%5D` as `[]`). `expect.request.query` is a map from decoded name to a string
or a list of strings. Rules:

- The set of names must equal the map exactly. No extra parameters.
- The ORDER of parameters is irrelevant.
- A list is an array parameter sent as `name[]` repeated: `cited_statutes[]=StGB&cited_statutes[]=StPO`.
  The order of the values inside one list matters and equals the order of the argument.
- Every value is a string: integers are decimal (`"5"`), booleans are `"true"` or `"false"`.
- An argument that is `null`, unset, or an empty array is not sent. `false` and `0` are values and are sent.
- Query values must be encoded so that they decode to the original string (`&`, `=`, `+`, `#`, `%`,
  `§`, umlauts). The exact bytes on the wire are not compared.
- `"query": {}` means there is no query string.

**Headers.** Names are case-insensitive. Every header listed in `expect.request.headers` must be
present; other headers (Host, Content-Length, Accept-Encoding, ...) are ignored. Values are compared
exactly, with two exceptions:

- `user-agent` is matched by PREFIX. The case lists `klaracase-`. The full form is
  `klaracase-<lang>/<sdk-version> <runtime>/<runtime-version>` (DESIGN.md 3.1). When the request has
  `user_agent_suffix`, the header must also END with that suffix, after a space.
- `content-type` is matched by media type only: the part before `;`, case-insensitive. JSON requests
  send `application/json`; an upload sends `multipart/form-data` (the boundary is ignored).

`authorization` is exactly `Bearer test_token_123`. `accept` is `application/json`.
Requests without a body (all GETs) assert no `content-type`.

**JSON body.** `expect.request.json` is compared as parsed JSON, deeply. Object key order is
irrelevant, array order matters, a string must equal the decoded string (the SDK may escape
non-ASCII as `\uXXXX` or not). Keys with `null` or unset arguments are absent, and no default is
added: `{"ids": [...]}` means exactly that body.

**Multipart.** `expect.request.multipart` is a list of parts, each `{name, filename, content_type}`.
The mock parses the body and compares the part list by field name, filename and content type only.
It does not compare file bytes or the boundary. There is exactly one part, `file`.

## 4. Mock server behaviour

Bind to `127.0.0.1` on a free port. Record method, raw path, decoded query, headers, and body of
every request. Never use the network. If a case needs a header the mock cannot produce (for
example `drop_connection` in your HTTP test toolkit), use a raw socket server for that case.

## 5. Success assertions

`expect_result.assert` maps a path to an expected value. The path addresses the SDK result as if it
were the JSON body of the answer, with these additions.

Path grammar: names joined by `.`, an integer index `[0]`, and a quoted key `["§ 543 Abs. 1 BGB"]`
for keys that contain dots or spaces. Names are the API's snake_case keys. Map them to your
language's accessor (`result.results[0].aktenzeichen`, `result["credits"]["cost"]`,
`res.Results[0].Aktenzeichen`). A runner may keep a small adapter per language.

Special roots:

- `meta.status`: the HTTP status of the answer (200, 202).
- `meta.api_release`: the value of `X-Klaracase-Api-Release`, or `null` when the header is absent.
- `meta.request_duration`: a number of seconds, 0 or more.
- `extra.<key>`: the logical home of a key the SDK does not model. `extra.future_key.nested[1]`
  means: the unknown top-level key `future_key`, then `nested`, then index 1. Each SDK documents
  where its unknown keys live (a map `extra`, an index into the raw JSON, `serde_json::Value`, ...)
  and the runner adapter maps `extra.` to that place. Known keys are not required to appear there.
- `credits.metered`, `credits.cost`, `credits.credits_remaining`: first-class field `credits`.
- `credits.api_budget.cents`, `credits.api_budget.rate_cents_per_credit`,
  `credits.api_budget.credits_at_rate` (0.96.0): the optional prepaid-budget object. When the
  server omits it, the SDK's field is absent or unset, never an invented zero (every older case has
  no `api_budget` and must still pass).

A value is a literal (string, number, boolean, `null`) compared by equality, or a matcher object
whose keys all start with `$`:

| Matcher | Meaning |
|---|---|
| `{"$type": "number"}` | JSON type: `number`, `string`, `object`, `array`, `boolean` |
| `{"$min": 0}` | number at least this |
| `{"$length": 1000}` | length of a string or array |
| `{"$contains": "text"}` | string contains the text |
| `{"$starts_with": "text"}` | string starts with the text |

Several matcher keys in one object must all hold.

Other result flags:

- `body_roundtrip: true`: the SDK's lossless view of the answer (its documented raw or `to_dict`
  form, without `meta`) equals the parsed body. This proves nothing was renamed, reordered, dropped
  or cleaned, including unknown keys nested in known objects. Required for `meta.unknown_keys_preserved`.
- `deprecation_warning: true|false`: the `on_deprecation` hook was or was not called.
  `deprecation`: the hook receives the raw `Deprecation`, `Sunset` and `Link` header values (the
  SDK may add parsed forms). `deprecation_warning_count`: how many times the hook ran in the whole case.

## 6. Retry and sleep assertions

The policy is DESIGN.md 3.5. `validate.py` runs a reference simulation of it over every case, so
the numbers in the pack agree with the policy. The cases fix these readings of it:

- Retry on HTTP 429 and 503, for GET and POST, up to `max_retries` times. So `max_retries` 2 means
  at most 3 requests. Never on 402, 404, 409, 422, nor on 500 or 502.
- The wait: `retry_after_seconds` from the problem body if present, else the `Retry-After` header
  (whole seconds), else exponential backoff with full jitter: a random wait between 0 and
  `min(8, 0.5 * 2^n)` seconds, where n is 0 for the first retry. The body value wins over the header.
- A server-stated wait ABOVE 30 seconds is not slept: the SDK raises `RateLimitError` at once with
  the value. Exactly 30 is slept. The 8 second cap applies to the computed backoff only.
- A transport error (the connection dropped, a timeout) is retried for GET only, with the backoff
  above. A POST is never retried after a transport error.
- `volume_cap` is a 429 whose wait is hours, so it is raised at once, never slept.

`expect.sleeps` is a list, one entry per wait, in order: `{"exact": 1}` or `{"min": 0, "max": 0.5}`
(the jitter range; assert `min <= slept <= max`). The wait is the duration passed to the SDK's
sleep function.

Every SDK MUST have an injectable sleep function used for retries and for `wait_until_ready` (a
client option or an internal hook that tests set), and a clock for the `wait_until_ready` timeout.
The runner replaces sleep with a recorder that returns at once. Cases with `runner.real_clock` use the real
sleep and clock.

`wait_until_ready` sleeps `poll_interval` between polls (`{"exact": 1}` when `poll_interval` is 1).
Non-terminal statuses: `uploaded`, `extracting`, `ocr_pending`. `ready` returns the receipt. `failed`
raises `DocumentFailedError`.

## 7. Error assertions

`expect_result` with `kind: "error"`:

| Key | Meaning |
|---|---|
| `class` | The exception or error type. One of the names below. |
| `code` | `error.code`. For a problem answer, the `code` member. |
| `status` | `error.status`: the HTTP status, or `null` when there was no answer. |
| `fields` | Extra assertions, same path grammar and matchers as `assert`, rooted at the error object. |

Classes by HTTP status (the HTTP status decides the class; the body `status` is not consulted):

| Status | Class | Extra typed field |
|---|---|---|
| 401 | `AuthenticationError` | |
| 402 | `InsufficientCreditsError` | `cost`, `balance` |
| 403 | `PermissionError` (`ForbiddenError` where the name clashes) | `required_ability` |
| 404 | `NotFoundError` | |
| 409 | `ConflictError` | |
| 422 | `ValidationError` | `errors` (map of field to list of messages) |
| 429 | `RateLimitError` | `retry_after_seconds` |
| 503 | `ServiceUnavailableError` | |
| any other | `ApiError` | |

All of these extend `KlaracaseError`. Classes with no HTTP answer, also `KlaracaseError`
subclasses: `TransportError` (status `null`, wraps the network exception), `DocumentFailedError`,
`DocumentTimeoutError`, and the client-side `ValidationError` (below). Outside that hierarchy:
`ConfigurationError`.

For every error that comes from a problem body the runner ALSO checks, without the case saying so:
`error.type`, `title`, `detail`, `status` and `code` equal the body members, `error.api_release`
equals the `X-Klaracase-Api-Release` header (`null` when absent), and `error.extra` holds every
member of the body except those five. Typed fields such as `cost` are therefore also present in
`extra`. In `fields`, a bare name such as `cost` means the typed field when the SDK has one and
`extra.<name>` otherwise. The SDK needs typed fields only for the five of DESIGN.md 3.4
(`required_ability`, `errors`, `cost`, `balance`, `retry_after_seconds`); `unit`, `cap`, `resets_at`,
`candidates` and `successor` are read from `extra`, and so are the 0.96.0 members `reason`,
`top_up_url`, `spent` and `settings_url`. A body member the SDK does not know stays
readable in `extra`.

**402 without `cost`.** `token_limit_reached` (0.96.0) is a 402, so it is an `InsufficientCreditsError`
by status, but its body carries no `cost` and no `balance`. The typed fields are then absent
(`null`, `None`, `nil`), and `insufficient_credits` is the only 402 that always has them. The SDK
never opens `top_up_url` or `settings_url`: they are for a human organization admin.

**Not a problem body.** A body is a problem when it is a JSON object with a string `code`. Any other
body on an error status (HTML from nginx, `{"message": "Server Error"}`, an empty body) becomes the
class for its status with `code = "unknown"`, and `detail` = the raw body text, cut to at most
1000 characters (a longer body gives exactly the first 1000 characters, no ellipsis). The content
type is not consulted. `type` and `title` are not asserted for these.

**Client-side errors** (no request is sent, `expect.request` is `null`):

- `ValidationError` with `code: "client_validation"` and `status: null`: `citation_checks.create`
  with both `text` and `document_id`, or with neither.
- `ConfigurationError` at construction: no token in the argument or in `KLARACASE_API_TOKEN`, or an
  empty token. Not a `KlaracaseError` and not part of the problem hierarchy. The message must contain
  `KLARACASE_API_TOKEN`. It has no `code` and no `status`.

**`wait_until_ready` errors.** `DocumentFailedError`: `code` equals the receipt's `error_code`
(`encrypted_pdf`), `status` is `null`, `error_code` and `document` (the receipt, with `id` and
`status`) are readable. `DocumentTimeoutError`: raised when the timeout passes before a terminal
status; `status` is `null`; `document` is the last receipt. A problem answer while polling raises
the class for its status as usual.

## 8. Notes for the five runners

- Name mapping: `snake_case` here; use your language's convention for methods and arguments, but keep
  the wire names (`cited_statutes[]`, `include_citations`) exact.
- `null` in `args`: pass the language's "unset". In Go and Rust that is a nil pointer or `None`.
- Files: read `{"$file": ...}` from this folder and pass bytes (or a reader) with `filename` and `content_type`.
- The deprecation guard ("once per process", DESIGN.md 3.5) is process-wide in production. Every SDK
  exposes an internal way to reset it between tests. The runner calls it in step 1.
- Do not assert on the SDK-private User-Agent runtime part, on `Accept-Encoding`, or on header order.
- The mock must record the raw request target to compare the raw path; most frameworks decode paths
  before the handler sees them, so read the raw request line or use a raw server.

## 9. Decisions where the contract is silent

The pack fixes these. If you disagree, tell the architect; do not diverge per language.

1. Path encoding rule: section 3 (the contract says only "URL-encoded" and "ONE segment").
2. A non-problem or `code`-less error body: section 7.
3. `extra` holds every non-standard problem member, typed ones included.
4. The server-stated wait limit is "above 30": 30 is slept, 31 is not. The 8 s cap covers backoff only.
5. `502` and `500` are not retried (DESIGN.md 3.5 names only 429 and 503).
6. A transport error on a POST is never retried, including a refused connection.
7. `ocr_pending` is non-terminal for `wait_until_ready`.
8. `DocumentTimeoutError` is the name for the timeout error DESIGN.md 3.2 leaves unnamed.
9. A `Retry-After` header holding an HTTP date is not covered. Only whole seconds are.
10. The `document_unavailable` problem carries NO upload `status` member. The server's problem builder
    drops any extra member named `status`, `type`, `title`, `detail` or `code`, so the field the
    facts list never reaches the wire. See `problems/document_unavailable.json`.
11. Server-side range limits (1 to 10 ids, `max_chars` bounds) are not duplicated on the client, and
    the pack has no case for them.

## 10. Case groups

| Prefix | What it covers |
|---|---|
| `decisions.search.*`, `search.*` | the two search operations: omission, null, booleans, arrays, encoding of values |
| `decisions.get.*`, `decisions.citations.*`, `norms.get.*` | path encoding, slice and option parameters |
| `datapackages.create.*`, `citation_checks.*` | JSON bodies, client-side validation |
| `citation_check_documents.*` | multipart upload, receipts, `wait_until_ready` |
| `corpus.*` | coverage and facets |
| `meta.*` | `meta`, `credits`, unknown keys |
| `errors.*` | one case per error code family, HTML and non-problem bodies |
| `retry.*`, `transport.*` | retry policy, sleeps, request counts, dropped connections, timeouts |
| `deprecation.*` | the deprecation hook |
| `construction.*` | token from environment, missing token, User-Agent suffix, base URL |

`python3 -I validate.py` must print `OK` before you copy the pack.
