# Althaqeb Standards

Reference specifications built on top of Althaqeb's benchmarks/registries. A spec lives here
only when it is backed by an evidence-traceable registry and an **executable conformance tool**
— a standard that is only prose is unfalsifiable.

| Standard | What it classifies | Spec | Conformance tool |
|---|---|---|---|
| **VEDC** | Vector-store erasure durability — how long a logically-deleted embedding vector stays recoverable | [`erasure-durability/SPEC.md`](erasure-durability/SPEC.md) | [`erasure-durability/classify.py`](erasure-durability/classify.py) → `CLASSIFICATION.md` |

## Principle

Every classification is **generated** from committed, positive-control-validated measurements
in the underlying registry, not asserted. The conformance tool reuses the registry's evidence
gate, so a row with missing or unbacked evidence cannot be classified. Conformance carries a
level — **Confirmed** (replicated across seeds/versions) vs **Provisional** (single trajectory)
— so the standard never launders a single run into authority.
