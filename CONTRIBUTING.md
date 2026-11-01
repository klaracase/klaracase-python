# Contributing

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
make lint        # ruff check and ruff format --check
make typecheck   # mypy --strict
make test        # pytest, no network
```

Rules:

- The only runtime dependency is `httpx`. Do not add another one.
- Request parameters are typed strictly. Response types keep unknown keys.
- Every change to behavior needs a test against the in-process mock transport. No test may touch
  the network.
- The shared conformance cases live in `tests/fixtures/conformance`. Do not edit them here. They
  are copied from the Klaracase SDK contract.
- Keep commits small and use semantic commit messages.
