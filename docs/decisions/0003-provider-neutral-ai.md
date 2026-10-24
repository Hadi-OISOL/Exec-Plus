> **File use case:** Architecture decision record for model and vector-provider flexibility.
> **What it does:** Prevents early vendor lock-in while preserving local and cloud deployment options.

# ADR 0003: Keep model and vector infrastructure replaceable

- Status: Accepted
- Date: 2026-09-02

## Context

Syntelio must evaluate local models, hosted language models, and vector databases. The final providers depend on privacy, quality, latency, cost, and operational tests that have not occurred.

## Decision

Application services depend on small `LanguageModel` and `EmbeddingStore` protocols. Initial language-model adapters target an OpenAI-compatible HTTP contract. Vector-specific adapters will be added only after a benchmark and a new decision record.

## Consequences

Provider capabilities cannot leak into the core without an explicit contract change. Switching providers remains configuration or adapter work. Lowest-common-denominator contracts may later require carefully designed optional capabilities.

