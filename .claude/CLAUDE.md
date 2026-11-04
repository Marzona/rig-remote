# rig-remote — Project Guidelines

## Memory bank

**Always read both memory-bank files at the start of every session before
making any code changes or answering architecture questions.  Update them
whenever the design or architecture changes.**

- `.claude/architecture.md` — *why* the system is structured as it is:
  architectural decisions, rationale, invariants, extension points.
- `.claude/design.md` — *what* each module, class, and method does:
  module map, threading model, config flow, domain models, scanner layers.

## Architecture

### Inter-thread communication
All communication between the UI thread and the scanner thread goes through
`STMessenger` (wrapping `QueueComms`). Events are `(name, value)` string tuples.
`ScannerCore._QUEUE_EVENT_CONVERTERS` is the type-safe whitelist that converts
incoming string values to the correct Python types before applying them to the task.
Do not add new queue parameters without adding an entry to `_QUEUE_EVENT_CONVERTERS`.

### Config flow
Configuration travels in one direction only:
`INI file → AppConfig dict → constructor parameters → task/endpoint objects`
`AppConfig` is never injected directly into domain objects. Convert and pass individual
parameters at the call site.

### Exception taxonomy
- `NonRetriableError` — abort the current scan loop entirely.
- `RetriableError` — log and continue to the next scan iteration.
Use these instead of bare `Exception` or `ValueError` where the scan-loop context applies.

### Validation style
Domain models (`ScanningTask`, `Channel`, `Bookmark`) clamp out-of-range numeric values
and log; they do not raise on bad numeric inputs. Raises are reserved for unsupported
modes/types where no sensible default exists.
