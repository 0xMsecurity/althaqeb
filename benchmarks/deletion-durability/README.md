# Deletion-Durability Benchmark & Registry

**Layer:** this module sits one rung above the `vdbresidue` tool on the Althaqeb ladder
(`Experiments → Tools → **Benchmarks → Taxonomies → Registries** → … → Authority`). It
elevates the per-engine residue experiments from prose into a structured, machine-readable,
**evidence-traceable** registry and a generated comparison matrix.

## The question

After an application calls `delete()` on a vector and the engine reports the logical layer
clean, **does the embedding vector still persist bit-identically on disk, and for how long?**
For "right to be forgotten" / GDPR erasure, "the API returned success" is not the same as
"the data is gone." This registry records the measured answer per engine.

## What's here

| File | Role |
|---|---|
| `registry.json` | the data — one entry per engine, each citing committed result files |
| `schema.json` | JSON Schema (draft-07) describing the registry contract |
| `build_matrix.py` | validator + matrix generator (stdlib only, no deps) |
| `MATRIX.md` | **generated** — the human-readable comparison matrix (do not hand-edit) |

## Integrity model (NO FAKE RESULTS)

`build_matrix.py` is the gate. It **fails the build (exit 2)** if:

- any cited evidence path does not exist as a committed file, or
- an entry claims `high`/`medium` confidence with no evidence cited, or
- any required field / enum is wrong.

Entries with `low`/`unverified` confidence are allowed but reported as **evidence gaps**
(`WARN`) so the registry honestly surfaces what is not yet backed by a committed result file.
As of v0.1.0 there are two such gaps (Postgres heap, pgvector HNSW index) — these are the
registry's own to-do list, not hidden assumptions.

## Reproduce

```bash
python3 build_matrix.py            # validate + (re)write MATRIX.md
python3 build_matrix.py --check    # validate only (CI gate); exit 2 on any integrity failure
```

The underlying measurements live in `../../experiments/residue/` (phase scripts +
`results/*.json` + `logs/`). Re-run a phase with `experiments/residue/.venv/bin/python
experiments/residue/scripts/<phase>.py`; see `experiments/residue/REPRODUCE.md`.

## Headline finding (from the matrix)

A post-delete recovery window exists in **every real engine tested**; its duration is
**unbounded only on ChromaDB**. Every other engine reclaims via a maintenance pass
(vacuum / optimizer / compaction-GC / tombstone-cleanup) that is itself gated by thresholds
or timers — and for realistic small-ratio erasure deletions those passes often do not fire.
A separate cross-cut (`experiments/residue/results/phase18_inversion_benchmark.json`) shows
the recovered ChromaDB residue inverts back to text with vec2text/gtr-base at cosine
mean 0.91 (95% CI 0.87–0.94), recall mean 0.84 vs a random-control vocab overlap of 0.08.

## Adding an engine

1. Run a measurement that produces a committed `results/<phase>.json` under
   `experiments/residue/`.
2. Add an entry to `registry.json` citing that file in `evidence`.
3. `python3 build_matrix.py` — it will refuse to build if the evidence is not on disk.

Negative results (engines that genuinely reclaim at write/close, e.g. FAISS) are first-class
rows — they are the positive controls that prove the method does not false-positive.
