#!/usr/bin/env python3
"""Validate the Klaracase SDK conformance pack.

Run with:  python3 -I validate.py

Checks every case file for shape, that every body_file exists, that every sdk.group/method pair
is in the design method table (DESIGN.md section 3.2), that each case's expected request equals
the request derived from its own arguments (path encoding, query array form, JSON body), that
every success assertion holds against the served body, that status codes match the error class
table, and that the expected request count and sleeps equal what the retry policy of DESIGN.md
section 3.5 produces. Exit status 0 means the pack is consistent.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
PROBLEMS = ROOT / "problems"

errors: list[str] = []


def fail(where: str, msg: str) -> None:
    errors.append(f"{where}: {msg}")


# --------------------------------------------------------------------------- tables

# (group, method) -> (http method, path template, path args, query args, body args, allowed args)
Q_SEARCH = ["query", "court", "branch", "document_type", "cited_norm", "cited_statutes", "date_from", "date_to", "mode", "limit", "page", "bridge"]
Q_XSEARCH = ["query", "jurisdiction", "court", "branch", "date_from", "date_to", "mode", "document_type", "cited_norm", "cited_statutes", "limit", "bridge"]
METHODS: dict[tuple[str | None, str], dict] = {
    ("decisions", "search"): dict(http="GET", path="/decisions/search", path_args=[], query=Q_SEARCH, body=[], required=["query"]),
    (None, "search"): dict(http="GET", path="/search", path_args=[], query=Q_XSEARCH, body=[], required=["query"]),
    ("decisions", "get"): dict(http="GET", path="/decisions/{id}", path_args=["id"], query=["max_chars", "rn_from", "rn_to", "section", "court", "date"], body=[], required=["id"]),
    ("decisions", "citations"): dict(http="GET", path="/decisions/{id}/citations", path_args=["id"], query=["direction", "depth", "court", "date", "page"], body=[], required=["id"]),
    ("norms", "get"): dict(http="GET", path="/norms/{reference}", path_args=["reference"], query=["jurisdiction"], body=[], required=["reference"]),
    ("datapackages", "create"): dict(http="POST", path="/datapackages", path_args=[], query=[], body=["ids", "include_citations", "full_text", "max_chars"], required=["ids"]),
    ("citation_checks", "create"): dict(http="POST", path="/citation-checks", path_args=[], query=[], body=["text", "document_id", "reference_date"], required=[]),
    ("citation_checks", "get"): dict(http="GET", path="/citation-checks/{run_id}", path_args=["run_id"], query=[], body=[], required=["run_id"]),
    ("citation_check_documents", "upload"): dict(http="POST", path="/citation-check-documents", path_args=[], query=[], body=[], required=["file"], extra_args=["file", "filename", "content_type"]),
    ("citation_check_documents", "get"): dict(http="GET", path="/citation-check-documents/{document_id}", path_args=["document_id"], query=[], body=[], required=["document_id"]),
    ("citation_check_documents", "wait_until_ready"): dict(http="GET", path="/citation-check-documents/{document_id}", path_args=["document_id"], query=[], body=[], required=["document_id"], extra_args=["poll_interval", "timeout"], helper=True),
    ("corpus", "coverage"): dict(http="GET", path="/corpus/coverage", path_args=[], query=["branch", "top"], body=[], required=[]),
    ("corpus", "facets"): dict(http="GET", path="/corpus/facets/{field}", path_args=["field"], query=["type", "norm", "prefix"], body=[], required=["field"]),
}
OPERATIONS = {k for k, v in METHODS.items() if not v.get("helper")}  # the 12 operations

STATUS_CLASS = {401: "AuthenticationError", 402: "InsufficientCreditsError", 403: "PermissionError", 404: "NotFoundError",
                409: "ConflictError", 422: "ValidationError", 429: "RateLimitError", 503: "ServiceUnavailableError"}
HTTP_CLASSES = set(STATUS_CLASS.values()) | {"ApiError"}
SYNTHETIC_CLASSES = {"TransportError", "ConfigurationError", "DocumentFailedError", "DocumentTimeoutError"}
ALL_CLASSES = HTTP_CLASSES | SYNTHETIC_CLASSES

CASE_KEYS = {"name", "description", "sdk", "expect", "responses", "expect_result", "runner"}
SDK_KEYS = {"group", "method", "args", "options", "env", "repeat"}
OPTION_KEYS = {"token", "base_url_trailing_slash", "timeout", "max_retries", "user_agent_suffix"}
RESPONSE_KEYS = {"status", "headers", "body", "body_file", "body_text", "delay_seconds", "drop_connection"}
EXPECT_KEYS = {"request", "request_count", "sleeps"}
REQUEST_KEYS = {"method", "path", "query", "headers", "json", "multipart", "user_agent_suffix"}
RESULT_KEYS = {"kind", "assert", "class", "code", "status", "fields", "deprecation_warning", "deprecation", "deprecation_warning_count", "body_roundtrip"}
RUNNER_KEYS = {"real_clock", "repeat_last_response"}
PROBLEM_MEMBERS = {"type", "title", "status", "detail", "code"}

# Codes the pack must cover (task list), and the operations (all twelve).
REQUIRED_CODES = {
    "unauthenticated", "personal_access_token_required", "token_ability_missing", "token_org_membership_lost",
    "two_factor_required", "not_found", "ambiguous_aktenzeichen", "validation_failed", "text_too_long",
    "not_german_legal_text", "insufficient_credits", "rate_limited", "volume_cap", "document_unavailable",
    "token_org_missing", "backend_unavailable", "search_timeout", "statute_superseded", "internal_error", "unknown",
}

# --------------------------------------------------------------------------- helpers

UNRESERVED_ESC = re.compile(r"^(?:[A-Za-z0-9\-._~]|%[0-9A-F]{2})+$")


def enc(value: str) -> str:
    return quote(value, safe="")  # RFC 3986: everything outside the unreserved set is percent-encoded


TOKEN_RE = re.compile(r'\["((?:[^"\\]|\\.)*)"\]|\[(\d+)\]|([^.\[\]]+)')


def tokenize(path: str) -> list:
    out, pos = [], 0
    while pos < len(path):
        if path[pos] == ".":
            pos += 1
            continue
        m = TOKEN_RE.match(path, pos)
        if not m:
            raise ValueError(f"bad path {path!r} at {pos}")
        if m.group(1) is not None:
            out.append(json.loads('"' + m.group(1) + '"'))
        elif m.group(2) is not None:
            out.append(int(m.group(2)))
        else:
            out.append(m.group(3))
        pos = m.end()
    return out


MISSING = object()


def resolve(obj, path: str):
    cur = obj
    for tok in tokenize(path):
        if isinstance(tok, int):
            if not isinstance(cur, list) or tok >= len(cur):
                return MISSING
            cur = cur[tok]
        else:
            if not isinstance(cur, dict) or tok not in cur:
                return MISSING
            cur = cur[tok]
    return cur


def is_matcher(expected) -> bool:
    return isinstance(expected, dict) and expected and all(k.startswith("$") for k in expected)


def matches(actual, expected) -> bool:
    if actual is MISSING:
        return False
    if not is_matcher(expected):
        return actual == expected and type(actual) is type(expected) or (
            isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and not isinstance(actual, bool)
            and not isinstance(expected, bool) and actual == expected)
    for key, want in expected.items():
        if key == "$type":
            kinds = {"number": (int, float), "string": str, "object": dict, "array": list, "boolean": bool}
            if not isinstance(actual, kinds[want]) or (want == "number" and isinstance(actual, bool)):
                return False
        elif key == "$min":
            if not isinstance(actual, (int, float)) or actual < want:
                return False
        elif key == "$length":
            if len(actual) != want:
                return False
        elif key == "$contains":
            if want not in actual:
                return False
        elif key == "$starts_with":
            if not str(actual).startswith(want):
                return False
        else:
            raise ValueError(f"unknown matcher {key}")
    return True


def load_json(path: Path, where: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail(where, f"does not parse: {exc}")
        return None


def body_of(resp: dict, case_path: Path, where: str):
    """Return (parsed JSON or None, raw text or None)."""
    if "body" in resp:
        return resp["body"], json.dumps(resp["body"], ensure_ascii=False)
    if "body_text" in resp:
        text = resp["body_text"]
        try:
            return json.loads(text), text
        except Exception:  # noqa: BLE001
            return None, text
    if "body_file" in resp:
        p = (case_path.parent / resp["body_file"]).resolve()
        if not p.is_file():
            fail(where, f"body_file {resp['body_file']} does not exist")
            return None, None
        text = p.read_text(encoding="utf-8")
        if p.suffix == ".json":
            try:
                return json.loads(text), text
            except Exception as exc:  # noqa: BLE001
                fail(where, f"body_file {resp['body_file']} does not parse: {exc}")
        return None, text
    return None, None


def is_problem(parsed) -> bool:
    return isinstance(parsed, dict) and isinstance(parsed.get("code"), str)


def derive_request(sdk: dict, spec: dict):
    args = {k: v for k, v in sdk.get("args", {}).items() if v is not None}
    path = spec["path"]
    for name in spec["path_args"]:
        path = path.replace("{" + name + "}", enc(str(args[name])))
    query: dict = {}
    for name in spec["query"]:
        if name not in args:
            continue
        v = args[name]
        if isinstance(v, list):
            if v:
                query[name + "[]"] = [str(x) for x in v]
        elif isinstance(v, bool):
            query[name] = "true" if v else "false"
        else:
            query[name] = str(v)
    body = None
    if spec["body"]:
        body = {k: args[k] for k in spec["body"] if k in args}
    return spec["http"], path, query, body


# --------------------------------------------------------------------------- retry simulation

def wait_for(resp: dict, body, attempt: int):
    """DESIGN 3.5: body retry_after_seconds, else Retry-After header, else backoff with full jitter."""
    if isinstance(body, dict) and isinstance(body.get("retry_after_seconds"), (int, float)):
        return ("exact", body["retry_after_seconds"])
    header = {k.lower(): v for k, v in resp.get("headers", {}).items()}.get("retry-after")
    if header is not None and re.fullmatch(r"\d+", str(header)):
        return ("exact", int(header))
    return ("range", 0, min(8, 0.5 * 2 ** attempt))


def simulate(case: dict, case_path: Path, where: str):
    opts = case["sdk"].get("options", {})
    max_retries = opts.get("max_retries", 2)
    timeout = opts.get("timeout", 30)
    spec = METHODS[(case["sdk"]["group"], case["sdk"]["method"])]
    is_get = spec["http"] == "GET"
    responses = case["responses"]
    repeat = case["sdk"].get("repeat", 1)
    count, sleeps, outcome = 0, [], None
    idx, retries = 0, 0
    for _call in range(repeat):
        retries = 0
        while True:
            if idx >= len(responses):
                fail(where, "simulation ran out of responses")
                return count, sleeps, outcome
            resp = responses[idx]
            idx += 1
            count += 1
            dropped = resp.get("drop_connection") or resp.get("delay_seconds", 0) > timeout
            if dropped:
                if is_get and retries < max_retries:
                    sleeps.append(("range", 0, min(8, 0.5 * 2 ** retries)))
                    retries += 1
                    continue
                outcome = ("error", None)
                break
            status = resp["status"]
            parsed, _ = body_of(resp, case_path, where)
            if status in (429, 503) and retries < max_retries:
                w = wait_for(resp, parsed, retries)
                if w[0] == "exact" and w[1] > 30:
                    outcome = ("error", status)
                    break
                sleeps.append(w)
                retries += 1
                continue
            outcome = ("ok", status) if 200 <= status < 300 else ("error", status)
            break
    return count, sleeps, outcome


def sleep_matches(sim, want: dict) -> bool:
    if sim[0] == "exact":
        return want.keys() == {"exact"} and want["exact"] == sim[1]
    return want.keys() == {"min", "max"} and want["min"] == sim[1] and want["max"] == sim[2]


# --------------------------------------------------------------------------- main checks

def check_case(path: Path, covered: dict) -> None:
    where = path.name
    case = load_json(path, where)
    if not isinstance(case, dict):
        return
    if path.stem != case.get("name"):
        fail(where, f"name {case.get('name')!r} does not equal the file name")
    extra = set(case) - CASE_KEYS
    if extra:
        fail(where, f"unknown case keys {sorted(extra)}")
    for key in ("name", "sdk", "expect", "responses", "expect_result"):
        if key not in case:
            fail(where, f"missing {key}")
            return

    sdk, exp, responses, result = case["sdk"], case["expect"], case["responses"], case["expect_result"]
    if set(sdk) - SDK_KEYS:
        fail(where, f"unknown sdk keys {sorted(set(sdk) - SDK_KEYS)}")
    if set(exp) - EXPECT_KEYS:
        fail(where, f"unknown expect keys {sorted(set(exp) - EXPECT_KEYS)}")
    if set(result) - RESULT_KEYS:
        fail(where, f"unknown expect_result keys {sorted(set(result) - RESULT_KEYS)}")
    if set(case.get("runner", {})) - RUNNER_KEYS:
        fail(where, "unknown runner keys")
    if set(sdk.get("options", {})) - OPTION_KEYS:
        fail(where, f"unknown option keys {sorted(set(sdk['options']) - OPTION_KEYS)}")

    pair = (sdk.get("group"), sdk.get("method"))
    spec = METHODS.get(pair)
    if spec is None:
        fail(where, f"sdk.group/method {pair} is not in the design method table")
        return
    allowed = set(spec["query"]) | set(spec["body"]) | set(spec["path_args"]) | set(spec.get("extra_args", []))
    for a in sdk.get("args", {}):
        if a not in allowed:
            fail(where, f"argument {a!r} is not a parameter of {pair}")
    for a in spec["required"]:
        if a not in sdk.get("args", {}) and not (result.get("class") in ("ValidationError", "ConfigurationError") and exp.get("request") is None):
            fail(where, f"required argument {a!r} missing")

    # ---- responses
    last = None
    for i, resp in enumerate(responses):
        rw = f"{where} responses[{i}]"
        if set(resp) - RESPONSE_KEYS:
            fail(rw, f"unknown response keys {sorted(set(resp) - RESPONSE_KEYS)}")
        if resp.get("drop_connection"):
            continue
        if not isinstance(resp.get("status"), int):
            fail(rw, "status missing")
        bodies = [k for k in ("body", "body_file", "body_text") if k in resp]
        if len(bodies) > 1:
            fail(rw, f"more than one body key {bodies}")
        for h in resp.get("headers", {}):
            if h != h.lower():
                fail(rw, f"header name {h!r} is not lower case")
        body_of(resp, path, rw)
    if responses and not responses[-1].get("drop_connection"):
        last = responses[-1]

    # ---- request
    req = exp.get("request")
    if req is None:
        if exp.get("request_count") != 0 or responses:
            fail(where, "request null needs request_count 0 and no responses")
        if result.get("kind") != "error":
            fail(where, "request null needs an error result")
        if result.get("class") not in ("ValidationError", "ConfigurationError"):
            fail(where, "request null is only for client validation or configuration errors")
        if result.get("class") == "ValidationError" and result.get("code") != "client_validation":
            fail(where, "client-side ValidationError needs code client_validation")
    else:
        if set(req) - REQUEST_KEYS:
            fail(where, f"unknown request keys {sorted(set(req) - REQUEST_KEYS)}")
        http, dpath, dquery, dbody = derive_request(sdk, spec)
        if req.get("method") != http:
            fail(where, f"method {req.get('method')} != derived {http}")
        if req.get("path") != dpath:
            fail(where, f"path {req.get('path')!r} != derived {dpath!r}")
        if not UNRESERVED_ESC.fullmatch(req.get("path", "").replace("/", "") or "x"):
            fail(where, f"path {req.get('path')!r} has unencoded characters or lower-case hex")
        if req.get("query") != dquery:
            fail(where, f"query {req.get('query')} != derived {dquery}")
        if spec["body"]:
            if req.get("json") != dbody:
                fail(where, f"json {req.get('json')} != derived {dbody}")
        elif "json" in req:
            fail(where, "json on a request without a JSON body")
        if pair == ("citation_check_documents", "upload"):
            a = sdk["args"]
            want = [{"name": "file", "filename": a.get("filename"), "content_type": a.get("content_type")}]
            if req.get("multipart") != want:
                fail(where, f"multipart {req.get('multipart')} != derived {want}")
            f = a["file"]
            if not (isinstance(f, dict) and (ROOT / f["$file"]).is_file()):
                fail(where, "upload file fixture missing")
        h = req.get("headers", {})
        for name in ("authorization", "accept", "user-agent"):
            if name not in h:
                fail(where, f"request header {name} missing")
        if h.get("authorization") != "Bearer test_token_123":
            fail(where, "authorization must be 'Bearer test_token_123'")
        if h.get("user-agent") != "klaracase-":
            fail(where, "user-agent must be the prefix 'klaracase-'")
        if spec["body"] and h.get("content-type") != "application/json":
            fail(where, "JSON POST needs content-type application/json")
        if pair == ("citation_check_documents", "upload") and h.get("content-type") != "multipart/form-data":
            fail(where, "upload needs content-type multipart/form-data")
        for name in h:
            if name != name.lower():
                fail(where, f"request header name {name!r} is not lower case")

    # ---- count and sleeps against the retry policy
    count = exp.get("request_count")
    if isinstance(count, dict):
        if set(count) != {"min", "max"}:
            fail(where, "request_count range needs min and max")
    elif not isinstance(count, int):
        fail(where, "request_count missing")

    if req is not None and not spec.get("helper"):
        n, sleeps, outcome = simulate(case, path, where)
        if count != n:
            fail(where, f"request_count {count} != simulated {n}")
        want_sleeps = exp.get("sleeps")
        if want_sleeps is None:
            if sleeps:
                fail(where, f"case omits sleeps but the retry policy sleeps {sleeps}")
        else:
            if len(want_sleeps) != len(sleeps) or not all(sleep_matches(s, w) for s, w in zip(sleeps, want_sleeps)):
                fail(where, f"sleeps {want_sleeps} != simulated {sleeps}")
        kind = result.get("kind")
        if outcome and not case.get("runner"):
            if kind == "success" and outcome[0] != "ok":
                fail(where, f"success expected but simulated outcome is {outcome}")
            if kind == "error" and outcome[0] != "error":
                fail(where, f"error expected but simulated outcome is {outcome}")
            if kind == "error" and result.get("status") != outcome[1]:
                fail(where, f"error status {result.get('status')} != simulated {outcome[1]}")
    elif spec.get("helper") and isinstance(count, int) and count > len(responses) and not case.get("runner", {}).get("repeat_last_response"):
        fail(where, "request_count exceeds responses")

    # ---- result
    kind = result.get("kind")
    if kind not in ("success", "error"):
        fail(where, "expect_result.kind must be success or error")
        return
    if kind == "success":
        covered["ops"].add(pair)
        if last is None or not (200 <= last["status"] < 300):
            fail(where, "success needs a 2xx final response")
            return
        parsed, _ = body_of(last, path, where)
        hdr = {k.lower(): v for k, v in last.get("headers", {}).items()}
        for p, want in result.get("assert", {}).items():
            try:
                if p.startswith("meta."):
                    if p == "meta.status":
                        actual = last["status"]
                    elif p == "meta.api_release":
                        actual = hdr.get("x-klaracase-api-release")
                    elif p == "meta.request_duration":
                        continue
                    else:
                        fail(where, f"unknown meta path {p}")
                        continue
                elif p.startswith("extra."):
                    actual = resolve(parsed, p[len("extra."):])
                else:
                    actual = resolve(parsed, p)
            except ValueError as exc:
                fail(where, str(exc))
                continue
            if not matches(actual, want):
                fail(where, f"assert {p}: expected {want!r}, body has {actual if actual is not MISSING else '<missing>'!r}")
        if result.get("body_roundtrip") and parsed is None:
            fail(where, "body_roundtrip needs a JSON body")
        if result.get("deprecation_warning") and not any(k in hdr for k in ("deprecation", "sunset")):
            fail(where, "deprecation_warning true but the response carries no Deprecation or Sunset header")
        if "deprecation" in result:
            for k, v in result["deprecation"].items():
                if hdr.get(k) != v:
                    fail(where, f"deprecation.{k} != response header")
    else:
        cls = result.get("class")
        if cls not in ALL_CLASSES:
            fail(where, f"unknown error class {cls!r}")
            return
        covered["classes"].add(cls)
        status = result.get("status")
        code = result.get("code")
        if cls in HTTP_CLASSES and req is None:
            pass  # client-side refusal: no response exists
        elif cls in HTTP_CLASSES:
            if last is None:
                fail(where, "HTTP error class needs a final response")
                return
            rs = last["status"]
            if rs != status:
                fail(where, f"result status {status} != final response status {rs}")
            want_cls = STATUS_CLASS.get(rs, "ApiError")
            if cls != want_cls:
                fail(where, f"status {rs} maps to {want_cls}, case says {cls}")
            parsed, raw = body_of(last, path, where)
            if is_problem(parsed):
                if code != parsed["code"]:
                    fail(where, f"code {code!r} != problem code {parsed['code']!r}")
                if parsed.get("status") != rs:
                    fail(where, "problem body status differs from the HTTP status")
                if parsed.get("type") != "https://klaracase.de/docs/api/errors#" + parsed["code"]:
                    fail(where, "problem type is not the errors#<code> URI")
                for k, v in (result.get("fields") or {}).items():
                    top = tokenize(k)[0]
                    if top == "extra":
                        actual = resolve(parsed, k[len("extra."):])
                    elif top in parsed or top in ("api_release",):
                        if top == "api_release":
                            actual = {kk.lower(): vv for kk, vv in last.get("headers", {}).items()}.get("x-klaracase-api-release")
                        else:
                            actual = resolve(parsed, k)
                    else:
                        fail(where, f"fields.{k} is not a member of the problem body")
                        continue
                    if not matches(actual, v):
                        fail(where, f"fields.{k}: expected {v!r}, problem has {actual if actual is not MISSING else '<missing>'!r}")
                covered["codes"].add(parsed["code"])
            else:
                if code != "unknown":
                    fail(where, "a non-problem body needs code 'unknown'")
                covered["codes"].add("unknown")
                for k, v in (result.get("fields") or {}).items():
                    if k == "detail":
                        text = raw or ""
                        if isinstance(v, dict) and v.get("$length") == 1000 and len(text) <= 1000:
                            fail(where, "truncation case needs a body longer than 1000 characters")
                        if isinstance(v, dict) and "$contains" in v and v["$contains"] not in text:
                            fail(where, "detail $contains text is not in the body")
                        if isinstance(v, dict) and "$starts_with" in v and not text.startswith(v["$starts_with"]):
                            fail(where, "detail $starts_with text is not the body start")
                        if isinstance(v, dict) and "$length" in v and not text.isascii():
                            fail(where, "truncation body must be ASCII")
        elif cls == "TransportError":
            if status is not None:
                fail(where, "TransportError has no status")
            if not (last is None or last.get("delay_seconds", 0) > sdk.get("options", {}).get("timeout", 30)):
                fail(where, "TransportError needs a dropped or timed-out final response")
        elif cls in ("DocumentFailedError", "DocumentTimeoutError"):
            if status is not None:
                fail(where, f"{cls} has no status")
            if cls == "DocumentFailedError":
                parsed, _ = body_of(last, path, where)
                if not isinstance(parsed, dict) or parsed.get("status") != "failed" or parsed.get("error_code") != code:
                    fail(where, "DocumentFailedError code must equal the failed receipt's error_code")
        elif cls == "ConfigurationError":
            if "code" in result or "status" in result:
                fail(where, "ConfigurationError carries neither code nor status")


def main() -> int:
    covered = {"ops": set(), "classes": set(), "codes": set()}
    case_files = sorted(CASES.glob("*.json"))
    if not case_files:
        fail("cases", "no case files")
    names = set()
    referenced_problems = set()
    for p in case_files:
        check_case(p, covered)
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r'"body_file":\s*"([^"]+)"', text):
            referenced_problems.add((p.parent / m.group(1)).resolve())
        names.add(p.stem)
    if len(names) != len(case_files):
        fail("cases", "duplicate case names")

    for p in sorted(PROBLEMS.glob("*.json")):
        body = load_json(p, p.name)
        if not isinstance(body, dict):
            continue
        if not PROBLEM_MEMBERS <= set(body):
            fail(p.name, f"problem lacks members {sorted(PROBLEM_MEMBERS - set(body))}")
            continue
        if body["type"] != "https://klaracase.de/docs/api/errors#" + body["code"]:
            fail(p.name, "type is not https://klaracase.de/docs/api/errors#<code>")
        if not isinstance(body["status"], int):
            fail(p.name, "status is not an integer")
        if p.resolve() not in referenced_problems:
            fail(p.name, "problem file is not referenced by any case")
    for p in sorted((ROOT / "bodies").glob("*")):
        if p.suffix == ".json":
            load_json(p, "bodies/" + p.name)
        if p.resolve() not in referenced_problems:
            fail("bodies/" + p.name, "body file is not referenced by any case")

    missing_ops = OPERATIONS - covered["ops"]
    if missing_ops:
        fail("coverage", f"operations without a success case: {sorted(missing_ops, key=str)}")
    missing_classes = ALL_CLASSES - covered["classes"]
    if missing_classes:
        fail("coverage", f"error classes without a case: {sorted(missing_classes)}")
    missing_codes = REQUIRED_CODES - covered["codes"]
    if missing_codes:
        fail("coverage", f"problem codes without a case: {sorted(missing_codes)}")

    # hygiene: no other token, no em dash, no stray files
    token_bad = re.compile(r"Bearer\s+(?!test_token_123\b)[A-Za-z0-9_\-.|]{16,}|klc_[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{8,}|\b\d+\|[A-Za-z0-9]{30,}")
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.suffix in (".pdf",) or p.name.endswith(".pyc") or "__pycache__" in p.parts:
            continue
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)
        if chr(0x2014) in text:
            fail(str(rel), "contains an em dash")
        if token_bad.search(text):
            fail(str(rel), "contains a token-like string")

    print(f"{len(case_files)} cases, {len(list(PROBLEMS.glob('*.json')))} problems")
    if errors:
        print(f"FAILED: {len(errors)} problem(s)")
        for e in errors:
            print("  -", e)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
