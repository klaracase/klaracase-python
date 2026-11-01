# Klaracase REST API v1 contract (generated from openapi-v1.json, version 0.95.0)

Base URL: https://klaracase.de/api/v1

Auth: `Authorization: Bearer <token>` (Sanctum personal access token, org-pinned, abilities: search, read, graph, datapackage, citation-check).

Every response carries `X-Klaracase-Api-Release`. Every error is RFC 9457 `application/problem+json`.


## POST /citation-checks

**Check the citations in a text**

Verifies every court-decision and statute citation in a German legal text against the corpus
and answers one verdict per citation, with offsets into your text: the REST twin of the MCP
tool `check_citations`. Synchronous: the answer is the finished run. Send the text as
`text`, or the `document_id` of an upload whose `status` is `ready`. Priced by length, from
2 credits; an upload's `quoted_credits` names the price before you check it. A text longer
than the cap is refused before any charge, and the same text checked again this month costs
nothing more.


### Request body

Content-Type: `application/json`

- `text` (string): The German legal text to verify (min 50 characters, max 20000; longer documents are checked in the Citation Check of the web app). The length is a floor, not the gate: the text must also show at least two of five independent legal-signal categories, so a lone statute sentence is rejected however long it is. Response offsets are Unicode codepoint offsets into THIS exact string.
- `reference_date` (string): OPTIONAL document date, ISO `YYYY-MM-DD`. It is applied to every statute citation whose own sentence names no date; a sentence that states its own date always wins. It gates the pre-reform-numbering advisory and changes no verdict. Each finding reports which date it used in `evidence.citation_date_source` (`sentence` | `reference_date` | `none`).
- `document_id` (string): The id of an upload whose `status` is `ready` (POST /citation-checks takes this or `text`, never both). The check consumes the upload.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "id": "0193b0c5-1a2b-7c3d-8e4f-5a6b7c8d9e0f",
 "status": "complete",
 "source": "api_v1",
 "progress": {
  "citations_total": 2,
  "citations_checked": 2,
  "unique_citations_total": 2
 },
 "verdict_counts": {
  "verified": 1,
  "not_found": 1
 },
 "partial": false,
 "unverified_count": 0,
 "reason_counts": [
  {
   "category": "statute_unknown",
   "count": 1
  }
 ],
 "unique_citations": [
  {
   "key_basis": "matched_decision",
   "target_artifact_id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
   "canonical": "BGH 1 StR 185/01",
   "spellings": [
    "BGH, Urt. v. 15.11.2001 – 1 StR 185/01"
   ],
   "occurrences": 1,
   "verdict": "verified",
   "reference_type": "case"
  },
  {
   "key_basis": "canonical",
   "target_artifact_id": null,
   "canonical": "§ 266a Abs. 9 StGB",
   "spellings": [
    "§ 266a Abs. 9 StGB"
   ],
   "occurrences": 1,
   "verdict": "not_found",
   "reference_type": "statute"
  }
 ],
 "extraction": {
  "detected": 2,
  "dropped": 0,
  "dropped_unreadable": 0,
  "dropped_truncation": 0,
  "dropped_trailing_noun": 0,
  "dropped_stacked_subdivision": 0,
  "dropped_refused_collision": 0,
  "dropped_by_token": [],
  "dropped_unreadable_texts": [],
  "refused_contract_collision": [],
  "not_verifiable": 0,
  "not_verifiable_by_type": [],
  "possible_citations_unparsed": 0,
  "possible_citations_unparsed_texts": []
 },
 "notes": [],
 "findings_unavailable_reason": null,
 "findings_purged_at": null,
 "findings": [
  {
   "id": "0193b0c5-2b3c-7d4e-9f50-6b7c8d9e0f1a",
   "raw_text": "BGH, Urt. v. 15.11.2001 – 1 StR 185/01",
   "canonical": "BGH 1 StR 185/01",
   "type": "case",
   "role": null,
   "verdict": "verified",
   "external_status": "skipped",
   "start_offset": 118,
   "end_offset": 157,
   "occurrence_index": 0,
   "confidence": null,
   "matched_decision": {
    "artifact_id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
    "ecli": "ECLI:DE:BGH:2001:151101U1STR185.01.0",
    "court": "BGH",
    "date": "2001-11-15"
   },
   "subdivision_check": "not_checked",
   "subdivision_advisory": null,
   "check_scope": {
    "subdivision": "not_applicable",
    "article_text_available": null,
    "article_text_read": false,
    "court": "checked"
   },
   "ambiguity_advisory": null,
   "coverage": null,
   "coverage_boundary": null,
   "coverage_advisory": null,
   "evidence": {
    "reason": "exact_match",
    "match_strength": "exact"
   },
   "disputed_at": null
  }
 ],
 "submitted_at": "2026-10-01T10:00:00+00:00",
 "completed_at": "2026-10-01T10:00:00+00:00",
 "created_at": "2026-10-01T10:00:00+00:00",
 "payload_truncated": false,
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 2,
  "credits_remaining": 18
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **402** Out of credits
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#insufficient_credits",
 "title": "Payment Required",
 "status": 402,
 "detail": "Insufficient credits: this call costs 2 credit(s), but organization \"Kanzlei Beispiel\" has 0 remaining this month. Credits renew automatically at the start of each calendar month (UTC). Ask your organization admin to raise the allotment, or retry next month.",
 "code": "insufficient_credits",
 "cost": 2,
 "balance": 0
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `citation-check` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "citation-check"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected text is invalid.",
 "code": "validation_failed",
 "errors": {
  "text": [
   "The selected text is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## GET /citation-checks/{run}

**Read a citation check run**

A run made through the API by your organization, read back by its id. Free.


### Responses

- **200** Success
  `application/json` example:
```json
{
 "id": "0193b0c5-1a2b-7c3d-8e4f-5a6b7c8d9e0f",
 "status": "complete",
 "source": "api_v1",
 "progress": {
  "citations_total": 2,
  "citations_checked": 2,
  "unique_citations_total": 2
 },
 "verdict_counts": {
  "verified": 1,
  "not_found": 1
 },
 "partial": false,
 "unverified_count": 0,
 "reason_counts": [
  {
   "category": "statute_unknown",
   "count": 1
  }
 ],
 "unique_citations": [
  {
   "key_basis": "matched_decision",
   "target_artifact_id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
   "canonical": "BGH 1 StR 185/01",
   "spellings": [
    "BGH, Urt. v. 15.11.2001 – 1 StR 185/01"
   ],
   "occurrences": 1,
   "verdict": "verified",
   "reference_type": "case"
  },
  {
   "key_basis": "canonical",
   "target_artifact_id": null,
   "canonical": "§ 266a Abs. 9 StGB",
   "spellings": [
    "§ 266a Abs. 9 StGB"
   ],
   "occurrences": 1,
   "verdict": "not_found",
   "reference_type": "statute"
  }
 ],
 "extraction": {
  "detected": 2,
  "dropped": 0,
  "dropped_unreadable": 0,
  "dropped_truncation": 0,
  "dropped_trailing_noun": 0,
  "dropped_stacked_subdivision": 0,
  "dropped_refused_collision": 0,
  "dropped_by_token": [],
  "dropped_unreadable_texts": [],
  "refused_contract_collision": [],
  "not_verifiable": 0,
  "not_verifiable_by_type": [],
  "possible_citations_unparsed": 0,
  "possible_citations_unparsed_texts": []
 },
 "notes": [],
 "findings_unavailable_reason": null,
 "findings_purged_at": null,
 "findings": [
  {
   "id": "0193b0c5-2b3c-7d4e-9f50-6b7c8d9e0f1a",
   "raw_text": "BGH, Urt. v. 15.11.2001 – 1 StR 185/01",
   "canonical": "BGH 1 StR 185/01",
   "type": "case",
   "role": null,
   "verdict": "verified",
   "external_status": "skipped",
   "start_offset": 118,
   "end_offset": 157,
   "occurrence_index": 0,
   "confidence": null,
   "matched_decision": {
    "artifact_id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
    "ecli": "ECLI:DE:BGH:2001:151101U1STR185.01.0",
    "court": "BGH",
    "date": "2001-11-15"
   },
   "subdivision_check": "not_checked",
   "subdivision_advisory": null,
   "check_scope": {
    "subdivision": "not_applicable",
    "article_text_available": null,
    "article_text_read": false,
    "court": "checked"
   },
   "ambiguity_advisory": null,
   "coverage": null,
   "coverage_boundary": null,
   "coverage_advisory": null,
   "evidence": {
    "reason": "exact_match",
    "match_strength": "exact"
   },
   "disputed_at": null
  }
 ],
 "submitted_at": "2026-10-01T10:00:00+00:00",
 "completed_at": "2026-10-01T10:00:00+00:00",
 "created_at": "2026-10-01T10:00:00+00:00",
 "payload_truncated": false,
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 0,
  "credits_remaining": 18
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `citation-check` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "citation-check"
}
```
- **404** Not found
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#not_found",
 "title": "Not Found",
 "status": 404,
 "detail": "The requested resource does not exist, or it belongs to another organization.",
 "code": "not_found"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected id is invalid.",
 "code": "validation_failed",
 "errors": {
  "id": [
   "The selected id is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```

## POST /citation-check-documents

**Upload a document to check**

Uploads a PDF, DOCX, Markdown or text file (up to 25 MB) as `multipart/form-data` in the
field `file`. Its text is extracted in the background: the answer is 202, and you poll the
upload until `status` is `ready`, then check it with `POST /citation-checks` and its
`document_id`. Free; your organization's upload quota applies.


### Request body

Content-Type: `multipart/form-data`

- `file` (string required): The document: PDF, DOCX, Markdown or plain text, up to 25 MB, sent as multipart/form-data.

### Responses

- **202** Accepted
  `application/json` example:
```json
{
 "id": "0193b0c6-3c4d-7e5f-8a60-7c8d9e0f1a2b",
 "filename": "schriftsatz.pdf",
 "format": "pdf",
 "status": "uploaded",
 "char_count": null,
 "page_count": null,
 "pages_without_text_layer": null,
 "check_max_chars": 20000,
 "quoted_credits": null,
 "error_code": null,
 "expires_at": "2026-10-02T10:00:00+00:00",
 "created_at": "2026-10-01T10:00:00+00:00",
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 0,
  "credits_remaining": 18
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `citation-check` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "citation-check"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected file is invalid.",
 "code": "validation_failed",
 "errors": {
  "file": [
   "The selected file is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```

## GET /citation-check-documents/{document}

**Read an upload**

The status of an upload by its id: `char_count` and `quoted_credits` once its text is
extracted, an `error_code` if extraction failed. The extracted text itself is never served.
Free.


### Responses

- **200** Success
  `application/json` example:
```json
{
 "id": "0193b0c6-3c4d-7e5f-8a60-7c8d9e0f1a2b",
 "filename": "schriftsatz.pdf",
 "format": "pdf",
 "status": "ready",
 "char_count": 14830,
 "page_count": 6,
 "pages_without_text_layer": 0,
 "check_max_chars": 20000,
 "quoted_credits": 2,
 "error_code": null,
 "expires_at": "2026-10-02T10:00:00+00:00",
 "created_at": "2026-10-01T10:00:00+00:00",
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 0,
  "credits_remaining": 18
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `citation-check` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "citation-check"
}
```
- **404** Not found
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#not_found",
 "title": "Not Found",
 "status": 404,
 "detail": "The requested resource does not exist, or it belongs to another organization.",
 "code": "not_found"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected id is invalid.",
 "code": "validation_failed",
 "errors": {
  "id": [
   "The selected id is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```

## GET /decisions/{id}/citations

**Citation graph of a decision**

The decisions one decision cites and the decisions citing it, paged, the REST twin of the
MCP tool `get_citation_graph`. Two credits per decision, direction and depth per month;
paging is free.


### Parameters

- `direction` (query, string enum[outgoing, incoming, both]) nullable: "outgoing" = decisions this one cites (references), "incoming" = decisions citing this one (referenced_by), "both" (default) = both directions.
- `depth` (query, integer enum[1, 2]) nullable: 1 (default) = direct neighbours; 2 = neighbours of neighbours, capped at 50 distinct neighbour decisions besides the source and served as a bounded sample.
- `court` (query, string) nullable: Optional disambiguator for an Aktenzeichen `id`: the canonical court short form, e.g. "BVerfG" or "OLG Hamm". Ignored for UUID lookups.
- `date` (query, string) nullable: Optional disambiguator for an Aktenzeichen `id`: the decision date in YYYY-MM-DD.
- `page` (query, integer) nullable: 1-based page (default 1) over the SOURCE decision's neighbour lists, 25 distinct decisions per direction, up to page 20. Defined at depth 1 only.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "source": {
  "id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
  "aktenzeichen": "1 StR 185/01",
  "court": "BGH",
  "date": "2001-11-15"
 },
 "references": [
  {
   "reference_canonical": "BGH 1 StR 50/15",
   "reference_role": "leitentscheidung",
   "resolution_status": "resolved",
   "in_corpus": true,
   "corpus": {
    "artifact_id": "0193b0c4-6a2d-7c4e-8f10-2b3c4d5e6f70",
    "court": "BGH",
    "date": "2015-03-12",
    "az": "1 StR 50/15",
    "document_type": "Urteil",
    "ecli": null,
    "corpus_url": "https://klaracase.de/decisions/0193b0c4-6a2d-7c4e-8f10-2b3c4d5e6f70"
   },
   "from_artifact_id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
   "hop": 1
  }
 ],
 "referenced_by": [
  {
   "reference_canonical": "BGH 1 StR 185/01",
   "reference_role": null,
   "resolution_status": "resolved",
   "in_corpus": true,
   "corpus": {
    "artifact_id": "0193b0c4-7b3e-7d5f-9a21-3c4d5e6f7a81",
    "court": "BGH",
    "date": "2022-06-08",
    "az": "4 StR 200/22",
    "document_type": "Beschluss",
    "ecli": null,
    "corpus_url": "https://klaracase.de/decisions/0193b0c4-7b3e-7d5f-9a21-3c4d5e6f7a81"
   },
   "from_artifact_id": "0193b0c4-7b3e-7d5f-9a21-3c4d5e6f7a81",
   "hop": 1
  }
 ],
 "served_direction": "both",
 "served_references_total": 1,
 "served_referenced_by_total": 1,
 "references_total": 1,
 "references_resolved_total": 1,
 "referenced_by_total": 1,
 "references_unresolved_total": 0,
 "references_withheld_reasons": [],
 "totals_scope": "source_decision_hop_1",
 "per_direction_cap": 25,
 "unresolved_cap": 25,
 "node_cap": 50,
 "truncated": false,
 "nodes_omitted": 0,
 "payload_truncated": false,
 "pagination": {
  "page": 1,
  "page_size": 25,
  "max_page": 20,
  "reachable_distinct_max": 500,
  "references_pages": 1,
  "referenced_by_pages": 1,
  "has_more_references": false,
  "has_more_referenced_by": false,
  "applies_at_depth": 1
 },
 "fortgeltung_checked": false,
 "fortgeltung_note": "Rechtskraft/Fortgeltung (whether a decision is still good law) is NOT checked. A decision returned here may have been quashed or superseded on appeal, and the ABSENCE of any such note is not evidence that it still stands.",
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 2,
  "credits_remaining": 25
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **402** Out of credits
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#insufficient_credits",
 "title": "Payment Required",
 "status": 402,
 "detail": "Insufficient credits: this call costs 2 credit(s), but organization \"Kanzlei Beispiel\" has 0 remaining this month. Credits renew automatically at the start of each calendar month (UTC). Ask your organization admin to raise the allotment, or retry next month.",
 "code": "insufficient_credits",
 "cost": 2,
 "balance": 0
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `graph` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "graph"
}
```
- **404** Not found
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#not_found",
 "title": "Not Found",
 "status": 404,
 "detail": "The requested resource does not exist, or it belongs to another organization.",
 "code": "not_found"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected direction is invalid.",
 "code": "validation_failed",
 "errors": {
  "direction": [
   "The selected direction is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## GET /corpus/coverage

**Corpus coverage**

What the corpus holds: per Gerichtsbarkeit and per court, the number of decisions and the
earliest and latest decision date, the REST twin of the MCP tool `corpus_coverage`. Free.
The figures in the example are illustrative.


### Parameters

- `branch` (query, string enum[ordentlich, verwaltung, sozial, arbeit, finanz, verfassung, patent, unbekannt]) nullable: Scope the report to one Gerichtsbarkeit slug. A branch is a COURT JURISDICTION, not a legal subject area: "patent" is the Bundespatentgericht. Omit to report every branch.
- `top` (query, integer) nullable: Cap on the per-court rows, busiest first (default 20, max 100). The branch rollup is never capped.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "total_decisions": {
  "value": 100000,
  "is_floor": false
 },
 "branches": [
  {
   "branch": "ordentlich",
   "count": {
    "value": 60000,
    "is_floor": false
   },
   "earliest": "1950-10",
   "latest": "2026-09",
   "court_founding_year": 1950,
   "court_founding_basis": "branch_wide_weakest_court_floor",
   "has_dates_below_floor": false,
   "instance_mix": {
    "federal": {
     "value": 25000,
     "is_floor": false
    },
    "appellate": {
     "value": 20000,
     "is_floor": false
    },
    "first_instance_and_regional": {
     "value": 15000,
     "is_floor": false
    },
    "other": {
     "value": 0,
     "is_floor": false
    },
    "note": "Instanzmix: 42% Bundesgerichte, 33% Obergerichte, 25% Eingangs- und Landgerichte. …"
   },
   "top_courts": [
    {
     "court": "BGH",
     "count": {
      "value": 25000,
      "is_floor": false
     },
     "earliest": "1950-10",
     "latest": "2026-09"
    }
   ]
  }
 ],
 "courts": [
  {
   "court": "BGH",
   "branch": "ordentlich",
   "count": {
    "value": 25000,
    "is_floor": false
   },
   "earliest": "1950-10",
   "latest": "2026-09",
   "court_founding_year": 1950,
   "court_founding_basis": "court_floor",
   "has_dates_below_floor": false
  }
 ],
 "courts_returned": 20,
 "courts_total": 400,
 "corpus_floors": "Earliest decision we hold per Gerichtsbarkeit … ordentlich 1950+. …",
 "coverage_ranges": {
  "note": "The ingestion boundary every `out_of_coverage` verdict is decided against. …",
  "scope": "all",
  "verified_at": "2026-08-13",
  "ranges": [
   {
    "bucket": "BGH_STRAFRECHT",
    "court": "BGH",
    "label": "BGH Strafsachen",
    "from": "1950-10-02",
    "until": null,
    "sources": [
     "ris"
    ],
    "exhaustive": true,
    "ocr": true,
    "note": "Strafsenate ab 1950.",
    "holdings_earliest": null
   }
  ]
 },
 "as_of": "2026-10-01T09:58:12+00:00",
 "filter_coverage_caveats": "Three known blind spots, all on scanned decisions. …",
 "law_coverage": {
  "note": "The law texts behind the citation check are German federal statutes, plus the EU and international instruments listed beside this note. …",
  "eu": [
   "AEUV",
   "DSGVO"
  ],
  "international": [
   "EMRK"
  ]
 },
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 0,
  "credits_remaining": 30
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `read` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "read"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected branch is invalid.",
 "code": "validation_failed",
 "errors": {
  "branch": [
   "The selected branch is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## GET /corpus/facets/{field}

**Filter values of a field**

The values the index holds for a filterable field, with counts, so a search filter uses
values that exist: the REST twin of the MCP tool `list_facets`. Free. The figures in the
example are illustrative.


### Parameters

- `type` (query, string enum[decision, law]) nullable: Restrict the counts to one artifact type. Omit to count across both. Ignored for field="cited_norms".
- `norm` (query, string) nullable: Required with field="cited_norms", ignored otherwise: the norm whose family to list, e.g. "§ 543 BGB". Canonicalized before use and echoed back.
- `prefix` (query, string) nullable: Case-insensitive prefix filter on the facet value. A trailing space counts: prefix="AG " excludes "AGH Niedersachsen", prefix="AG" keeps it.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "field": "court_name",
 "applies_to": "DECISION",
 "values": {
  "BGH": {
   "value": 90000,
   "is_floor": false
  },
  "BVerfG": {
   "value": 20000,
   "is_floor": false
  },
  "BVerwG": {
   "value": 15000,
   "is_floor": false
  }
 },
 "total_values": 3,
 "truncated": false,
 "value_limit": 500,
 "count_basis": "indexed_passages",
 "as_of": "2026-10-01T09:40:00+00:00",
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 0,
  "credits_remaining": 30
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `read` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "read"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected type is invalid.",
 "code": "validation_failed",
 "errors": {
  "type": [
   "The selected type is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## POST /datapackages

**Assemble a datapackage**

Up to ten decisions with their outgoing citation edges in one structured payload, as
grounded context for a language model: the REST twin of the MCP tool `assemble_datapackage`.
Five credits per set of decisions and options per month.


### Request body

Content-Type: `application/json`

- `ids` (array of string required): 1-10 decision ids. Order matters: the response budget drops decisions from the END. Duplicates collapse into one decision; `requested`, `included` and `deduped` report that.
- `include_citations` (boolean): Include each decision's outgoing citation edges (default true).
- `full_text` (boolean): Serve whole judgments instead of ~700-character excerpts (default false). Token-heavy; excerpts plus targeted get_decision calls are the lighter alternative.
- `max_chars` (integer): Per-decision text cap when `full_text` is true (default 60000, minimum 500, maximum 200000). A ceiling, not a guarantee: the response budget outranks it.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "decisions": [
  {
   "id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
   "aktenzeichen": "1 StR 185/01",
   "court": "BGH",
   "date": "2001-11-15",
   "document_type": "Urteil",
   "ecli": "ECLI:DE:BGH:2001:151101U1STR185.01.0",
   "jurisdiction": "DE",
   "excerpt": "Tenor … Gründe: I. Der Angeklagte war Geschäftsführer …",
   "excerpt_span": "document_start",
   "text_length": 48213,
   "truncated": true,
   "fortgeltung_checked": false,
   "fortgeltung_note": "Rechtskraft/Fortgeltung (whether a decision is still good law) is NOT checked. A decision returned here may have been quashed or superseded on appeal, and the ABSENCE of any such note is not evidence that it still stands."
  }
 ],
 "citation_edges": [
  {
   "reference_canonical": "BGH 1 StR 50/15",
   "reference_role": "leitentscheidung",
   "resolution_status": "resolved",
   "in_corpus": true,
   "corpus": {
    "artifact_id": "0193b0c4-6a2d-7c4e-8f10-2b3c4d5e6f70",
    "court": "BGH",
    "date": "2015-03-12",
    "az": "1 StR 50/15",
    "document_type": "Urteil",
    "ecli": null,
    "corpus_url": "https://klaracase.de/decisions/0193b0c4-6a2d-7c4e-8f10-2b3c4d5e6f70"
   },
   "from_artifact_id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d"
  }
 ],
 "edge_accounting": [
  {
   "from_artifact_id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
   "unit": "edge_rows",
   "edges_total": 1,
   "edges_included": 1,
   "edges_resolved_included": 1,
   "edges_unresolved_included": 0,
   "edges_resolved_total": 1,
   "edges_unresolved_total": 0,
   "targets_resolved_included": 1,
   "targets_resolved_total": 1
  }
 ],
 "per_source_resolved_target_cap": 25,
 "per_source_unresolved_edge_row_cap": 25,
 "requested": 1,
 "included": 1,
 "deduped": 0,
 "text_mode": "excerpt",
 "max_chars": 700,
 "truncated": false,
 "payload_truncated": false,
 "assembled_at": "2026-10-01T10:00:00+00:00",
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 5,
  "credits_remaining": 20
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **402** Out of credits
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#insufficient_credits",
 "title": "Payment Required",
 "status": 402,
 "detail": "Insufficient credits: this call costs 5 credit(s), but organization \"Kanzlei Beispiel\" has 0 remaining this month. Credits renew automatically at the start of each calendar month (UTC). Ask your organization admin to raise the allotment, or retry next month.",
 "code": "insufficient_credits",
 "cost": 5,
 "balance": 0
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `datapackage` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "datapackage"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected ids is invalid.",
 "code": "validation_failed",
 "errors": {
  "ids": [
   "The selected ids is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## GET /decisions/{id}

**Read a decision**

One decision's full text, or a named section or a Randnummer window of it, with its
metadata: the REST twin of the MCP tool `get_decision`. One credit per decision per month;
reading it again, in any slice, costs nothing more.


### Parameters

- `max_chars` (query, integer) nullable: Maximum characters of text to return (default 40000, minimum 500).
- `rn_from` (query, integer) nullable: Optional range start: the first Randnummer to return. Whole chunks come back, so the served span is reported in `returned_range`.
- `rn_to` (query, integer) nullable: Optional range end: the highest Randnummer to return (inclusive). Must be >= rn_from.
- `section` (query, string) nullable: Optional named section instead of the whole text. One of: Tenor, Leitsatz, Tatbestand, Gründe (case-insensitive). `available_sections` lists the sections a decision has.
- `court` (query, string) nullable: Optional disambiguator for an Aktenzeichen `id`: the court short form, e.g. "BGH". Matched as a whole-word prefix. Ignored for UUID lookups.
- `date` (query, string) nullable: Optional disambiguator for an Aktenzeichen `id`: the decision date in YYYY-MM-DD.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
 "aktenzeichen": "1 StR 185/01",
 "court": "BGH",
 "date": "2001-11-15",
 "jurisdiction": "DE",
 "metadata": {
  "document_type": "Urteil",
  "ecli": "ECLI:DE:BGH:2001:151101U1STR185.01.0",
  "file_numbers": [
   "1 StR 185/01"
  ]
 },
 "fortgeltung_checked": false,
 "fortgeltung_note": "Rechtskraft/Fortgeltung (whether a decision is still good law) is NOT checked. A decision returned here may have been quashed or superseded on appeal, and the ABSENCE of any such note is not evidence that it still stands.",
 "full_text": "Tenor … Gründe: I. … 21 Die Revision ist unbegründet …",
 "text_length": 48213,
 "truncated": true,
 "rn_source": "printed",
 "rn_source_note": "The Randnummern are the court's own printed numbers.",
 "available_sections": [
  "Tenor",
  "Gründe"
 ],
 "available_range": {
  "rn_from": 1,
  "rn_to": 64,
  "rn_source": "printed"
 },
 "available_range_scope": "decision",
 "has_rn_anchors": true,
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 1,
  "credits_remaining": 27
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **402** Out of credits
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#insufficient_credits",
 "title": "Payment Required",
 "status": 402,
 "detail": "Insufficient credits: this call costs 1 credit(s), but organization \"Kanzlei Beispiel\" has 0 remaining this month. Credits renew automatically at the start of each calendar month (UTC). Ask your organization admin to raise the allotment, or retry next month.",
 "code": "insufficient_credits",
 "cost": 1,
 "balance": 0
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `read` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "read"
}
```
- **404** Not found
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#not_found",
 "title": "Not Found",
 "status": 404,
 "detail": "The requested resource does not exist, or it belongs to another organization.",
 "code": "not_found"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected max_chars is invalid.",
 "code": "validation_failed",
 "errors": {
  "max_chars": [
   "The selected max_chars is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## GET /norms/{reference}

**Read a norm**

The full current text of one German federal or EU norm by its citation, with the version it
was served from, its neighbours and the decisions that cite it: the REST twin of the MCP
tool `get_norm`. One credit per norm per month; reading it again costs nothing more.


### Parameters

- `jurisdiction` (query, string) nullable: DE or EU; only read when the abbreviation is ambiguous.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "reference": "§ 535 BGB",
 "requested_reference": "§ 535 Abs. 1 BGB",
 "law": {
  "id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
  "abbreviation": "BGB",
  "source_abbreviation": "BGB",
  "official_name": "Bürgerliches Gesetzbuch",
  "law_level": "BUND",
  "jurisdiction": "DE",
  "source_url": "https://www.gesetze-im-internet.de/bgb/",
  "upstream_status": "confirmed",
  "upstream_last_seen_at": "2026-10-05T04:17:00Z",
  "upstream_missing_since": null
 },
 "norm": {
  "number": "§ 535",
  "title": "Inhalt und Hauptpflichten des Mietvertrags",
  "lifecycle": "current",
  "text": "(1) Durch den Mietvertrag wird der Vermieter verpflichtet, dem Mieter den Gebrauch der Mietsache während der Mietzeit zu gewähren. …\n(2) Der Mieter ist verpflichtet, dem Vermieter die vereinbarte Miete zu entrichten.",
  "absatz_identifiers": [
   "1",
   "2"
  ],
  "chars": 612
 },
 "requested_qualifiers": [
  {
   "type": "Abs.",
   "value": "1",
   "checked": true,
   "present": true
  }
 ],
 "version": {
  "id": "0193b0c4-aaaa-7a2b-9c3d-4e5f6a7b8c9d",
  "last_amendment_date": "2024-12-20",
  "last_amendment_date_basis": "source_stand",
  "source_fetched_at": "2026-10-05T04:17:00Z",
  "source_last_seen_at": "2026-10-05T04:17:00Z"
 },
 "neighbours": {
  "previous": "§ 534 BGB",
  "next": "§ 536 BGB"
 },
 "links": {
  "decisions_citing": {
   "tool": "search_decisions",
   "arguments": {
    "cited_norm": "§ 535 BGB"
   }
  },
  "decisions_citing_url": "/api/v1/decisions/search?cited_norm=%C2%A7%20535%20BGB",
  "self_url": "/api/v1/norms/%C2%A7%20535%20BGB"
 },
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 1,
  "credits_remaining": 27
 }
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **402** Out of credits
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#insufficient_credits",
 "title": "Payment Required",
 "status": 402,
 "detail": "Insufficient credits: this call costs 1 credit(s), but organization \"Kanzlei Beispiel\" has 0 remaining this month. Credits renew automatically at the start of each calendar month (UTC). Ask your organization admin to raise the allotment, or retry next month.",
 "code": "insufficient_credits",
 "cost": 1,
 "balance": 0
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `read` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "read"
}
```
- **404** Not found
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#not_found",
 "title": "Not Found",
 "status": 404,
 "detail": "The requested resource does not exist, or it belongs to another organization.",
 "code": "not_found"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected jurisdiction is invalid.",
 "code": "validation_failed",
 "errors": {
  "jurisdiction": [
   "The selected jurisdiction is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## GET /decisions/search

**Search decisions**

Hybrid search over the German court decisions in the corpus, the REST twin of the MCP tool
`search_decisions`. Phrase the query as German legal concepts. One credit per distinct query
and filter set per month: paging, and the same search again this month, on REST or MCP, cost
nothing more.


### Parameters

- `query` (query, required, string): Search query in German legal-concept phrasing, e.g. "Widerrufsrecht Fernabsatzvertrag Wertersatz Verbraucher". 2-500 characters; longer input is REJECTED.
- `court` (query, string) nullable: Court filter on the indexed court name. That vocabulary is MIXED and chamber-level, so the value is the court, not the chamber (values: list_facets(field="court_name")).
- `branch` (query, string enum[ordentlich, verwaltung, sozial, arbeit, finanz, verfassung, patent, unbekannt]) nullable: Gerichtsbarkeit (court branch) filter. It names the COURT JURISDICTION that decided the case, not the legal subject area. "patent" is the Bundespatentgericht alone: BGH patent decisions sit under "ordentlich".
- `document_type` (query, string enum[Urteil, Beschluss, Verfügung, Sonstige, Gerichtsbescheid, Schlussanträge]) nullable: Restrict to one decision document type; list_facets gives the counts.
- `cited_norm` (query, string) nullable: Restrict to decisions whose extracted Normenkette cites this statute, e.g. "§ 906 BGB". One canonical §-token; subdivisions nest ("§ 823 BGB" matches "§ 823 Abs. 1 BGB").
- `cited_statutes` (query, array of string enum[StGB, StPO, InsO, DSGVO, GDPR, BDSG, BauGB, BBauG, BauNVO, StVG, StVO]): Any section of these statutes, e.g. ["StGB", "StPO"].
- `date_from` (query, string) nullable: Earliest decision date, inclusive, formatted YYYY-MM-DD (e.g. "2015-01-01"). ACCURACY CAVEAT: a scanned decision can carry a WRONG stored date; see `date_source`/`date_confidence`.
- `date_to` (query, string) nullable: Latest decision date, inclusive, formatted YYYY-MM-DD (e.g. "2020-12-31"), not earlier than date_from. ACCURACY CAVEAT: a scanned decision can carry a WRONG stored date; see `date_source`/`date_confidence`.
- `mode` (query, string enum[keyword, semantic, hybrid]) nullable: Retrieval mode. "hybrid" (default) blends semantic and keyword. "keyword" requires ALL query terms at once and is not reranked; a query that is a citation throughout ("§ 550a BGB", "VIII ZR 311/02") is matched EXACTLY, with no typo tolerance, so a similar number cannot answer it. "semantic" is pure vector search. Unset does not guarantee hybrid: a precise identifier is auto-classified to keyword.
- `limit` (query, integer) nullable: Maximum results. Default 20, which is also the hard cap, so this can only narrow the window.
- `page` (query, integer) nullable: 1-based page number, default 1, maximum 10, for results past the first page when `candidate_pool` exceeds `limit`.
- `bridge` (query, boolean) nullable: Whether the server may ADD curated German legal-register terms before retrieval (default true); the outcome is in `query_expansion`.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "results": [
  {
   "id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
   "aktenzeichen": "1 StR 185/01",
   "court": "BGH",
   "date": "2001-11-15",
   "document_type": "Urteil",
   "title": "BGH, Urteil vom 15.11.2001",
   "snippet": "… die <mark>Vermögensbetreuungspflicht</mark> des Geschäftsführers …",
   "snippets": [
    {
     "text": "… die <mark>Vermögensbetreuungspflicht</mark> des Geschäftsführers …",
     "rn": 21
    }
   ],
   "chunk_title": "Gründe",
   "rn_range": "21-23",
   "fundstelle": null,
   "fortgeltung_checked": false,
   "fortgeltung_note": "Rechtskraft/Fortgeltung (whether a decision is still good law) is NOT checked. A decision returned here may have been quashed or superseded on appeal, and the ABSENCE of any such note is not evidence that it still stands.",
   "confidence": "high"
  }
 ],
 "payload_truncated": false,
 "total_available": {
  "value": 42,
  "is_floor": false
 },
 "total_available_basis": "matching_indexed_passages_lexical_arm",
 "candidate_pool": 42,
 "pool_exhaustive": false,
 "truncated": true,
 "page": 1,
 "limit": 20,
 "mode": "hybrid",
 "frequently_cited_by_results": [],
 "query_expansion": {
  "status": "abstained",
  "applied": false,
  "reason": "no_lay_term",
  "note": "Nothing was added to your query: it was retrieved exactly as you typed it. …"
 },
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 1,
  "credits_remaining": 29
 },
 "top_confidence": "high"
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **402** Out of credits
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#insufficient_credits",
 "title": "Payment Required",
 "status": 402,
 "detail": "Insufficient credits: this call costs 1 credit(s), but organization \"Kanzlei Beispiel\" has 0 remaining this month. Credits renew automatically at the start of each calendar month (UTC). Ask your organization admin to raise the allotment, or retry next month.",
 "code": "insufficient_credits",
 "cost": 1,
 "balance": 0
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `search` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "search"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected query is invalid.",
 "code": "validation_failed",
 "errors": {
  "query": [
   "The selected query is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## GET /search

**Search statutes and decisions**

One search over German statutes and court decisions, answered in two sections, the REST twin
of the MCP tool `cross_type_search`. One credit per distinct query and filter set per month.


### Parameters

- `query` (query, required, string): Search query, German legal-concept phrasing, e.g. "Widerrufsrecht Fernabsatzvertrag Wertersatz Verbraucher". 2-500 characters; longer input is REJECTED, not truncated.
- `jurisdiction` (query, string) nullable: Jurisdiction code. It narrows the LAWS section only — no decision carries the field — so it never empties `sections.decisions`; `filters_applied_sections.jurisdiction` says so. Values `DE`, `EU` (EU law and the Treaties), `XI` (international); counts via list_facets.
- `court` (query, string) nullable: Court name filter on the decisions section, canonical German short form, e.g. "BGH".
- `branch` (query, string enum[ordentlich, verwaltung, sozial, arbeit, finanz, verfassung, patent, unbekannt]) nullable: Gerichtsbarkeit (court branch): it names the COURT JURISDICTION that decided the case, not the legal subject area. "patent" is the Bundespatentgericht, and BGH patent decisions sit under "ordentlich".
- `date_from` (query, string) nullable: Earliest decision date, inclusive, YYYY-MM-DD.
- `date_to` (query, string) nullable: Latest decision date, inclusive, YYYY-MM-DD, NOT earlier than date_from.
- `mode` (query, string enum[keyword, semantic, hybrid]) nullable: Retrieval mode. "hybrid" (default) blends semantic and keyword; "keyword" is not reranked; "semantic" is pure vector search.
- `document_type` (query, string enum[Urteil, Beschluss, Verfügung, Sonstige, Gerichtsbescheid, Schlussanträge]) nullable: Restrict the decisions section to one document type.
- `cited_norm` (query, string) nullable: Restrict the decisions section to decisions whose EXTRACTED Normenkette cites this statute, e.g. "§ 906 BGB". Canonicalized, and subdivisions nest.
- `cited_statutes` (query, array of string enum[StGB, StPO, InsO, DSGVO, GDPR, BDSG, BauGB, BBauG, BauNVO, StVG, StVO]): Any section of these statutes, e.g. ["StGB", "StPO"].
- `limit` (query, integer) nullable: Maximum results PER section (default 5, hard-capped at 10 server-side).
- `bridge` (query, boolean) nullable: Whether the server may ADD terms before retrieval (default true). Covers every server-side addition to your query, `query_expansion` included. False searches your literal query; nothing is then added.

### Responses

- **200** Success
  `application/json` example:
```json
{
 "sections": {
  "laws": [
   {
    "id": "0193b0c4-8c4f-7e60-ab32-4d5e6f7a8b92",
    "artifact_type": "LAW",
    "aktenzeichen": null,
    "court": null,
    "date": null,
    "document_type": null,
    "title": "§ 266 StGB Untreue",
    "snippet": "… <mark>Vermögensbetreuungspflicht</mark> …",
    "snippets": [
     {
      "text": "… <mark>Vermögensbetreuungspflicht</mark> …"
     }
    ],
    "chunk_title": null,
    "rn_range": null,
    "fundstelle": null,
    "breadcrumb": null,
    "abbreviation": "StGB",
    "law_type": "Gesetz",
    "jurisdiction": "DE",
    "confidence": "high"
   }
  ],
  "decisions": [
   {
    "id": "0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d",
    "artifact_type": "DECISION",
    "aktenzeichen": "1 StR 185/01",
    "court": "BGH",
    "date": "2001-11-15",
    "document_type": "Urteil",
    "title": "BGH, Urteil vom 15.11.2001",
    "snippet": "… <mark>Vermögensbetreuungspflicht</mark> …",
    "snippets": [
     {
      "text": "… <mark>Vermögensbetreuungspflicht</mark> …",
      "rn": 21
     }
    ],
    "chunk_title": "Gründe",
    "rn_range": "21-23",
    "fundstelle": null,
    "fortgeltung_checked": false,
    "fortgeltung_note": "Rechtskraft/Fortgeltung (whether a decision is still good law) is NOT checked. A decision returned here may have been quashed or superseded on appeal, and the ABSENCE of any such note is not evidence that it still stands.",
    "confidence": "medium"
   }
  ]
 },
 "section_totals": {
  "laws": {
   "total_available": {
    "value": 3,
    "is_floor": false
   },
   "total_available_basis": "matching_indexed_passages_lexical_arm",
   "candidate_pool": 3,
   "pool_exhaustive": true,
   "truncated": false
  },
  "decisions": {
   "total_available": {
    "value": 7,
    "is_floor": false
   },
   "total_available_basis": "matching_indexed_passages_lexical_arm",
   "candidate_pool": 7,
   "pool_exhaustive": true,
   "truncated": true
  }
 },
 "limit": 5,
 "total_available": {
  "value": 10,
  "is_floor": false
 },
 "total_available_basis": "matching_indexed_passages_lexical_arm",
 "pool_exhaustive": true,
 "truncated": true,
 "mode": "hybrid",
 "query_expansion": {
  "status": "abstained",
  "applied": false,
  "reason": "no_lay_term",
  "note": "Nothing was added to your query: it was retrieved exactly as you typed it. …"
 },
 "frequently_cited_by_results": [],
 "norms_cited_by_decision_results": [],
 "api_version": "0.95.0",
 "changelog_url": "https://klaracase.de/docs/mcp/changelog",
 "credits": {
  "metered": true,
  "cost": 1,
  "credits_remaining": 28
 },
 "top_confidence": "high"
}
```
- **401** Unauthenticated
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#unauthenticated",
 "title": "Unauthorized",
 "status": 401,
 "detail": "Authentication is required. Send a Klaracase API token as a Bearer token.",
 "code": "unauthenticated"
}
```
- **402** Out of credits
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#insufficient_credits",
 "title": "Payment Required",
 "status": 402,
 "detail": "Insufficient credits: this call costs 1 credit(s), but organization \"Kanzlei Beispiel\" has 0 remaining this month. Credits renew automatically at the start of each calendar month (UTC). Ask your organization admin to raise the allotment, or retry next month.",
 "code": "insufficient_credits",
 "cost": 1,
 "balance": 0
}
```
- **403** Forbidden
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_ability_missing",
 "title": "Forbidden",
 "status": 403,
 "detail": "This API token does not carry the `search` ability this endpoint needs. Nothing was executed and nothing was charged. Create a token with that ability in Settings, API tokens.",
 "code": "token_ability_missing",
 "required_ability": "search"
}
```
- **409** Conflict
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#token_org_missing",
 "title": "Conflict",
 "status": 409,
 "detail": "This API token was created before tokens named an organization, so the API cannot tell which organization it acts for. Create a new token in Settings, API tokens; it acts for the organization you have open.",
 "code": "token_org_missing"
}
```
- **422** Validation error
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#validation_failed",
 "title": "Unprocessable Content",
 "status": 422,
 "detail": "The selected query is invalid.",
 "code": "validation_failed",
 "errors": {
  "query": [
   "The selected query is invalid."
  ]
 }
}
```
- **429** Too many requests
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#rate_limited",
 "title": "Too Many Requests",
 "status": 429,
 "detail": "Too many requests for this token. Wait `retry_after_seconds` and retry. Nothing was executed and nothing was charged.",
 "code": "rate_limited",
 "retry_after_seconds": 42
}
```
- **503** Service unavailable
  `application/problem+json` example:
```json
{
 "type": "https://klaracase.de/docs/api/errors#backend_unavailable",
 "title": "Service Unavailable",
 "status": 503,
 "detail": "The backend could not complete this call, so nothing was charged. Retry in a few seconds.",
 "code": "backend_unavailable"
}
```

## Components
```json
{
 "securitySchemes": {
  "default": {
   "type": "http",
   "scheme": "bearer",
   "description": "Send an API token as `Authorization: Bearer <token>`. Create the token in Settings, API tokens: it acts for the organization you have open when you create it, carries the abilities you select, and expires after 365 days unless you choose a shorter lifetime. A browser session is not accepted."
  }
 },
 "schemas": {
  "Problem": {
   "type": "object",
   "description": "An RFC 9457 problem, served as application/problem+json. `code` is stable and machine-readable; `detail` is prose for a human and may change.",
   "required": [
    "type",
    "title",
    "status",
    "detail",
    "code"
   ],
   "properties": {
    "type": {
     "type": "string",
     "format": "uri",
     "description": "A URI naming the problem: https://klaracase.de/docs/api/errors#<code>."
    },
    "title": {
     "type": "string",
     "description": "The HTTP status text."
    },
    "status": {
     "type": "integer",
     "description": "The HTTP status code."
    },
    "detail": {
     "type": "string",
     "description": "What went wrong and what to do, for a human."
    },
    "code": {
     "type": "string",
     "description": "The machine-readable reason, the same vocabulary the MCP tools serve as `error_code`, e.g. `insufficient_credits`, `token_ability_missing`, `two_factor_required`, `validation_failed`, `rate_limited`, `volume_cap`, `not_found`, `backend_unavailable`."
    },
    "cost": {
     "type": "integer",
     "description": "On 402: what the call would have cost, in credits."
    },
    "balance": {
     "type": "integer",
     "description": "On 402: the organization's remaining credits this month."
    },
    "required_ability": {
     "type": "string",
     "description": "On 403 `token_ability_missing`: the token ability the endpoint needs."
    },
    "errors": {
     "type": "object",
     "description": "On 422 `validation_failed`: the messages per argument.",
     "additionalProperties": {
      "type": "array",
      "items": {
       "type": "string"
      }
     }
    },
    "retry_after_seconds": {
     "type": "integer",
     "description": "On 429: how long to wait before retrying. Also sent as the Retry-After header."
    },
    "unit": {
     "type": "string",
     "description": "On 429 `volume_cap`: the capped unit, `rows` or `documents`."
    },
    "cap": {
     "type": "integer",
     "description": "On 429 `volume_cap`: the organization's daily cap for that unit."
    },
    "resets_at": {
     "type": "string",
     "format": "date-time",
     "description": "On 429 `volume_cap`: when the daily cap resets (midnight Europe/Berlin)."
    }
   }
  }
 }
}
```