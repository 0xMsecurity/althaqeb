# DRAFT — Milvus: deleted vectors persist in segment binlogs until compaction+GC reclaim

**Status: DRAFT, not sent.**

## Summary
After `delete(ids=...)` + `flush()` (logical query for the ids returns empty), the deleted
rows' **vectors and scalar fields persist bit-identically** in the segment binlog stored in
object storage (MinIO/S3). Deletion only appends a small **delta (tombstone) parquet**
listing the deleted ids; the original segment is untouched. A read-only reader of the object
store can join the delta tombstone ids with the segment binlog to recover exactly the
deleted rows (vectors + text).

## Affected / tested
- Milvus **standalone v2.5.10** (etcd + MinIO + Milvus, docker) and **milvus-lite 3.0**
  (embedded, parquet on local FS). Linux x86_64.

## Reproduction
`../scripts/phase11_milvus_standalone.sh` (+ `phase11_milvus_scan.py`) and
`../scripts/phase3_cross_backend.py` (lite). Inspect `collections/.../data/*.parquet`
(column `vector`, `id`) and `.../delta/*.parquet` (tombstone `id`,`_seq`).

## Evidence
- `../results/phase11_milvus_standalone.json`: 0.16% delete ratio — vectors persist through
  delete+flush+compact+GC-wait (compaction threshold not met → no segment rewrite).
- `../results/phase12_milvus_highratio.json`: **40%** delete ratio — compaction state reached
  `Completed`, yet vectors **still recoverable** after an 80s GC wait under aggressive GC
  config; object-store size grew monotonically (old segments not collected in-window).
- milvus-lite (`phase3`): structured recovery from the segment parquet at cosine 1.0; delta
  parquet contained only `{id:[0..4]}`.

## Impact / severity — LOW–MEDIUM (transient; bounded by compaction+GC)
UPDATE (phase15): Milvus DOES reclaim. After a completed high-ratio compaction, GC removed the
superseded segment between 240–360s (object store 47MB→11MB, deleted vectors 5/5→0/5;
`../results/phase15_milvus_gctimeline.json`). So the residue window is bounded by compaction+GC,
not indefinite. BUT for the common case of *small* per-subject deletions, the single-segment
compaction threshold is not met (`phase11`: 0.16% ratio → no rewrite, residue persisted), so
data can persist for a long time until an unrelated compaction reclaims the segment. Severity
depends on delete ratio + compaction/GC config.

## Limitations (honest)
- Requires read access to the object store (MinIO/S3 bucket).
- We did **not** observe the upper bound of persistence: even a completed high-ratio
  compaction did not yield purge within our window because GC did not collect the superseded
  segments in time. We cannot claim Milvus *never* purges — only that it did not in our tests.

## Suggested mitigations
- Document erasure semantics (delete is logical; physical reclamation is compaction+GC-gated).
- Provide guidance / tooling to force compaction + GC for erasure requests, and confirm old
  segment binlogs are removed from object storage. Object-store encryption as compensating control.
