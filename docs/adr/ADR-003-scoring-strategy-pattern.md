# ADR-003 — Strategy Pattern for the composite scoring engine

**Status:** Accepted
**Date:** 2025-06-01
**Author:** David Font Muñoz

---

## Context

The composite scoring engine must combine a fundamental score (Shiller)
and a technical score (Murphy) into a single actionable verdict.
Several combining strategies are plausible:

- Equal-weighted average (50% / 50%)
- Fundamental-only (value investing, no technical noise)
- Technical-only (momentum / trend following)
- Adaptive weighting based on market regime (advanced, Phase 4+)

The naïve implementation — an `if/elif` block in a single function —
would require modifying core logic every time a new strategy is added.
This violates the Open/Closed Principle.

## Decision

Implement the **Strategy Pattern** (Gamma et al., 1994, p.315):

- `ScoringStrategy` — abstract base class defining `combine()`.
- `WeightedAverageStrategy` — default implementation (50/50, configurable).
- `FundamentalOnlyStrategy` — for assets with short price history.
- `run_scoring()` — the single public entry point; accepts any strategy.

## Rationale

1. **Open for extension, closed for modification.** Adding a new strategy
   (e.g. a momentum-weighted mode for volatile markets) is a new subclass,
   not a change to existing code. No risk of breaking the default behaviour.

2. **Testable in isolation.** Each strategy is a class with a single
   `combine()` method. Tests can inject any `FundamentalScore` and
   `TechnicalScore` fixture without touching the data layer.

3. **Transparent to the UI.** `CompositeResult.strategy_name` and
   `CompositeResult.weights` are always populated, so the UI can show
   the user exactly how the score was computed.

4. **Configurable without code changes.** Default weights are read from
   `settings.weight_fundamental` / `settings.weight_technical`, which
   can be overridden via environment variables in production.

## Consequences

- All UI and API layers call `run_scoring()` only — never instantiate
  a strategy directly.
- Adding a strategy requires: (1) a new subclass, (2) a test file,
  (3) exposing it in the API/UI if desired. No other files change.
- The `CompositeResult` dataclass is the stable contract between the
  scoring engine and its consumers. Changing its fields is a breaking
  change that requires updating all consumers.
