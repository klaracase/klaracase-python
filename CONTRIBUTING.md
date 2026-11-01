# Contributing

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
make lint        # ruff check and ruff format --check
make typecheck   # mypy --strict and pyright strict
make test        # pytest, no network
```

Rules:

- The only runtime dependency is `httpx2`, and only `klaracase/_transport.py` imports it. Do not
  add another dependency.
- Request parameters are typed strictly. Response types keep unknown keys in `extra`. A new
  response field goes into `types.py`; `tests/test_drift.py` fails until the model covers every
  key of the examples.
- Every change to behavior needs a test against the in-process mock transport. No test may touch
  the network.
- The shared conformance cases live in `tests/fixtures/conformance`. Do not edit them here. They
  are copied from the Klaracase SDK contract.
- `src/klaracase/_sync.py` and `_async.py` mirror each other. `tests/test_parity.py` checks it.
  `tests/typing/consumer.py` shows what a user's type checker must accept and refuse.
- Keep commits small and use semantic commit messages.
