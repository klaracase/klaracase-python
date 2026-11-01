"""Tool definitions and a dispatcher, so an LLM agent can call Klaracase through this client.

There is no new dependency and no framework code. ``tool_definitions`` returns plain dicts in
the shape your provider wants. ``dispatch`` runs one tool call and returns compact JSON text for
the model. A Klaracase error comes back as ``{"error": {...}}`` text, not as an exception, so the
model can read it and decide what to do::

    from klaracase import Klaracase
    from klaracase.agents import dispatch, tool_definitions

    client = Klaracase()
    tools = tool_definitions(format="anthropic")
    # ... the model asks for a tool: name and arguments ...
    result_text = dispatch(client, name, arguments)

The tools match the Klaracase MCP tools of the same names. An agent should cite only what a tool
returned.
"""

from __future__ import annotations

import copy
import json
import typing
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

from .errors import ConfigurationError, KlaracaseError, RateLimitError
from .types import Branch, CitedStatute, DocumentType, NormJurisdiction, SearchMode
from .types import SearchJurisdiction as _SearchJurisdiction

if TYPE_CHECKING:
    from ._async import AsyncKlaracase
    from ._sync import Klaracase

__all__ = ["TOOL_NAMES", "adispatch", "dispatch", "tool_definitions"]

ToolFormat = Literal["anthropic", "openai", "json_schema"]

DEFAULT_GET_DECISION_MAX_CHARS = 4000
"""``get_decision`` returns at most this many characters of text unless the model asks for more."""

_DATE = "A date as YYYY-MM-DD."
_FINDING_KEYS = ("id", "canonical", "verdict", "raw_text", "start_offset", "end_offset")


def _enum(values: Any) -> list[Any]:
    return list(typing.get_args(values))


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _integer(description: str, **limits: int) -> dict[str, Any]:
    return {"type": "integer", "description": description, **limits}


def _choice(description: str, literal: Any) -> dict[str, Any]:
    return {"type": "string", "enum": _enum(literal), "description": description}


_COURT_FILTERS: dict[str, Any] = {
    "court": _string("Court filter on the court name, for example BGH."),
    "branch": _choice(
        "Court branch (Gerichtsbarkeit). It names the court jurisdiction, not the legal subject.",
        Branch,
    ),
    "document_type": _choice("Restrict to one document type.", DocumentType),
    "cited_norm": _string("Only decisions that cite this norm, for example '§ 906 BGB'."),
    "cited_statutes": {
        "type": "array",
        "items": {"type": "string", "enum": _enum(CitedStatute)},
        "description": "Only decisions that cite any section of these statutes.",
    },
    "date_from": _string(f"Earliest decision date, inclusive. {_DATE}"),
    "date_to": _string(f"Latest decision date, inclusive. {_DATE}"),
    "mode": _choice("Retrieval mode. hybrid is the default. keyword needs all terms.", SearchMode),
    "bridge": {
        "type": "boolean",
        "description": "Let the server add legal-register terms to the query. Default true.",
    },
}


@dataclass(frozen=True, slots=True)
class _Tool:
    name: str
    description: str
    target: str
    properties: dict[str, Any]
    required: tuple[str, ...]

    def input_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {
            "type": "object",
            "properties": copy.deepcopy(self.properties),
            "additionalProperties": False,
        }
        if self.required:
            schema["required"] = list(self.required)
        return schema


