# DRAFT — Weaviate: deleted object vectors persist on disk pending async tombstone cleanup

**Status: READY (staged, NOT sent).**

**VEDC classification: `VEDC-AT` (Auto / timed) — Conformance: Confirmed.**
Residue is auto-reclaimed by the async tombstone-cleanup pass on a timer (`AT`); not
self-identifying. "Confirmed" = multi-seed (phase19, ×3 seeds). Low severity — a transient,
interval-bounded on-disk window, not durable retention; worth a documentation note on erasure
completeness vs the cleanup interval.

## Summary
After `DELETE /v1/objects/<Class>/<id>` (subsequent GET returns 404), the deleted object's
**vector persists bit-identically** in the on-disk store (LSM segments + HNSW commitlog)
until the asynchronous tombstone-cleanup / LSM compaction reclaims it. In our window the
cleanup did not fire, so the vector remained recoverable.

## Affected / tested
- Weaviate **1.28.2** (docker), `DEFAULT_VECTORIZER_MODULE=none`, Linux x86_64.

## Reproduction
`../scripts/phase10_weaviate.py`: insert objects with explicit vectors, delete a subset,
churn + wait, then byte-scan `/var/lib/weaviate` for the raw float32 vectors (positive
control on a live filler vector).

## Evidence
- `../results/phase10_weaviate.json`: 5/5 deleted vectors present BEFORE delete, AFTER delete
  (GET=404), and AFTER 300-insert churn + 20s wait. Async tombstone cleanup did not fire in window.
- `../results/phase19_weaviate_multiseed.json`: multi-seed (×3) confirmation of the same
  post-delete window + timed purge — the basis for the **Confirmed** `VEDC-AT` classification.

## Impact / severity — LOW (residue is transient)
UPDATE (phase14): Weaviate's tombstone cleanup **does purge** the deleted vector from disk.
With `cleanupIntervalSeconds=5` it was gone at ~70s post-delete (`../results/phase14_weaviate_cleanup.json`).
The default interval is 300s, so the residue window is roughly the configured cleanup interval.
Severity is therefore Low: a transient on-disk window, not durable retention. Worth only a
documentation note that erasure completeness is bounded by the tombstone-cleanup interval and
that very large/old segments may need compaction to fully reclaim.

## Limitations (honest)
- Requires filesystem access during the (short, interval-bounded) window between delete and
  the next tombstone cleanup pass.

## Suggested mitigations
- Document tombstone-cleanup timing and its erasure implications; provide a way to force
  cleanup/compaction for erasure requests and confirm physical removal. At-rest encryption
  as compensating control.
