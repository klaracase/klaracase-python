"""The sync and the async client must offer the same methods with the same arguments."""

from __future__ import annotations

import inspect
import re
from typing import Any

import pytest

from klaracase import AsyncKlaracase, Klaracase
from klaracase import _async as async_module
from klaracase import _sync as sync_module

RESOURCES = [
    ("Decisions", "decisions"),
    ("Norms", "norms"),
    ("Datapackages", "datapackages"),
    ("CitationChecks", "citation_checks"),
    ("CitationCheckDocuments", "citation_check_documents"),
    ("Corpus", "corpus"),
]
CLIENT_ONLY_SYNC = {"close", "__enter__", "__exit__"}
CLIENT_ONLY_ASYNC = {"aclose", "__aenter__", "__aexit__"}
# Plain functions that return an iterator, or build a client. They are not coroutines.
NOT_COROUTINES = {"with_options", "iter_pages", "iter_citation_pages"}
THE_TWELVE = {
    "Klaracase.search",
    "Decisions.search",
    "Decisions.get",
    "Decisions.citations",
    "Norms.get",
    "Datapackages.create",
    "CitationChecks.create",
    "CitationChecks.get",
    "CitationCheckDocuments.upload",
    "CitationCheckDocuments.get",
    "Corpus.coverage",
    "Corpus.facets",
}


def public_methods(cls: type) -> dict[str, Any]:
    return {
        name: member
        for name, member in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_") or name in {"__init__", "__repr__"}
    }


def shape(function: Any) -> list[tuple[str, Any, Any, Any]]:
    """Name, kind, default and annotation of every parameter except ``self``."""
    return [
        (p.name, p.kind, p.default, p.annotation)
        for p in inspect.signature(function).parameters.values()
        if p.name != "self"
    ]


def pairs() -> list[tuple[str, type, type]]:
    found: list[tuple[str, type, type]] = [("Klaracase", Klaracase, AsyncKlaracase)]
    for class_name, _attribute in RESOURCES:
        found.append(
            (class_name, getattr(sync_module, class_name), getattr(async_module, class_name))
        )
    return found


@pytest.mark.parametrize(("name", "sync_cls", "async_cls"), pairs(), ids=[p[0] for p in pairs()])
def test_same_public_methods_and_signatures(name: str, sync_cls: type, async_cls: type) -> None:
    sync_methods = public_methods(sync_cls)
    async_methods = public_methods(async_cls)
    if name == "Klaracase":
        sync_methods = {k: v for k, v in sync_methods.items() if k not in CLIENT_ONLY_SYNC}
        async_methods = {k: v for k, v in async_methods.items() if k not in CLIENT_ONLY_ASYNC}
    assert sync_methods.keys() == async_methods.keys()
    for method, function in sync_methods.items():
        if method == "__repr__":
            continue
        if method == "__init__":
            # The client types, the HTTP client and the sleep function differ by design.
            left = [(n, k, d) for n, k, d, _a in shape(function)]
            right = [(n, k, d) for n, k, d, _a in shape(async_methods[method])]
            assert left == right, f"{name}.{method}"
            continue
        assert shape(function) == shape(async_methods[method]), f"{name}.{method}"


@pytest.mark.parametrize(("name", "sync_cls", "async_cls"), pairs(), ids=[p[0] for p in pairs()])
def test_async_methods_are_coroutines(name: str, sync_cls: type, async_cls: type) -> None:
    for method, function in public_methods(async_cls).items():
        if method.startswith("__") or method in NOT_COROUTINES:
            continue
        assert inspect.iscoroutinefunction(function), f"{name}.{method}"
    for method, function in public_methods(sync_cls).items():
        assert not inspect.iscoroutinefunction(function), f"{name}.{method}"


def test_the_clients_hold_the_same_resource_groups() -> None:
    sync = Klaracase("klc_your_token_here")
    asynchronous = AsyncKlaracase("klc_your_token_here")
    for _class_name, attribute in RESOURCES:
        assert (
            type(getattr(sync, attribute)).__name__
            == type(getattr(asynchronous, attribute)).__name__
        )
    sync.close()


def documented_arguments(function: Any) -> set[str]:
    doc = inspect.getdoc(function) or ""
    section = re.search(r"^Args:\n(.*?)(?:\n\n\S|\Z)", doc, flags=re.MULTILINE | re.DOTALL)
    assert section, f"no Args section in {function.__qualname__}"
    return set(re.findall(r"^ {4}(\*{0,2}\w+):", section.group(1), flags=re.MULTILINE))


@pytest.mark.parametrize("qualified", sorted(THE_TWELVE))
@pytest.mark.parametrize("module", [sync_module, async_module], ids=["sync", "async"])
def test_the_twelve_methods_document_every_argument(module: Any, qualified: str) -> None:
    class_name, method = qualified.split(".")
    cls = getattr(
        module,
        "AsyncKlaracase" if class_name == "Klaracase" and module is async_module else class_name,
    )
    function = getattr(cls, method)
    parameters = {name for name, *_rest in shape(function)}
    documented = {name.lstrip("*") for name in documented_arguments(function)}
    assert parameters == documented, f"{qualified}: {parameters ^ documented}"
