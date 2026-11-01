"""The tolerant decoder behind every response class.

``Model.from_dict`` turns a parsed JSON object into a frozen dataclass. It reads the field types
of the class, so a class lists its fields once and the decoder cannot drift from it.

The rules, which hold at every depth:

* A key the class does not list lands in ``extra`` (the API only adds keys).
* A value of the wrong type never raises. A scalar or an object reads as ``None``, a list as
  ``[]`` and a mapping as ``{}``, as the field default says. The original is still in ``raw``.
* A list or mapping drops the items of the wrong type and keeps the rest.
* A field without a default is an identity key (``id``, ``reference``, ``field``). A body that
  lacks it, or carries it with the wrong type, raises :class:`~klaracase.ResponseShapeError`.
* A field name that ends in ``_`` (``from_``) is the wire key without the underscore (``from``).
"""

import types
import typing
from collections.abc import Mapping
from dataclasses import MISSING, dataclass, field, fields
from typing import Any, Self, TypeVar, cast, get_args, get_origin, get_type_hints

from .errors import ResponseShapeError

__all__ = ["Model"]

M = TypeVar("M", bound="Model")

_DROP: Any = object()
_ABSENT: Any = object()
_NON_WIRE = {"wire": False}


@dataclass(frozen=True, slots=True, kw_only=True)
class Model:
    """Base of every response object: a frozen dataclass that keeps unknown keys in ``extra``."""

    extra: dict[str, Any] = field(default_factory=dict[str, Any], repr=False)

    @classmethod
    def from_dict(cls, body: Mapping[str, Any]) -> Self:
        """Build the object from a parsed JSON object. See the module docstring for the rules."""
        return decode_model(cls, body, "")


@dataclass(frozen=True, slots=True)
class _Entry:
    name: str
    wire: str
    hint: Any
    required: bool


_PLANS: dict[type, tuple[_Entry, ...]] = {}


def _plan(cls: type) -> tuple[_Entry, ...]:
    cached = _PLANS.get(cls)
    if cached is not None:
        return cached
    hints = get_type_hints(cls)
    entries: list[_Entry] = []
    for item in fields(cls):
        if item.name == "extra" or item.metadata.get("wire") is False:
            continue
        required = item.default is MISSING and item.default_factory is MISSING
        wire = item.name[:-1] if item.name.endswith("_") else item.name
        entries.append(_Entry(item.name, wire, hints[item.name], required))
    plan = tuple(entries)
    _PLANS[cls] = plan
    return plan


def decode_model(
    cls: type[M], body: Mapping[str, Any], path: str, injected: Mapping[str, Any] | None = None
) -> M:
    """Decode ``body`` into ``cls``. ``injected`` adds constructor arguments that are not keys."""
    kwargs: dict[str, Any] = dict(injected) if injected else {}
    known: set[str] = set()
    for entry in _plan(cls):
        known.add(entry.wire)
        raw = body.get(entry.wire, _ABSENT)
        value = _DROP if raw is _ABSENT else _decode(entry.hint, raw, f"{path}.{entry.wire}")
        if value is not _DROP:
            kwargs[entry.name] = value
        elif entry.required:
            where = f"{path}.{entry.wire}".lstrip(".")
            raise ResponseShapeError(f"The response lacks the required key {where!r}.", path=where)
    kwargs["extra"] = {key: value for key, value in body.items() if key not in known}
    return cls(**kwargs)


def _decode(hint: Any, value: Any, path: str) -> Any:
    if hint is Any:
        return value
    origin = get_origin(hint)
    if origin is typing.Union or origin is types.UnionType:
        return _decode_union(get_args(hint), value, path)
    if origin is typing.Literal:
        return value if isinstance(value, str) and value in get_args(hint) else _DROP
    if value is None:
        return _DROP
    if origin is list:
        return _decode_list(get_args(hint)[0], value, path)
    if origin is dict:
        return _decode_dict(get_args(hint)[1], value, path)
    if hint is bool:
        return value if isinstance(value, bool) else _DROP
    if hint is int:
        return value if isinstance(value, int) and not isinstance(value, bool) else _DROP
    if hint is float:
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        return value if ok else _DROP
    if hint is str:
        return value if isinstance(value, str) else _DROP
    if isinstance(hint, type) and issubclass(hint, Model):
        return (
            decode_model(hint, cast("dict[str, Any]", value), path)
            if isinstance(value, dict)
            else _DROP
        )
    raise TypeError(f"Unsupported field type {hint!r}")


def _decode_union(options: tuple[Any, ...], value: Any, path: str) -> Any:
    if value is None:
        return None if type(None) in options else _DROP
    for option in options:
        if option is type(None):
            continue
        decoded = _decode(option, value, path)
        if decoded is not _DROP:
            return decoded
    return _DROP


def _decode_list(item_hint: Any, value: Any, path: str) -> Any:
    if not isinstance(value, list):
        return _DROP
    items: list[Any] = value  # pyright: ignore[reportUnknownVariableType]
    decoded = (_decode(item_hint, item, f"{path}[{index}]") for index, item in enumerate(items))
    return [item for item in decoded if item is not _DROP]


def _decode_dict(item_hint: Any, value: Any, path: str) -> Any:
    if not isinstance(value, dict):
        return _DROP
    result: dict[str, Any] = {}
    mapping: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
    for key, item in mapping.items():
        decoded = _decode(item_hint, item, f"{path}[{key!r}]")
        if decoded is not _DROP:
            result[key] = decoded
    return result
