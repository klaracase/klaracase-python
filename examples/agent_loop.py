"""Give an agent the Klaracase tools. A scripted stand-in plays the model. Local mock only.

    uv run python examples/agent_loop.py

In a real agent, pass ``tool_definitions(format="anthropic")`` (or ``"openai"``) to the model,
and call ``dispatch`` for every tool call it makes. The text that ``dispatch`` returns goes back
to the model as the tool result. A Klaracase error comes back as ``{"error": ...}`` text.
"""

from __future__ import annotations

import json

from _mock_api import mock_client
from klaracase.agents import dispatch, tool_definitions

SCRIPTED_CALLS = [
    ("search_decisions", {"query": "Vermögensbetreuungspflicht Geschäftsführer", "court": "BGH"}),
    ("get_norm", {"reference": "§ 535 BGB"}),
    ("get_norm", {"reference": "§ 999 BGB"}),
    ("get_citation_graph", {"id": "x"}),
]


def main() -> None:
    tools = tool_definitions(format="anthropic")
    print("tools:", ", ".join(tool["name"] for tool in tools))
    with mock_client() as client:
        for name, arguments in SCRIPTED_CALLS:
            text = dispatch(client, name, arguments)
            body = json.loads(text)
            if "error" in body:
                print(f"{name}: error {body['error']['code']} - {body['error']['detail'][:60]}")
            else:
                print(f"{name}: ok, {len(text)} characters of JSON")


if __name__ == "__main__":
    main()
