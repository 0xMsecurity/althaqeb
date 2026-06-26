# DRAFT (FYI / low severity) — Qdrant & pgvector: post-delete residue purged by routine maintenance

**Status: READY (staged, NOT sent). Lower severity than Chroma/Milvus/Weaviate — residue is transient.**

These are included for completeness and honesty: a post-delete recovery window exists,
but the engine's routine maintenance reclaimed it in our tests. Frame as an FYI / docs note,
not a vulnerability report. **VEDC classes** (per `../../../standards/erasure-durability/CLASSIFICATION.md`):
Qdrant-server `VEDC-AU` (Confirmed), pgvector HNSW index `VEDC-AU` (Confirmed), Postgres heap
`VEDC-M+S` (Confirmed). `AU` = auto-reclaimed but without a measured timer; `M` = manual-only
reclamation (the heap channel needs an explicit `VACUUM FULL`).

## Qdrant (server, Rust engine) — VEDC-AU, Confirmed
- Container: `qdrant/qdrant:latest` (pulled at test time; exact version/digest not captured in
  the run record — `:latest` tag). Qdrant is FYI-tier (it purges), so version precision is
  non-critical; a sender should confirm against the current release.
- `../results/phase9_qdrant_server.json`: deleted vectors present after `delete` (5/5), then
  **0/5 after the vacuum optimizer triggered** (forced via aggressive `deleted_threshold`
  + churn). Live filler vectors retained throughout (positive control).
- `../results/phase22_qdrant_multiseed.json`: multi-seed (×3) confirmation — the basis for the
  **Confirmed** `VEDC-AU` class. (One seed discarded for a positive-control failure per SPEC §4;
  the kept trials all show present-after-delete → purged.)
- Takeaway: residue exists only in the window before the optimizer runs. Worth a docs note
  that erasure completeness depends on optimizer settings/scheduling.
- Repro: `../scripts/phase9_qdrant_server.py`, `../scripts/phase22_qdrant_multiseed.py`.

## pgvector (PG18 + pgvector 0.8.3) — index VEDC-AU (Confirmed), heap VEDC-M+S (Confirmed)
- HNSW **index** residue: vector present in index pages after DELETE, **purged by plain
  `VACUUM`** (cosine drops to noise). Index self-cleans under autovacuum. Multi-seed:
  `../results/phase8_pgvector_hnsw.json`, `phase8_pgvector_hnsw_seed1.json`,
  `phase8_pgvector_hnsw_seed2.json`.
- HEAP/TOAST residue: deleted vector survives plain `VACUUM` (4/5) and is removed only by
  `VACUUM FULL` (table rewrite) — the classic Postgres MVCC dead-tuple behavior (well
  documented; SIGMOD'07 class), not pgvector-specific. Self-identifying via `xmax` (`+S`).
  Multi-seed: `../results/phase4_postgres.json`, `phase4_postgres_seed1.json`,
  `phase4_postgres_seed2.json`.
- Takeaway: largely expected DB behavior. A docs note that `VACUUM` does not zero heap pages
  (only `VACUUM FULL` rewrites) may help erasure-conscious operators.
- Repro: `../scripts/phase8_pgvector_hnsw.py`, `../scripts/phase4_postgres_heap.py`.

## Net
Qdrant and pgvector are the *good* end of the spectrum (routine maintenance reclaims the
index residue). The durable-without-intervention cases (Chroma, Milvus small-ratio, Weaviate)
are where disclosure effort should focus.
