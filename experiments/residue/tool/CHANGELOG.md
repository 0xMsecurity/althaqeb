# Changelog — vdbresidue

All notable changes to the read-only deleted-vector residue auditor. Versioning: SemVer.

## [0.1.0] — 2026-06-26 (staged; NOT published — human gate)

First reference release of the VEDC erasure-verification tool. Read-only, deterministic,
no-LLM, no-network. Chain-of-custody JSONL on every operation.

### Capabilities
- Subcommands: `inspect`, `recover`, `report`, `acquire`, `match`, `verify`; `--version`.
- Backends: `chroma` (hnswlib `DELETE_MARK` blind recovery), `milvus` (segment+delta parquet),
  `generic` (size-inferred float32 carve), plus a SQLite-page-aware overflow detector and a
  streaming bounded-memory `match` mode for multi-GB stores.
- Exit code 2 when recoverable deleted residue is found (erasure-verification / CI gate),
  0 when clean, 1 on error.

### Guarantees (validated by `selftest.py`)
- Read-only on the target (opens files `rb`; never writes/mutates the source).
- Deterministic: no randomness, no network, no model/LLM.
- Bounded memory: streaming scan over large segments (stream-boundary regression in selftest).
- Self-test PASS: chroma + milvus + stream-boundary + sqlite-page-aware regressions.

### Scope / limitations
- Detector is **float32-exact**; quantized (int8/PQ/binary) residue requires a quantization-aware
  detector (future work). Per VEDC SPEC §9, a "no residue" result is **format-scoped**.

### Not in this release
- PyPI publish (the package is built and tagged locally; not yet uploaded).
