# Architecture decisions

Append a new entry when you make an architectural decision (new dependency, new layer or package, change to a port, switch to migrations, ...). Newest last. Keep entries to a few lines: what, why, consequence.

## Layered architecture with enforced dependency direction
interfaces -> adapters -> services -> domain, checked by `lint-imports`. Business rules live in `domain/` and `services/` so they can be tested without any framework.

## Project kind: application
Runs on its own. Configuration is read once into `Settings` and the object graph is built in `wiring.py` (the composition root).

## Concurrency: async
I/O-bound work with concurrent operations. Ports, services and adapters that do I/O are `async def`; pure domain code stays synchronous. Switching back to sync touches every port, service and test.

## Interfaces: fastapi
Each interface is a thin adapter: parse input, call one service, render the result. No business logic in handlers.

## Hosting: Render free tier
512 MB RAM, 0.1 CPU, an ephemeral filesystem and a sleep after 15 idle minutes are design inputs, not deployment details. One worker, small database pool, no heavyweight dependencies (enforced by `lint-imports`), stateless processes, lazy startup, and a cheap `/healthz`. The service requests its own public `/healthz` every 10 minutes (`keepawake.py`, enabled by an environment variable) so it does not sleep; that uses about 730 of the 750 shared free instance hours a month. `render.yaml` describes the service.

## Container image
Multi-stage Docker build with uv, non-root user, configuration only through environment variables.

## Fixed project policies
- 100% line and branch coverage, enforced in `pyproject.toml`.
- Ruff (format and lint), pyright strict, import-linter contracts, pre-commit.
- Standard-library first; new dependencies need an entry here.