_TOOLS: tuple[_Tool, ...] = (
    _Tool(
        name="search_decisions",
        description=(
            "Search German court decisions. Write the query as German legal concepts, for "
            "example 'Widerrufsrecht Fernabsatzvertrag Wertersatz Verbraucher'. Returns rows "
            "with an id, the Aktenzeichen, court, date and text snippets. Use the id with "
            "get_decision. Costs 1 credit."
        ),
        target="decisions.search",
        properties={
            "query": _string("The search query, 2 to 500 characters."),
            **_COURT_FILTERS,
            "limit": _integer("Most results to return. Default and maximum 20.", minimum=1),
            "page": _integer("Page number, 1 to 10.", minimum=1, maximum=10),
        },
        required=("query",),
    ),
    _Tool(
        name="cross_type_search",
        description=(
            "Search German statutes and court decisions together. The answer has two "
            "sections, laws and decisions. Use it when the question needs both the norm and "
            "the case law. Costs 1 credit."
        ),
        target="search",
        properties={
            "query": _string("The search query in German legal concepts, 2 to 500 characters."),
            "jurisdiction": _choice(
                "Narrows the laws section only: DE, EU or XI (international).", _SearchJurisdiction
            ),
            **_COURT_FILTERS,
            "limit": _integer("Most results per section. Default 5, maximum 10.", minimum=1),
        },
        required=("query",),
    ),
    _Tool(
        name="get_decision",
        description=(
            "Read the text of one German court decision. The id is an id from a search, an "
            "Aktenzeichen or an ECLI. By default the text is cut to "
            f"{DEFAULT_GET_DECISION_MAX_CHARS} characters. Ask for a section or a range of "
            "Randnummern, or raise max_chars, to read more. Costs 1 credit."
        ),
        target="decisions.get",
        properties={
            "id": _string("A decision id from a search, an Aktenzeichen or an ECLI."),
            "max_chars": _integer(
                f"Most characters of text. Default {DEFAULT_GET_DECISION_MAX_CHARS}, minimum 500.",
                minimum=500,
            ),
            "rn_from": _integer("First Randnummer to return.", minimum=1),
            "rn_to": _integer("Last Randnummer to return, inclusive.", minimum=1),
            "section": _string("One section: Tenor, Leitsatz, Tatbestand or Gründe."),
            "court": _string("Court short form, to tell apart equal Aktenzeichen."),
            "date": _string(f"Decision date, to tell apart equal Aktenzeichen. {_DATE}"),
        },
        required=("id",),
    ),
    _Tool(
        name="get_norm",
        description=(
            "Read the current text of one German or EU norm by its citation, for example "
            "'§ 535 BGB' or 'Art. 6 DSGVO'. Costs 1 credit."
        ),
        target="norms.get",
        properties={
            "reference": _string("The norm citation, for example '§ 535 BGB'."),
            "jurisdiction": _choice(
                "DE or EU. Only used when the abbreviation is ambiguous.", NormJurisdiction
            ),
        },
        required=("reference",),
    ),
    _Tool(
        name="check_citations",
        description=(
            "Check the court-decision and statute citations in a German legal text against the "
            "Klaracase corpus. Pass text, or the document_id of a ready upload, not both. "
            "Returns one verdict per citation. A not_found verdict means the citation was not "
            "found in the corpus; it is not a claim that the citation is fabricated. Check "
            "such a citation by hand. A verified_corpus verdict shows that the citation exists, "
            "not that a quote or a legal claim is correct. Costs at least 2 credits."
        ),
        target="citation_checks.create",
        properties={
            "text": _string("The German legal text, 50 to 20000 characters."),
            "document_id": _string("The id of an upload with status ready."),
            "reference_date": _string(f"Optional date of the text, for statute citations. {_DATE}"),
        },
        required=(),
    ),
)

_BY_NAME = {tool.name: tool for tool in _TOOLS}
TOOL_NAMES: tuple[str, ...] = tuple(_BY_NAME)
"""The names ``tool_definitions`` can return."""


def tool_definitions(
    names: Sequence[str] | None = None, *, format: ToolFormat = "json_schema"
) -> list[dict[str, Any]]:
    """Return tool definitions for an LLM provider.

    Args:
        names: Which tools. ``None`` returns all five: ``search_decisions``, ``get_decision``,
            ``get_norm``, ``check_citations`` and ``cross_type_search``.
        format: ``"anthropic"`` gives ``{"name", "description", "input_schema"}``. ``"openai"``
            gives ``{"type": "function", "function": {"name", "description", "parameters"}}``.
            ``"json_schema"`` gives ``{"name", "description", "parameters"}``.

    Returns:
        A new list of new dicts each time, so you may change them.

    Raises:
        ConfigurationError: A name is not a known tool, or the format is unknown.
    """
    chosen = _BY_NAME.values() if names is None else [_tool(name) for name in names]
    if format not in {"anthropic", "openai", "json_schema"}:
        raise ConfigurationError(
            f"Unknown format {format!r}. Use anthropic, openai or json_schema."
        )
    return [_definition(tool, format) for tool in chosen]


def _tool(name: str) -> _Tool:
    tool = _BY_NAME.get(name)
    if tool is None:
        raise ConfigurationError(f"Unknown tool {name!r}. Known tools: {', '.join(TOOL_NAMES)}.")
    return tool


def _definition(tool: _Tool, format: ToolFormat) -> dict[str, Any]:
    schema = tool.input_schema()
    if format == "anthropic":
        return {"name": tool.name, "description": tool.description, "input_schema": schema}
    if format == "openai":
        return {
            "type": "function",
            "function": {"name": tool.name, "description": tool.description, "parameters": schema},
        }
    return {"name": tool.name, "description": tool.description, "parameters": schema}


