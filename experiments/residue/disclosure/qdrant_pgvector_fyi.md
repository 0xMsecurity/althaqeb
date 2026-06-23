# DRAFT (FYI / low severity) — Qdrant & pgvector: post-delete residue purged by routine maintenance

**Status: DRAFT, not sent. Lower severity than Chroma/Milvus/Weaviate — residue is transient.**

These two are included for completeness and honesty: a post-delete recovery window exists,
but the engine's routine maintenance reclaimed it in our tests. Frame as an FYI / docs note,
not a vulnerability report.

## Qdrant (server, Rust engine, v latest container)
- `../results/phase9_qdrant_server.json`: deleted vectors present after `delete` (5/5), then
  **0/5 after the vacuum optimizer triggered** (forced via aggressive `deleted_threshold`
  + churn). Live filler vectors retained throughout (positive control).
- Takeaway: residue exists only in the window before the optimizer runs. Worth a docs note
  that erasure completeness depends on optimizer settings/scheduling.
- Repro: `../scripts/phase9_qdrant_server.py`.

## pgvector (PG18 + pgvector 0.8.3)
- HNSW **index** residue (`../results/`/`phase8` log): vector present in index pages after
  DELETE, **purged by plain `VACUUM`** (cosine drops to noise). Index self-cleans under autovacuum.
- HEAP/TOAST residue (`../results/phase4_postgres.json`): deleted vector survives plain
  `VACUUM` (4/5) and is removed only by `VACUUM FULL` (table rewrite). This is the classic
  Postgres MVCC dead-tuple behavior (well documented; SIGMOD'07 class), not pgvector-specific.
- Takeaway: largely expected DB behavior. A docs note that `VACUUM` does not zero heap pages
  (only `VACUUM FULL` rewrites) may help erasure-conscious operators.
- Repro: `../scripts/phase8_pgvector_hnsw.py`, `../scripts/phase4_postgres_heap.py`.

## Net
Qdrant and pgvector are the *good* end of the spectrum (routine maintenance reclaims the
index residue). The durable-without-intervention cases (Chroma, Milvus small-ratio, Weaviate)
are where disclosure effort should focus.
