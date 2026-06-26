# DRAFT — ChromaDB: deleted embedding vectors remain recoverable (and invertible) on disk

**Status: READY (staged, NOT sent). Coordinated-disclosure, no public PoC before agreement.**

**VEDC classification: `VEDC-U+S` (Unbounded, self-identifying) — Conformance: Confirmed.**
Under the VEDC erasure-durability standard (`../../../standards/erasure-durability/SPEC.md`,
roster in `CLASSIFICATION.md`), ChromaDB is the **only** engine of 10 with class `U`
(no observed reclamation across any tested attack). `+S` = deletion is self-identifying, so
recovery targets exactly the erased records. "Confirmed" = multi-seed + cross-version evidence
through the registry's evidence gate. This is a **data-lifecycle / "deletion ≠ secure erasure"**
finding (privacy/compliance), not a remote/memory-safety vulnerability — severity Low–Medium,
gated on filesystem/backup access to the persistence directory.

## Summary
After `collection.delete(ids=...)` returns and the logical layer reports the records gone
(count drops, `get(ids)` returns empty) and the SQLite WAL plaintext is purged, the deleted
records' **embedding vectors persist bit-identically** in the on-disk hnswlib segment
(`<collection>/data_level0.bin`). They are recoverable by a read-only parse of that file —
**without** the API, IDs, or schema — because hnswlib persists a per-element `DELETE_MARK`
bit that identifies exactly the deleted elements. The recovered vectors invert to their
source text via `vec2text`, so this is recoverable *content*, not opaque floats.

## Affected / tested
- chromadb **1.5.9** (Rust core), Python 3.13, Linux x86_64, CPU-only.
- **Cross-version bisection** (`../results/cross_version_chroma_summary.json`): identical
  behavior on **0.5.23, 0.6.3, 1.0.21 (Rust-core rewrite), 1.3.7, and 1.5.9 (latest)** —
  ARCHITECTURAL, present in the latest release, survived the 1.0 rewrite. (0.4.x/0.5.0 not
  testable on Python 3.13 but use the same hnswlib segment.)

## Environment & reproduction
Full env in `../results/ENV.txt`; pinned deps in `../requirements.lock.txt`; steps in
`../REPRODUCE.md`. Minimal:
1. Create a persistent collection, add records (embeddings flush to the HNSW segment after
   enough writes), then `collection.delete(ids=...)`.
2. Confirm logical deletion: `collection.count()` excludes them, `get(ids)` is empty,
   `embeddings_queue` has no plaintext for them.
3. Parse `<persist>/<uuid>/data_level0.bin`: element block stride
   `132 + dim*4 + 8` (hnswlib M=16, `maxM0=32`); `dim`/counts from sibling `header.bin`
   (`size_data_per_element`@28, `offsetData`@44). Elements with byte `+2 & 0x01` set are the
   logically-deleted ones; their float32[dim] payload is intact.

## Evidence (this study)
- `../results/phase1_seed0.json`: 5/5 deleted vectors bit-identical in segment; blind-parse cosine 1.0.
- `../results/phase6_blind_deletemark.json`: `DELETE_MARK` selects exactly 5/5 deleted of 3005, blind.
- `../results/phase2_seed{0..4}.json`: residue persists across 50k inserts, 3 restart cycles,
  and `delete_collection` — **no observed reclamation** (5 seeds).
- `../results/phase16_chroma_idle.json`, `../results/phase13_chroma_reclaim_attack.json`,
  `../results/phase12_chroma_highratio.json`: no reclamation under idle time, four active
  reclaim attacks (slot-reuse churn, 100%-delete refill, re-add same ids, tiny-batch churn),
  or a 60% high-ratio delete — the evidence basis for the `VEDC-U` (unbounded) class.
- `../results/phase7_audit.json`: an independent replication on Chroma's **default**
  MiniLM-L6-v2 (dim 384) embedding fn with realistic PII records — a different model + dim than
  the gtr runs, rebutting synthetic-data bias. After delete + compaction the logical layer is
  clean yet the auditor recovers **8/8** deleted records (validation PASS, exit code 2 = residue).
  Reproduce: `../scripts/phase7_audit_validation.py`.
- Inversion: `../results/phase1_seed0.json` (vec2text gtr-base) reconstructs trigger-bearing
  text from the residue (cosine 0.89–0.97; trigger-token preservation 0.8–1.0).

## Impact
A party with read access to the persistence directory (host, backup, snapshot, shared/мulti-
tenant volume, or a decommissioned disk) can recover and read content that was "deleted",
including data deleted to satisfy an erasure / right-to-be-forgotten request. Because
deletion is self-identifying, recovery is *targeted* at exactly the erased records.

## Limitations (honest)
- Requires filesystem access to the persistence directory; not a remote/network issue.
- Residue in the HNSW segment appears only after the vector has been flushed WAL→HNSW at
  least once (delete-before-first-flush leaves no HNSW residue).
- Text reconstruction quality depends on the embedding model and storage precision
  (strong at fp32/fp16/int8; degraded under PQ; poor at 1-bit) and on availability of an
  inverter for that model (vec2text ships gtr-base / ada-002).

## Suggested mitigations (for discussion, not prescriptive)
- Document clearly that `delete` is *logical*; physical bytes persist in the HNSW segment.
- Offer an opt-in **secure delete** / compaction-on-delete that rewrites the segment without
  deleted elements, and/or zeroes reclaimed slots.
- Consider encryption-at-rest guidance for the persistence directory as a compensating control.

## Disclosure logistics (fill before sending)
Channel: Chroma security policy / private GitHub advisory. Timeline: 90 days, extensible.
We will share the audit tool (`../tool/vdbresidue.py`) and full repro privately on request.