def dispatch(client: Klaracase, name: str, args: Mapping[str, Any] | str | None) -> str:
    """Run one tool call and return compact JSON text for the model.

    A :class:`~klaracase.KlaracaseError` comes back as
    ``{"error": {"code", "detail", "retry_after_seconds"}}``. So does a call with an unknown
    tool name or bad arguments. ``get_decision`` cuts the text to 4000 characters unless the
    call sets ``max_chars``.

    Args:
        client: A :class:`~klaracase.Klaracase`.
        name: The tool name.
        args: The arguments as a mapping, or as JSON text (some providers send text).
    """
    prepared = _prepare(name, args)
    if isinstance(prepared, str):
        return prepared
    tool, kwargs = prepared
    try:
        result = _resolve(client, tool.target)(**kwargs)
    except KlaracaseError as error:
        return _error_text(error)
    return _render(tool, result)


async def adispatch(client: AsyncKlaracase, name: str, args: Mapping[str, Any] | str | None) -> str:
    """Run one tool call on an async client. Same as :func:`dispatch`, with ``await``."""
    prepared = _prepare(name, args)
    if isinstance(prepared, str):
        return prepared
    tool, kwargs = prepared
    try:
        result = await _resolve_async(client, tool.target)(**kwargs)
    except KlaracaseError as error:
        return _error_text(error)
    return _render(tool, result)


def _resolve(client: Klaracase, target: str) -> Callable[..., Any]:
    obj: Any = client
    for part in target.split("."):
        obj = getattr(obj, part)
    return cast("Callable[..., Any]", obj)


def _resolve_async(client: AsyncKlaracase, target: str) -> Callable[..., Awaitable[Any]]:
    obj: Any = client
    for part in target.split("."):
        obj = getattr(obj, part)
    return cast("Callable[..., Awaitable[Any]]", obj)


def _prepare(name: str, args: Mapping[str, Any] | str | None) -> tuple[_Tool, dict[str, Any]] | str:
    """Return the tool and its keyword arguments, or the error text for a bad call."""
    tool = _BY_NAME.get(name)
    if tool is None:
        return _error(
            "unknown_tool", f"Unknown tool {name!r}. Known tools: {', '.join(TOOL_NAMES)}."
        )
    parsed = _parse_args(args)
    if isinstance(parsed, str):
        return parsed
    unknown = sorted(set(parsed) - set(tool.properties))
    if unknown:
        allowed = ", ".join(tool.properties)
        return _error("invalid_arguments", f"Unknown argument {unknown}. Allowed: {allowed}.")
    missing = [key for key in tool.required if parsed.get(key) is None]
    if missing:
        return _error("invalid_arguments", f"Missing required argument {missing}.")
    kwargs = {key: value for key, value in parsed.items() if value is not None}
    if tool.name == "get_decision":
        kwargs.setdefault("max_chars", DEFAULT_GET_DECISION_MAX_CHARS)
    return tool, kwargs


def _parse_args(args: Mapping[str, Any] | str | None) -> dict[str, Any] | str:
    if args is None or args == "":
        return {}
    if isinstance(args, str):
        try:
            loaded = json.loads(args)
        except ValueError:
            return _error("invalid_arguments", "The arguments are not valid JSON.")
        if not isinstance(loaded, dict):
            return _error("invalid_arguments", "The arguments must be a JSON object.")
        return dict(typing.cast("dict[str, Any]", loaded))
    return dict(args)


def _render(tool: _Tool, result: Any) -> str:
    body: dict[str, Any] = result.to_dict()
    if tool.name == "check_citations":
        findings = typing.cast("list[Any]", body.get("findings") or [])
        reduced: dict[str, Any] = {
            "id": body.get("id"),
            "status": body.get("status"),
            "verdict_counts": body.get("verdict_counts"),
            "unique_citations": body.get("unique_citations"),
            "findings": [
                {key: cast("dict[str, Any]", finding).get(key) for key in _FINDING_KEYS}
                for finding in findings
                if isinstance(finding, dict)
            ],
        }
        return _compact(reduced)
    body.pop("api_version", None)
    body.pop("changelog_url", None)
    return _compact(body)


def _error_text(error: KlaracaseError) -> str:
    wait = error.retry_after_seconds if isinstance(error, RateLimitError) else None
    return _error(error.code, error.detail or error.message, wait)


def _error(code: str | None, detail: str, retry_after_seconds: float | None = None) -> str:
    payload = {"code": code, "detail": detail, "retry_after_seconds": retry_after_seconds}
    return _compact({"error": payload})


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
